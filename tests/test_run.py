"""The terminal review loop: what the reviewer sees and how edits are built."""

from issue_triage import run


def test_review_prompt_shows_characters_that_could_redraw_the_terminal():
    cr, esc, rlo = chr(13), chr(27), chr(0x202E)
    shown = run.visible(f"spam{cr}Thanks for the report!{esc}[2K{rlo}x")
    assert cr not in shown and esc not in shown and rlo not in shown
    bs = chr(92)  # a backslash: the escapes are shown as text
    assert shown == f"spam{bs}rThanks for the report!{bs}x1b[2K{bs}u202ex"
    assert run.visible("line one\nline two\ttab") == "line one\nline two\ttab"


def test_edit_changes_and_drops_items_of_the_batch(monkeypatch):
    # item 1: new labels; item 2: dropped; item 3 (the comment): new text
    answers = iter(["e", "1", "bug, documentation", "2", "-", "3", "Tracking this in #1.", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    args = {"labels": [{"number": 3}, {"number": 5, "labels": ["bug"]}],  # a change without labels still edits
            "comments": [{"number": 5, "body": "Duplicate of #1."}]}
    decision = run.ask_reviewer({"name": "apply_triage", "args": args, "description": "batch"})
    assert decision == {"type": "edit", "edited_action": {"name": "apply_triage", "args": {
        "labels": [{"number": 3, "labels": ["bug", "documentation"]}],
        "comments": [{"number": 5, "body": "Tracking this in #1."}]}}}
    assert args["labels"][0] == {"number": 3}  # the request itself is not mutated
