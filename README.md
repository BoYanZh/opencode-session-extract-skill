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

On Windows, install to the shared Agent Skills location, OpenCode's global skill location, or both:

```powershell
./install.ps1                    # both locations
./install.ps1 -Target Shared     # ~/.agents/skills only
./install.ps1 -Target OpenCode   # ~/.config/opencode/skills only
```

On macOS or Linux, copy `SKILL.md` and `scripts/` into the desired skill root:

```bash
mkdir -p ~/.agents/skills/opencode-session-extract
cp -R SKILL.md scripts ~/.agents/skills/opencode-session-extract/
```

The installer backs up an existing installation before replacing its two managed files.

## CLI

```bash
python scripts/extract_opencode_session.py --project /path/to/repo --list
python scripts/extract_opencode_session.py --project /path/to/repo --latest
python scripts/extract_opencode_session.py --project /path/to/repo --session ses_abc123
python scripts/extract_opencode_session.py --project /path/to/repo --latest --tail 10 --keyword updater
python scripts/extract_opencode_session.py --project /path/to/repo --latest --format json
```

The database is auto-detected from common OpenCode locations. Override it with `--db PATH` or `OPENCODE_DB_PATH`.

## Privacy

Session text and tool output may contain source code, local paths, commands, or secrets. This tool does not upload anything and does not perform automatic secret redaction. Review generated output before sharing or committing it.

## Development

```bash
python -m unittest discover -s tests -v
python -m py_compile scripts/extract_opencode_session.py
```

## Related projects

- [`daedalus/opencode-session-extractor`](https://github.com/daedalus/opencode-session-extractor) is a general Python export package.
- [`huairenwww/opencode-skill-session-export`](https://github.com/huairenwww/opencode-skill-session-export) synchronizes all sessions into Markdown files through the OpenCode CLI.
- [`ZelinZhou-THU/opencode-export`](https://github.com/ZelinZhou-THU/opencode-export) provides full HTML/JSON archives and an MCP server.

This repository focuses on lightweight, project-scoped, read-only context recovery for coding agents.

## License

MIT
