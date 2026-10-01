"""The terminal review loop: what the reviewer sees and how edits are built."""

from issue_triage import run


def test_review_prompt_shows_characters_that_could_redraw_the_terminal():
    cr, esc, rlo = chr(13), chr(27), chr(0x202E)
    shown = run.visible(f"spam{cr}Thanks for the report!{esc}[2K{rlo}x")
    assert cr not in shown and esc not in shown and rlo not in shown
    bs = chr(92)  # a backslash: the escapes are shown as text
    assert shown == f"spam{bs}rThanks for the report!{bs}x1b[2K{bs}u202ex"
    assert run.visible("line one\nline two\ttab") == "line one\nline two\ttab"


def test_editing_labels_survives_a_call_without_labels(monkeypatch):
    answers = iter(["e", "bug, documentation"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    decision = run.ask_reviewer({"name": "add_labels", "args": {"number": 3}, "description": "Add labels"})
    assert decision == {"type": "edit", "edited_action": {
        "name": "add_labels", "args": {"number": 3, "labels": ["bug", "documentation"]}}}
