import sqlite3
import unittest

import opportunity_store
import wechat_intelligence_hub as radar


def message(time: str, content: str, chat: str = "品牌方A") -> radar.Message:
    return radar.Message(
        chat=chat,
        sender=chat,
        time=time,
        content=content,
        source_file="test",
    )


def sourced_message(
    time: str,
    content: str,
    *,
    chat: str,
    source_file: str,
) -> radar.Message:
    row = message(time, content, chat)
    row.source_file = source_file
    return row


class OpportunityPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        radar.init_radar_db(self.conn)
        cursor = self.conn.execute(
            """
            insert into runs(run_type, since_time, until_time, created_at, groups_count, messages_count, output_dir)
            values ('test', '', '', '2026-07-30 10:00:00', 1, 1, 'test')
            """
        )
        self.run_id = int(cursor.lastrowid)

    def tearDown(self) -> None:
        self.conn.close()

    def sync(self, messages: list[radar.Message], created_at: str = "2026-07-30 10:00:00") -> tuple[int, int, int]:
        radar.insert_messages_to_db(self.conn, self.run_id, messages, created_at)
        candidates = radar.build_opportunity_candidates(messages)
        return opportunity_store.sync_opportunity_candidates(
            self.conn,
            self.run_id,
            candidates,
            created_at,
        )

    def test_repeat_scan_updates_one_open_opportunity(self) -> None:
        first = message("2026-07-30 09:00:00", "我们有一轮AI产品合作，预算3000元")
        second = message("2026-07-30 11:00:00", "brief发你了，今天确认排期")

        self.assertEqual(self.sync([first]), (1, 0, 0))
        self.assertEqual(self.sync([first, second], "2026-07-30 11:05:00"), (0, 1, 0))

        rows = opportunity_store.list_opportunities(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["chat"], "品牌方A")
        self.assertIn("3000元", rows[0]["amount"])
        self.assertGreaterEqual(rows[0]["evidence_count"], 2)

    def test_message_indexing_deduplicates_by_hash(self) -> None:
        row = message("2026-07-30 09:00:00", "我们有一轮AI产品合作，预算3000元")

        first = radar.insert_messages_to_db(self.conn, self.run_id, [row], "2026-07-30 10:00:00")
        second = radar.insert_messages_to_db(self.conn, self.run_id, [row], "2026-07-30 10:01:00")

        self.assertEqual(first[0], 1)
        self.assertEqual(second[0], 0)
        self.assertEqual(self.conn.execute("select count(*) from messages").fetchone()[0], 1)

    def test_manual_stage_is_not_overwritten_by_later_scan(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "请问报价和预算")])
        opportunity_store.update_opportunity(
            self.conn,
            1,
            stage="待创作",
            next_action="今晚完成初稿",
        )

        self.sync([message("2026-07-30 12:00:00", "方便再确认一下报价吗")], "2026-07-30 12:01:00")

        row = opportunity_store.list_opportunities(self.conn)[0]
        self.assertEqual(row["stage"], "待创作")
        self.assertEqual(row["next_action"], "今晚完成初稿")

    def test_new_signal_after_closed_opportunity_starts_new_cycle(self) -> None:
        self.sync([message("2026-07-01 09:00:00", "这一轮品牌合作预算2000元")])
        opportunity_store.update_opportunity(self.conn, 1, status="lost")

        self.sync([message("2026-07-30 09:00:00", "新一轮品牌合作预算3500元")], "2026-07-30 09:01:00")

        rows = opportunity_store.list_opportunities(self.conn, include_closed=True)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["status"] for row in rows}, {"lost", "new"})

    def test_ignore_feedback_suppresses_current_and_future_detection(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "群里有商单合作")], "2026-07-30 09:01:00")
        opportunity_store.add_feedback(
            self.conn,
            "chat",
            "品牌方A",
            "ignore",
            "测试消息，不是真实商单",
        )

        open_rows = opportunity_store.list_opportunities(self.conn)
        self.assertEqual(open_rows, [])
        result = self.sync([message("2026-07-30 10:00:00", "又一条商单合作")], "2026-07-30 10:01:00")
        self.assertEqual(result, (0, 0, 1))

    def test_low_priority_feedback_is_persistent(self) -> None:
        opportunity_store.add_feedback(
            self.conn,
            "chat",
            "品牌方A",
            "low_priority",
            "和商业机会无关",
        )
        self.sync([message("2026-07-30 09:00:00", "品牌合作预算5000元")])

        row = opportunity_store.list_opportunities(self.conn)[0]
        self.assertEqual(row["priority"], 1)
        self.assertEqual(row["priority_locked"], 0)

    def test_group_anchors_do_not_merge_unrelated_campaigns(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "品牌A招募AI博主，预算2000元",
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
            sourced_message(
                "2026-07-30 10:00:00",
                "企业AI培训项目找讲师，3小时工作坊",
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 2)
        self.assertEqual({row["stage"] for row in candidates}, {"新线索"})
        self.assertEqual(
            {row["opportunity_type"] for row in candidates},
            {"商单/推广", "培训/咨询/项目合作"},
        )

    def test_same_display_name_with_different_wxids_stays_separate(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "合作预算2000元",
                chat="Emerson",
                source_file="wechat-cli:timeline:fake-contact-a",
            ),
            sourced_message(
                "2026-07-30 10:00:00",
                "合作预算3000元",
                chat="Emerson",
                source_file="wechat-cli:timeline:fake-contact-b",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 2)
        self.assertEqual(len({row["opportunity_key"] for row in candidates}), 2)

    def test_search_result_joins_unique_private_timeline_identity(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "有一轮品牌合作",
                chat="Emerson",
                source_file="wechat-cli:timeline:fake-contact-c",
            ),
            sourced_message(
                "2026-07-30 09:05:00",
                "预算3000元，今天确认",
                chat="Emerson",
                source_file="wechat-cli:search:合作",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0]["message_hashes"]), 2)

    def test_search_result_joins_unique_group_timeline_identity(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "品牌A招募AI博主，预算2000元",
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
            sourced_message(
                "2026-07-30 09:00:00",
                "品牌A招募AI博主，预算2000元",
                chat="资源群",
                source_file="wechat-cli:search:商单",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 1)

    def test_group_system_payment_noise_is_not_an_opportunity(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "收到转账5.00元。如需收钱，请点此升级至最新版本",
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
            sourced_message(
                "2026-07-30 09:01:00",
                '<img src="SystemMessages_HongbaoIcon.png"/> 小王领取了你的红包',
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        self.assertEqual(radar.build_opportunity_candidates(messages), [])

    def test_project_collaboration_group_tracks_post_publish_data_action(self) -> None:
        source = "wechat-cli:timeline:proj-a@chatroom"
        messages = [
            sourced_message(
                "2026-08-17 09:44:44",
                "创作者老师，帖子浏览量只有6k多，麻烦增加曝光并找KOL朋友转发",
                chat="项目A 8月合作-终稿",
                source_file=source,
            ),
            sourced_message(
                "2026-08-17 09:50:00",
                "好的老师，我会多quote几次，同时让其他博主帮忙加热",
                chat="项目A 8月合作-终稿",
                source_file=source,
            ),
            sourced_message(
                "2026-08-17 10:07:00",
                "嗯嗯对的",
                chat="项目A 8月合作-终稿",
                source_file=source,
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]["opportunity_key"].startswith("private:"))
        self.assertEqual(candidates[0]["stage"], "已发布待数据跟进")
        self.assertIn("Quote/KOL 转发", candidates[0]["next_action"])

    def test_project_collaboration_migrates_legacy_group_opportunity(self) -> None:
        self.conn.execute(
            """
            insert into opportunities(
                opportunity_key, chat, title, opportunity_type, stage, status, priority,
                last_signal_time, next_action, created_at, updated_at
            ) values (
                'group:legacy:project-a', '项目A 8月合作-终稿', '旧项目A线索',
                '商单/推广', '新线索', 'new', 5, '2026-08-17 09:44:44',
                '回原群核实', '2026-08-17 09:44:44', '2026-08-17 09:44:44'
            )
            """
        )
        source = "wechat-cli:timeline:proj-a@chatroom"
        messages = [
            sourced_message(
                "2026-08-17 09:44:44",
                "创作者老师，帖子浏览量只有6k多，麻烦增加曝光并找KOL朋友转发",
                chat="项目A 8月合作-终稿",
                source_file=source,
            ),
            sourced_message(
                "2026-08-17 09:50:00",
                "好的老师，我会多quote几次，同时让其他博主帮忙加热",
                chat="项目A 8月合作-终稿",
                source_file=source,
            ),
        ]

        self.sync(messages, "2026-08-17 10:00:00")

        rows = opportunity_store.list_opportunities(self.conn)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["opportunity_key"].startswith("private:"))
        self.assertEqual(rows[0]["stage"], "已发布待数据跟进")

    def test_single_group_generic_boost_stays_in_intelligence_layer(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "求加热，三连2元 https://x.com/example/status/123",
                chat="资源群A",
                source_file="wechat-cli:timeline:111@chatroom",
            ),
        ]

        self.assertEqual(radar.build_opportunity_candidates(messages), [])

    def test_cross_group_paid_link_becomes_one_opportunity(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "求加热，三连2元 https://x.com/example/status/123?s=20",
                chat="资源群A",
                source_file="wechat-cli:timeline:111@chatroom",
            ),
            sourced_message(
                "2026-07-30 09:05:00",
                "四连5元 https://twitter.com/example/status/123",
                chat="资源群B",
                source_file="wechat-cli:timeline:222@chatroom",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 1)
        self.assertIn("资源群A", candidates[0]["chat"])
        self.assertIn("资源群B", candidates[0]["chat"])

    def test_historical_group_identity_prevents_private_stage_inference(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "商单已经审核通过，准备发布",
                chat="X商单博主群",
                source_file="wechat-cli:search:品牌方",
            ),
        ]

        candidates = radar.build_opportunity_candidates(
            messages,
            known_group_chats_seed={"X商单博主群"},
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["stage"], "新线索")

    def test_group_training_narrative_is_not_actionable(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "这是企业培训的公司给我配的编导",
                chat="闲聊群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        self.assertEqual(radar.build_opportunity_candidates(messages), [])

    def test_natural_group_training_request_is_actionable(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "最近有个企业AI培训项目，需要找一位讲师",
                chat="资源群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        candidates = radar.build_opportunity_candidates(messages)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["opportunity_type"], "培训/咨询/项目合作")

    def test_group_market_price_discussion_is_not_actionable(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "这个账号后台报价40w一条广告",
                chat="闲聊群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        self.assertEqual(radar.build_opportunity_candidates(messages), [])

    def test_group_daily_recap_does_not_create_opportunities(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "AI群聊日报：昨日品牌方投放和商单机会整体判断",
                chat="AI群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        self.assertEqual(radar.build_opportunity_candidates(messages), [])

    def test_group_reward_amount_is_not_presented_as_deal_budget(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "Topview商单求加热，三连2元 https://x.com/example/status/123",
                chat="商单群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        candidate = radar.build_opportunity_candidates(messages)[0]

        self.assertEqual(candidate["amount"], "")

    def test_group_explicit_budget_is_retained(self) -> None:
        messages = [
            sourced_message(
                "2026-07-30 09:00:00",
                "品牌方招募AI博主，预算3000元",
                chat="商单群",
                source_file="wechat-cli:timeline:123@chatroom",
            ),
        ]

        candidate = radar.build_opportunity_candidates(messages)[0]

        self.assertIn("3000元", candidate["amount"])

    def test_inbox_only_returns_unreviewed_high_priority_items(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "品牌合作预算5000元", chat="品牌方A")])
        self.sync([message("2026-07-30 09:10:00", "请确认合作报价和预算", chat="品牌方B")])
        opportunity_store.update_opportunity(self.conn, 1, status="active")

        rows = opportunity_store.list_opportunity_inbox(
            self.conn,
            min_priority=4,
            limit=20,
        )

        self.assertEqual([row["chat"] for row in rows], ["品牌方B"])

    def test_today_excludes_future_waiting_items(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "品牌合作预算5000元", chat="品牌方A")])
        self.sync([message("2026-07-30 09:10:00", "品牌合作预算6000元", chat="品牌方B")])
        opportunity_store.triage_opportunity(
            self.conn,
            1,
            "wait",
            next_follow_up="2026-08-05",
        )
        opportunity_store.triage_opportunity(self.conn, 2, "pursue")

        rows = opportunity_store.list_today_opportunities(
            self.conn,
            today="2026-08-02",
            min_priority=3,
            limit=10,
        )

        self.assertEqual([row["chat"] for row in rows], ["品牌方B"])

    def test_wait_triage_requires_follow_up_date(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "品牌合作预算5000元")])

        with self.assertRaisesRegex(ValueError, "必须提供"):
            opportunity_store.triage_opportunity(self.conn, 1, "wait")

        row = opportunity_store.triage_opportunity(
            self.conn,
            1,
            "wait",
            next_follow_up="2026-08-03",
        )
        self.assertEqual(row["status"], "waiting")
        self.assertEqual(row["next_follow_up"], "2026-08-03")

    def test_unreviewed_candidate_expires_without_deleting_evidence(self) -> None:
        rows = [
            sourced_message(
                "2026-07-01 09:00:00",
                "https://x.com/brand/status/99 三连3元，截图结算",
                chat="资源群A",
                source_file="wechat-cli:timeline:a@chatroom",
            ),
            sourced_message(
                "2026-07-01 09:05:00",
                "https://x.com/brand/status/99 限10个加热名额",
                chat="资源群B",
                source_file="wechat-cli:timeline:b@chatroom",
            ),
        ]
        self.sync(rows, "2026-07-01 10:00:00")

        expired = opportunity_store.expire_stale_candidates(
            self.conn,
            now="2026-07-20 10:00:00",
            stale_days=14,
            apply=True,
        )

        self.assertEqual(len(expired), 1)
        record = opportunity_store.list_opportunities(
            self.conn,
            include_closed=True,
        )[0]
        self.assertEqual(record["status"], "stale")
        self.assertGreaterEqual(record["evidence_count"], 2)

    def test_triage_promotes_candidate_and_persists_exact_feedback(self) -> None:
        self.sync([message("2026-07-30 09:00:00", "品牌合作预算5000元")])

        row = opportunity_store.triage_opportunity(self.conn, 1, "pursue")
        feedback = opportunity_store.list_feedback(self.conn)

        self.assertEqual(row["record_type"], "opportunity")
        self.assertEqual(row["confidence"], "confirmed")
        self.assertEqual(feedback[0]["target_type"], "opportunity")
        self.assertEqual(feedback[0]["target_key"], row["opportunity_key"])


if __name__ == "__main__":
    unittest.main()
