---
name: opencode-session-extract
description: Extract OpenCode chat sessions for a project and load prior prompts, responses, and tool results into the current agent context. Use when asked to find, list, load, continue, recover, or search an OpenCode session for a workspace.
---

# OpenCode Session Extraction

Use the bundled read-only extractor before writing ad hoc SQL. It reads OpenCode's SQLite database, filters by project directory, excludes child/subagent sessions by default, and omits reasoning parts.

## Run

Resolve this Skill's directory as `$skillRoot`, then run:

```powershell
$extractor = Join-Path $skillRoot 'scripts\extract_opencode_session.py'

# Extract the latest main session for the current project as Markdown.
python $extractor --project $PWD --latest

# List candidate sessions before choosing one.
python $extractor --project $PWD --list

# Extract a specific session to a file for large transcripts.
python $extractor `
  --project $PWD `
  --session ses_abc123 `
  --output opencode-session.md
```

Useful narrowing options:

- `--keyword TEXT` may be repeated to keep only matching parts.
- `--tail N` keeps the last N messages and prompts.
- `--format json` produces structured output.
- `--include-children` includes subagent sessions.
- `--max-part-chars 0` disables per-part truncation; use this only when the extra context is necessary.
- `--db PATH` selects a non-default or recovered database.

The default action without `--list` or `--session` is latest-session extraction, so `--latest` is optional but useful for clarity.

## Load context

Read the generated output, summarize the user's goals, completed changes, unresolved failures, and last verified state. Do not dump a large transcript into the reply. Cross-check the repository's current files, `git status`, and recent commits because a session may end after a tool result without a final assistant message.

The SQLite database is authoritative. The script opens it with `mode=ro`; do not copy, migrate, vacuum, or write to the live database for extraction. Fall back to manual schema inspection only if the script reports an unsupported schema.

