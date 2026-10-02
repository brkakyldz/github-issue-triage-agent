"""Acceptance run for batched triage against the real model and the playground repo: batch approval, report quality and tracing.

    uv run python scripts/acceptance.py

Before the run, labels are stripped from the open issues so the result is readable.
Two triage passes follow, each ending in one review of the whole batch: the first
rejects it (GitHub must not change), the second edits it — one issue's labels changed,
one issue dropped, only the first duplicate comment kept. GitHub is then read back to
confirm that exactly the kept writes happened. Needs GITHUB_TOKEN and LANGSMITH_API_KEY.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from issue_triage.config import LANGSMITH_PROJECT, PROJECT_DIR, load_env

load_env()

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

from issue_triage.agent import build_agent  # noqa: E402
from issue_triage.config import make_model  # noqa: E402
from issue_triage.github_tools import COMMENT_MARKER, _repo  # noqa: E402
from issue_triage.run import run_triage, save_report  # noqa: E402
from issue_triage.seed import answer_key  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []
MAIN_LABELS = {"bug", "enhancement", "question", "documentation"}


def check(name: str, ok: bool, evidence: str) -> None:
    RESULTS.append((name, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}\n       {evidence}\n")


def parse_report(text: str) -> tuple[dict[int, dict], set[frozenset[int]]]:
    rows: dict[int, dict] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"#?\d+", cells[0]):
            labels = {x.strip().strip("`").lower() for x in re.split(r"[,;]", cells[2]) if x.strip()}
            rows[int(cells[0].lstrip("#"))] = {"labels": labels, "reason": cells[3], "duplicate_of": cells[4]}
    pairs = {frozenset(map(int, m)) for m in re.findall(r"#(\d+)\s+(?:duplicates|is a duplicate of)\s+#(\d+)", text)}
    for number, row in rows.items():
        if m := re.search(r"#(\d+)", row["duplicate_of"]):
            pairs.add(frozenset({number, int(m.group(1))}))
    return rows, pairs


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    repo = _repo()
    key = answer_key(repo)
    numbers = key["numbers"]
    open_issues = {i.number: i for i in repo.get_issues(state="open") if i.pull_request is None}
    for issue in open_issues.values():  # a readable starting point: no labels
        if issue.labels:
            issue.delete_labels()
    comments_before = {n: i.comments for n, i in open_issues.items()}
    print(f"Repository {repo.full_name}: {len(open_issues)} open issues; labels cleared.\n")

    reject_labels_on = numbers["stats-dark-mode"]
    edit_labels_on = numbers["help-typo"]
    known_labels = {label.name.lower() for label in repo.get_labels()}
    applied: dict[str, list] = {"labels_approved": [], "labels_edited": [], "labels_dropped": [],
                                "comment_approved": [], "comment_dropped": []}

    def number_of(change: dict) -> int | None:
        try:  # the model's raw arguments: "10" and 10 are the same issue to the tool
            return int(change.get("number"))
        except (TypeError, ValueError):
            return None

    def reviewer(request: dict) -> dict:
        """Edit the one batch: drop one issue's labels, change another's, keep only the first comment."""
        args = request["args"]
        labels, comments = [], []
        for change in args.get("labels") or []:
            number, wanted = number_of(change), [str(x).strip() for x in change.get("labels") or []]
            if number is None:
                continue
            if number == reject_labels_on:
                applied["labels_dropped"].append(number)
                continue
            if number == edit_labels_on:
                wanted = sorted({x.lower() for x in wanted} | {"documentation", "good first issue"})
                applied["labels_edited"].append((number, wanted))
            else:
                applied["labels_approved"].append((number, wanted))
            labels.append({**change, "labels": wanted})
        for change in args.get("comments") or []:
            number = number_of(change)
            if number is not None and not comments and not any(COMMENT_MARKER in (c.body or "") for c in open_issues[number].get_comments()):
                applied["comment_approved"].append((number, change.get("body", "")))
                comments.append(change)
            else:
                applied["comment_dropped"].append((number, change.get("body", "")))
        return {"type": "edit", "edited_action": {"name": request["name"],
                                                  "args": {**args, "labels": labels, "comments": comments}}}

    # A first pass rejects the whole batch: GitHub must not change at all.
    def status() -> dict[int, tuple[frozenset[str], int]]:
        return {i.number: (frozenset(label.name.lower() for label in i.labels), i.comments)
                for i in repo.get_issues(state="open") if i.pull_request is None}

    before = status()
    started = time.time()
    _, reject_log = run_triage(build_agent(make_model(), checkpointer=InMemorySaver()),
                               lambda request: {"type": "reject", "message": "Not today."})
    print(f"Reject pass finished in {time.time() - started:.0f}s with {len(reject_log)} review(s)\n")
    rejected_untouched = status() == before

    thread_id = str(uuid.uuid4())
    agent = build_agent(make_model(), checkpointer=InMemorySaver())
    started = time.time()
    result, log = run_triage(agent, reviewer, thread_id=thread_id)
    print(f"Run finished in {time.time() - started:.0f}s with {len(log)} review(s); "
          f"todos: {[t.get('status') for t in result.value.get('todos', [])]}\n")

    path = save_report(result.value.get("files", {}))
    report = path.read_text(encoding="utf-8") if path else ""
    rows, pairs = parse_report(report)

    # 1. One row per open issue with a label and a reason.
    missing = sorted(set(open_issues) - set(rows))
    bad = [n for n, r in rows.items() if not (r["labels"] & MAIN_LABELS) or len(r["reason"]) < 5]
    agree = sum(1 for n, r in rows.items() if key["expected_label"].get(n) in r["labels"])
    check("1. triage.md lists every open issue with a label and a one-line reason",
          bool(path) and not missing and not bad,
          f"{path}: {len(rows)} rows for {len(open_issues)} open issues; missing {missing}; rows without a main "
          f"label or reason {bad}; main label agrees with the seed's answer key on {agree}/{len(rows)}")

    # 2. At least one of the two seeded duplicate pairs is found.
    expected_pairs = {frozenset(p) for p in key["duplicate_pairs"]}
    found = expected_pairs & pairs
    check("2. at least one seeded duplicate pair is found", len(found) >= 1,
          f"seeded {sorted(sorted(p) for p in expected_pairs)}; found in report {sorted(sorted(p) for p in pairs)}; "
          f"{len(found)}/2 correct")

    # 3. Writes interrupt once, as one batch; reject -> nothing changes; the edited batch
    # -> exactly what the reviewer kept is on GitHub. Labels were cleared first, and a
    # label change with any unknown label is refused whole by the tool.
    reviews = [r["name"] for r, _ in reject_log + log]
    check("3a. every write waits for ONE review of the whole batch; reject changes nothing",
          reviews == ["apply_triage", "apply_triage"] and rejected_untouched,
          f"reviews per run: reject pass {[r['name'] for r, _ in reject_log]}, edit pass "
          f"{[r['name'] for r, _ in log]}; GitHub unchanged after the rejected batch: {rejected_untouched}")
    repo_now = {i.number: i for i in repo.get_issues(state="open") if i.pull_request is None}
    labels_now = {n: {label.name.lower() for label in i.labels} for n, i in repo_now.items()}
    expected_labels: dict[int, set[str]] = {}
    for n, ls in applied["labels_approved"] + applied["labels_edited"]:
        wanted = {x.lower() for x in ls if x}
        if wanted and wanted <= known_labels:
            expected_labels.setdefault(n, set()).update(wanted)
    approved_comments = [n for n, _ in applied["comment_approved"]]
    wrong_labels = {n: sorted(labels_now[n]) for n in repo_now if labels_now[n] != expected_labels.get(n, set())}
    wrong_comments = [n for n in repo_now if repo_now[n].comments != comments_before.get(n, 0) + approved_comments.count(n)]
    comment_text_ok = all(n in repo_now and repo_now[n].get_comments().reversed[0].body.strip() == (body.strip() + "\n\n" + COMMENT_MARKER)
                          for n, body in applied["comment_approved"])
    duplicates = {newer for newer, _ in key["duplicate_pairs"]}
    proposed = len(applied["labels_approved"]) + len(applied["labels_edited"]) + len(applied["labels_dropped"])
    check("3b. the edited batch: exactly what the reviewer kept shows on GitHub",
          bool(log) and not wrong_labels and not wrong_comments and comment_text_ok
          and bool(applied["comment_approved"] or applied["comment_dropped"])
          and applied["labels_dropped"] == [reject_labels_on] and labels_now.get(reject_labels_on) == set()
          and [d["type"] for _, d in log] == ["edit"],
          f"one batch with {proposed} label changes and "
          f"{len(applied['comment_approved']) + len(applied['comment_dropped'])} comments; every open issue's labels "
          f"equal the kept changes: {not wrong_labels} {wrong_labels or ''}; edited #{edit_labels_on} -> "
          f"{sorted(labels_now.get(edit_labels_on, []))}; dropped #{reject_labels_on} -> labels "
          f"{sorted(labels_now.get(reject_labels_on, [])) or 'none'}; comment counts equal the kept comments "
          f"({approved_comments} kept, {[n for n, _ in applied['comment_dropped']]} dropped): "
          f"{not wrong_comments} {wrong_comments or ''}; kept text posted: {comment_text_ok}; comments proposed "
          f"on non-duplicates: {sorted({n for n, _ in applied['comment_approved'] + applied['comment_dropped']} - duplicates) or 'none'}")

    # 4. Traces: the subagent's runs sit inside the main agent's trace, under a `task` tool run.
    if not os.environ.get("LANGSMITH_API_KEY"):
        check("4. subagent runs nested in the main trace", False, "NOT RUN: LANGSMITH_API_KEY is not set")
    else:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        from langsmith import Client

        wait_for_all_tracers()
        # PLAN names the project; an inherited LANGSMITH_PROJECT would send traces elsewhere
        client, project = Client(), LANGSMITH_PROJECT
        nested, evidence = False, f"no root run for the thread in {project} (LANGSMITH_PROJECT={os.environ.get('LANGSMITH_PROJECT')})"
        for _ in range(36):  # ingestion is asynchronous
            roots = [r for r in client.list_runs(project_name=project, is_root=True, limit=50,
                                                 start_time=datetime.now(timezone.utc) - timedelta(minutes=60))
                     if ((r.extra or {}).get("metadata") or {}).get("thread_id") == thread_id]
            for root in roots:
                runs = {r.id: r for r in client.list_runs(project_name=project, trace_id=root.id)}
                for run in runs.values():
                    if run.name != "duplicate-finder":
                        continue
                    chain, parent = [], run.parent_run_id
                    while parent in runs:
                        chain.append(runs[parent])
                        parent = runs[parent].parent_run_id
                    if chain and chain[-1].id == root.id and any(c.name == "task" and c.run_type == "tool" for c in chain):
                        nested = True
                        evidence = (f"project {project}, root run '{root.name}' ({len(runs)} runs): "
                                    + " > ".join(c.name for c in reversed(chain)) + " > duplicate-finder; "
                                    + client.get_run_url(run=root, project_name=project))
                        break
                if nested:
                    break
            if nested:
                break
            time.sleep(5)
        check("4. subagent runs nested in the main agent's trace", nested, evidence)

    if path:
        (PROJECT_DIR / "docs").mkdir(exist_ok=True)
        shutil.copyfile(path, PROJECT_DIR / "docs" / "triage-example.md")
    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
