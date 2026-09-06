#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


MESSAGES = [
    {
        "chat": "NovaAI",
        "sender": "NovaAI",
        "time": "2026-06-30 10:12",
        "content": "你好，想咨询一下 X thread 的合作报价，7 月初有一个 campaign",
    },
    {
        "chat": "NovaAI",
        "sender": "NovaAI",
        "time": "2026-06-30 11:25",
        "content": "预算 650 USD，想这周五发布，可以先给一个 quote repost 和 thread 两个档位吗？",
    },
    {
        "chat": "Web3 Alpha 群",
        "sender": "群友A",
        "time": "2026-06-30 19:45",
        "content": "有项目方找 KOL 做投放，预算 3000-5000 RMB，AI/Web3 方向优先",
    },
]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("missing command")
    command = sys.argv[1]
    if command == "status":
        print(json.dumps({"ok": True, "decrypted_dir": "sample", "message_count": len(MESSAGES)}, ensure_ascii=False))
        return
    if command == "new-messages":
        print(json.dumps({"messages": MESSAGES}, ensure_ascii=False))
        return
    if command == "search":
        keyword = sys.argv[2] if len(sys.argv) > 2 else ""
        matched = [row for row in MESSAGES if keyword.lower() in row["content"].lower()]
        print(json.dumps({"messages": matched}, ensure_ascii=False))
        return
    raise SystemExit(f"unknown command: {command}")


if __name__ == "__main__":
    main()

