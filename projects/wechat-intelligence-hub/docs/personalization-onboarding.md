# 个性化初始化

WeChat Intelligence Hub 的公共代码不包含维护者的联系人、行业偏好或人生计划。首次安装应先建立本地 Profile，让群聊排序、重点私聊和复联范围服务于当前使用者。

## 最小准备材料

准备两类本地 Markdown 或文本文件即可：

1. **个人说明**：身份、业务或岗位、擅长领域、已有资源、账号方向、重要约束和长期目标。
2. **当前计划**：本月或本季度目标、正在推进的项目、收入/交付/求职等优先级、关键截止时间。

没有现成文档时，可以先写各 5–10 条。不要为了使用工具先制作一份很长的“人生档案”。

## 初始化 Profile

```bash
python3 wechat_intelligence_hub.py profile-init \
  --owner-alias "你的微信昵称" \
  --personal-doc "/path/to/个人说明.md" \
  --plan-doc "/path/to/当前计划.md" \
  --priority-label "重点客户" \
  --commercial-label "品牌与客户" \
  --creator-label "同行与资源方"
```

输出：

- `config/profile.local.json`：本地私有配置，不进入公开仓库。
- `output/onboarding/profile_setup.md`：缺项、识别重点和下一步。

已有 Profile 时使用 `--force` 在保留未指定字段的基础上更新。运行 `profile-status` 检查是否齐全。

## 自定义重点

通用维度包括 AI、赚钱、培训、商单、出海、产品、Web3、自媒体增长、合作和 B 端 AI 赋能。其他职业可自行扩展：

```bash
python3 wechat_intelligence_hub.py profile-init --force \
  --focus "法律科技" \
  --custom-topic "法律科技=律所,法律顾问,合同审查" \
  --priority-keyword "重点客户A" \
  --deprioritize-keyword "固定娱乐闲聊"
```

`priority_keywords` 会把命中的群提升为个人重点；`deprioritize_keywords` 只在没有更高优先级行动信号时降级，不能覆盖明确的客户回复、交付、付款或截止时间。

## 微信标签策略

标签的作用是稳定定位需要长期跟踪的联系人，不是替代全微信搜索。推荐按关系或工作流建标签：

- 客户、品牌或甲方
- 同行、创作者或行业专家
- 渠道、资源方或中间人
- 供应商、合作伙伴或团队成员
- 自媒体网友
- 品牌方

同一联系人可以有多个标签。不要为了工具一次性重做全部通讯录，先覆盖最影响当前目标的 20–100 位联系人。

重点联系人日报有两种范围：

- `contact_daily.scope=hybrid`：标签联系人之外，也纳入已在商机库跟踪、双向商业对话或命中个人重点主题的人。
- `contact_daily.scope=priority_labels_only`：只把 `labels.priority / commercial / creator` 指定的微信标签联系人放进重点联系人页。全微信检索和群聊商机扫描仍保留。

只读查看现有标签并获得候选建议：

```bash
python3 wechat_intelligence_hub.py profile-init --inspect-wechat-labels
```

系统不会自动修改微信标签。用户在微信中确认标签后，再运行 `wechat-labels` 导出本地联系人索引。

## 更新节奏

- 当前计划明显改变时，更新计划文档并重新运行 `profile-init --force`。
- 新增客户或资源标签时，更新 Profile 并重新运行 `wechat-labels`。
- 每次日报仍允许全群扫描；Profile 只改变排序、重点和降噪，不删除原始证据。
- 定制查询不受标签限制，可以继续用 `chat-search` 或 `topic` 搜索全部微信记录。
