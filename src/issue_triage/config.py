"""Environment and model setup, shared by the dev server, the scripts and the tests.

Keys live in `.env` at the repository root (see `env.example`). The LangSmith
project is pinned here *before* anything traced runs: langsmith caches its
environment lookups, so setting them later has no effect.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

LANGSMITH_PROJECT = "github-issue-triage-agent"
DEFAULT_MODEL = "gpt-6-luna"
PROJECT_DIR = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(PROJECT_DIR / ".env", override=False)
    os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)
    if os.environ.get("LANGSMITH_API_KEY"):
        os.environ.setdefault("LANGSMITH_TRACING", "true")


def make_model():
    """gpt-6 models only call tools on Chat Completions at reasoning effort `none`, so
    the Responses API is requested explicitly. Deep Agents only switches to it by
    itself for "openai:..." model strings, not for an instance."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL),
        use_responses_api=True,
        reasoning={"effort": "low"},
        timeout=120,
        max_retries=2,
    )
