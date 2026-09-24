import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = (
    Path(__file__).parents[1]
    / "scripts"
    / "extract_opencode_session.py"
)
SPEC = importlib.util.spec_from_file_location("extract_opencode_session", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class ExtractOpenCodeSessionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.db = self.root / "opencode.db"
        connection = sqlite3.connect(self.db)
        connection.executescript(
            """
            CREATE TABLE session (
                id TEXT PRIMARY KEY, parent_id TEXT, title TEXT, directory TEXT,
                model TEXT, agent TEXT, time_created INTEGER, time_updated INTEGER
            );
            CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT);
            CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);
            CREATE TABLE session_input (id TEXT PRIMARY KEY, session_id TEXT, prompt TEXT, time_created INTEGER);
            """
        )
        connection.execute(
            "INSERT INTO session VALUES (?, NULL, ?, ?, ?, ?, ?, ?)",
            ("ses_main", "Main work", str(self.project), "provider/model", "build", 1000, 4000),
        )
        connection.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("ses_child", "ses_main", "Explore (@explore subagent)", str(self.project), "provider/model", "explore", 2000, 5000),
        )
        connection.execute(
            "INSERT INTO message VALUES (?, ?, ?, ?)",
            ("msg_user", "ses_main", 1000, json.dumps({"role": "user"})),
        )
        connection.execute(
            "INSERT INTO message VALUES (?, ?, ?, ?)",
            ("msg_assistant", "ses_main", 2000, json.dumps({"role": "assistant"})),
        )
        connection.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
            ("prt_user", "msg_user", "ses_main", 1000, json.dumps({"type": "text", "text": "fix session loading"})),
        )
        connection.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
            ("prt_answer", "msg_assistant", "ses_main", 2000, json.dumps({"type": "text", "text": "implemented the fix"})),
        )
        connection.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
            (
                "prt_tool",
                "msg_assistant",
                "ses_main",
                3000,
                json.dumps({"type": "tool", "tool": "bash", "state": {"input": {"command": "test"}, "output": "abcdefghij"}}),
            ),
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_lists_main_sessions_and_excludes_children_by_default(self):
        with MODULE.connect_read_only(self.db) as connection:
            sessions = MODULE.list_sessions(connection, self.project)
        self.assertEqual(["ses_main"], [session["id"] for session in sessions])

    def test_extracts_part_fallback_and_truncates_tool_output(self):
        with MODULE.connect_read_only(self.db) as connection:
            session = MODULE.list_sessions(connection, self.project)[0]
            extracted = MODULE.extract_session(connection, session, [], 0, 5)
        self.assertEqual(["fix session loading"], extracted["prompts"])
        tool = next(part for part in extracted["parts"] if part["type"] == "tool")
        self.assertTrue(tool["truncated"])
        self.assertTrue(tool["output"].startswith("abcde"))

    def test_keyword_filter_and_json_cli_output(self):
        output = self.root / "session.json"
        exit_code = MODULE.main(
            [
                "--db",
                str(self.db),
                "--project",
                str(self.project),
                "--session",
                "ses_main",
                "--keyword",
                "implemented",
                "--format",
                "json",
                "--output",
                str(output),
            ]
        )
        self.assertEqual(0, exit_code)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(["implemented the fix"], [part["text"] for part in payload["parts"]])

    def test_tail_also_limits_prompt_timeline(self):
        connection = sqlite3.connect(self.db)
        connection.execute(
            "INSERT INTO message VALUES (?, ?, ?, ?)",
            ("msg_user_2", "ses_main", 4000, json.dumps({"role": "user"})),
        )
        connection.execute(
            "INSERT INTO part VALUES (?, ?, ?, ?, ?)",
            ("prt_user_2", "msg_user_2", "ses_main", 4000, json.dumps({"type": "text", "text": "verify it"})),
        )
        connection.commit()
        connection.close()
        with MODULE.connect_read_only(self.db) as read_only:
            session = MODULE.list_sessions(read_only, self.project)[0]
            extracted = MODULE.extract_session(read_only, session, [], 1, 100)
        self.assertEqual(["verify it"], extracted["prompts"])

    def test_database_override_takes_precedence(self):
        with patch.dict(os.environ, {"OPENCODE_DB_PATH": str(self.db)}, clear=False):
            self.assertEqual(self.db, MODULE.default_database())


if __name__ == "__main__":
    unittest.main()
