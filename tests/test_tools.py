"""The GitHub tools against an in-memory repository: what they return and what they refuse."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from issue_triage import github_tools as gt

from .conftest import FakeIssue

RETRIAGE = {"configurable": {"retriage": True}}


def test_list_open_issues_skips_pull_requests_and_truncates(repo):
    listed = json.loads(gt.list_open_issues.invoke({}))
    issues = listed["to_triage"]
    assert [i["number"] for i in issues] == [1, 2, 3]
    assert len(issues[2]["body"]) == gt.MAX_BODY_CHARS
    assert listed["already_triaged"] == []


def test_labelled_issues_are_listed_as_triaged_unless_retriaging(repo):
    repo.issues[1].add_to_labels("bug")
    listed = json.loads(gt.list_open_issues.invoke({}))
    assert [i["number"] for i in listed["to_triage"]] == [2, 3]
    assert [(i["number"], i["labels"]) for i in listed["already_triaged"]] == [(1, ["bug"])]
    assert len(json.loads(gt.list_open_issues.invoke({}))["already_triaged"][0]["body_start"]) <= gt.MAX_EXCERPT_CHARS

    listed = json.loads(gt.list_open_issues.invoke({}, config=RETRIAGE))
    assert [i["number"] for i in listed["to_triage"]] == [1, 2, 3]


def test_add_labels_refuses_an_issue_triaged_before_unless_retriaging(repo):
    repo.issues[1].add_to_labels("question")
    refused = gt.add_labels.invoke({"number": 1, "labels": ["bug"]})
    assert refused.startswith("Error: #1 was triaged before (labels: question)")
    assert [label.name for label in repo.issues[1].labels] == ["question"]

    assert gt.add_labels.invoke({"number": 1, "labels": ["bug"]}, config=RETRIAGE) == "Labelled #1: bug"
    assert [label.name for label in repo.issues[1].labels] == ["question", "bug"]


def test_get_issue_reports_missing_and_pull_requests(repo):
    issue = json.loads(gt.get_issue.invoke({"number": 1}))
    assert issue["title"].startswith("Crash") and issue["comments"] == []  # no comments is not an error
    assert gt.get_issue.invoke({"number": 99}) == "Error: not found"
    assert "pull request" in gt.get_issue.invoke({"number": 4})


def test_add_labels_adds_existing_labels_only(repo):
    assert gt.add_labels.invoke({"number": 1, "labels": ["Bug"]}) == "Labelled #1: bug"
    assert [label.name for label in repo.issues[1].labels] == ["bug"]

    refused = gt.add_labels.invoke({"number": 2, "labels": ["bug", "urgent-fix-now"]})
    assert refused.startswith("Error: unknown or empty labels ['urgent-fix-now']")
    assert repo.issues[2].labels == []  # nothing applied when any label is unknown
    assert gt.add_labels.invoke({"number": 2, "labels": []}).startswith("Error")


def test_post_comment_length_limits(repo):
    assert gt.post_comment.invoke({"number": 2, "body": "  "}).startswith("Error")
    assert gt.post_comment.invoke({"number": 2, "body": "x" * (gt.MAX_COMMENT_CHARS + 1)}).startswith("Error")
    assert repo.issues[2].comments == 0
    assert gt.post_comment.invoke({"number": 2, "body": "Duplicate of #1"}).startswith("Commented on #2")
    assert repo.issues[2].comment_list[0].body == "Duplicate of #1\n\n" + gt.COMMENT_MARKER


def test_the_agent_never_comments_twice_on_an_issue(repo):
    repo.issues[2].create_comment("A maintainer's own comment.")  # comments by others do not count
    assert gt.post_comment.invoke({"number": 2, "body": "Duplicate of #1"}).startswith("Commented on #2")
    again = gt.post_comment.invoke({"number": 2, "body": "Duplicate of #1, as said."}, config=RETRIAGE)
    assert again == "Error: this agent already commented on #2; it never comments twice"
    assert repo.issues[2].comments == 2


def test_an_issue_moved_to_another_repository_is_refused(repo):
    # GitHub redirects a transferred issue and PyGithub follows it; writing would hit the other repo
    repo.issues[7] = FakeIssue(7, "Moved away", repository_url="https://api.github.com/repos/someone-else/other")
    assert "moved to another repository" in gt.add_labels.invoke({"number": 7, "labels": ["bug"]})
    assert "moved to another repository" in gt.post_comment.invoke({"number": 7, "body": "hi"})
    assert repo.issues[7].labels == [] and repo.issues[7].comments == 0


def test_parallel_writes_reach_github_one_at_a_time(repo, monkeypatch):
    # Tool calls from one model turn run in parallel threads; one PyGithub client is not thread-safe.
    active, most = [0], [0]
    get_issue = repo.get_issue

    def slow_get_issue(number):
        active[0] += 1
        most[0] = max(most[0], active[0])
        time.sleep(0.01)
        active[0] -= 1
        return get_issue(number)

    monkeypatch.setattr(repo, "get_issue", slow_get_issue)
    start = threading.Barrier(6)

    def label(number):
        start.wait()
        return gt.add_labels.invoke({"number": number, "labels": ["bug"]}, config=RETRIAGE)

    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(label, [1, 2, 3, 1, 2, 3]))
    assert most[0] == 1
    assert all(r.startswith("Labelled") for r in results)


def test_there_is_no_tool_that_closes_or_deletes():
    names = {t.name for t in gt.READ_TOOLS + gt.WRITE_TOOLS}
    assert names == {"list_open_issues", "get_issue", "apply_triage"}
    assert all("repo" not in t.args for t in gt.READ_TOOLS + gt.WRITE_TOOLS)  # no way to target another repo


def test_repo_resolution_refuses_a_redirect(monkeypatch):
    class Redirected:
        full_name = "someone-else/other-repo"

    class FakeGithub:
        def __init__(self, **kwargs):
            pass

        def get_repo(self, name):
            return Redirected()

    monkeypatch.setenv("GITHUB_REPO", "example/streaks")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(gt, "Github", FakeGithub)
    gt._repo.cache_clear()
    try:
        gt._repo()
    except RuntimeError as exc:
        assert "refusing to continue" in str(exc)
    else:
        raise AssertionError("expected a refusal")
    finally:
        gt._repo.cache_clear()


def test_batch_keeps_guards_and_continues_after_a_failed_item(repo):
    result = gt.apply_triage.invoke({"labels": [
        {"number": 1, "labels": ["unknown"]},
        {"number": 2, "labels": ["bug"]}], "comments": []})
    assert "Error: unknown" in result and "Labelled #2: bug" in result
    assert repo.issues[1].labels == []
    assert [label.name for label in repo.issues[2].labels] == ["bug"]


def test_batch_forwards_retriage_configuration(repo):
    repo.issues[1].add_to_labels("question")
    batch = {"labels": [{"number": 1, "labels": ["bug"]}], "comments": []}
    assert "was triaged before" in gt.apply_triage.invoke(batch)
    assert gt.apply_triage.invoke(batch, config=RETRIAGE) == "Labelled #1: bug"
