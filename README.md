# GitHub Issue Triage Agent

An AI assistant for GitHub maintainers that reviews unlabelled issues, suggests labels,
finds duplicates and prepares replies. It saves a triage report, then asks a human to
approve, edit or reject every proposed label and comment before changing GitHub.

![Terminal demo: the agent reviews new issues, requests approval for labels and a duplicate comment, then finds nothing left to triage on the next run](docs/demo.gif)

See the resulting labels and comments in the public
[issue-triage sandbox](https://github.com/brkakyldz/issue-triage-sandbox), a fictional
habit-tracker project used for the demo.

## What it does

- Reviews open issues with no labels. Already labelled issues remain available as
  references when looking for duplicates.
- Suggests one main label: `bug`, `enhancement`, `question` or `documentation`.
  It can also suggest `duplicate` and `good first issue`.
- Identifies a newer issue that describes the same problem as an older open issue.
- Writes `output/triage.md` with suggested labels, reasons, duplicate pairs and a
  draft reply for each issue.
- Proposes comments on duplicates that point to the original issue. Other replies
  stay in the report for the maintainer to use.

For example, a report about a streak resetting after a second check-in can be labelled
`bug, duplicate` and linked to the earlier report. The maintainer reviews both the
labels and the comment; rejecting either leaves that action unapplied.

## How a triage pass works

```mermaid
flowchart TD
    A["Read unlabelled issues and older open issues"] --> B["Suggest labels and check duplicates"]
    B --> C["Write the triage report"]
    C --> D["Propose labels and duplicate comments"]
    D --> E{"Maintainer review"}
    E -->|Approve or edit| F["Apply the reviewed action to GitHub"]
    E -->|Reject| G["Leave that action unapplied"]
```

Built with **Deep Agents**, a read-only duplicate-finder subagent and **PyGithub**.
The agent plans the pass and prepares the report before requesting approval.

The tools restrict writes to the repository configured in `GITHUB_REPO` and accept
only labels that already exist there. By default, they refuse to label an issue that
has gained labels since it was read. Posted comments carry a hidden marker, preventing
the agent from commenting twice on the same issue. Issue text is treated as untrusted
input, and every proposed write still goes through review.

## Run locally

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), an OpenAI API key and a
GitHub fine-grained personal access token scoped to your target repository with
**Issues: Read and write** permission.

```bash
git clone https://github.com/brkakyldz/github-issue-triage-agent.git
cd github-issue-triage-agent
uv sync
cp env.example .env
```

In `.env`, set `OPENAI_API_KEY`, `GITHUB_REPO=owner/repo` and `GITHUB_TOKEN`.
The repository should have the labels listed above. The default model is
`gpt-6-luna`; change it with `OPENAI_MODEL`. Add `LANGSMITH_API_KEY` to enable tracing.

```bash
uv run triage --reject-all   # generate a report; reject every GitHub write
uv run triage                # review and apply individual actions
uv run triage --all           # include already labelled open issues
```

The report is saved to `output/triage.md`. Its *Applied* column is the model's summary
and can be inaccurate; check GitHub for the actual result.

### Try the sample issues

For a repository you own and use as a sandbox, these commands create the demo labels
and issues in the repository named by `GITHUB_REPO`:

```bash
uv run triage-seed --first-wave   # create labels and the first 14 issues
uv run triage
uv run triage-seed                # add the second wave of six issues
uv run triage
uv run triage-seed --status       # compare GitHub with the sample answer key
```

The 20 fictional issues and their expected results are in
[`seed/issues.json`](seed/issues.json). Example reports:
[first wave](docs/triage-example.md) and [second wave](docs/triage-wave-2.md).

### Use LangGraph Studio

Run `uv run langgraph dev`, open
[Studio](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024),
select `triage` and send: *"Triage the open issues that have no labels yet."*
Review the interrupted calls and resume with one decision per action, in order.
The report is available as `/triage.md` in the thread state's `files`.

## Verification

```bash
uv run pytest
uv run python scripts/acceptance.py
```

Offline tests cover the tools, repeated runs, approval flow and file permissions.
The acceptance script uses the real model and writes to the configured GitHub
repository; run it against a seeded sandbox with LangSmith configured.

The recorded acceptance run on **2026-10-01** passed **5/5 checks**, including duplicate
detection, approved/edited/rejected actions and a second pass over the remaining
unlabelled issue. [Full results](docs/acceptance-2026-10-01.txt).

<details>
<summary>LangSmith trace</summary>

With tracing enabled, runs appear in `github-issue-triage-agent`. The duplicate-finder's
model and tool calls are nested under the main agent's trace.

![LangSmith trace showing the duplicate-finder inside the main agent's run](docs/langsmith-trace.jpg)

</details>

## Current scope

Runs on demand against one repository. It does not listen for webhooks, close or
delete issues, triage pull requests, or run code.

## License

[MIT](LICENSE)
