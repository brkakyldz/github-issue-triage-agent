"""Entry point for `langgraph dev` (see langgraph.json). No checkpointer here: the
server persists threads itself."""

from issue_triage.config import load_env, make_model

load_env()

from issue_triage.agent import build_agent  # noqa: E402  (env must be loaded before LangChain traces)

agent = build_agent(make_model())
