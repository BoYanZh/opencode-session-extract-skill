# OpenCode Session Extract Skill

A small, read-only Agent Skill for recovering OpenCode conversation context from `opencode.db`.

It is designed for the common handoff: find sessions for the current repository, select one, and load a bounded Markdown or JSON transcript into another coding agent without modifying the live OpenCode database.

## Features

- Filters sessions by exact project directory.
- Lists or extracts the latest/specific session.
- Reads SQLite with `mode=ro` and Python's standard library only.
- Falls back from `session_input` to user text stored in `part`.
- Includes assistant text and bounded tool inputs/outputs.
- Omits reasoning parts and child/subagent sessions by default.
- Supports keywords, tail limits, JSON output, and atomic file output.
- Runs on Windows, macOS, and Linux with Python 3.10+.

## Install

Recent GitHub CLI releases provide a first-party Skill installer. Run one of these commands from the repository where you want to use the Skill.

```powershell
# Project scope: installs to .agents/skills and can be committed for the team.
gh skill install BoYanZh/opencode-session-extract-skill opencode-session-extract --agent opencode

# User scope: available to OpenCode in every repository.
gh skill install BoYanZh/opencode-session-extract-skill opencode-session-extract --agent opencode --scope user

# Reproducible install: pin a released version.
gh skill install BoYanZh/opencode-session-extract-skill opencode-session-extract@v1.0.0 --agent opencode --scope user
```

GitHub CLI records source metadata, so later updates are handled by:

```powershell
gh skill update
```

For Codex, replace `--agent opencode` with `--agent codex`. OpenCode discovers both project-level `.agents/skills` and global `~/.config/opencode/skills` locations.

Choose one scope for this Skill:

- Use **user scope** for personal use across all repositories.
- Use **project scope** when the repository should carry a team-visible or pinned copy.

Avoid installing the same Skill ID at both scopes. OpenCode gives `~/.config/opencode/skills` higher precedence than project `.agents/skills`, so a stale user-scoped copy can shadow the project-scoped version.

## CLI

```bash
python skills/opencode-session-extract/scripts/extract_opencode_session.py --project /path/to/repo --list
python skills/opencode-session-extract/scripts/extract_opencode_session.py --project /path/to/repo --latest
python skills/opencode-session-extract/scripts/extract_opencode_session.py --project /path/to/repo --session ses_abc123
python skills/opencode-session-extract/scripts/extract_opencode_session.py --project /path/to/repo --latest --tail 10 --keyword updater
python skills/opencode-session-extract/scripts/extract_opencode_session.py --project /path/to/repo --latest --format json
```

The database is auto-detected from common OpenCode locations. Override it with `--db PATH` or `OPENCODE_DB_PATH`.

## Privacy

Session text and tool output may contain source code, local paths, commands, or secrets. This tool does not upload anything and does not perform automatic secret redaction. Review generated output before sharing or committing it.

## Development

```bash
python -m unittest discover -s tests -v
python -m py_compile skills/opencode-session-extract/scripts/extract_opencode_session.py
```

## Related projects

- [`daedalus/opencode-session-extractor`](https://github.com/daedalus/opencode-session-extractor) is a general Python export package.
- [`huairenwww/opencode-skill-session-export`](https://github.com/huairenwww/opencode-skill-session-export) synchronizes all sessions into Markdown files through the OpenCode CLI.
- [`ZelinZhou-THU/opencode-export`](https://github.com/ZelinZhou-THU/opencode-export) provides full HTML/JSON archives and an MCP server.

This repository focuses on lightweight, project-scoped, read-only context recovery for coding agents.

## License

MIT
