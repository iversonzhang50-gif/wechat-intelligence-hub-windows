# 许可证与依赖处理

核对日期：2026-09-06。以固定提交中的LICENSE、NOTICE、项目元数据及实际下载wheel内元数据核对。依赖的官方页面仅用于公开信息，不传输任何微信内容。

| 来源 | 核验的许可 | 发布处理 |
|---|---|---|
| Rion-Wu-tech/wechat-intelligence-hub，3afe33e0742ef4e92b4babe399bf471fdcd86a7b | AGPL-3.0-only | 分发修改源码；完整保留LICENSE、NOTICE、商业授权说明，注明修改日期与来源 |
| fanyuantaier/wechatauto-replica，04ef8cbde3862cff90b5f6b42c9ebfcea44ef48d | 该提交LICENSE为Apache-2.0，pyproject.toml同样声明 | 仅链接和记录历史修复来源，不打包源码、二进制或安装依赖，不在安装、自检中调用 |
| cffi 2.1.1 | MIT-0 | 安装时单独从PyPI取得，不再分发wheel |
| cryptography 46.0.3 | Apache-2.0 OR BSD-3-Clause | 同上；所带底层库许可保留在原发行包内 |
| pycparser 3.0 | BSD-3-Clause | 同上 |
| pywin32 311 | PSF（wheel元数据标签） | 同上；具体许可原文以发行包内LICENSE为准 |
| sqlcipher3 0.6.2 | MIT（Python绑定元数据） | 同上；不将绑定许可误称为其所有内置库唯一许可 |
| zstandard 0.25.0 | BSD-3-Clause | 同上 |
| pypandoc-binary 1.17 | Python包装器MIT；所带Pandoc有独立GPL许可 | 同上；源代码ZIP中不包含Pandoc二进制，下载后的依赖保留原许可证 |
| Python 3.12 | Python Software Foundation许可及其组件许可 | 用户单独安装，本源码包不包含解释器 |

PyPI链接采用固定版本，例如`https://pypi.org/project/sqlcipher3/0.6.2/`；每个包的具体下载URL、SHA256及其许可文件位置见dependency-provenance.json。

源码的源头和权利声明保留，不宣称完成了上游所有第三方代码的权属审计。若后续需要改为“内置Python、依赖、Pandoc的一体安装包”，必须重新处理二进制组件的许可证、NOTICE及对应源码提供要求，不能直接把本机.runtime压入ZIP。

参考：[主项目NOTICE](https://github.com/Rion-Wu-tech/wechat-intelligence-hub/blob/3afe33e0742ef4e92b4babe399bf471fdcd86a7b/NOTICE.md)、[固定provider许可证](https://github.com/fanyuantaier/wechatauto-replica/blob/04ef8cbde3862cff90b5f6b42c9ebfcea44ef48d/LICENSE)、[GNU AGPL正文](https://www.gnu.org/licenses/agpl-3.0.html)、[Pandoc版权声明](https://github.com/jgm/pandoc/blob/main/COPYRIGHT)。
