#!/usr/bin/env python3
"""Read OpenCode sessions from its SQLite database without modifying it."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def database_candidates() -> list[Path]:
    candidates: list[Path] = []
    if explicit := os.environ.get("OPENCODE_DB_PATH"):
        candidates.append(Path(explicit))
    if xdg_data := os.environ.get("XDG_DATA_HOME"):
        candidates.append(Path(xdg_data) / "opencode" / "opencode.db")
    candidates.append(Path.home() / ".local" / "share" / "opencode" / "opencode.db")
    if local_app_data := os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(local_app_data) / "opencode" / "opencode.db")
    candidates.append(Path.home() / "Library" / "Application Support" / "opencode" / "opencode.db")
    return candidates


def default_database() -> Path:
    return next((path for path in database_candidates() if path.is_file()), database_candidates()[0])


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or extract OpenCode sessions from the read-only SQLite database."
    )
    parser.add_argument("--db", type=Path, default=default_database(), help="Path to opencode.db")
    parser.add_argument(
        "--project",
        type=Path,
        default=Path.cwd(),
        help="Project directory used to filter sessions (default: current directory)",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="List matching sessions")
    action.add_argument("--session", help="Extract an exact or uniquely prefixed session ID")
    action.add_argument("--latest", action="store_true", help="Extract the latest matching session")
    parser.add_argument(
        "--include-children",
        action="store_true",
        help="Include child/subagent sessions in listing and latest-session selection",
    )
    parser.add_argument("--keyword", action="append", default=[], help="Keep parts matching this text; repeatable")
    parser.add_argument("--tail", type=int, default=0, help="Keep only the last N messages and prompts (0 means all)")
    parser.add_argument(
        "--max-part-chars",
        type=int,
        default=8000,
        help="Maximum characters per text/tool output; 0 disables truncation",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="Write output atomically instead of printing it")
    return parser.parse_args(argv)


@contextlib.contextmanager
def connect_read_only(path: Path) -> Iterable[sqlite3.Connection]:
    path = path.expanduser().resolve()
    if not path.is_file():
        checked = "\n  ".join(str(candidate) for candidate in database_candidates())
        raise ExtractError(f"OpenCode database not found: {path}\nChecked defaults:\n  {checked}")
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


class ExtractError(RuntimeError):
    pass


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def require_tables(connection: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    missing = {"session", "message", "part"} - tables
    if missing:
        raise ExtractError(f"Unsupported OpenCode database schema; missing tables: {', '.join(sorted(missing))}")


def normalize_path(value: str | Path) -> str:
    normalized = os.path.normpath(os.path.abspath(os.path.expanduser(str(value))))
    return os.path.normcase(normalized)


def parse_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def timestamp_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        number = float(value)
        if number > 10_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return str(value)


def list_sessions(
    connection: sqlite3.Connection,
    project: Path,
    include_children: bool = False,
) -> list[dict[str, Any]]:
    columns = table_columns(connection, "session")
    wanted = [
        name
        for name in (
            "id", "project_id", "workspace_id", "parent_id", "title", "directory",
            "path", "model", "agent", "time_created", "time_updated",
        )
        if name in columns
    ]
    if "id" not in wanted:
        raise ExtractError("Unsupported OpenCode session schema: missing session.id")
    rows = connection.execute(
        f"SELECT {', '.join(wanted)} FROM session ORDER BY "
        + ("time_updated DESC" if "time_updated" in columns else "rowid DESC")
    ).fetchall()
    project_path = normalize_path(project)
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        session_path = item.get("directory") or item.get("path")
        if not session_path or normalize_path(session_path) != project_path:
            continue
        if not include_children and item.get("parent_id"):
            continue
        item["time_created_iso"] = timestamp_text(item.get("time_created"))
        item["time_updated_iso"] = timestamp_text(item.get("time_updated"))
        result.append(item)
    return result


def resolve_session(sessions: list[dict[str, Any]], session_id: str | None) -> dict[str, Any]:
    if not sessions:
        raise ExtractError("No matching OpenCode sessions found for the project.")
    if not session_id:
        return sessions[0]
    exact = [session for session in sessions if session["id"] == session_id]
    if exact:
        return exact[0]
    prefixes = [session for session in sessions if session["id"].startswith(session_id)]
    if len(prefixes) == 1:
        return prefixes[0]
    if not prefixes:
        raise ExtractError(f"Session not found in this project: {session_id}")
    raise ExtractError(f"Session prefix is ambiguous: {session_id}")


def truncate(value: str, limit: int) -> tuple[str, bool]:
    if limit <= 0 or len(value) <= limit:
        return value, False
    omitted = len(value) - limit
    return value[:limit] + f"\n… [truncated {omitted} characters]", True


def message_roles(connection: sqlite3.Connection, session_id: str) -> dict[str, str]:
    roles: dict[str, str] = {}
    for row in connection.execute("SELECT id, data FROM message WHERE session_id = ?", (session_id,)):
        roles[row["id"]] = str(parse_json(row["data"]).get("role") or "unknown")
    return roles


def load_parts(
    connection: sqlite3.Connection,
    session_id: str,
    keywords: Iterable[str],
    max_part_chars: int,
) -> list[dict[str, Any]]:
    roles = message_roles(connection, session_id)
    part_columns = table_columns(connection, "part")
    order = "time_created, rowid" if "time_created" in part_columns else "rowid"
    rows = connection.execute(
        f"SELECT message_id, data{', time_created' if 'time_created' in part_columns else ''} "
        f"FROM part WHERE session_id = ? ORDER BY {order}", (session_id,),
    ).fetchall()
    lowered_keywords = [keyword.casefold() for keyword in keywords if keyword]
    parts: list[dict[str, Any]] = []
    for row in rows:
        data = parse_json(row["data"])
        part_type = data.get("type")
        if part_type not in {"text", "tool"}:
            continue
        role = roles.get(row["message_id"], "unknown")
        if part_type == "text":
            content = str(data.get("text") or "")
            tool = None
            title = None
            state: dict[str, Any] = {}
        else:
            state = data.get("state") if isinstance(data.get("state"), dict) else {}
            content = str(state.get("output") or "")
            tool = data.get("tool")
            title = data.get("title")
        searchable = json.dumps(data, ensure_ascii=False).casefold()
        if lowered_keywords and not any(keyword in searchable for keyword in lowered_keywords):
            continue
        content, was_truncated = truncate(content, max_part_chars)
        created = row["time_created"] if "time_created" in row.keys() else None
        parts.append({
            "message_id": row["message_id"], "role": role, "type": part_type,
            "time_created": created, "time_created_iso": timestamp_text(created),
            "text": content if part_type == "text" else None, "tool": tool, "title": title,
            "input": state.get("input") if part_type == "tool" else None,
            "output": content if part_type == "tool" else None,
            "status": state.get("status") if part_type == "tool" else None,
            "truncated": was_truncated,
        })
    return parts


def load_prompts(connection: sqlite3.Connection, session_id: str) -> list[str]:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    prompts: list[str] = []
    if "session_input" in tables and {"session_id", "prompt"} <= table_columns(connection, "session_input"):
        for row in connection.execute(
            "SELECT prompt FROM session_input WHERE session_id = ? ORDER BY time_created, rowid", (session_id,),
        ):
            prompt = row["prompt"]
            parsed = parse_json(prompt) if isinstance(prompt, str) else {}
            text = parsed.get("text") if parsed else str(prompt or "")
            if text and (not prompts or prompts[-1] != text):
                prompts.append(str(text))
    if prompts:
        return prompts
    roles = message_roles(connection, session_id)
    part_columns = table_columns(connection, "part")
    order = "time_created, rowid" if "time_created" in part_columns else "rowid"
    for row in connection.execute(
        f"SELECT message_id, data FROM part WHERE session_id = ? ORDER BY {order}", (session_id,),
    ):
        data = parse_json(row["data"])
        text = data.get("text")
        if data.get("type") == "text" and roles.get(row["message_id"]) == "user" and text:
            if not prompts or prompts[-1] != text:
                prompts.append(str(text))
    return prompts


def apply_tail(parts: list[dict[str, Any]], tail: int) -> list[dict[str, Any]]:
    if tail <= 0:
        return parts
    message_ids: list[str] = []
    for part in parts:
        if part["message_id"] not in message_ids:
            message_ids.append(part["message_id"])
    keep = set(message_ids[-tail:])
    return [part for part in parts if part["message_id"] in keep]


def extract_session(connection: sqlite3.Connection, session: dict[str, Any], keywords: Iterable[str], tail: int, max_part_chars: int) -> dict[str, Any]:
    parts = load_parts(connection, session["id"], keywords, max_part_chars)
    prompts = load_prompts(connection, session["id"])
    if tail > 0:
        prompts = prompts[-tail:]
    return {"session": session, "prompts": prompts, "parts": apply_tail(parts, tail)}


def markdown_list(sessions: list[dict[str, Any]]) -> str:
    lines = ["# OpenCode sessions", ""]
    for session in sessions:
        title = session.get("title") or "(untitled)"
        lines.append(f"- `{session['id']}` — {title} — {session.get('time_updated_iso') or session.get('time_created_iso')}")
    return "\n".join(lines) + "\n"


def markdown_extract(data: dict[str, Any]) -> str:
    session = data["session"]
    lines = [
        f"# {session.get('title') or session['id']}", "", f"- Session: `{session['id']}`",
        f"- Directory: `{session.get('directory') or session.get('path') or ''}`",
        f"- Updated: {session.get('time_updated_iso') or session.get('time_created_iso')}",
        f"- Model: `{session.get('model') or ''}`", f"- Agent: `{session.get('agent') or ''}`",
        "", "## User prompts", "",
    ]
    lines.extend(f"{index}. {prompt}" for index, prompt in enumerate(data["prompts"], 1))
    lines.extend(["", "## Transcript", ""])
    for part in data["parts"]:
        if part["type"] == "text":
            lines.extend([f"### {part['role']} · `{part['message_id']}`", "", part["text"] or "", ""])
        else:
            lines.extend([
                f"### tool `{part.get('tool') or 'unknown'}` · `{part['message_id']}`", "", "Input:",
                "```json", json.dumps(part.get("input"), ensure_ascii=False, indent=2), "```", "",
                "Output:", "```text", part.get("output") or "", "```", "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def write_output(path: Path | None, content: str) -> None:
    if path is None:
        sys.stdout.write(content)
        return
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        with connect_read_only(args.db) as connection:
            require_tables(connection)
            sessions = list_sessions(connection, args.project, args.include_children)
            if args.list:
                payload: Any = sessions
                content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else markdown_list(sessions)
            else:
                selected = resolve_session(sessions, args.session)
                payload = extract_session(connection, selected, args.keyword, args.tail, args.max_part_chars)
                content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n" if args.format == "json" else markdown_extract(payload)
            write_output(args.output, content)
        return 0
    except (ExtractError, sqlite3.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

