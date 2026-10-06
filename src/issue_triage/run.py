"""Run a triage pass from the terminal; you review the GitHub writes once, as one batch.

    uv run triage                  # triage the issues without labels; you review the batch
    uv run triage --all            # re-triage every open issue, labelled or not
    uv run triage --reject-all     # dry run: the report is written, GitHub is untouched

The report the agent writes in its virtual filesystem is saved to output/triage.md.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

from issue_triage.config import PROJECT_DIR, load_env, make_model

load_env()

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from issue_triage.agent import REPORT_PATH, build_agent, describe_batch  # noqa: E402

OUTPUT_DIR = PROJECT_DIR / "output"
BOLD, DIM, GREEN, RED, YELLOW, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[0m"

Decide = Callable[[dict], dict]

# Control characters (a carriage return, an ANSI escape) and bidi overrides would let a
# model-written comment redraw the terminal, so the reviewer approves text they never saw.
_HIDDEN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def visible(value: object) -> str:
    """Text for the review prompt, with anything that could redraw the terminal escaped."""
    return _HIDDEN.sub(lambda m: m.group().encode("unicode_escape").decode("ascii"), str(value))


def _decisions_for(interrupt, decide: Decide) -> list[dict]:
    requests = interrupt.value["action_requests"]
    allowed = {c["action_name"]: c["allowed_decisions"] for c in interrupt.value["review_configs"]}
    decisions = []
    for request in requests:
        decision = decide(request)
        if decision["type"] not in allowed[request["name"]]:
            raise ValueError(f"{decision['type']!r} is not allowed for {request['name']}")
        decisions.append(decision)
    return decisions  # exactly one per request, in order: the middleware requires it


def run_triage(agent, decide: Decide, thread_id: str | None = None,
               retriage: bool = False) -> tuple[object, list[tuple[dict, dict]]]:
    """Run until the agent finishes, answering every approval request with `decide`.
    `retriage` reaches the tools through the run config: only then do they list and
    label issues that already have labels. Returns the final result and the
    (request, decision) log."""
    config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4()), "retriage": retriage}}
    request = ("Re-triage every open issue, including the ones that already have labels." if retriage
               else "Triage the open issues that have no labels yet.")
    log: list[tuple[dict, dict]] = []

    def logged(request: dict) -> dict:
        decision = decide(request)
        log.append((request, decision))
        return decision

    result = agent.invoke({"messages": [{"role": "user", "content": request}]}, config, version="v2")
    while result.interrupts:
        if len(result.interrupts) == 1:
            resume = {"decisions": _decisions_for(result.interrupts[0], logged)}
        else:  # several pending interrupts must be answered by id
            resume = {i.id: {"decisions": _decisions_for(i, logged)} for i in result.interrupts}
        result = agent.invoke(Command(resume=resume), config, version="v2")
    return result, log


def save_report(files: dict, out_dir: Path = OUTPUT_DIR) -> Path | None:
    """Copy /triage.md from the agent's virtual filesystem to disk (host code, not the
    agent, touches the disk)."""
    data = files.get(REPORT_PATH)
    if data is None:
        return None
    content = data["content"]
    if isinstance(content, list):  # older FileData shape
        content = "\n".join(content)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / Path(REPORT_PATH).name
    dest.write_text(content, encoding="utf-8", newline="\n")
    return dest


def _edit_batch(args: dict) -> dict:
    """Change or drop items of the batch by their number on the review screen."""
    labels = [dict(c) for c in args.get("labels") or []]
    comments = [dict(c) for c in args.get("comments") or []]
    items = [("labels", c) for c in labels] + [("comment", c) for c in comments]
    dropped: set[int] = set()
    while True:
        raw = input("  item to change or drop (number), Enter when done: ").strip()
        if not raw:
            break
        if not raw.isdigit() or not 1 <= int(raw) <= len(items):
            print(f"  pick 1-{len(items)}")
            continue
        index = int(raw) - 1
        kind, change = items[index]
        if kind == "labels":
            current = ", ".join(map(str, change.get("labels") or []))
            new = input(f"  labels for #{visible(change.get('number'))}, comma-separated, '-' drops it "
                        f"[{visible(current)}]: ").strip()
            if new and new != "-":
                change["labels"] = [x.strip() for x in new.split(",") if x.strip()]
        else:
            new = input(f"  comment for #{visible(change.get('number'))}, '-' drops it, Enter keeps it: ").strip()
            if new and new != "-":
                change["body"] = new
        if new == "-":
            dropped.add(index)
        else:
            dropped.discard(index)
    edited = {**args,
              "labels": [c for i, c in enumerate(labels) if i not in dropped],
              "comments": [c for i, c in enumerate(comments, len(labels)) if i not in dropped]}
    print(visible(describe_batch(edited)))
    return edited


def ask_reviewer(request: dict) -> dict:
    """One review screen for the whole batch the agent prepared."""
    print(f"\n{YELLOW}{BOLD}── review the triage before it goes to GitHub ─────────────────{RESET}")
    print(visible(request.get("description") or request["args"]))
    while True:
        choice = input(f"{YELLOW}[a]pply all / [e]dit / [r]eject all{RESET}: ").strip().lower()[:1]
        if choice == "a":
            return {"type": "approve"}
        if choice == "r":
            reason = input("  reason (optional): ").strip()
            return {"type": "reject", "message": reason} if reason else {"type": "reject"}
        if choice == "e":
            args = _edit_batch(request["args"])
            return {"type": "edit", "edited_action": {"name": request["name"], "args": args}}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="re-triage issues that already have labels")
    parser.add_argument("--reject-all", action="store_true", help="reject every write (GitHub stays unchanged)")
    args = parser.parse_args()

    decide = (lambda r: {"type": "reject", "message": "dry run"}) if args.reject_all else ask_reviewer
    agent = build_agent(make_model(), checkpointer=InMemorySaver())
    scope = "every open issue" if args.all else "the open issues without labels"
    print(f"{DIM}Triaging {scope}; the agent plans, reads, delegates and drafts first...{RESET}")
    result, log = run_triage(agent, decide, retriage=args.all)

    for request, decision in log:
        colour = {"approve": GREEN, "reject": RED}.get(decision["type"], YELLOW)
        print(f"{colour}{decision['type']:<8}{RESET} {request['name']}")
    path = save_report(result.value.get("files", {}))
    print(f"\n{result.value['messages'][-1].text}\n")
    print(f"{BOLD}Report:{RESET} {path if path else 'the agent did not write ' + REPORT_PATH}")


if __name__ == "__main__":
    main()
