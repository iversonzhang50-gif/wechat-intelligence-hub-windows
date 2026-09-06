# Security and privacy

Please do not open a public issue containing chat messages, contact details, local paths, API keys, cookies, access tokens, invoices, client briefs, or other personal and commercial data.

Before reporting a bug, reproduce it with the bundled fictional samples whenever possible. If a private report is required, contact the maintainer through a private channel and share the minimum evidence needed.

The Reader and Intelligence Hub are read-only with respect to WeChat: they do not send messages or automate replies. The separate experimental `rion-wechat-access` helper is not read-only: after explicit review and confirmation it can invoke an external local provider with macOS administrator authorization, which may restart WeChat, debug its process and re-sign a shadow copy. Installation and daily reports never invoke acquisition. No provider is bundled or downloaded by the installer/helper; when first access is explicitly requested, Codex may prepare a pinned, reviewed provider separately. Acquisition compatibility on a fresh machine is not yet verified. See [the authorization and recovery boundaries](skills/wechat-cli/references/experimental-access.md). Users remain responsible for local data access, backups, applicable platform rules, and legal compliance.

Never commit:

- real WeChat IDs or chatroom IDs;
- exported chats, contact lists, databases, screenshots, or generated reports;
- `config/profile.local.json` or equivalent personal profiles;
- secrets, tokens, passwords, cookies, private keys, or paid client materials.
