"""The deep agent's HITL flow with a scripted model and the in-memory repository."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from issue_triage.agent import REPORT_PATH, build_agent
from issue_triage.github_tools import COMMENT_MARKER
from issue_triage.run import run_triage, save_report

from .conftest import ScriptedModel, calls

REPORT = "# Issue triage\n\n| # | Title | Suggested labels | Reason | Duplicate of | Applied |\n"


def scripted_run(repo, decide):
    model = ScriptedModel(replies=[
        calls(("write_file", {"file_path": REPORT_PATH, "content": REPORT})),
        calls(
            ("add_labels", {"number": 1, "labels": ["bug"]}),
            ("add_labels", {"number": 2, "labels": ["bug", "duplicate"]}),
            ("post_comment", {"number": 2, "body": "Looks like a duplicate of #1."}),
        ),
        AIMessage("Done: 1 labelled, 1 rejected, 1 comment edited."),
    ])
    agent = build_agent(model, checkpointer=InMemorySaver())
    return run_triage(agent, decide), model


def test_every_write_waits_for_the_reviewer_and_follows_the_decision(repo, tmp_path):
    decisions = iter([
        {"type": "approve"},
        {"type": "reject", "message": "Not sure it is the same bug."},
        {"type": "edit", "edited_action": {"name": "post_comment",
                                           "args": {"number": 2, "body": "Thanks! Tracking this in #1."}}},
    ])
    (result, log), _ = scripted_run(repo, lambda request: next(decisions))

    # one batched interrupt with the three writes, each described for the reviewer
    assert [r["name"] for r, _ in log] == ["add_labels", "add_labels", "post_comment"]
    assert log[0][0]["description"] == "Add labels ['bug'] to issue #1"
    # approve -> applied; reject -> nothing changed; edit -> the reviewer's text was posted
    assert [label.name for label in repo.issues[1].labels] == ["bug"]
    assert repo.issues[2].labels == []
    assert [c.body for c in repo.issues[2].comment_list] == ["Thanks! Tracking this in #1.\n\n" + COMMENT_MARKER]

    # the report lives in the virtual filesystem and is saved by host code
    path = save_report(result.value["files"], tmp_path)
    assert path.read_text(encoding="utf-8") == REPORT


def test_reject_all_leaves_github_untouched(repo):
    scripted_run(repo, lambda request: {"type": "reject", "message": "dry run"})
    assert all(issue.labels == [] and issue.comments == 0 for issue in repo.issues.values())


def test_the_agent_can_only_write_the_report_file(repo):
    model = ScriptedModel(replies=[
        calls(("write_file", {"file_path": "/notes.md", "content": "hi"})),
        AIMessage("ok"),
    ])
    result, _ = run_triage(build_agent(model, checkpointer=InMemorySaver()), lambda r: {"type": "approve"})
    refusal = [m for m in result.value["messages"] if m.type == "tool"][-1]
    assert "permission denied" in refusal.content
    assert "/notes.md" not in result.value.get("files", {})


def test_the_subagent_cannot_write_the_report(repo):
    # duplicate-finder reads the raw issue text, so it gets no file writes at all
    model = ScriptedModel(replies=[
        calls(("task", {"description": "Find duplicates.", "subagent_type": "duplicate-finder"})),
        calls(("write_file", {"file_path": REPORT_PATH, "content": "overwritten by the subagent"})),
        AIMessage("none"),
        AIMessage("ok"),
    ])
    result, _ = run_triage(build_agent(model, checkpointer=InMemorySaver()), lambda r: {"type": "approve"})
    assert REPORT_PATH not in result.value.get("files", {})
    subagent_saw = [m.content for m in model.seen[2] if m.type == "tool"]
    assert any("permission denied" in c for c in subagent_saw)


def triage_labelled_issue(repo, retriage: bool):
    """#1 already has a label; the model lists issues, asks the subagent (which lists them
    too) and tries to relabel #1. Returns what the main agent and the subagent were told."""
    repo.issues[1].add_to_labels("question")
    model = ScriptedModel(replies=[
        calls(("list_open_issues", {})),
        calls(("task", {"description": "Find duplicates.", "subagent_type": "duplicate-finder"})),
        calls(("list_open_issues", {})),  # the subagent
        AIMessage("none"),
        calls(("add_labels", {"number": 1, "labels": ["bug"]})),
        AIMessage("done"),
    ])
    result, _ = run_triage(build_agent(model, checkpointer=InMemorySaver()), lambda r: {"type": "approve"},
                           retriage=retriage)
    tool_results = [m.content for m in result.value["messages"] if m.type == "tool"]
    subagent_saw = [m.content for m in model.seen[3] if m.type == "tool"]
    return tool_results, subagent_saw


def test_a_normal_run_leaves_issues_triaged_before_alone(repo):
    tool_results, subagent_saw = triage_labelled_issue(repo, retriage=False)
    assert '"already_triaged": [{"number": 1' in tool_results[0]
    assert '"already_triaged": [{"number": 1' in subagent_saw[-1]  # the subagent runs with the same config
    assert tool_results[-1].startswith("Error: #1 was triaged before")
    assert [label.name for label in repo.issues[1].labels] == ["question"]


def test_a_retriage_run_reaches_the_tools_and_the_subagent(repo):
    tool_results, subagent_saw = triage_labelled_issue(repo, retriage=True)
    assert '"already_triaged": []' in tool_results[0]
    assert '"already_triaged": []' in subagent_saw[-1]
    assert tool_results[-1] == "Labelled #1: bug"


def test_served_agent_has_no_checkpointer_and_no_general_purpose_subagent(repo, monkeypatch):
    # The general-purpose subagent is switched off by a harness profile registered for the
    # "openai" provider, so this check uses the real model class (building it makes no call).
    from issue_triage.config import make_model

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    agent = build_agent(make_model())
    assert agent.checkpointer is None  # `langgraph dev` refuses graphs that bring one
    tools = agent.nodes["tools"].bound.tools_by_name
    assert "- duplicate-finder:" in tools["task"].description
    assert "- general-purpose:" not in tools["task"].description  # not among the listed subagents
    assert "write_todos" in tools
