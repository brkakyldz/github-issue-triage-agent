"""Fill the sandbox repository with labels and the seed issues in seed/issues.json.

    uv run triage-seed --first-wave    # labels and the first 14 issues
    uv run triage-seed                 # every missing issue: the second wave arrives
    uv run triage-seed --reset-labels  # also strip labels from every open issue, for a fresh run
    uv run triage-seed --status        # issues, labels, comment counts and the answer key; changes nothing

Seeding is idempotent (issues are matched by title). The two waves let you triage a
repository, then add new issues and see the next run triage only those. Uses the same
fine-grained token as the agent (Issues: read/write, Metadata: read) and the repository
in GITHUB_REPO; PyGithub spaces content-creating requests a second apart, as GitHub asks.
"""

from __future__ import annotations

import argparse
import json
import sys

from issue_triage.config import PROJECT_DIR, load_env

load_env()

from issue_triage.github_tools import _repo  # noqa: E402

SEED_FILE = PROJECT_DIR / "seed" / "issues.json"
MAIN_LABELS = ("bug", "enhancement", "question", "documentation")


def load_seed() -> dict:
    return json.loads(SEED_FILE.read_text(encoding="utf-8"))


def answer_key(repo) -> dict:
    """Map the seed's keys to live issue numbers (matched by title). Issues that are not
    on GitHub yet (the second wave, before it is seeded) are left out."""
    seed = load_seed()
    by_title = {i.title: i.number for i in repo.get_issues(state="all") if i.pull_request is None}
    numbers = {s["key"]: by_title[s["title"]] for s in seed["issues"] if s["title"] in by_title}
    return {
        "numbers": numbers,
        "expected_label": {numbers[s["key"]]: s["expected_label"] for s in seed["issues"] if s["key"] in numbers},
        "duplicate_pairs": {
            (numbers[s["key"]], numbers[s["duplicate_of"]])
            for s in seed["issues"]
            if "duplicate_of" in s and s["key"] in numbers and s["duplicate_of"] in numbers
        },
    }


def status(repo) -> None:
    """Every open issue with its labels and comment count, next to the answer key."""
    key = answer_key(repo)
    duplicates = {newer: older for newer, older in key["duplicate_pairs"]}
    agree = labelled = 0
    for issue in repo.get_issues(state="open", sort="created", direction="asc"):
        if issue.pull_request is not None:
            continue
        names = [label.name for label in issue.labels]
        expected = key["expected_label"].get(issue.number)
        if expected:
            expected += f", duplicate of #{duplicates[issue.number]}" if issue.number in duplicates else ""
        verdict = ""
        if names and expected:
            labelled += 1
            main = [n for n in names if n in MAIN_LABELS]
            ok = main == [key["expected_label"][issue.number]] and ((issue.number in duplicates) == ("duplicate" in names))
            agree += ok
            verdict = "  ok" if ok else f"  expected: {expected}"
        print(f"  #{issue.number:<3} [{', '.join(names) or '-'}] ({issue.comments} comments) {issue.title}{verdict}")
    print(f"Labels agree with the answer key on {agree}/{labelled} labelled issues.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--first-wave", action="store_true", help="create only the first wave of issues")
    parser.add_argument("--reset-labels", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    repo = _repo()
    print(f"Repository {repo.full_name}")
    if args.status:
        status(repo)
        return

    seed = load_seed()
    existing_labels = {label.name.lower() for label in repo.get_labels()}
    for label in seed["labels"]:
        if label["name"].lower() not in existing_labels:
            repo.create_label(label["name"], label["color"], label["description"])
            print(f"  created label {label['name']}")

    titles = {i.title for i in repo.get_issues(state="all") if i.pull_request is None}
    for spec in seed["issues"]:
        if spec["title"] in titles or (args.first_wave and spec.get("wave", 1) > 1):
            continue
        issue = repo.create_issue(title=spec["title"], body=spec["body"])
        print(f"  created #{issue.number} {spec['title']}")

    if args.reset_labels:
        for issue in repo.get_issues(state="open"):
            if issue.labels and issue.pull_request is None:  # the issues API also returns pull requests
                issue.delete_labels()  # removes the labels from this issue only
                print(f"  cleared labels on #{issue.number}")

    key = answer_key(repo)
    pairs = ", ".join(f"#{a} duplicates #{b}" for a, b in sorted(key["duplicate_pairs"]))
    print(f"Answer key: {pairs}")
    status(repo)


if __name__ == "__main__":
    main()
