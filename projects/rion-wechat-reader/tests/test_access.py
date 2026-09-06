import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rion_wechat_access as access


class AccessOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.environment = mock.patch.dict(os.environ, {"HOME": str(self.root)})
        self.environment.start()
        self.provider = self.root / "reviewed-helper"
        self.provider.write_bytes(b"test-only-not-a-real-provider")
        self.provider.chmod(0o700)
        self.digest = hashlib.sha256(self.provider.read_bytes()).hexdigest()
        self.db = self.root / "db_storage"
        self.db.mkdir()

    def tearDown(self):
        self.environment.stop()
        self.temp.cleanup()

    def args(self):
        from argparse import Namespace
        return Namespace(provider=self.provider, sha256=self.digest, database_root=self.db,
                         confirm_reviewed_provider=True, confirm_side_effects=True,
                         config=self.root / "reader" / "config.json", timeout=30, max_files=500)

    def test_plan_does_not_execute_or_expose_paths(self):
        with mock.patch.object(access.subprocess, "run", side_effect=AssertionError("must not execute")):
            result = access.inspect(self.provider, self.digest, self.db)
        self.assertEqual(result["state"], "review_required")
        self.assertTrue(result["digest_matches"])
        self.assertFalse(result["provider_executed"])
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_provider_symlink_and_broad_permissions_rejected(self):
        link = self.root / "link"
        link.symlink_to(self.provider)
        with self.assertRaisesRegex(access.AccessError, "symlink"):
            access.provider_digest(link)
        self.provider.chmod(0o777)
        with self.assertRaisesRegex(access.AccessError, "writable"):
            access.provider_digest(self.provider)

    def test_multiple_accounts_rejected(self):
        for account in ("one", "two"):
            (self.db / account / "db_storage").mkdir(parents=True)
        with self.assertRaisesRegex(access.AccessError, "account_selection"):
            access.check_root(self.db)

    def test_no_confirmation_never_executes(self):
        args = self.args()
        args.confirm_side_effects = False
        with mock.patch.object(access.platform, "system", return_value="Darwin"), \
             mock.patch.object(access.os, "geteuid", return_value=501), \
             mock.patch.object(access.subprocess, "run", side_effect=AssertionError("must not execute")):
            with self.assertRaisesRegex(access.AccessError, "explicit_confirmation"):
                access.run(args)

    def test_changed_provider_never_executes(self):
        args = self.args()
        self.provider.write_bytes(b"changed-provider")
        with mock.patch.object(access.platform, "system", return_value="Darwin"), \
             mock.patch.object(access.os, "geteuid", return_value=501):
            with self.assertRaisesRegex(access.AccessError, "digest_mismatch"):
                access.run(args)

    def test_non_mac_acquisition_rejected(self):
        with mock.patch.object(access.platform, "system", return_value="Windows"):
            with self.assertRaisesRegex(access.AccessError, "platform_not_supported"):
                access.run(self.args())

    def test_existing_config_is_never_overwritten(self):
        args = self.args()
        args.config.parent.mkdir(mode=0o700)
        args.config.write_text("existing", encoding="utf-8")
        with self.assertRaisesRegex(access.AccessError, "not_overwritten"):
            access.connect(self.provider, self.db, args.config)
        self.assertEqual(args.config.read_text(), "existing")

    def test_provider_output_is_suppressed(self):
        state = access.bounded_provider([sys.executable, "-c", "print('PRIVATE MATERIAL'); raise SystemExit(3)"], {}, 5)
        self.assertEqual(state, "provider_failed")

    @unittest.skipUnless(os.name == "posix", "process groups require POSIX")
    def test_provider_timeout_is_bounded(self):
        started = time.monotonic()
        state = access.bounded_provider([sys.executable, "-c", "import time; time.sleep(30)"], {}, 1)
        self.assertEqual(state, "provider_timeout_cleanup_required")
        self.assertLess(time.monotonic() - started, 6)

    def test_connect_failure_does_not_leave_keys_or_config(self):
        config = self.root / "private" / "config.json"
        with mock.patch.object(access.reader, "import_access_bundle", side_effect=access.reader.ReaderError("private-key-error")):
            with self.assertRaises(access.reader.ReaderError):
                access.connect(self.provider, self.db, config)
        self.assertFalse(config.exists())
        self.assertEqual(list(config.parent.iterdir()), [])

    def test_key_environment_cannot_override_staged_verification(self):
        with mock.patch.dict(os.environ, {"RION_WECHAT_READER_KEYS": "/unrelated/material"}):
            with self.assertRaisesRegex(access.AccessError, "environment_override"):
                access.connect(self.provider, self.db, self.root / "new/config.json")

    @unittest.skipUnless(os.name == "posix", "POSIX worker")
    def test_worker_does_not_inherit_password_or_original_resign_flags(self):
        import pwd
        from types import SimpleNamespace
        run_dir = self.root / ".config/rion-wechat-reader/access-runs/run-test"
        run_dir.mkdir(mode=0o700, parents=True)
        args = self.args()
        args.run_dir = run_dir
        args.uid = os.getuid()
        with mock.patch.object(access.os, "geteuid", return_value=0), \
             mock.patch.object(pwd, "getpwuid", return_value=SimpleNamespace(pw_dir=str(self.root), pw_name="testuser", pw_gid=os.getgid())), \
             mock.patch.object(access.subprocess, "run", return_value=SimpleNamespace(stdout="")), \
             mock.patch.object(access.os, "chown"), \
             mock.patch.object(access, "bounded_provider", return_value="provider_finished") as invoke, \
             mock.patch.dict(os.environ, {"WXKEY_BOOTSTRAP_ORIGINAL_WECHAT": "1", "SECRET_PASSWORD": "must-not-pass"}):
            self.assertEqual(access.worker(args), 0)
        env = invoke.call_args.args[1]
        self.assertEqual(env["WXKEY_NO_ELEVATE"], "1")
        self.assertNotIn("WXKEY_BOOTSTRAP_ORIGINAL_WECHAT", env)
        self.assertNotIn("SECRET_PASSWORD", env)
        self.assertEqual(json.loads((run_dir / "worker-result.json").read_text()), {"state": "provider_finished"})

    def test_encrypted_connect_publishes_only_verified_generation(self):
        import test_reader as fixtures
        if fixtures.SQLCIPHER is None:
            self.skipTest("SQLCipher unavailable")
        fixture = fixtures.ReaderContractTest()
        fixture.setUp()
        try:
            key = "74" * 32
            for source in (fixture.session, fixture.contact, fixture.message):
                fixture.encrypt_fixture(source, self.db / source.name, key)
            source = self.root / "authorized.json"
            source.write_text(json.dumps({p.name: key for p in self.db.glob("*.db")}))
            source.chmod(0o600)
            before = source.read_bytes()
            config = self.root / "reader/config.json"
            result = access.connect(source, self.db, config)
            self.assertEqual(result["state"], "ready")
            self.assertEqual(result["verified_database_count"], 3)
            self.assertEqual(source.read_bytes(), before)
            self.assertNotIn(key, json.dumps(result))
            db = access.reader.DatabaseSet(config)
            self.assertTrue(access.reader.status(db)["status"]["live_database_read_ok"])
            self.assertEqual(db.keys_path.stat().st_mode & 0o777, 0o600)
        finally:
            fixture.tearDown()

    def test_partial_connect_does_not_publish(self):
        config = self.root / "private" / "config.json"
        with mock.patch.object(access.reader, "import_access_bundle", return_value={"verification": {"matched_database_count": 1}}), \
             mock.patch.object(access.reader, "access_plan", return_value={"state": "partial", "counts": {"unresolved": 1}}):
            result = access.connect(self.provider, self.db, config)
        self.assertEqual(result["state"], "partial")
        self.assertFalse(config.exists())

    def test_run_uses_native_authorization_and_preserves_failure_lock(self):
        args = self.args()
        with mock.patch.object(access.platform, "system", return_value="Darwin"), \
             mock.patch.object(access.os, "geteuid", return_value=501), \
             mock.patch.object(access.Path, "home", return_value=self.root), \
             mock.patch.object(access.reader, "sqlcipher_driver", return_value=(object(), "test")), \
             mock.patch.object(access.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as auth:
            with self.assertRaisesRegex(access.AccessError, "authorization_or_worker_failed"):
                access.run(args)
        argv = auth.call_args.args[0]
        self.assertEqual(argv[0], "/usr/bin/osascript")
        self.assertIn("with administrator privileges", argv[2])
        self.assertNotIn("sudo -S", argv[2])
        self.assertTrue((self.root / ".config/rion-wechat-reader/access-runs/recovery-required.lock").exists())

    def test_cli_error_does_not_include_source_contents(self):
        self.provider.write_text("sensitive-invalid-json", encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "rion_wechat_access.py"), "connect",
                                 "--source", str(self.provider), "--database-root", str(self.db),
                                 "--config", str(self.root / "private/config.json")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("sensitive-invalid-json", result.stdout + result.stderr)
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    def workflow_args(self):
        args = self.args()
        args.source = None
        args.provider = None
        args.apply = False
        args.confirm_reviewed_provider = False
        args.confirm_side_effects = False
        return args

    def plan(self, state):
        return {"state": state, "live_database_read_ok": state == "ready", "scope": "test",
                "counts": {}, "performed": {"key_acquisition": False, "provider_execution": False,
                "configuration_write": False}, "next_actions": ["test"]}

    def test_onboard_ready_reuses_without_running_provider(self):
        with mock.patch.object(access.reader, "access_plan", return_value=self.plan("ready")), \
             mock.patch.object(access, "run", side_effect=AssertionError("must not execute")):
            result = access.onboard(self.workflow_args())
        self.assertTrue(result["reused_existing_configuration"])
        self.assertFalse(result["performed"]["key_acquisition"])

    def test_onboard_partial_or_missing_dependency_never_acquires(self):
        for state in ("partial", "dependency_required", "account_selection_required", "verification_failed"):
            with self.subTest(state=state), \
                 mock.patch.object(access.reader, "access_plan", return_value=self.plan(state)), \
                 mock.patch.object(access, "run", side_effect=AssertionError("must not execute")):
                result = access.onboard(self.workflow_args())
                self.assertEqual(result["state"], state)

    def test_onboard_does_not_replace_existing_configuration(self):
        args = self.workflow_args()
        args.config.parent.mkdir(mode=0o700)
        args.config.write_text("unchanged")
        args.apply = True
        with mock.patch.object(access.reader, "access_plan", return_value=self.plan("needs_access")):
            result = access.onboard(args)
        self.assertEqual(result["state"], "existing_configuration_requires_review")
        self.assertEqual(args.config.read_text(), "unchanged")

    def test_onboard_provider_and_consent_gates(self):
        args = self.workflow_args()
        with mock.patch.object(access.reader, "access_plan", return_value=self.plan("needs_access")), \
             mock.patch.object(access.platform, "system", return_value="Darwin"), \
             mock.patch.object(access.reader, "sqlcipher_driver", return_value=(object(), "test")), \
             mock.patch.object(access, "run", return_value={"state": "ready", "configured": True, "live_database_read_ok": True}) as acquire:
            self.assertEqual(access.onboard(args)["state"], "provider_required")
            args.provider = self.provider
            args.sha256 = ""
            self.assertEqual(access.onboard(args)["state"], "provider_review_required")
            args.sha256 = self.digest
            args.apply = True
            self.assertEqual(access.onboard(args)["state"], "authorization_required")
            args.confirm_reviewed_provider = True
            self.assertEqual(access.onboard(args)["state"], "authorization_required")
            acquire.assert_not_called()
            args.confirm_side_effects = True
            result = access.onboard(args)
        acquire.assert_called_once()
        self.assertTrue(result["performed"]["provider_execution"])

    def test_onboard_bad_explicit_material_does_not_fall_back_to_acquisition(self):
        args = self.workflow_args()
        args.source = self.root / "empty.json"
        args.source.write_text("{}")
        args.source.chmod(0o600)
        with mock.patch.object(access.reader, "access_plan", return_value=self.plan("needs_access")), \
             mock.patch.object(access, "run", side_effect=AssertionError("must not execute")):
            result = access.onboard(args)
        self.assertEqual(result["state"], "access_material_requires_review")

    def test_onboard_plaintext_requires_apply_then_publishes_verified_config(self):
        import test_reader as fixtures
        fixture = fixtures.ReaderContractTest()
        fixture.setUp()
        try:
            args = self.workflow_args()
            args.database_root = fixture.data_root.resolve()
            preview = access.onboard(args)
            self.assertEqual(preview["state"], "ready_to_configure")
            self.assertFalse(args.config.exists())
            args.apply = True
            result = access.onboard(args)
            self.assertEqual(result["state"], "ready")
            self.assertTrue(result["live_database_read_ok"])
            self.assertFalse(result["performed"]["provider_execution"])
            args.database_root = None
            again = access.onboard(args)
            self.assertTrue(again["reused_existing_configuration"])
        finally:
            fixture.tearDown()

    def test_onboard_fresh_home_acquisition_then_real_encrypted_connect(self):
        import test_reader as fixtures
        if fixtures.SQLCIPHER is None:
            self.skipTest("SQLCipher unavailable")
        fixture = fixtures.ReaderContractTest()
        fixture.setUp()
        old_umask = os.umask(0o022)
        try:
            key = "35" * 32
            for source in (fixture.session, fixture.contact, fixture.message):
                fixture.encrypt_fixture(source, self.db / source.name, key)
            args = self.workflow_args()
            args.config = self.root / ".config/rion-wechat-reader/config.json"
            args.provider = self.provider
            args.apply = args.confirm_reviewed_provider = args.confirm_side_effects = True

            def authorization(*unused_args, **unused_kwargs):
                material = self.root / ".config/wxcli/config.json"
                material.parent.mkdir(mode=0o700, parents=True)
                material.write_text(json.dumps({p.name: key for p in self.db.glob("*.db")}))
                material.chmod(0o600)
                run_dir = next((args.config.parent / "access-runs").glob("run-*"))
                (run_dir / "worker-result.json").write_text('{"state":"provider_finished"}')
                return subprocess.CompletedProcess([], 0)

            with mock.patch.object(access.Path, "home", return_value=self.root), \
                 mock.patch.object(access.platform, "system", return_value="Darwin"), \
                 mock.patch.object(access.os, "geteuid", return_value=501), \
                 mock.patch.object(access.subprocess, "run", side_effect=authorization):
                result = access.onboard(args)
            self.assertEqual(result["state"], "ready")
            self.assertTrue(result["live_database_read_ok"])
            self.assertEqual(args.config.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(args.config.stat().st_mode & 0o777, 0o600)
            self.assertFalse((args.config.parent / "access-runs/recovery-required.lock").exists())
            self.assertNotIn(key, json.dumps(result))
            self.assertTrue(access.reader.status(access.reader.DatabaseSet(args.config))["status"]["live_database_read_ok"])
        finally:
            os.umask(old_umask)
            fixture.tearDown()

    def test_run_rejects_public_config_directory_before_authorization(self):
        args = self.args()
        args.config.parent.mkdir(mode=0o755)
        args.config.parent.chmod(0o755)
        with mock.patch.object(access.Path, "home", return_value=self.root), \
             mock.patch.object(access.platform, "system", return_value="Darwin"), \
             mock.patch.object(access.os, "geteuid", return_value=501), \
             mock.patch.object(access.reader, "sqlcipher_driver", return_value=(object(), "test")), \
             mock.patch.object(access.subprocess, "run", side_effect=AssertionError("must not authorize")):
            with self.assertRaisesRegex(access.AccessError, "config_directory_not_private"):
                access.run(args)


if __name__ == "__main__":
    unittest.main()
