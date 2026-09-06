# Capability Matrix

基准：本机旧 `wechat-cli 1.6.19` 的公开只读工具元数据。矩阵不读取联系人或聊天正文。

## 已实现等价能力

- 会话：`sessions`
- 联系人和名称解析：`contacts`、`resolve-chat`
- 消息：`history/messages`、`timeline`
- 上下文：`context`、`search-context`
- 搜索：`search`
- 增量读取：`tail` 普通轮询、`--jsonl` 和 `--follow`
- 未读和统计：`unread`、`stats`
- 群成员：`members/group-members`
- 数据库结构：`schema`
- 工具发现：`tools`、`tool-schema`
- Agent 能力总览：`agent/read-os`
- 无内容缓存状态：`cache-status`
- 缓存兼容命令：`cache-refresh`、`cache-rebuild`；新 CLI 不维护内容缓存，因此执行只读健康检查并返回无需重建
- 本地导出：`export`，支持 JSONL、Markdown 和 HTML
- 群公告：`announcements/chatroom-announcements`
- 受限只读 SQL：仅允许对已配置数据库执行单条 `SELECT/WITH`，最多返回 1000 行
- 特殊消息：`transfers`、`red-packets`、`forward-history`
- 收藏：`favorites`
- 朋友圈：`sns/sns-feed`、`sns-search`、`sns-notifications`

## 部分实现

- 通知预览：可以读取 macOS 入站通知，但它不是旧 CLI 的完整消息或朋友圈通知能力。
- 媒体：`media` 能识别图片、语音、视频、文件和表情的消息元数据；配置授权 `hardlink_db` 与 `resource_roots` 后可返回已存在的本地资源路径。

## 尚未实现

- 当前没有已知的旧 CLI 核心只读能力缺口。
- 尚缺不同微信版本的 HardLink 目录样本；当前 macOS 版本的图片、视频和文件本地路径已实读通过。

## 本机结构审计（2026-09-02）

本轮通过旧 CLI 的公开 `schema`/受限只读 SQL 接口，只检查当前微信数据库的表名与列名，没有读取联系人、会话标识或消息正文。已确认新 Reader 当前投影覆盖：

- `SessionTable` 的会话、摘要、未读、时间和最后发送者字段；
- `contact` 的 username、昵称、备注、alias、描述与联系人类型字段；
- `Msg_<hash>` 的 local/server ID、消息类型、发送者、时间、正文、压缩正文及 `WCDB_CT_message_content`；
- `fav_db_item`、`SnsTimeLine`、`SnsMessage_tmp3` 与 HardLink v4 表的当前结构。

旧 CLI 的本机元数据缓存包含解密后的 session/contact 快照，但不包含消息库，因此不能作为完整聊天历史的独立替代后端。

## 本机实读验证（2026-09-03）

在用户明确授权的本地 schema-2 配置上，`v0.9.2-preview.2` 已完成：

- 15 个加密数据库的只读打开，10/10 个消息库兼容；
- 旧 CLI 的 1,536 个会话和前 5,000 个联系人全部被新 CLI 覆盖；
- 旧 CLI 最近 100 个会话中的 97 个可读会话、4,479 条消息，local/server ID、时间、类型与发送方向全部一致；
- `resolve-chat`、`context`、`search`、`tail` 的真实数据读取；
- HardLink 抽检 14,568 条，808 条能落到真实本地文件；
- 新增当前 macOS `msg/attach`、`msg/video`、`msg/file` 目录规则后，最近各 300 条媒体消息中，图片 52 条、视频 25 条、文件 203 条可直接定位本地文件；
- 朋友圈动态/搜索/通知实读通过，并兼容 `pack_info_buf` 中的非 UTF-8 二进制数据；
- JSONL 导出已对包含二进制列的实际聊天记录验收，输出文件权限为 `0600`；
- 微信个人情报库兼容门禁 `ready`，并以临时 SQLite/FTS 索引完成 15 条消息和 4 个链接的端到端验证。
- 2026-09-04 使用新 Reader 完成月度实跑：覆盖 104 位重点联系人、229 个活跃群和约 7.9 万条群消息；同时修复带时区时间戳比较和大批量消息去重性能问题。

所有验收输出只包含布尔值、数量和错误码，不包含密钥、路径、联系人、会话 ID 或聊天正文。通过后 Skill wrapper 默认使用 `rion-wechat-cli`，旧 CLI 仅作为最后回退。

公开来源复核还确认，MIT 许可的 `github.com/r266-tech/wechat-cli@v1.6.21` 在 Go 官方模块代理中保留了 schema-2 配置与 WCDB raw-key 契约。新 Reader 已实现并通过虚构 SQLCipher 库验证：读取数据库头部 salt、匹配用户提供的 `enc_key`，再以 `enc_key + salt` 的 96-hex raw-key 形式只读打开私有快照。未复制或调用其中的 wxkey、调试器、进程扫描或重签名实现。

## 循环验收门槛

每轮必须依次通过：

1. `scripts/capability_gap.py` 更新差距；
2. 全虚构数据库契约测试；
3. 全虚构 SQLCipher 加密数据库端到端测试，包括加密库自动发现与 `setup`；
4. 微信个人情报库通过真实新 CLI 进程跑通兼容门禁、搜索、Markdown 与 SQLite 索引；
5. 空白安装和隐私扫描；
6. 本机只读兼容检查，不输出联系人、微信号或消息正文；
7. 新 CLI 完整实读通过前，包装器继续优先旧 CLI。

当新旧 Reader 都已经能读取同一组用户授权数据时，运行：

```bash
python3 scripts/live_parity.py \
  --legacy-bin wechat-cli \
  --candidate-bin rion-wechat-cli \
  --strict --pretty
```

该对照器只输出能力布尔值、数量、会话类型分布和无正文的结构化消息指纹对照结果；不输出路径、密钥、联系人、会话 ID 或消息正文。
