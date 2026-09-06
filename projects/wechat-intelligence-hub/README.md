# 微信个人情报库

**WeChat Intelligence Hub**

一个本地只读的微信个人情报系统：检索聊天、查看联系人历史、生成群聊摘要，并把高价值商业信号整理成可以持续推进的商机管线。

`Deal Radar / 商单雷达` 现在是系统中的商业机会模块，不再代表整个产品。正式项目目录为 `wechat-intelligence-hub`；历史名称 `wechat-deal-radar` 保留为兼容入口。

架构、质量评估和发布边界分别见 `docs/architecture.md`、`docs/evaluation.md` 和 `docs/release-checklist.md`。

这个工具默认只处理你主动给它的本地文件；进一步版可以调用本机 `vault_cli.py` 的只读查询接口。它不发微信消息，不点击微信 UI，不自动回复。

> 隐私提示：真实聊天、联系人名单、生成报告和本地数据库均属于私有数据。仓库提供的 `.gitignore` 默认排除 `output/`、真实 `contacts/`、数据库、日志和环境变量；开源、提 Issue 或录屏前仍应人工检查 `git status` 和待提交 diff。

## 适合解决什么

- 品牌方太多，不记得谁聊到哪一步
- 群聊太杂，容易漏掉合作、brief、报价、排期、结算信息
- 想每天快速知道哪些人要回复、哪些商单要推进
- 想把微信里的线索同步到飞书多维表格，而不是散在聊天里
- 想按关键词搜索所有微信聊天，或查看某个联系人/群的历史上下文

## 输入格式

### 1. 普通文本

```text
[2026-06-30 10:12] Brand A: 你好，想咨询一下 X thread 合作报价
[2026-06-30 10:15] 我: 可以，麻烦发一下 brief 和预期发布时间
2026-06-30 12:20 Brand B: 预算是 650 USD，可以这周五发布吗？
```

### 2. JSON

支持单个对象数组：

```json
[
  {
    "chat": "Brand A",
    "sender": "Brand A",
    "time": "2026-06-30 10:12",
    "content": "想咨询一下 X thread 合作报价"
  }
]
```

也支持 `wechat-local-vault` / `vault_cli.py` 常见的外层对象，只要里面有 `messages` 数组。

## 快速使用

面向普通使用者的完整教程见仓库根目录 [`docs/USAGE.md`](../../docs/USAGE.md)，包括首次检查、个人 Profile、常用自然语言请求，以及 Markdown + HTML 双版本输出方法。

在 Codex 中优先调用：

```text
$wechat-intelligence-hub
```

历史调用 `$wechat-deal-radar` 仍然可用，但只作为兼容别名。

不读取真实微信数据，先用全虚构样本跑通完整链路：

```bash
bash scripts/run_demo.sh
```

Demo 默认写入系统临时目录，不会读取联系人、真实聊天或本地情报库。可用 `WECHAT_DEMO_OUT=/path/to/demo` 指定输出位置。

## 开源核心与个人 Profile

项目只维护一套代码，不维护互相漂移的“开源版”和“个人版”分支：

- **开源核心**：微信只读适配、索引检索、群聊主题归组、商机状态机、Markdown/CSV/JSON 输出和测试。
- **公开默认配置**：提供可直接运行的标签与交付群识别规则，见 `config/profile.example.json`。
- **个人 Profile**：保存自己的微信昵称、重点标签和交付群识别词；真实联系人、排除群、商业数据和报告继续留在本机。

首次使用推荐先做个性化初始化，而不是直接沿用维护者的行业和标签：

```bash
python3 wechat_intelligence_hub.py profile-init \
  --owner-alias "你的微信昵称" \
  --personal-doc "/path/to/个人说明.md" \
  --plan-doc "/path/to/本月计划.md" \
  --priority-label "你的重点客户标签" \
  --commercial-label "你的品牌或客户标签" \
  --creator-label "你的同行或资源方标签"

python3 wechat_intelligence_hub.py profile-status
```

个人说明可以包括身份、业务、擅长领域、资源、约束和长期目标；当前计划可以包括本月/本季度目标、正在推进的项目、收入或交付优先级和截止时间。系统会从这些本地文档识别通用重点，也可以用 `--focus`、`--priority-keyword` 和 `--custom-topic "主题=关键词1,关键词2"` 精确覆盖。原文不会上传。

如果用户暂时没有个人说明或当前计划，`profile-init` 仍会生成 `output/onboarding/profile_setup.md`，明确列出需要准备的材料；状态保持 `needs_context`，日报会使用通用默认维度并提醒结果尚未充分个性化。

也可以只读检查本机已有微信标签，让系统给出候选分类：

```bash
python3 wechat_intelligence_hub.py profile-init --inspect-wechat-labels
```

标签名称可以按自己的工作流设计，例如“客户、同行、渠道、供应商、自媒体网友、品牌方”，再通过 Profile 指定哪些标签需要优先扫描。标签只负责缩小联系人定位范围，全微信关键词搜索仍然可用。

完整流程见 `docs/personalization-onboarding.md`。

也可以手工创建本地 Profile：

```bash
cp config/profile.example.json config/profile.local.json
```

然后编辑 `config/profile.local.json`。这个文件已被 `.gitignore` 排除，不会进入公开仓库。程序按以下顺序读取 Profile：

1. 命令行 `--profile` 指定的文件
2. 环境变量 `WECHAT_HUB_PROFILE`
3. 项目内 `config/profile.local.json`
4. `~/.config/wechat-intelligence-hub/profile.json`

如果某个群已有成员定时发布图片日报，可在 Profile 中用 `group_recap_senders` 配置发布者，再用 `group_recap_time_windows` 限定常见发布时段。这些日报只会进入独立索引，不再作为本系统的主题、关键发言或商机证据。
5. 内置公开默认配置

指定其他 Profile 时，`--profile` 放在子命令前：

```bash
python3 wechat_intelligence_hub.py --profile ~/.config/wechat-intelligence-hub/profile.json group-daily
```

开源用户获得的是完整功能，不是删减版；个人版只是同一核心叠加私有 Profile、本地聊天数据和个人工作流集成。

### 日常最常用：行动、分流、推进

```bash
python3 wechat_intelligence_hub.py home
python3 wechat_intelligence_hub.py today
python3 wechat_intelligence_hub.py inbox
python3 wechat_intelligence_hub.py triage 12 pursue \
  --follow-up 2026-08-03 \
  --next-action "发送合作方案"
python3 wechat_intelligence_hub.py triage 12 wait \
  --follow-up 2026-08-06 \
  --note "等待品牌确认预算"
```

- `home`：统一展示今日总览、主题搜索、联系人、回复建议和商单雷达五个入口，并把信息分成立即处理、值得关注和仅供存档。
- `today`：最多显示 10 条今天最值得处理的行动。
- `inbox`：显示尚未人工分流的高优先级候选；候选不等于确认商机。
- `triage`：支持 `pursue / wait / pause / ignore / won / lost`。选择 `wait` 时必须设置跟进日期，避免永久沉底。

线索现在分为待审核候选和正式机会。候选默认 14 天没有新证据就过期，但原消息和证据不会删除；人工选择 `pursue / wait / won` 会把它晋级为正式机会并保存反馈，后续扫描不会覆盖人工判断。

```bash
python3 wechat_intelligence_hub.py opportunities                 # 只看正式机会
python3 wechat_intelligence_hub.py opportunities --include-candidates
python3 wechat_intelligence_hub.py opportunity-maintain          # 只预览过期候选
python3 wechat_intelligence_hub.py opportunity-maintain --apply  # 确认后标记过期
```

历史输出默认只预览、不删除：

```bash
python3 wechat_intelligence_hub.py cleanup --raw-days 7 --report-days 30
```

确认预览列表后才使用 `--apply`。原始 JSON/JSONL 默认保留 7 天，Markdown/CSV/日志默认保留 30 天。

准备开源时不要直接压缩个人工作目录。使用公开白名单生成本地发布候选：

```bash
python3 scripts/build_release.py
```

它不会上传任何内容，只会把公开核心、示例配置、虚构样本、测试和文档复制到 `dist/wechat-intelligence-hub/`，并生成文件校验清单。

### 联系人、主题和任意时间范围简报

查看一个联系人聊到哪里、双方留下了什么要求、当前商机和下一步：

```bash
python3 wechat_intelligence_hub.py person "品牌联系人A"
python3 wechat_intelligence_hub.py person "品牌联系人A" --refresh
```

`--refresh` 会先通过微信只读接口刷新该会话，再生成联系人情报。模糊名称匹配到多个会话时，系统不会混在一起，而是要求使用更完整的名字。

根据联系人最近上下文生成可审核的回复草稿：

```bash
python3 wechat_intelligence_hub.py reply "品牌联系人A"
```

`reply` 会参考最后发送者、当前关系语气、明确承诺、开放商机，以及当前安装者最近 30 天跨联系人私聊的长度习惯。跨联系人样本只学习长度、分段和标点；称呼、确认词、笑声、英文和表情从当前联系人会话学习。默认只给一条短回复；本人已经回复或对话自然结束时，会直接建议不再追发。它只生成本地草稿，不发送微信；金额、日期和承诺必须人工核对。

跨私聊和群聊查看主题：

```bash
python3 wechat_intelligence_hub.py topic "培训" --keyword "赚钱" --days 7
python3 wechat_intelligence_hub.py topic "结算" --since "2026-07-01"
```

`培训 / 赚钱 / 商单 / 结算` 内置了小范围同义词扩展。报告按会话聚合，不再把同一条信息在多个历史日报里重复展示。

生成近24小时简报，并自动与前24小时比较：

```bash
python3 wechat_intelligence_hub.py db-index \
  --scope sessions \
  --session-type private,group \
  --session-limit 80 \
  --per-chat-limit 500 \
  --default-24h \
  --out output/db-index-brief

python3 wechat_intelligence_hub.py brief --hours 24
```

简报会分别展示待回复、待兑现承诺、已经人工确认或正在推进的机会、待审核候选、重点私聊/项目合作群、重点群聊、主题变化和附件核验队列。自动发现的 `new` 候选不会再和正式商机混在一起。如果最新索引距现在超过2小时，报告会标记数据过期，并停止把原始差值解释成趋势。

只看品牌方、中间人和自媒体博主私聊时，另生成重点私聊日报：

```bash
python3 wechat_intelligence_hub.py contact-daily --hours 24 --out output/contact-daily
```

它会区分 `待回复 / 等待对方 / 留意 / 无需立即回复`。默认 `contact_daily.scope=hybrid`，收录个人 Profile 重点标签、开放商机、双向商业对话或个人重点主题联系人；设为 `priority_labels_only` 后，重点联系人页只收录 `labels.priority / commercial / creator` 中的微信标签联系人。全微信搜索、群聊雷达和商机库不受此选项影响。输出中的回复建议是方向，不会发送微信。

联系人日报还会向前回看 30 天的个人承诺。只要检出“周四前给初稿”“明天回传数据”一类承诺且后续没有完成证据，就会提升为 `待兑现`，不会因为对方最后只说了一句“好的”或补充开票说明而消失。无标签联系人必须由对方也发出明确商业信号才会进入日报；服务通知、公众号提醒和仅由自己咨询商单/开票产生的闲聊会被排除。

完整的多会话时间范围报告拆成三层，而不是把群聊和私聊揉成一篇长文。24/48 小时只是日常示例，也可以使用一周、一个月或明确的起止日期：

1. `group_daily_topics.md`：按真实项目、事件和问题生成话题日报；`group_daily_groups.md` 只保留有信息增量的重点群聊；`group_selection_matrix.md/json/csv` 列出本窗口全部活跃群，供用户逐群调整关注级别。
2. `contact_daily_digest.md`：只看品牌方、中间人和自媒体博主，给出待回复、等待对方和回复方向。
3. `brief`：只汇总跨两份报告最需要马上处理的事项。

跨群重复链接作为第四个独立索引保留，用于识别集中投放和潜在商单，但不会反复占用日报正文。

小型品牌交付群会按直接商业会话处理。对方最后回复“好的/嗯嗯”只代表暂时无需继续回复，不会自动关闭你已经承诺的初稿、发布、Quote/KOL 转发、加热或数据回传。发布后出现浏览量偏低、需要补曝光或追加 KOL 转发时，商机阶段会进入 `已发布待数据跟进`。

### 扫描本地文件

```bash
python3 wechat_intelligence_hub.py scan samples/sample_chat.txt --out output
```

输出：

- `output/signals.csv`：逐条商单信号
- `output/deals.csv`：按聊天对象聚合的飞书导入表
- `output/daily_digest.md`：当天跟进摘要
- `output/signals.json`：给 Codex/Claude 继续处理的结构化数据

如果你已经在微信里建了需要长期跟进的标签（例如「重点客户」），可以把里面的联系人同步到：

```text
contacts/重点客户名单.txt
```

然后按白名单扫描：

```bash
python3 wechat_intelligence_hub.py scan samples/sample_chat.txt \
  --watchlist contacts/重点客户名单.txt \
  --out output/tagged
```

但商单不只来自已建联品牌方。有些机会来自博主好友、资源群、KOL 群，例如群里有人发品牌合作、红包加热、问谁想接。把这些来源同步到：

```text
contacts/资源群名单.txt
```

然后开机会雷达：

```bash
python3 wechat_intelligence_hub.py scan samples/sample_chat.txt \
  --source-list contacts/资源群名单.txt \
  --out output/opportunities
```

你也可以两类一起扫：

```bash
python3 wechat_intelligence_hub.py scan samples/sample_chat.txt \
  --watchlist contacts/重点客户名单.txt \
  --source-list contacts/资源群名单.txt \
  --exclude-list contacts/排除名单.txt \
  --since 2025-11-01 \
  --out output/all-radar
```

## 进一步版：接入本机只读读取器

本仓库包含 clean-room、自有的 `Rion WeChat Reader` MVP，并通过 `wechat-cli` Skill 提供统一入口。它可以读取用户明确提供且有权使用的数据库输入，也能把 macOS 通知预览作为不完整的入站降级数据源；它不获取数据库密钥。没有可用数据库输入时，请先运行虚构 Demo 或通知预览，不要把个人二进制、数据库密钥、本机配置、联系人或聊天原文提交到仓库和 Issue。

### 微信升级兼容保护

不需要永久固定微信版本。每次微信或 `wechat-cli` 升级后，先运行：

```bash
python3 wechat_intelligence_hub.py compat-check --force
```

它会在严格只读模式下检查三层能力：

- `status`：本地数据库密钥和读取状态
- `sessions`：能否读到最近会话
- `timeline`：能否实际读到一条聊天时间线

报告保存在 `~/.wechat-intelligence-hub/compatibility/`，只记录版本、文件指纹和检查结果，不保存联系人 ID 或聊天正文。相同版本的检查最多缓存 6 小时；检测到版本或读取器二进制变化时，会自动重新实读测试。

`daily`、`group-daily`、`chat-search`、`chat-history`、`db-index`、`wechat-labels` 等所有实时读取命令都已接入这个门禁：

- 检查通过：正常继续
- 只有非核心警告：标记为可用，继续运行
- 核心读取失败：立即停止，避免生成残缺日报

阻断时不会破坏已有情报库，仍可继续查历史记录：

```bash
python3 wechat_intelligence_hub.py db-search 商单 --limit 30
```

Finder/快捷指令的群聊日报脚本 `scripts/run_group_daily.sh` 会在每次读取前强制做一次体检，并把当次结果写入日报目录的 `wechat_compatibility.json`。

脚本会自动按自身位置寻找项目目录。若把 AppleScript 单独保存成应用，需要设置 `WECHAT_HUB_HOME` 指向克隆目录；未设置时默认使用 `~/wechat-intelligence-hub`。

> 这套机制能自动发现升级是否破坏读取，并保证失败时不产出误导结果。如果腾讯大改本地数据库或密钥机制，仍需要等待或编写新的读取适配；任何第三方工具都无法承诺每个未来版本永久零修改兼容。

日常最省心的方式是一键跑完整流程：

```bash
python3 wechat_intelligence_hub.py daily \
  --since 2025-11-01 \
  --scan-out output/wechat-latest \
  --out output/personal-workbench
```

这一步会自动完成：同步个人 Profile 中配置的重点标签名单、扫描本地微信、生成个人机会工作台。

如果你想不定期检查某个客户或合作方标签中，哪些关系值得重新建联、复购保温或失败后修复，跑：

```bash
python3 wechat_intelligence_hub.py reactivation \
  --index-first \
  --label 重点客户 \
  --since 2025-11-01 \
  --inactive-days 21 \
  --out output/reactivation
```

它会生成：

- `reactivation_report.md`：按「优先复联 / 复购保温 / 待交接跟进 / 待下一批跟进 / 失败可修复 / 暂缓」分组，并给出复联建议
- `reactivation_candidates.csv`：适合导入飞书，做品牌方复联清单

新版复联判断会按时间顺序处理冲突信号：后来的发布/结算可以覆盖更早的“先不急”，只有品牌方本人说出的“下一批/之后联系”才会生成窗口提醒。报告还会标出「我最后发出 / 对方最后发来」、建议跟进日期和是否已经到期；未到期对象不会挤进“今天优先看”。今天清单最多展开 10 个，并优先排列更容易成交的复购品牌；完整候选仍保留在 CSV。复联分析只读取对应联系人的一对一聊天，共同群记录留给单联系人检索，避免短昵称污染评分。

拒绝规则还会区分四种不同含义：

- 品牌方明确拒绝/预算不匹配：`暂缓` 或沉默后进入 `失败可修复`
- 品牌方改成纯佣/无保底：`纯佣低优先级`，不会冒充付费商单
- 原负责人离开或交接：`待交接跟进`，提醒确认新负责人
- 你因产品风险主动停止：`我方主动放弃`，不会因为缺单重新推到优先列表

“如果价格不合适可以调整”、讨论其他博主“他暂时不行”等假设或第三方句子不会再被当成你的合作失败。

如果品牌项目发生负责人交接，可以精确查两人的共同群：

```bash
python3 wechat_intelligence_hub.py common-groups \
  "原负责人" "新负责人" \
  --since 2025-11-01 \
  --out output/common-groups
```

这条命令会用联系人的微信 ID 检查群成员，因此没有群名、只有 `xxx@chatroom` 的讨论组也能找到；命中的群聊会写入本地情报库。确认交接后，把关系记录到 `contacts/交接关系.csv`。之后运行 `reactivation --index-first` 时，会自动完成：

- 原负责人标为 `已交接`，不再重复提醒
- 新负责人合并共同讨论组中的报价、排期和合作窗口
- 交接群重新索引，后续可以用 `db-search` 检索

发送者名字默认从个人 Profile 的 `owner_aliases` 读取，也可以临时补充：

```bash
python3 wechat_intelligence_hub.py reactivation \
  --self-name 你的微信昵称 \
  --out output/reactivation
```

如果刚刚已经索引过聊天记录，也可以不加 `--index-first`，直接分析本地情报库：

```bash
python3 wechat_intelligence_hub.py reactivation --out output/reactivation
```

修改复联规则后可以运行内置测试：

```bash
python3 -m unittest discover -s tests -v
```

如果你想看“今天各个群聊都聊了什么，以及里面有没有商单/变现机会”，跑：

```bash
python3 wechat_intelligence_hub.py group-daily \
  --group-limit 60 \
  --per-group-limit 500 \
  --out output/group-daily
```

它会生成：

- `group_daily_digest.md`：可复现的机器初筛，用于语义编辑和审计，不是默认最终日报
- `group_daily_digest.html`：可选的机器初筛网页；只有 `group-daily --html` 时生成
- `group_daily_editorial_packet.json`：供 Codex/Claude 二次语义编辑的精简输入，包含候选主题和代表证据，不重复装入全部原始消息
- `group_daily_topics.md`：跨群话题/事件日报
- `group_daily_groups.md`：按群追溯的重点群聊日报，不使用原始 HTML 折叠标签
- `group_daily_brief.md`：旧版兼容入口，双视图存在时不再作为主要交付
- `group_daily_brief.html`：可选的单文件群聊阅读页；复合日报优先使用下面的综合 HTML
- `group_daily_appendix.md`：按时间和主题切分的完整讨论段与证据，避免主日报变成聊天流水账
- `group_daily_coverage.json`：记录请求、成功和失败读取的群。有失败项时，日报会显式警告，不会把“未读到”当成“没有新消息”
- `group_daily.csv`：适合导入飞书或继续筛选
- `group_daily.json`：结构化结果，保留本机即可
- `cross_group_links.md`：跨群重复链接和商单/变现链接聚合
- `cross_group_links.csv`：跨群链接结构化结果

最终群聊日报采用双视图：

1. `话题日报`：先列最重要的事，再按真实项目、事件、问题或争议跨群聚类，不用宽泛规则标签代替总结。
2. `重点群聊`：只保留有信息增量的群，按群追溯结论、分歧、行动和代表证据，不使用原始 HTML 折叠标签。
3. `群聊筛选`：列出全部活跃群，支持按活跃度、AI、赚钱、培训、商单、出海、产品、Web3、自媒体增长、合作和 B 端 AI 赋能筛选。HTML 中可以调整关注级别并导出选择；不会未经确认就永久排除群聊。

必要证据直接放在相关结论下；跨群链接在商单雷达中每个 URL 只展示一次。完整附录和结构化数据仍保留在本地，但不进入默认阅读导航。

讨论段先按时间间隔切分，再在同一时间会话中按主题归组。红包加热和重复链接只进入链接聚合区，群内其他成员的日报只进入二手索引，两者都不再占用重点讨论篇幅。商单、培训、项目合作、活动、招聘/外包和赚钱/奖励使用独立信号类型，避免用一个“商单”标签包办所有机会。

微信可能返回多个同名会话入口。日报会先按展示群名合并并去重消息，再生成一份群级摘要，避免同一个群在行动清单和可展开列表中重复出现。

规则层擅长不漏掉候选，但不能把抽取的原话冒充语义总结。在 Codex 中调用 `$wechat-intelligence-hub` 时，Skill 会继续读取 `group_daily_editorial_packet.json`，先把同一项目、事件或问题跨群合并，再保留按群证据追溯。高活跃但没有信息增量的泛聊保持折叠。

交付形式默认由 Skill 自动选择：单个联系人、单一项目、关键词核实和回复建议直接在 Codex 回答；完整多会话日报、周报、月报或指定时间段报告同时交付分区 Markdown 和交互 HTML。也可以围绕某条信息、某个人、某个群、某个产品/物品、某个微信标签、某个项目或某件事件定向查找和总结。HTML 采用信号雷达风格，只保留综合行动、群聊日报、重点联系人和商单信号雷达四个入口。群聊页可切换话题日报、重点群聊与群聊筛选；重点群聊可点击群名展开细节。证据就地放在相关结论下，附录和机器审计留在本地但不进入阅读导航。网页支持全分区搜索、路由跳转、原链接直达、明暗主题、打印和当前分区 Markdown 下载。

在群聊与私信语义编辑完成后，对本轮运行目录执行：

```bash
python3 wechat_intelligence_hub.py render-bundle \
  output/run-24h-YYYYMMDD-HHMMSS
```

它会生成：

- `wechat_daily_full.md`：短报告入口，链接到 HTML 和各个 Markdown 分区
- `wechat-report/index.md`：综合行动；同目录另有 `groups.md`、`group-topics.md`、`key-groups.md`、`contacts.md` 和 `radar.md`
- `wechat_daily_report.html`：包含全部源报告的旗舰版交互日报；通过分区路由阅读，外部原链接可直接打开

`render-report` 仍保留给单份 Markdown 的轻量转换，但不再作为完整日报的主要交付。

设计依据、参考项目和后续验证方法见 [`docs/group-digest-design.md`](docs/group-digest-design.md)。

同一个跨群链接保留在 `cross_group_links.md` 中一次，并列出出现群、发布者和判断依据；话题日报只在相关事件下放一次必要 URL，不按群重复。普通报价讨论、培训经历分享、泛泛提到“合作”或单群自然分享不会自动提升为行动项。

跨群链接会按 `高概率商单 / 疑似商单 / 明确非商单 / 普通内容` 分级。同一推广链接在多个群里用红包、付费接龙、三连/四连等方式加热，默认判为高概率商单；出现万粉以上博主信号时进一步加权。原文明确写了“非商单/纯分享”时，不会误报为商单。

如果原文明确写了“不是商单 / 非推广 / 纯分享”，该人工语义优先于付费加热统计；链接仍保留在索引中，但标为 `明确非商单`，不进入建联动作。

机会类型和发现方式是两个独立维度：

- 商单既可能通过跨群链接、红包加热和集中投放发现，也可能直接出现在自然对话里，例如品牌方找博主、中间人问谁想接、还有名额或求推荐。
- 培训、咨询和项目合作通常没有链接，主要从自然对话、关键中间人、图片、文件、语音以及前后文发现。
- 链接热度只用于提高商单置信度，不是任何机会类型的准入条件。
- 高价值对话附近出现图片或文件时，日报会标记为需要展开原始附件核验，不能只把它当成 `[图片]` 跳过。

同时会写入本地情报库：

```text
~/.wechat-intelligence-hub/radar.db
```

以后可以直接搜索历史群聊：

```bash
python3 wechat_intelligence_hub.py db-status
python3 wechat_intelligence_hub.py db-index --scope labels --per-chat-limit 500 --out output/db-index-labels-2025-11
python3 wechat_intelligence_hub.py db-search 商单 --limit 20
python3 wechat_intelligence_hub.py db-search invoice --chat "tutti.so" --limit 20
python3 wechat_intelligence_hub.py db-search 预算 --since "2026-07-01" --out output/search-budget.md
python3 wechat_intelligence_hub.py db-links --since "2026-07-01" --out output/cross-links-history.md
```

`db-index --scope labels` 会把个人 Profile 重点标签里的好友一对一聊天索引进本地情报库。需要搜微信所有聊天时，用全局关键词索引：

```bash
python3 wechat_intelligence_hub.py db-index --scope search --keyword 报价 --keyword 品牌方 --out output/db-index-search
python3 wechat_intelligence_hub.py db-search 报价 --limit 30
```

`db-links` 会从本地情报库里聚合历史链接，适合找“同一条推文/brief/项目机会被哪些群反复转过”。旧库第一次运行时会自动回填链接索引。

### 持久化商机管线

实时扫描、标签索引、群聊日报和全局搜索写入本地数据库时，会把高信号消息先同步为待审核候选。只有人工确认推进后，才进入正式商机管线。重复扫描同一联系人只更新现有开放候选或商机；已经成交或失败后出现更新的合作信号，才会开启新一轮。

群聊采用更严格的入池规则：明确商单/招募/预算/培训需求的自然对话可以入池；普通单群加热只保留在日报和链接情报中；同一付费加热链接跨群出现时合并为一条商机。系统红包、转账回执、否定句和群日报复述不会创建商机。

查看当前开放商机：

```bash
python3 wechat_intelligence_hub.py opportunity-sync --since 2026-07-01 --dry-run
python3 wechat_intelligence_hub.py opportunity-sync --since 2026-07-01
python3 wechat_intelligence_hub.py opportunities
python3 wechat_intelligence_hub.py opportunities --due-only
python3 wechat_intelligence_hub.py opportunities --chat "品牌联系人A"
python3 wechat_intelligence_hub.py opportunities --min-priority 0
```

默认只显示优先级 3-5 的商机；`--min-priority 0` 可查看全部低优先级记录。

更新推进状态、阶段和跟进日期：

```bash
python3 wechat_intelligence_hub.py opportunity-update 12 \
  --status waiting \
  --stage "待 brief" \
  --follow-up 2026-08-02 \
  --next-action "等伦敦团队确认受众和形式" \
  --note "已发送初步课程框架"
```

人工设置的阶段、优先级和下一步会自动锁定，不会被下一次扫描覆盖。需要重新交给自动判断时使用：

```bash
python3 wechat_intelligence_hub.py opportunity-update 12 \
  --unlock-stage \
  --unlock-priority \
  --unlock-next-action
```

把误报、确认机会和低优先级判断沉淀为长期反馈：

```bash
python3 wechat_intelligence_hub.py feedback-add \
  --target-type chat \
  --target "测试群" \
  --verdict ignore \
  --note "测试消息，不是真实商单"

python3 wechat_intelligence_hub.py feedback-add \
  --target-type chat \
  --target "品牌方联系人" \
  --verdict confirmed
```

反馈结论包括：

- `confirmed`：确认是真实机会，优先级至少为 5
- `false_positive`：误报，忽略该聊天的后续自动识别
- `ignore`：长期忽略
- `low_priority`：保留记录，但优先级压到 1

### 通用微信记忆检索

商单只是一个视图。如果你想按任意需求检索微信，例如找某个关键词、某个人说过的话、某个群里的上下文，用下面两个通用入口。

查看任意联系人或群聊最近聊天记录：

```bash
python3 wechat_intelligence_hub.py chat-history "品牌联系人A" \
  --limit 120 \
  --out output/chat-history-zhao
```

只看某个时间之后，或在该聊天里过滤关键词：

```bash
python3 wechat_intelligence_hub.py chat-history "项目合作群A" \
  --since "2026-07-01" \
  --query "agent" \
  --out output/chat-history-project-a
```

全微信关键词搜索，并把结果写入本地情报库：

```bash
python3 wechat_intelligence_hub.py chat-search "签证" --since "2026-01-01" --out output/search-visa
python3 wechat_intelligence_hub.py chat-search "20万" --since "2026-07-01" --out output/search-200k
python3 wechat_intelligence_hub.py chat-search "报价" --chat "某个重点联系人或群名" --out output/search-quote-in-chat
```

输出：

- `search_results.md` / `chat_history.md`：给你和 Codex 看的 Markdown
- `messages.json` / `messages.jsonl`：结构化消息，只放本机
- `search_raw.json`：`wechat-cli` 原始搜索结果，只放本机

这些通用检索命令不判断商单阶段，也不自动生成回复。它们的目标是先把“微信记忆”找出来，再让 Codex 根据你的问题总结。

先把微信通讯录标签转成扫描名单：

```bash
python3 wechat_intelligence_hub.py wechat-labels \
  --label 重点客户 \
  --label 同行创作者 \
  --out contacts
```

它会生成：

- `contacts/重点客户名单.txt`
- `contacts/同行创作者名单.txt`
- `contacts/重点联系人名单.txt`
- `contacts/微信标签联系人.csv`

再用重点联系人名单扫描聊天记录：

```bash
python3 wechat_intelligence_hub.py wechat-scan \
  --watchlist contacts/重点联系人名单.txt \
  --exclude-list contacts/排除名单.txt \
  --since 2025-11-01 \
  --out output/wechat-today
```

把关键词扫描结果按你的真实商单工作流重排：

```bash
python3 wechat_intelligence_hub.py prioritize \
  output/wechat-today/signals.json \
  --contacts contacts/微信标签联系人.csv \
  --out output/商单机会工作台
```

它会生成：

- `prioritized_digest.md`：先看商单推进，再看二跳资源机会，最后看低优先级噪音
- `prioritized_deals.csv`：适合导入飞书多维表格的结构化结果

如果只想扫某个资源群：

```bash
python3 wechat_intelligence_hub.py wechat-scan \
  --chat "X商单共享联盟" \
  --since 2025-11-01 \
  --out output/x-deals-group
```

`wechat-scan` 会额外生成：

- `wechat_raw.json`：`wechat-cli` 原始查询结果，敏感，只放本机
- `wechat_messages.json`：标准化后的消息，敏感，只放本机

### 通用 vault_cli 兼容入口

如果你已经安装并配置好类似 `wechat-local-vault` 的工具，且有 `vault_cli.py`，先检查状态：

```bash
python3 wechat_intelligence_hub.py vault-status --vault-cli /path/to/wechat-local-vault/scripts/vault_cli.py
```

扫描商单关键词：

```bash
python3 wechat_intelligence_hub.py vault-scan \
  --vault-cli /path/to/wechat-local-vault/scripts/vault_cli.py \
  --watchlist contacts/重点客户名单.txt \
  --source-list contacts/资源群名单.txt \
  --since 2025-11-01 \
  --out output/vault-today
```

只扫某个品牌方或群聊：

```bash
python3 wechat_intelligence_hub.py vault-scan \
  --vault-cli /path/to/wechat-local-vault/scripts/vault_cli.py \
  --chat "某个群名或联系人备注" \
  --since 2025-11-01 \
  --out output/brand-a
```

只扫 vault 的新增消息：

```bash
python3 wechat_intelligence_hub.py vault-scan \
  --vault-cli /path/to/wechat-local-vault/scripts/vault_cli.py \
  --mode new-messages \
  --out output/new-messages
```

本仓库自带一个假的 `vault_cli` 用来测试链路：

```bash
python3 wechat_intelligence_hub.py vault-status --vault-cli samples/fake_vault_cli.py
python3 wechat_intelligence_hub.py vault-scan --vault-cli samples/fake_vault_cli.py --out output/fake-vault
```

`vault-scan` 会额外生成：

- `vault_raw.json`：vault 原始查询结果，敏感，只放本机
- `vault_messages.json`：标准化后的消息，敏感，只放本机

## 飞书多维表格建议字段

把 `deals.csv` 导入飞书多维表格后，可以建这些字段：

- `品牌/聊天对象`
- `当前阶段`
- `下一步动作`
- `优先级`
- `最后信号时间`
- `报价/预算`
- `证据条数`
- `证据摘要`
- `来源聊天`

推荐视图：

- 今日要回复
- 待 brief
- 待报价确认
- 待品牌审核
- 已发布待结算
- 已发布待数据跟进
- 高优先级线索

## 安全边界

- CLI 和 Finder 日报入口默认使用私密权限：目录仅当前用户可访问，新文件仅当前用户可读写
- 原始聊天记录不要放进 Obsidian Sync、iCloud、网盘或公开仓库
- `output/signals.json` 仍可能包含客户信息，只放本机私有目录
- Obsidian 只存摘要、线索和行动项，不存完整聊天原文
- 飞书里只放推进商单需要的摘要字段，不放完整私聊

## 支持这个项目 / Support the Project

如果微信个人情报库帮你少翻了聊天记录、找到了值得跟进的机会，欢迎给项目点个 Star。你的支持会让它持续更新，也让更多人用好自己的聊天信息。

If WeChat Intelligence Hub saves you time reviewing chats or helps you spot an opportunity worth following up, please consider giving the project a Star. Your support helps it keep improving.

[前往 GitHub，点个 Star / Star on GitHub](https://github.com/Rion-Wu-tech/wechat-intelligence-hub)
