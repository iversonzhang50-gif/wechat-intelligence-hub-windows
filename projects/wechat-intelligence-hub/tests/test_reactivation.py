import sqlite3
import unittest

import wechat_intelligence_hub as radar


def message(time: str, sender: str, content: str, chat: str = "品牌方") -> radar.Message:
    return radar.Message(
        chat=chat,
        sender=sender,
        time=time,
        content=content,
        source_file="test",
    )


class ReactivationClassificationTests(unittest.TestCase):
    def classify(self, messages: list[radar.Message], inactive_days: int = 30) -> str:
        signals = radar.extract_signals(messages)
        status, _, _ = radar.classify_reactivation(
            messages,
            signals,
            inactive_days,
            threshold=21,
            self_names=["创作者A"],
        )
        return status

    def test_configured_owner_is_recognized_as_self(self) -> None:
        messages = [message("2026-07-09 10:00:00", "创作者A", "老师，最近还有合作计划吗？")]
        self.assertTrue(radar.self_sent_latest(messages, ["创作者A"]))

    def test_newer_success_overrides_old_negative(self) -> None:
        messages = [
            message("2026-06-20 10:00:00", "品牌方", "已经打款，后面继续合作"),
            message("2026-06-01 10:00:00", "品牌方", "这次预算不够，暂不合作"),
        ]
        self.assertEqual(self.classify(messages), "复购保温")

    def test_recent_negative_is_temporarily_paused(self) -> None:
        messages = [message("2026-07-09 10:00:00", "品牌方", "这批预算不够，暂不考虑了")]
        self.assertEqual(self.classify(messages, inactive_days=1), "暂缓")

    def test_newer_next_batch_message_becomes_follow_up(self) -> None:
        messages = [
            message("2026-07-09 10:00:00", "品牌方", "这批没有了，要下一批了，下次我跟你聊"),
            message("2026-07-07 10:00:00", "品牌方", "2000以内能接吗，预算不够"),
        ]
        self.assertEqual(self.classify(messages, inactive_days=1), "待下一批跟进")

    def test_own_expectation_does_not_create_next_batch_commitment(self) -> None:
        messages = [
            message("2026-07-09 10:00:00", "创作者A", "好滴，期待下次合作"),
            message("2026-07-09 09:00:00", "品牌方", "好的"),
        ]
        self.assertEqual(self.classify(messages, inactive_days=1), "近期已联系")

    def test_next_batch_follow_up_is_scheduled_after_seven_days(self) -> None:
        deferred = message("2026-07-09 10:00:00", "品牌方", "要下一批了")
        self.assertEqual(radar.defer_wait_days(deferred), 7)
        self.assertEqual(radar.follow_up_date(deferred, 7), "2026-07-16")

    def test_waiting_for_payment_is_not_next_batch_follow_up(self) -> None:
        messages = [
            message("2026-06-22 20:48:21", "品牌方", "我们还在走内部流程，需要等等"),
            message("2026-06-22 20:47:45", "创作者A", "请问打款流程也是和上次一样吗"),
            message("2026-06-17 00:48:17", "创作者A", "发布链接"),
        ]

        self.assertNotEqual(self.classify(messages, inactive_days=26), "待下一批跟进")

    def test_asking_about_commission_is_not_a_rejection_or_success(self) -> None:
        messages = [
            message("2026-07-06 16:41:57", "品牌方", "打款方式是直接打款"),
            message("2026-07-06 16:39:13", "创作者A", "明白，那现在就是纯佣金合作吧？"),
        ]
        self.assertEqual(self.classify(messages, inactive_days=1), "近期已联系")

    def test_partner_commission_only_rule_is_low_priority(self) -> None:
        messages = [
            message("2026-07-06 16:41:00", "品牌方", "结算周期是15天已结算，去除已经退款的"),
            message("2026-07-06 16:40:00", "品牌方", "投放效果不如预期，我们没有付费投放了，现在是纯佣投放，没有保底"),
        ]
        self.assertEqual(self.classify(messages, inactive_days=1), "纯佣低优先级")

    def test_published_article_link_counts_as_past_collaboration(self) -> None:
        messages = [message("2026-05-01 10:00:00", "创作者A", "文章链接")]
        self.assertEqual(self.classify(messages, inactive_days=30), "复购保温")

    def test_owner_handoff_is_not_a_rejection(self) -> None:
        messages = [
            message("2026-05-26 22:31:20", "创作者A", "好滴"),
            message("2026-05-26 18:19:58", "品牌方", "我暂时不负责这个项目，会拉创始人进来交接合作"),
        ]
        self.assertEqual(self.classify(messages, inactive_days=30), "待交接跟进")

    def test_third_party_qualification_does_not_count_as_rejection(self) -> None:
        messages = [message("2026-06-16 00:49:52", "创作者A", "我还有另一个朋友1000多粉，他应该暂时不行吧")]
        self.assertNotIn(self.classify(messages, inactive_days=30), {"失败可修复", "暂缓"})

    def test_hypothetical_price_adjustment_is_not_a_rejection(self) -> None:
        messages = [message("2026-05-21 00:24:49", "创作者A", "老师你好，请问进展如何？如果价格不合适可以再调整")]
        self.assertNotIn(self.classify(messages, inactive_days=30), {"失败可修复", "暂缓", "我方主动放弃"})

    def test_self_declined_risky_product_is_marked_separately(self) -> None:
        messages = [message("2026-04-20 19:45:29", "创作者A", "产品存在历史负面反馈，所以这次合作我这边就先不推进了")]
        self.assertEqual(self.classify(messages, inactive_days=30), "我方主动放弃")


class ContactMessageLookupTests(unittest.TestCase):
    def test_short_contact_name_does_not_pull_group_messages(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            create table messages (
                chat text,
                sender text,
                time text,
                content text,
                source_file text
            )
            """
        )
        conn.executemany(
            "insert into messages values (?, ?, ?, ?, ?)",
            [
                ("Ji", "Ji", "2026-07-01 10:00:00", "直接聊天", "test"),
                ("某个共同群", "Ji", "2026-07-02 10:00:00", "群内发言", "test"),
                ("吃喝玩乐歪脖山", "Jing", "2026-07-03 10:00:00", "无关内容", "test"),
            ],
        )

        messages = radar.fetch_messages_for_contact(conn, ["Ji"], "2026-01-01", 20)

        self.assertEqual([item.content for item in messages], ["直接聊天"])
        conn.close()


class HandoffRelationTests(unittest.TestCase):
    def test_handoff_group_moves_follow_up_to_new_owner(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            create table messages (
                chat text,
                sender text,
                time text,
                content text,
                source_file text
            )
            """
        )
        conn.executemany(
            "insert into messages values (?, ?, ?, ?, ?)",
            [
                ("前负责人（项目A）", "前负责人（项目A）", "2026-05-26 18:19:58", "我暂时不负责项目A，会拉新负责人交接合作", "test"),
                ("group1@chatroom", "创作者A", "2026-05-26 22:32:29", "商单报价：长文章2800元", "test"),
                ("group1@chatroom", "新负责人（项目A）", "2026-05-27 00:00:49", "收，后面宣传的时候联络", "test"),
            ],
        )
        targets = [
            {"display_name": "前负责人（项目A）", "label": "商单推广", "names": ["前负责人（项目A）"]},
            {"display_name": "新负责人（项目A）", "label": "商单推广", "names": ["新负责人（项目A）"]},
        ]
        relations = [
            {
                "项目": "项目A",
                "原负责人": "前负责人（项目A）",
                "新负责人": "新负责人（项目A）",
                "共同群ID": "group1@chatroom",
                "共同群名": "group1@chatroom",
                "交接确认时间": "2026-05-27",
                "状态": "有效",
            }
        ]

        rows = radar.build_reactivation_rows(targets, conn, "2026-04-01", 100, 21, ["创作者A"], relations)
        by_name = {row["联系人"]: row for row in rows}

        self.assertEqual(by_name["前负责人（项目A）"]["复联类型"], "已交接")
        self.assertEqual(by_name["新负责人（项目A）"]["复联类型"], "待下一批跟进")
        self.assertIn("前负责人（项目A） → 新负责人（项目A）", by_name["新负责人（项目A）"]["交接关系"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
