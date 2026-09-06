import json
from pathlib import Path
import tempfile
import unittest

import wechat_intelligence_hub as radar


class ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_profile = radar.ACTIVE_PROFILE
        self.original_path = radar.ACTIVE_PROFILE_PATH

    def tearDown(self) -> None:
        radar.ACTIVE_PROFILE = self.original_profile
        radar.ACTIVE_PROFILE_PATH = self.original_path

    def test_profile_override_keeps_unspecified_public_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "profile.json"
            path.write_text(
                json.dumps({"owner_aliases": ["Alice"], "labels": {"priority": ["合作方"]}}),
                encoding="utf-8",
            )

            profile, selected = radar.load_profile(str(path))

        self.assertEqual(selected, path)
        self.assertEqual(profile["owner_aliases"], ["Alice"])
        self.assertEqual(profile["labels"]["priority"], ["合作方"])
        self.assertEqual(profile["reply_style"]["history_days"], 30)
        self.assertEqual(profile["reply_style"]["minimum_chat_messages"], 5)
        self.assertEqual(profile["contact_daily"]["scope"], "hybrid")
        self.assertEqual(profile["labels"]["commercial"], [])
        self.assertIn("交付群", profile["project_chat_terms"])
        self.assertEqual(profile["group_recap_senders"], {})
        self.assertEqual(profile["group_recap_time_windows"], {})
        self.assertEqual(profile["context"]["setup_status"], "needs_context")
        self.assertIn("B端AI赋能", profile["intelligence_priorities"]["focus_areas"])

    def test_profile_controls_owner_and_project_group_detection(self) -> None:
        radar.ACTIVE_PROFILE = radar.merge_profile(
            radar.DEFAULT_PROFILE,
            {"owner_aliases": ["Alice"], "project_chat_terms": ["交付"]},
        )
        rows = [
            radar.Message(
                chat="Alice 8月合作",
                sender="品牌负责人",
                time="2026-08-20 10:00:00",
                content="Alice老师，初稿需要修改后再审核",
                source_file="test",
            )
        ]

        self.assertTrue(radar.is_owner_sender("Alice"))
        self.assertTrue(radar.is_project_collaboration_group("Alice 8月合作", rows))

    def test_profile_controls_group_recap_sender_and_time_window(self) -> None:
        radar.ACTIVE_PROFILE = radar.merge_profile(
            radar.DEFAULT_PROFILE,
            {
                "group_recap_senders": {"TATALAB": ["那时年少"]},
                "group_recap_time_windows": {"TATALAB": ["06:50-07:20"]},
            },
        )

        self.assertEqual(radar.configured_group_recap_senders("TATALAB👾一起早起"), ["那时年少"])
        self.assertEqual(radar.configured_group_recap_time_windows("TATALAB👾一起早起"), ["06:50-07:20"])
        self.assertTrue(radar.message_time_in_windows("2026-08-25 07:00:00", ["06:50-07:20"]))
        self.assertFalse(radar.message_time_in_windows("2026-08-25 07:42:00", ["06:50-07:20"]))

    def test_profile_init_uses_local_context_labels_and_custom_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            personal = root / "personal.md"
            plan = root / "plan.md"
            profile_path = root / "profile.json"
            report_path = root / "setup.md"
            personal.write_text("我在做跨境电商和法律科技产品。", encoding="utf-8")
            plan.write_text("本月重点是企业 AI 培训、客户合作和内容增长。", encoding="utf-8")
            parser = radar.build_parser()
            args = parser.parse_args(
                [
                    "profile-init",
                    "--out", str(profile_path),
                    "--report", str(report_path),
                    "--owner-alias", "Alice",
                    "--personal-doc", str(personal),
                    "--plan-doc", str(plan),
                    "--priority-label", "重点客户",
                    "--commercial-label", "重点客户",
                    "--custom-topic", "法律科技=律所,法律科技",
                ]
            )

            args.func(args)
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            report_text = report_path.read_text(encoding="utf-8")

        self.assertEqual(payload["context"]["setup_status"], "ready")
        self.assertEqual(payload["labels"]["priority"], ["重点客户"])
        self.assertIn("AI", payload["intelligence_priorities"]["focus_areas"])
        self.assertEqual(payload["intelligence_priorities"]["custom_topics"]["法律科技"], ["律所", "法律科技"])
        self.assertNotIn("建议先准备", report_text)

    def test_custom_profile_topics_change_group_selection(self) -> None:
        radar.ACTIVE_PROFILE = radar.merge_profile(
            radar.DEFAULT_PROFILE,
            {
                "intelligence_priorities": {
                    "focus_areas": ["法律科技"],
                    "priority_keywords": ["重点客户"],
                    "deprioritize_keywords": [],
                    "custom_topics": {"法律科技": ["律所", "法律科技"]},
                }
            },
        )
        row = radar.Message(
            chat="行业交流群",
            sender="项目方",
            time="2026-08-20 10:00:00",
            content="有一家律所正在找法律科技产品方案",
            source_file="test",
        )

        rows = radar.build_group_selection_rows([radar.summarize_group([row])], [row])

        self.assertTrue(rows[0]["法律科技"])
        self.assertEqual(rows[0]["建议关注级别"], "重点")

    def test_profile_force_update_preserves_existing_context_documents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            personal = root / "personal.md"
            plan = root / "plan.md"
            profile_path = root / "profile.json"
            report_path = root / "setup.md"
            personal.write_text("个人背景和长期目标。", encoding="utf-8")
            plan.write_text("当前正在推进企业 AI 培训。", encoding="utf-8")
            profile_path.write_text(
                json.dumps(
                    radar.merge_profile(
                        radar.DEFAULT_PROFILE,
                        {
                            "labels": {"priority": ["重点客户"]},
                            "context": {
                                "setup_status": "ready",
                                "personal_documents": [str(personal)],
                                "current_plan_documents": [str(plan)],
                            },
                        },
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            parser = radar.build_parser()
            args = parser.parse_args(
                [
                    "profile-init",
                    "--force",
                    "--out", str(profile_path),
                    "--report", str(report_path),
                    "--priority-keyword", "新产品",
                ]
            )

            args.func(args)
            payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["context"]["personal_documents"], [str(personal)])
        self.assertEqual(payload["context"]["current_plan_documents"], [str(plan)])
        self.assertEqual(payload["context"]["setup_status"], "ready")
        self.assertEqual(payload["intelligence_priorities"]["priority_keywords"], ["新产品"])


if __name__ == "__main__":
    unittest.main()
