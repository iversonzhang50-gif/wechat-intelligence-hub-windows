# WeChat CLI Usage

Default Skill entrypoint: `${CODEX_HOME:-$HOME/.codex}/skills/wechat-cli/scripts/reader.sh`. The standalone public command is `rion-wechat-cli`. A compatible independently installed backend can be selected through `RION_WECHAT_CLI_BIN`; never commit a personal path to the skill.

## First-run diagnosis

```bash
reader.sh self-test
reader.sh setup --pretty
```

独立安装公开 CLI 时，完整加密数据库链路使用 `projects/rion-wechat-reader/install.sh --with-sqlcipher`。安装后先运行 `rion-wechat-cli self-test --require-sqlcipher`；该测试只创建和读取临时虚构加密数据库，不访问微信数据。

Only use `discover` and `init` when `setup` reports an ambiguous custom database directory. Both `setup --keys-file ...` and `discover --keys-file ...` can classify encrypted databases when the private 0600 keys file already contains matching user-authorized keys.

If the user explicitly provides an already-owned path-key or schema-2 salt-key access bundle, convert it with `import-access --source ... --database-root ... --keys-file ...`. A schema-2 config may also be passed directly as an explicit `--keys-file`. Never auto-discover another tool's private state directory, echo key values, or disable the default verification step.

`doctor` must report `live_database_read_ok=true` before treating `sessions`, `timeline`, or `search` as complete local history. `notification_preview_ok=true` by itself only means incomplete incoming previews are available.

## Read a current conversation

```bash
reader.sh resolve-chat "联系人" --type-filter private --pretty
reader.sh timeline "稳定 talker id" --limit 50 --display-order asc --include-media-paths false --pretty
```

If a relevant message needs more context:

```bash
reader.sh context "稳定 talker id" --local-id 123 --before-count 15 --after-count 10 --pretty
```

Use `search` followed by `context` for a specific historical topic instead of reading an entire conversation.

情报分析只需要文本时保持 `--include-media-paths false`，避免无谓访问图片、文件和媒体资源数据库。

## Extended read-only sources

When `doctor` reports the matching capability as available:

```bash
reader.sh favorites --limit 20 --pretty
reader.sh sns-feed --limit 20 --pretty
reader.sh sns-search "关键词" --limit 20 --pretty
reader.sh sns-notifications --pretty
reader.sh members "群聊" --limit 100 --pretty
reader.sh announcements "群聊" --pretty
```

Use `tools --profile all` for machine-readable command discovery and `tool-schema <name>` for a command contract. The `media` command currently guarantees message classification and embedded metadata only; do not claim that a local media file path exists unless the result actually contains one.

## Reply-quality gate

Before drafting, determine:

- latest sender: user, contact, or system;
- whether the message actually requires a reply;
- relationship register: close friend, familiar peer, familiar collaborator, new business contact, authority/client, or group;
- the contact-specific use of names, slang, emoji, English, sentence length, and directness;
- the one question or action that the reply must address;
- any factual item that still needs user confirmation.

Default output is one Chinese reply, normally one or two chat bubbles and under 50 Chinese characters. Do not repeat the whole context, produce three stylistic variants, or open with “老师你好，收到” unless that phrasing is normal in this exact chat.

For a stable personal style profile, aggregate a rolling 30-day sample of the current user's outgoing private messages across varied contacts—not only commercial or creator labels. Exclude group chats, links, attachments, copied long text, and forwarded material.

Use the global sample only for length, paragraphing and punctuation. Learn acknowledgements, laughter spelling, address terms, slang, English and emoji from the target contact's recent chat. Require at least five outgoing messages in that chat before adopting contact-specific mannerisms; otherwise use a neutral register. Store aggregate features, not raw private examples.
