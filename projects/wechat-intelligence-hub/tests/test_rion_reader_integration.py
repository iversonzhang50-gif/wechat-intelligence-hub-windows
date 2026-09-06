import json
import os
from pathlib import Path
import plistlib
import shlex
import sqlite3
import subprocess
import sys
import tempfile
import unittest

try:
    from sqlcipher3 import dbapi2 as SQLCIPHER
except ImportError:
    try:
        from pysqlcipher3 import dbapi2 as SQLCIPHER
    except ImportError:
        SQLCIPHER = None


HUB_ROOT = Path(__file__).resolve().parents[1]
READER = HUB_ROOT.parent / "rion-wechat-reader" / "rion_wechat_reader.py"


@unittest.skipUnless(SQLCIPHER is not None, "SQLCipher driver not installed")
class RionReaderEncryptedIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = "33" * 32
        self.data_root = self.root / "encrypted-wechat"
        self.data_root.mkdir()
        self.session = self.data_root / "session.db"
        self.contact = self.data_root / "contact.db"
        self.message = self.data_root / "message_0.db"
        self.keys = self.root / "keys.json"
        self.config = self.root / "config.json"
        self.reader = self.root / "rion-wechat-cli"
        self.wechat_app = self.root / "WeChat.app"
        self._build_encrypted_fixtures()
        self._write_reader_files()
        self._write_fake_wechat_app()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def encrypted_connection(self, path: Path):
        connection = SQLCIPHER.connect(str(path))
        connection.execute(f'PRAGMA key="x\'{self.key}\'"')
        connection.execute("PRAGMA cipher_compatibility = 4")
        return connection

    def _build_encrypted_fixtures(self) -> None:
        with self.encrypted_connection(self.contact) as connection:
            connection.executescript(
                """
                CREATE TABLE contact(
                  id INTEGER PRIMARY KEY, username TEXT, nick_name TEXT, remark TEXT,
                  alias TEXT, description TEXT, local_type INTEGER
                );
                INSERT INTO contact VALUES
                  (1, 'fixture_contact', 'Fixture Alice', 'Fixture Partner', 'fixture', '', 1),
                  (2, 'fixture_owner', 'Fixture Owner', 'Me', '', '', 1);
                """
            )
        with self.encrypted_connection(self.session) as connection:
            connection.executescript(
                """
                CREATE TABLE SessionTable(
                  username TEXT, type INTEGER, unread_count INTEGER, summary TEXT,
                  last_timestamp INTEGER, sort_timestamp INTEGER,
                  last_msg_type INTEGER, last_msg_sub_type INTEGER,
                  last_msg_sender TEXT, last_sender_display_name TEXT
                );
                INSERT INTO SessionTable VALUES(
                  'fixture_contact', 1, 1, '方案什么时候发？', 200, 200, 1, 0,
                  'fixture_contact', 'Fixture Alice'
                );
                """
            )
        with self.encrypted_connection(self.message) as connection:
            table_name = "Msg_" + __import__("hashlib").md5(b"fixture_contact").hexdigest()
            connection.execute("CREATE TABLE Name2Id(user_name TEXT PRIMARY KEY, is_session INTEGER)")
            connection.execute(
                "INSERT INTO Name2Id(rowid, user_name, is_session) VALUES(1, 'fixture_contact', 1)"
            )
            connection.execute(
                "INSERT INTO Name2Id(rowid, user_name, is_session) VALUES(2, 'fixture_owner', 1)"
            )
            connection.execute(
                f'''CREATE TABLE "{table_name}"(
                  local_id INTEGER PRIMARY KEY, server_id INTEGER, local_type INTEGER,
                  sort_seq INTEGER, real_sender_id INTEGER, create_time INTEGER,
                  status INTEGER, message_content TEXT, compress_content TEXT
                )'''
            )
            connection.execute(
                f'''INSERT INTO "{table_name}" VALUES(
                  1, 101, 1, 1, 1, 100, 0, '请明天发合作方案', ''
                )'''
            )
            connection.execute(
                f'''INSERT INTO "{table_name}" VALUES(
                  2, 102, 1, 2, 2, 200, 0, '好的，明天发方案', ''
                )'''
            )

    def _write_reader_files(self) -> None:
        databases = [self.session, self.contact, self.message]
        self.keys.write_text(
            json.dumps(
                {
                    "keys": {
                        path.name: {"key": self.key, "cipher_compatibility": 4}
                        for path in databases
                    }
                }
            ),
            encoding="utf-8",
        )
        self.keys.chmod(0o600)
        self.config.write_text(
            json.dumps(
                {
                    "session_db": str(self.session),
                    "contact_db": str(self.contact),
                    "message_dbs": [str(self.message)],
                    "keys_file": str(self.keys),
                    "self_username": "fixture_owner",
                }
            ),
            encoding="utf-8",
        )
        launcher = (
            "#!/bin/sh\nexec "
            + shlex.quote(sys.executable)
            + " "
            + shlex.quote(str(READER))
            + " --config "
            + shlex.quote(str(self.config))
            + ' "$@"\n'
        )
        self.reader.write_text(launcher, encoding="utf-8")
        self.reader.chmod(0o700)

    def _write_fake_wechat_app(self) -> None:
        plist = self.wechat_app / "Contents" / "Info.plist"
        plist.parent.mkdir(parents=True)
        with plist.open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleShortVersionString": "fixture",
                    "CFBundleVersion": "1",
                    "WeChatBundleVersion": "fixture.1",
                },
                handle,
            )

    def run_hub(self, *args: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["HOME"] = str(self.root / "home")
        result = subprocess.run(
            [sys.executable, str(HUB_ROOT / "wechat_intelligence_hub.py"), *args],
            cwd=HUB_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def test_encrypted_reader_to_hub_search_and_local_index(self) -> None:
        state = self.root / "compatibility"
        report = self.root / "compatibility.json"
        self.run_hub(
            "compat-check",
            "--wechat-cli",
            str(self.reader),
            "--wechat-app",
            str(self.wechat_app),
            "--state-dir",
            str(state),
            "--out",
            str(report),
            "--force",
        )
        compatibility = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(compatibility["result"], "ready")
        self.assertEqual(compatibility["checks"]["timeline"]["count"], 1)

        output = self.root / "search-output"
        intelligence_db = self.root / "intelligence.sqlite3"
        self.run_hub(
            "chat-search",
            "方案",
            "--wechat-cli",
            str(self.reader),
            "--db",
            str(intelligence_db),
            "--out",
            str(output),
        )

        messages = json.loads((output / "messages.json").read_text(encoding="utf-8"))
        self.assertEqual(len(messages), 2)
        self.assertTrue(all("方案" in row["content"] for row in messages))
        self.assertIn("方案", (output / "search_results.md").read_text(encoding="utf-8"))
        with sqlite3.connect(intelligence_db) as connection:
            indexed = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(indexed, 2)


if __name__ == "__main__":
    unittest.main()
