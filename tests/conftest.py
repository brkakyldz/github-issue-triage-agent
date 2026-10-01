"""An in-memory stand-in for the PyGithub objects the tools use, and a scripted model.
Tracing is switched off first: the package loads .env, which turns it on
when a LangSmith key is present."""

from __future__ import annotations

import os

os.environ["LANGSMITH_TRACING"] = "false"

from dataclasses import dataclass, field
from typing import Any

import pytest
from github import UnknownObjectException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from issue_triage import github_tools as gt

REPO_URL = "https://api.github.com/repos/example/streaks"


@dataclass
class FakeUser:
    login: str


@dataclass
class FakeLabel:
    name: str


@dataclass
class FakeComment:
    body: str
    user: FakeUser = field(default_factory=lambda: FakeUser("triage-bot"))
    html_url: str = "https://github.com/o/r/issues/0#issuecomment-1"


@dataclass
class FakeIssue:
    number: int
    title: str
    body: str | None = ""
    labels: list[FakeLabel] = field(default_factory=list)
    comment_list: list[FakeComment] = field(default_factory=list)
    pull_request: Any = None
    state: str = "open"
    user: FakeUser = field(default_factory=lambda: FakeUser("someone"))
    repository_url: str = REPO_URL  # another repository's URL when the issue was transferred

    @property
    def comments(self) -> int:
        return len(self.comment_list)

    def get_comments(self):
        return iter(list(self.comment_list))  # lazy like PyGithub's PaginatedList: iterate, don't slice

    def add_to_labels(self, *names: str) -> None:
        for name in names:
            if name not in [label.name for label in self.labels]:
                self.labels.append(FakeLabel(name))

    def create_comment(self, body: str) -> FakeComment:
        comment = FakeComment(body, html_url=f"https://github.com/o/r/issues/{self.number}#issuecomment-1")
        self.comment_list.append(comment)
        return comment


class FakeRepo:
    full_name = "example/streaks"
    url = REPO_URL

    def __init__(self) -> None:
        self.labels = [FakeLabel(n) for n in
                       ("bug", "enhancement", "question", "documentation", "duplicate", "good first issue")]
        self.issues = {
            1: FakeIssue(1, "Crash when a habit name contains an emoji", "UnicodeEncodeError on Windows"),
            2: FakeIssue(2, "UnicodeEncodeError on Windows when listing habits", "Same crash, 'Stretch 🧘'"),
            3: FakeIssue(3, "Export check-in history to CSV", "x" * 5000),
            4: FakeIssue(4, "A pull request", "not an issue", pull_request={"url": "..."}),
        }

    def get_issues(self, state="open", sort=None, direction=None):
        return [i for i in self.issues.values() if state == "all" or i.state == state]

    def get_issue(self, number: int) -> FakeIssue:
        if number not in self.issues:
            raise UnknownObjectException(404, {"message": "Not Found"}, None)
        return self.issues[number]

    def get_labels(self):
        return list(self.labels)


@pytest.fixture
def repo(monkeypatch) -> FakeRepo:
    fake = FakeRepo()
    monkeypatch.setattr(gt, "_repo", lambda: fake)
    return fake


class ScriptedModel(BaseChatModel):
    """Returns queued AIMessages in order and records what it was sent."""

    replies: list[AIMessage]
    seen: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> ScriptedModel:
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


def calls(*specs: tuple[str, dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=[
        {"name": name, "args": args, "id": f"call_{i}", "type": "tool_call"} for i, (name, args) in enumerate(specs)
    ])
