"""End-to-end acceptance checks against the real model, GitHub and LangSmith.

    uv run triage-seed --first-wave        # a freshly seeded sandbox
    uv run python scripts/acceptance.py

Before the run, labels are stripped from the open issues so every issue is untriaged.
The scripted reviewer approves most label calls, edits one, rejects one, approves the
first duplicate comment and rejects the rest; GitHub is then read back to confirm that
exactly the approved writes happened. A second run follows, rejecting everything: it
must only look at the issues that are still unlabelled. Needs GITHUB_TOKEN and
LANGSMITH_API_KEY.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

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
    commented_before = {n for n, i in open_issues.items()  # the agent never comments on these again
                        if i.comments and any(COMMENT_MARKER in (c.body or "") for c in i.get_comments())}
    print(f"Repository {repo.full_name}: {len(open_issues)} open issues; labels cleared.\n")

    reject_labels_on = numbers["stats-dark-mode"]
    edit_labels_on = numbers["help-typo"]
    known_labels = {label.name.lower() for label in repo.get_labels()}
    applied: dict[str, list] = {"labels_approved": [], "labels_edited": [], "comment_approved": [], "comment_rejected": []}

    def reviewer(request: dict) -> dict:
        args = request["args"]
        try:  # the model's raw arguments: "10" and 10 are the same issue to the tool
            number = int(args.get("number"))
        except (TypeError, ValueError):
            return {"type": "reject", "message": "Not an issue number."}
        if request["name"] == "add_labels":
            labels = [str(x).strip() for x in args.get("labels") or []]
            if number == reject_labels_on:
                return {"type": "reject", "message": "Leave this one for the maintainers."}
            if number == edit_labels_on:
                edited = sorted({x.lower() for x in labels} | {"documentation", "good first issue"})
                applied["labels_edited"].append((number, edited))
                return {"type": "edit", "edited_action": {"name": "add_labels", "args": {**args, "labels": edited}}}
            applied["labels_approved"].append((number, labels))
            return {"type": "approve"}
        if not applied["comment_approved"]:  # approve the first comment, reject every later one
            applied["comment_approved"].append((number, args.get("body", "")))
            return {"type": "approve"}
        applied["comment_rejected"].append((number, args.get("body", "")))
        return {"type": "reject", "message": "Keep it open; the reporter asked a different question."}

    thread_id = str(uuid.uuid4())
    agent = build_agent(make_model(), checkpointer=InMemorySaver())
    started = time.time()
    result, log = run_triage(agent, reviewer, thread_id=thread_id)
    print(f"Run finished in {time.time() - started:.0f}s with {len(log)} reviewed writes; "
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
          f"{len(found)}/{len(expected_pairs)} correct")

    # 3. Writes interrupt; approve -> visible on GitHub; reject -> nothing changes.
    # Every open issue must now look exactly as the approved calls say: labels were cleared
    # first, and a call with any unknown label is refused whole by the tool.
    repo_now = {i.number: i for i in repo.get_issues(state="open") if i.pull_request is None}
    labels_now = {n: {label.name.lower() for label in i.labels} for n, i in repo_now.items()}
    expected_labels: dict[int, set[str]] = {}
    for n, ls in applied["labels_approved"] + applied["labels_edited"]:
        wanted = {x.lower() for x in ls if x}
        if wanted and wanted <= known_labels:
            expected_labels.setdefault(n, set()).update(wanted)
    approved_comments = [n for n, _ in applied["comment_approved"] if n not in commented_before]
    wrong_labels = {n: sorted(labels_now[n]) for n in repo_now if labels_now[n] != expected_labels.get(n, set())}
    wrong_comments = [n for n in repo_now if repo_now[n].comments != comments_before.get(n, 0) + approved_comments.count(n)]
    comment_text_ok = all(
        repo_now[n].get_comments().reversed[0].body.replace(COMMENT_MARKER, "").strip() == body.strip()
        for n, body in applied["comment_approved"] if n in approved_comments
    )
    duplicates = {newer for newer, _ in key["duplicate_pairs"]}
    check("3. label/comment writes wait for approval; approve shows on GitHub, reject changes nothing",
          bool(log) and not wrong_labels and not wrong_comments and comment_text_ok and bool(approved_comments)
          and labels_now.get(reject_labels_on) == set()
          and any(d["type"] == "reject" for _, d in log) and any(d["type"] == "edit" for _, d in log),
          f"{len(log)} writes reviewed ({sum(1 for r, _ in log if r['name'] == 'add_labels')} add_labels, "
          f"{sum(1 for r, _ in log if r['name'] == 'post_comment')} post_comment); every open issue's labels "
          f"equal the approved calls: {not wrong_labels} {wrong_labels or ''}; edited #{edit_labels_on} -> "
          f"{sorted(labels_now.get(edit_labels_on, []))}; rejected #{reject_labels_on} -> labels "
          f"{sorted(labels_now.get(reject_labels_on, [])) or 'none'}; comment counts equal the approved comments "
          f"({approved_comments} approved, {[n for n, _ in applied['comment_rejected']]} rejected): "
          f"{not wrong_comments} {wrong_comments or ''}; approved text posted: {comment_text_ok}; comments proposed "
          f"on non-duplicates: {sorted({n for n, _ in applied['comment_approved'] + applied['comment_rejected']} - duplicates) or 'none'}")

    # 4. Traces: the subagent's runs sit inside the main agent's trace, under a `task` tool run.
    if not os.environ.get("LANGSMITH_API_KEY"):
        check("4. subagent runs nested in the main trace", False, "NOT RUN: LANGSMITH_API_KEY is not set")
    else:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        from langsmith import Client

        wait_for_all_tracers()
        # config.py names the project; an inherited LANGSMITH_PROJECT would send traces elsewhere
        client, project = Client(), LANGSMITH_PROJECT
        nested, evidence = False, f"no root run for the thread in {project} (LANGSMITH_PROJECT={os.environ.get('LANGSMITH_PROJECT')})"
        for _ in range(36):  # ingestion is asynchronous
            roots = [r for r in client.list_runs(project_name=project, is_root=True, limit=50,
                                                 start_time=datetime.now(UTC) - timedelta(minutes=60))
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

    if path:  # before the second run overwrites output/triage.md
        (PROJECT_DIR / "docs").mkdir(exist_ok=True)
        shutil.copyfile(path, PROJECT_DIR / "docs" / "triage-example.md")

    # 5. A second, default run looks only at the issues that are still unlabelled. Its
    # reviewer rejects everything, so GitHub must not change at all.
    state_before = {n: (labels_now[n], repo_now[n].comments) for n in repo_now}
    unlabelled = {n for n, labels in labels_now.items() if not labels}
    second, second_log = run_triage(build_agent(make_model(), checkpointer=InMemorySaver()),
                                    lambda r: {"type": "reject", "message": "Second run: no changes."})
    listed = next((json.loads(m.content) for m in second.value["messages"]
                   if m.type == "tool" and m.name == "list_open_issues"), None)
    to_triage = {i["number"] for i in (listed or {}).get("to_triage", [])}
    label_targets = {str(r["args"].get("number")) for r, _ in second_log if r["name"] == "add_labels"}
    repo_after = {i.number: i for i in repo.get_issues(state="open") if i.pull_request is None}
    state_after = {n: ({label.name.lower() for label in i.labels}, i.comments) for n, i in repo_after.items()}
    check("5. a second run triages only the issues still without labels",
          listed is not None and to_triage == unlabelled
          and label_targets <= {str(n) for n in unlabelled} and state_after == state_before,
          f"unlabelled after the first run: {sorted(unlabelled)}; the second run's to_triage: {sorted(to_triage)}; "
          f"add_labels proposed for {sorted(label_targets)} ({len(second_log)} reviewed calls, all rejected, "
          f"against {len(log)} in the first run); GitHub unchanged: {state_after == state_before}")

    passed = sum(ok for _, ok, _ in RESULTS)
    print(f"{passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
