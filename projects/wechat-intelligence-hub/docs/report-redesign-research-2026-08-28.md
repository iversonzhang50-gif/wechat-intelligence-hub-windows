# 微信个人情报库报告重设计调研与方案

> 日期：2026-08-28  
> 决策问题：如何让 Markdown 和 HTML 同时保留完整信息，又不再变成长页面，并让用户能从总览进入不同分区、具体事项与原始证据。

## 结论

不要继续优化“把所有 Markdown 拼到一个页面”的方案。下一版应改成：

1. 先生成统一的结构化报告模型，而不是先生成八份互相重复的 Markdown。
2. Markdown 输出一个短入口页和若干独立分区页；入口页不再复制全部正文。
3. HTML 仍可保持一个便于本地打开和分享的独立文件，但使用路由切换分区，每次只渲染一个页面。
4. 行动、机会、联系人、话题、群聊、跨群链接、证据和机器审计分层呈现。
5. 同一商机或联系人在主层只出现一次，其他页面只引用它，不重复解释。

推荐视觉方向是“静默情报台”，并吸收“编辑部简报”的话题阅读方式：总览和行动保持紧凑，话题与项目详情更像编辑后的专题页。

## 当前问题审计

本轮 `wechat_daily_full.md` 有 1845 行、约 164 KB；`wechat_daily_report.html` 约 395 KB。真正的执行总览只有 41 行，但渲染器随后把 8 份来源报告全文再次拼接。

当前结构的主要问题不是 CSS，而是信息架构：

- 以源文件为栏目，不以用户任务为栏目。
- 总览、行动总览、群聊精编和机器初筛反复描述同一联系人或项目。
- 搜索只能隐藏整块来源文件，不能定位到一个具体商机、话题或证据。
- `<details>` 只是把过长内容藏起来，展开后仍然是长页面。
- 机器审计与人工编辑的内容权重过于接近，误报容易干扰判断。
- Markdown 的“完整版”实际上是拼接档案，不适合日常阅读。

## 调研依据

### 信息架构与交互

- Shneiderman 的信息可视化原则是“先总览，再缩放和筛选，最后按需查看细节”。这支持“首页概览 + 分区路由 + 证据详情”，而不是一次展示所有原文。[The Eyes Have It](https://drum.lib.umd.edu/items/155a868e-fb83-4115-9899-9187ea8c0498)
- Apple 建议侧边栏用于平级内容区，层级不要无限加深；重要信息先出现，次要细节通过渐进式披露进入。[Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars)、[Disclosure controls](https://developer.apple.com/design/human-interface-guidelines/disclosure-controls)、[Layout](https://developer.apple.com/design/human-interface-guidelines/layout)
- GOV.UK 明确建议：内容过多时优先简化、拆成多页或使用页首锚点；不要用嵌套 Accordion 解决长内容。[Accordion](https://design-system.service.gov.uk/components/accordion/)
- GitHub Primer 的 Action List 和 Nav List 更适合高频操作界面：单列、可扫描、元数据紧凑，点击导航后替换主内容。[Action list](https://primer.github.io/design/components/action-list/)
- Fluent 建议导航名称简短、直接、围绕目标；搜索和收藏不能替代清晰的信息架构。[Nav usage](https://fluent2.microsoft.design/components/web/react/core/nav/usage)、[Accessibility](https://fluent2.microsoft.design/accessibility)

### 长对话与群聊总结

- TextTiling 说明长文本应先按语义话题边界切成连贯片段，而不是按来源文件机械分块。[TextTiling](https://aclanthology.org/J97-1003/)
- QMSum 指出，一个通用短摘要很难覆盖多话题长对话，应先定位与用户问题相关的片段，再进行针对性总结。[QMSum](https://aclanthology.org/2021.naacl-main.472/)
- 长对话总结研究显示，“先检索相关发言，再总结”的管线在多类长对话数据上表现更好。这与微信情报库的“时间过滤 -> 主题/机会检索 -> 编辑总结 -> 证据回链”一致。[Long Dialogue Summarization](https://aclanthology.org/2021.findings-emnlp.377/)
- DialogLM 把话题分段列为长对话理解的重要任务，进一步支持按项目、事件和讨论问题组织群聊内容。[DialogLM](https://ojs.aaai.org/index.php/AAAI/article/view/21432)

### 开源项目、教程、视频与社区资料

- VitePress 提供文件式路由、多侧边栏和本地全文搜索，适合作为“多页 Markdown 报告站”的参考实现。[VitePress](https://github.com/vuejs/vitepress)、[Sidebar](https://vitepress.dev/reference/default-theme-sidebar)、[Local Search](https://vitepress.dev/reference/default-theme-search.html)
- Material for MkDocs 支持导航标签、离线分发和浏览器内搜索，适合开源版或历史档案站。[Material for MkDocs](https://github.com/squidfunk/mkdocs-material)、[Search and offline](https://github.com/squidfunk/mkdocs-material/blob/master/docs/plugins/search.md)
- Pagefind 可为纯静态多页网站建立本地搜索索引和元数据筛选，适合未来报告历史库。[Pagefind](https://github.com/CloudCannon/pagefind)、[Filtering](https://pagefind.app/docs/filtering/)
- Observable Framework 擅长从构建期数据快照生成交互式报告和数据应用，适合后续月度看板，不适合直接作为每日单文件报告的首选依赖。[Observable Framework](https://github.com/observablehq/framework)
- FOSDEM 的 Material for MkDocs 实战演讲展示了从 Markdown 到可搜索文档站的完整路径，可作为开源版交付教程参考。[演讲页面与视频](https://archive.fosdem.org/2024/schedule/event/fosdem-2024-1815-easily-going-beyond-markdown-with-material-for-mkdocs/)
- MkDocs 社区讨论强调离线搜索和结果层级上下文的重要性；同时其新搜索曾因上游技术问题延期，因此不应把当前个人版强绑定到该框架。[搜索改进讨论](https://github.com/squidfunk/mkdocs-material/issues/6307)、[项目状态讨论](https://github.com/squidfunk/mkdocs-material/discussions/8461)

### 书籍

- Stephen Few 的《Information Dashboard Design》强调“一眼监控”和减少视觉噪声，适合总览与行动页。[官方书页](https://www.analyticspress.com/idd.php)
- Rosenfeld、Morville、Arango 的《Information Architecture: For the Web and Beyond》强调围绕内容、用户与情境建立组织、标签、导航和搜索系统，适合重构报告目录。[O'Reilly 书页](https://www.oreilly.com/library/view/information-architecture-4th/9781491913529/copyright-page01.html)
- Marti Hearst 的《Search User Interfaces》系统讨论目录、分类导航、分面搜索和重新查找，适合联系人、项目、状态和来源筛选。[在线全文](https://searchuserinterfaces.com/book/)

## 推荐信息架构

主导航固定为七个用户任务，不再暴露源文件名：

1. **总览**：时间范围、覆盖情况、三条最重要结论、今天先做、风险提示。
2. **行动**：待回复、待建联、待交付、待结算、等待结果，按截止和价值排序。
3. **商业机会**：商单、培训、项目、活动，按同一品牌或 campaign 去重。
4. **对话**：品牌方、中间人、自媒体博主的当前状态、建议回复和下一节点。
5. **群聊话题**：先按项目/事件/讨论问题总结，再提供群聊来源与代表证据。
6. **跨群链接**：一个标准化链接只出现一次，列出出现群、发起人、时间和判断。
7. **证据与审计**：人工引用证据、覆盖率、附件待核实和机器初筛；默认不放进主阅读流。

每个实体应有稳定 ID，例如 `opp-gearzero-202608`、`contact-starryblu`、`topic-hy4-launch`。不同页面引用同一个 ID，避免重新生成一段相似文字。

## Markdown 交付结构

```text
wechat-report/
  index.md                 # 入口，总览不超过 100 行
  actions.md               # 今日行动与状态
  opportunities.md         # 商单、培训、项目、活动
  conversations.md         # 私信与回复建议
  topics.md                # 编辑后的群聊话题
  groups.md                # 按群追溯
  links.md                 # 跨群重复链接，一条链接一行/一项
  evidence.md              # 正文实际使用的证据
  audit.md                 # 覆盖率、附件、机器候选与错误
  report.html              # HTML 入口
```

每个 Markdown 页顶部使用同一行相对链接导航：

```markdown
[总览](index.md) · [行动](actions.md) · [商业机会](opportunities.md) · [对话](conversations.md) · [群聊话题](topics.md) · [按群追溯](groups.md) · [跨群链接](links.md) · [证据](evidence.md)
```

`wechat_daily_full.md` 不再作为默认交付。需要归档时可通过显式参数生成 `export/complete.md`，但入口页不链接它。

## HTML 交付结构

个人版继续生成单个 `report.html`，但内部改成轻量 Hash Router：

```text
#/overview
#/actions
#/opportunities
#/conversations
#/topics
#/groups
#/links
#/evidence
#/audit
```

这样既保留单文件、离线、`file://` 直接打开和方便分享，又能让浏览器前进/后退、收藏具体页面，并确保一次只显示一个分区。详情使用嵌套路由或右侧检查器，例如 `#/opportunity/opp-gearzero-202608`。

HTML 必须具备：

- 点击主导航切换页面，不滚动穿越整份报告。
- 全局搜索返回“结论 + 所属分区 + 来源”，点击直接跳到目标。
- 外部原链接使用新标签打开，并保留来源群、发言人和时间。
- 桌面使用左侧导航 + 主内容 + 可选右侧详情；手机改成顶部标签和“更多”菜单。
- 只在详情页展开证据，不在首页使用大段折叠。
- HTML 与 Markdown 来自同一个 `report_model.json`，禁止分别拼写两套结论。

开源托管版可以另加真正的多页静态站输出，采用 VitePress/MkDocs 风格和 Pagefind 搜索；这不应成为个人本地日报的运行依赖。

## 四套待选视觉风格

### A. 静默情报台（推荐）

**定位**：每天高频查看、推进合作和回复联系人。

- 视觉：白色、浅灰、炭黑为主，信号绿、警示红、等待琥珀、链接蓝作为功能色；不使用大渐变和装饰性卡片墙。
- 布局：216px 左侧导航，760-860px 主阅读区，详情需要时打开 300-340px 右侧检查器。
- 组件：紧凑行动列表、状态圆点、截止时间、联系人头像/首字母、轻量分段控件。
- 优点：最快找到“我现在该做什么”，最贴合你的个人工作流。
- 缺点：用于公开分享时视觉叙事感略弱。

### B. 情报编辑部

**定位**：阅读群聊主题、复盘趋势、对外展示付费社群能力。

- 视觉：白底、石墨黑、钴蓝和信号红；标题可使用系统宋体，正文保持苹方/无衬线。
- 布局：首页是“头条 + 今日信号 + 话题目录”，详情页像专题文章，证据位于文末。
- 组件：主题导语、来源脚注、跨群时间线、关键引用和“与 Rion 的关系”。
- 优点：群聊总结更像编辑后的简报，阅读体验和品牌感更好。
- 缺点：待回复和项目管线不如 A 高效。

### C. 信号雷达

**定位**：月度商单复盘、商业漏斗、跨群投放追踪。

- 视觉：冷灰、深石墨、钢蓝、珊瑚红；数字和状态更突出。
- 布局：指标条、筛选栏、机会表格、时间线和链接聚类；点击进入项目详情。
- 组件：商机阶段、预算区间、联系人覆盖、重复链接强度、漏斗与趋势小图。
- 优点：适合长期商业分析和寻找漏项。
- 缺点：容易把未经核实的机器分数做得过于“确定”；不适合作为唯一日报界面。

### D. 知识库导航

**定位**：GitHub 开源文档、历史报告和付费社群知识库。

- 视觉：接近 VitePress/MkDocs，但使用更安静的中性色和品牌绿，不直接照搬主题。
- 布局：左侧目录、顶部搜索、面包屑、正文、右侧页内目录，上一页/下一页导航。
- 组件：标签、版本/日期、原文链接、相关报告、引用来源。
- 优点：最适合多日归档、搜索和开源用户学习。
- 缺点：对“今天马上做什么”的推动力最弱。

## 最适合 Rion 的组合

采用 **A 作为主框架，B 作为群聊话题和项目详情的阅读风格，D 作为未来历史档案/开源文档层**。

不建议把 C 直接做成首页。等机会状态、预算、交付和结算字段稳定后，再把 C 作为“商业复盘”独立页面加入。

## 统一内容模型

下一版先创建一个标准模型，再从它生成所有页面：

```text
ReportModel
  meta
  overview
  actions[]
  opportunities[]
  conversations[]
  topics[]
  groups[]
  links[]
  evidence[]
  audit
```

每条机会至少包含：`id`、名称、类型、阶段、优先级、价值判断、联系人、下一步、截止时间、证据 ID、原链接和不确定性。页面生成器只引用这些字段，不重新自由总结。

## 内容长度规则

- 首页：3 条结论、最多 7 个行动、最多 5 个信号；目标 800-1200 个汉字。
- 行动页：只放仍需执行的事项，已结束移动到历史筛选。
- 商业机会页：同一 campaign 一条主记录，不按群重复。
- 话题页：3-8 个真实项目/事件/问题，不使用宽泛标签凑数。
- 群聊页：只有出现信息增量的群进入正文，其他群在覆盖页列名。
- 跨群链接页：每个 URL 只出现一次，群名和发起人作为元数据。
- 证据页：只保留正文实际使用的证据；完整机器包进入 `.internal/`。

## 实现路线

1. 定义 `report_model.json` 和稳定实体 ID，先解决跨文件重复。
2. 把当前 `build_combined_markdown()` 替换成多页 Markdown 生成器和 `report_manifest.json`。
3. 把当前“所有 source panel 纵向排列”替换成 Hash Router 和按路由渲染。
4. 增加详情检查器、全局搜索结果页、原链接跳转和证据反向链接。
5. 建立三个 CSS 预览主题，选定后只保留一个默认主题；明暗模式是颜色模式，不作为另一套风格。
6. 用同一 24 小时数据做旧版与新版对照，确认没有丢失任何主报告信息。
7. 使用 Playwright 在 1440px、1024px 和 390px 视口检查导航、文本溢出、链接、搜索、前进后退和打印。

## 验收标准

- 30 秒内能找到前三个行动项。
- 从首页到任一原始证据不超过 3 次点击。
- 同一商机在主信息层只完整描述一次。
- Markdown 和 HTML 的行动数、商机数、联系人状态与证据 ID 完全一致。
- 首页不出现机器候选流水账、附件占位列表或完整跨群 URL 清单。
- HTML 离线打开可用，不依赖 CDN 或本地服务器。
- 浏览器前进/后退可切换分区，复制带 Hash 的地址可回到同一页面。
- 所有外部原链接可点击，所有内部 Markdown 相对链接通过自动检查。

## 下一步决策

默认按 **A 静默情报台 + B 话题详情** 推进。视觉确认阶段应先用同一份真实日报制作 A、B、C 三张桌面/手机预览，再开始重写正式渲染器；D 直接用于后续开源文档和历史报告库。
