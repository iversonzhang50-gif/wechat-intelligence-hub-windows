# 微信个人情报库 · Windows 兼容版

基于 [Rion Wu 的 WeChat Intelligence Hub](https://github.com/Rion-Wu-tech/wechat-intelligence-hub) 修改的 Windows 源码发布候选，包含微信只读 CLI、个人情报分析引擎及 Codex Skills。**不是腾讯官方工具，也不是上游官方发布。**

- 本版本：`0.9.2-win-preview.1`，修改日期：2026-09-06。
- 上游：`0.9.2-preview.2`，提交 `3afe33e0742ef4e92b4babe399bf471fdcd86a7b`。
- 许可证：**AGPL-3.0-only**，保留原作者 Rion Wu 的署名与声明；见 [LICENSE](LICENSE)、[NOTICE.md](NOTICE.md)、[修改说明](WINDOWS-CHANGES.md)。原项目商业授权说明仍在 [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)，本兼容版不授予额外商业许可。

## 能做什么

| 功能 | 当前边界 |
|---|---|
| 查询聊天、联系人、群聊和关键词 | 在一台 Windows 电脑、微信4.1.13.12上完成实读验证；只读本机已有数据 |
| 汇总询价、项目进展、待回复和合作线索 | 查询时读取或刷新；旧索引不代表全量记录；内容分析需按原消息核实 |
| 生成回复建议 | 仅生成草稿，不发送微信 |
| 本机情报索引 | 本地SQLite／全文检索；已有Profile保留，首次个性化需用户提供目标 |
| 日报、周报、交互HTML | 四页导航：综合行动、群聊日报、重点联系人、商单信号雷达；机器初筛需语义编辑后交付 |
| 图片、语音、视频及附件正文 | **未完成本Windows版验收**；读到消息类型或文件名，不等于拿到文件内容 |
| 后台监控、自动提醒、自动发送 | 默认不创建后台任务；不提供自动发送 |

安装成功、自检通过、真实账号接通是不同状态。没有有效的本机授权配置时，程序不会自动获取密钥，也不会把空结果说成没有聊天。

## 安装

1. 安装 **Windows x64 的 Python 3.12**。打包验收使用3.12.9；其他3.12补丁版及其他Windows电脑需自检后再验证真实数据。Python解释器不包含在ZIP中。
2. 将源码ZIP解压到独立目录。路径可以有中文和空格；不要覆盖旧安装。
3. 双击 **Install.cmd**。仅在解压目录创建`.runtime`，按清单固定地址从PyPI官方文件服务下载wheel、校验SHA256，再本地安装并运行虚构数据自检。不下载或运行密钥获取工具。
4. 双击 **SelfTest.cmd** 可再次验证。失败会报错，不应反复盲试。

`Install.cmd`仅对该次PowerShell进程使用ExecutionPolicy Bypass，不修改系统执行策略。若企业策略禁止执行，交给管理员处理，不修改企业安全设置。

程序入口是`wechat.cmd`。日常使用可交给Codex运行，以下仅供维护者参考：

```powershell
.\wechat.cmd reader --pretty doctor
.\wechat.cmd reader search "询价" --after "2026-09-01" --before "2026-09-07"
.\wechat.cmd hub home
```

未指定配置时，Reader复用当前用户`~/.config/rion-wechat-reader/config.json`；Hub复用其既有Profile和本地索引。安装程序不会创建、覆盖或修复这些真实文件。改动用户配置应在单独检查后完成，不能以重装代替故障诊断。

**首次接入**见 [Windows接入说明](docs/WINDOWS-ACCESS.md)。运行只读检查；有效配置直接复用。确实缺少访问材料时，先核验固定版本工具、说明影响并获得用户明确确认，才另行执行。本包不承诺新电脑免配置。

## 在Codex中使用

包内`skills/wechat-cli`和`skills/wechat-intelligence-hub`包含两项技能。可由Codex执行`windows/install_skills.py`注册到指定Codex目录。遇到同名技能会停止且不覆盖；默认安装流程不自动注册，避免影响现有技能。

注册后可直接说：

- “汇总近一周询价，列出已报价、供方未回复、需要我处理的事项。”
- “查我和示例客户最近聊到哪里，给我一条回复草稿。”
- “生成今天群聊和重点联系人报告，说明覆盖范围和未核实附件。”

技能注册文件`windows.json`仅在本机生成，用于记录安装位置，不能提交。移动目录后应重新核对注册映射；已有虚拟环境不建议直接搬动，重新解压安装更可靠。

## 隐私与控制权

- 数据库读取、快照和索引在本机进行，代码不自动把数据库上传。**选中的内容交给Codex等云端模型分析时会进入模型上下文，不是全程离线。**
- 本项目只读微信，不发消息、不改标签、不删除聊天。不要在公开Issue中粘贴真实聊天、联系人、配置或访问材料。
- 真实配置、密钥、Profile、数据库、原始日志、报告、媒体和安装后的`.runtime`全部不属于发布内容。
- 新建Reader密钥／配置、Hub Profile和索引使用Windows私有ACL。报告、导出等额外文件仍应放在用户控制的私有目录；不要把源码目录当私人资料归档目录。

## 验证与限制

详细结果见 [验证说明](docs/VALIDATION.md)、[已知限制](docs/KNOWN-LIMITATIONS.md)、[故障排查](docs/TROUBLESHOOTING.md)。自检全部使用虚构数据库和消息，不能代替新机器上的账号验证。

本包是**源码包**，不是免安装EXE，不包含Python、Pandoc二进制或依赖wheel。依赖固定在[requirements-windows.lock](requirements-windows.lock)，下载来源、哈希和元数据记录见[dependency-provenance.json](dependency-provenance.json)。

## 来源与再发布

请保留许可证、NOTICE、上游链接和修改日期。发布修改后的源码仍使用AGPL-3.0-only；如改成网络服务，还需落实相应源码提供义务。查看[上游许可证](https://github.com/Rion-Wu-tech/wechat-intelligence-hub/blob/3afe33e0742ef4e92b4babe399bf471fdcd86a7b/LICENSE)和[第三方依赖说明](THIRD-PARTY.md)。这不是将上游作品改名为原创项目。

仓库中保留部分上游跨平台说明与源码，Windows行为以本README及`docs/WINDOWS-*.md`为准。上游设计预览图片和页面未打包；本包提供的测试数据均为虚构。
