# Rion WeChat CLI

`rion-wechat-cli` 是微信个人情报库唯一面向用户的数据读取入口。内部 Reader 负责本地只读查询，但用户不需要安装或理解多个组件。

当前 `v0.9.2-preview.2` 提供：

- 标准 JSON 输出；
- `status`、`sessions`、`contacts`、`resolve-chat`、`timeline/history`；
- 搜索、上下文、增量跟踪、未读、统计、群成员、群公告和本地导出；
- 收藏、朋友圈时间线/搜索/通知，以及转账、红包、合并转发和媒体资源索引；
- `tools`、`tool-schema` 和[旧版能力对照矩阵](CAPABILITY_MATRIX.md)；
- 用户自行提供并有权使用的 SQLite/WCDB 数据库与密钥输入；
- macOS Notification Center 微信通知预览读取，作为明确不完整的降级后端；
- 查询前复制数据库和 WAL/SHM 到私有临时目录，不直接打开微信正在写入的原文件。
- `access-plan` 只读接入诊断、`setup` 首次配置，以及用于高级排障的 `discover`、`init`、`doctor`；
- 独立安装器，不要求先安装 Codex Skill。

Reader 核心不提供：

- 从微信进程内存提取密钥；
- 重签名、注入、Hook 或控制微信；
- 自动发送、删除、转发或修改消息；
- 把通知预览冒充为完整聊天记录。

另附可选的 `rion-wechat-access` 实验性助手，支持检查指定外部工具、验证并接入已有材料，以及经单独确认后尝试 macOS 本机获取。它不属于上述只读接口，不下载或附带获取工具；可能重启微信并重签名副本。新机器获取路径尚未实测，不支持 Windows 获取。见[实验性接入说明](../../skills/wechat-cli/references/experimental-access.md)。

统一首次接入入口为 `rion-wechat-access onboard`，默认只检查；`--apply`允许验证接入，获取分支仍要求单独审核和确认。配套Skill负责准备工具、选择参数和验收，用户无需手工复制key。已有配置可用时直接复用。

## 快速检查

```bash
./install.sh --with-sqlcipher
rion-wechat-cli self-test
rion-wechat-cli self-test --require-sqlcipher
rion-wechat-cli access-plan --pretty
rion-wechat-cli tools --profile all --pretty
```

`--with-sqlcipher` 会把固定版本的 SQLCipher 与 Zstandard Python 依赖安装到 CLI 自己的隔离运行环境，不修改系统 Python。Zstandard 用于解析 `WCDB_CT_message_content=4` 的压缩聊天内容。网络较慢时可先下载与当前 Python/系统匹配的 wheel，再运行：

```bash
./install.sh \
  --sqlcipher-wheel "/path/to/sqlcipher3.whl" \
  --zstandard-wheel "/path/to/zstandard.whl"
```

如果只需要明文测试数据库或通知预览，也可以省略 `--with-sqlcipher`；此时加密数据库诊断会明确显示驱动未安装。

也可以不安装，直接运行：

```bash
python3 rion_wechat_reader.py --pretty status
python3 rion_wechat_reader.py --pretty notifications --limit 10
```

没有数据库配置时，`status` 会返回 `degraded`：只能使用通知预览。通知模式只覆盖系统实际保留的入站预览，不覆盖静音聊天、完整历史、附件或自己发出的消息。

`setup` 会自动检查微信数据目录、寻找可访问数据库、写入本机私有配置并运行诊断。导入授权材料后，它会复用材料中经过验证的数据库根目录，自动推导本人发送者标识，并发现已授权的媒体目录。完整数据库读取可用时返回 `ready`；当前微信数据库缺少访问材料时返回 `database_access_material_required`。

已经合法持有兼容 `all_keys.json` 授权材料的用户，可以显式导入并在写入前验证：

```bash
chmod 600 /path/to/user-authorized-access.json
rion-wechat-cli import-access \
  --source /path/to/user-authorized-access.json \
  --keys-file ~/.config/rion-wechat-reader/keys.json \
  --pretty
```

schema-2 salt-key 文件会使用其中自带的 `db_root` 完成验证；路径型 key 文件仍需加 `--database-root /path/to/authorized/db_storage`。验证通过后，根目录只保存在权限为 `0600` 的私有 key 文件中，后续 `setup --keys-file ...` 无需重复输入。该命令不会自动搜索其他工具的私有状态目录，不获取新 key，也不在输出中显示 key。格式、路径限制与来源说明见 [Access bundle compatibility](docs/access-bundle-compatibility.md)。

## 高级配置

先在一个你明确有权使用的目录内寻找可直接识别的明文数据库：

```bash
rion-wechat-cli discover \
  --root "/path/to/authorized/database-directory" \
  --keys-file ~/.config/rion-wechat-reader/keys.json \
  --pretty
```

然后用返回的候选路径初始化配置：

```bash
rion-wechat-cli --config ~/.config/rion-wechat-reader/config.json init \
  --session-db "/path/to/session.db" \
  --contact-db "/path/to/contact.db" \
  --message-db "/path/to/message_0.db" \
  --favorite-db "/path/to/favorite.db" \
  --sns-db "/path/to/sns.db" \
  --hardlink-db "/path/to/hardlink.db" \
  --resource-root "/path/to/authorized/resource-root" \
  --self-username "your-local-username" \
  --pretty
rion-wechat-cli --pretty doctor
```

也可以手工复制 `config.example.json` 到：

```text
~/.config/rion-wechat-reader/config.json
```

密钥单独放在 `keys.json`，并设置为只有本人可读：

```bash
chmod 600 ~/.config/rion-wechat-reader/keys.json
```

每个数据库既可以使用 64/96 位十六进制 raw key，也可以使用对象形式同时指定 `cipher_compatibility`、`cipher_page_size`、`kdf_iter`、`cipher_use_hmac`、`cipher_plaintext_header_size`、`cipher_hmac_algorithm` 和 `cipher_kdf_algorithm`。同一授权 key 适用于所有库时，可在 `keys` 中使用 `"*"` 或 `"default"` 作为兜底；按完整路径、解析后路径或文件名配置的值仍优先。这些参数必须来自用户有权使用的来源；CLI 只校验并应用，不负责从微信或其他进程提取。

`favorite_db`、`sns_db`、`hardlink_db` 和 `resource_roots` 是可选项；只有配置了相应数据库时，收藏、朋友圈与媒体本地路径才会标为可用。公共仓库、Issue、日志和截图中不得出现数据库、密钥、联系人或聊天原文。加密数据库需要兼容的 `sqlcipher3` DB-API 驱动；`install.sh --with-sqlcipher` 会安装到 CLI 自己的隔离环境，但不保证所有微信版本的加密参数已经兼容。

常用读取命令：

```bash
rion-wechat-cli sessions --limit 20 --pretty
rion-wechat-cli timeline "聊天名称" --limit 50 --pretty
rion-wechat-cli search "关键词" --limit 20 --pretty
rion-wechat-cli favorites --limit 20 --pretty
rion-wechat-cli sns-feed --limit 20 --pretty
rion-wechat-cli sns-search "关键词" --pretty
rion-wechat-cli sns-notifications --pretty
```

## 当前成熟度

这是 Reader 核心的可安装测试版本，不是“一键读取所有人的微信”。`v0.9.2-preview.2` 已覆盖旧 `wechat-cli 1.6.19` 的 29 项只读工具和 266 个公开输入字段，并提供隔离 SQLCipher/Zstandard 运行环境、路径 key 与 schema-2 salt-key 显式导入、虚构加密数据库回归。在一套用户本人授权的实际数据上，已完成新旧 CLI 会话/联系人覆盖、97 个会话、4,479 条消息的结构对照、搜索/上下文/增量读取、当前 macOS 的图片/视频/文件 HardLink 本地路径以及微信个人情报库 SQLite/FTS 索引验证。但“一台机器实读通过”不等于“所有微信版本都已兼容”。当前仍需继续积累：

1. 微信不同版本的 schema/加密兼容矩阵；
2. 无需从进程提取秘密的更通用授权数据接入方式；
3. 不同微信版本下 HardLink 资源目录的真实路径兼容矩阵。
