# Personalization Onboarding

Use this flow on first installation, when `profile-status` returns `needs_context`, or when the user's priorities have materially changed.

## Inputs

Prefer two short local sources:

1. Personal context: role, business or job, strengths, resources, account direction, constraints and long-term goals.
2. Current plan: current month/quarter objectives, active projects, revenue/delivery/career priorities and deadlines.

If the user already has documents such as a personal manual, operating plan, OKRs or monthly plan, use those local files. If none exist, generate `output/onboarding/profile_setup.md` and ask the user to prepare 5–10 bullets for each category. Do not require a long autobiography.

## Initialize

```bash
$HOME/.codex/skills/wechat-intelligence-hub/scripts/hub.sh profile-init \
  --owner-alias "本人微信昵称" \
  --personal-doc "/path/to/personal.md" \
  --plan-doc "/path/to/current-plan.md" \
  --priority-label "重点联系人标签"

$HOME/.codex/skills/wechat-intelligence-hub/scripts/hub.sh profile-status
```

Use `--focus`, `--priority-keyword`, `--deprioritize-keyword`, and `--custom-topic "主题=关键词1,关键词2"` for domains outside the built-in dimensions. Updating an existing Profile requires `--force`; unspecified fields are preserved.

## WeChat Labels

Labels are optional but strongly recommended for stable private-chat coverage. Suggested examples are clients, peers, channels, suppliers, self-media contacts and brand contacts, while users remain free to choose names that match their own work.

```bash
$HOME/.codex/skills/wechat-intelligence-hub/scripts/hub.sh profile-init --inspect-wechat-labels
```

Treat discovered labels as candidates. Never infer a label's meaning from its name and silently commit it. Recommend 2–5 useful labels, let the user confirm roles, then update `labels.priority`, `labels.commercial`, `labels.creator`, and `labels.reactivation` as appropriate. The system never changes labels inside WeChat.

Tags narrow routine contact scans; they do not constrain `chat-search`, `topic`, or other all-WeChat queries.

## Refresh

When a new monthly plan replaces the old one, update `context.current_plan_documents` and rerun `profile-init --force`. Comprehensive reports should state whether personalization is `ready` or still using generic defaults.
