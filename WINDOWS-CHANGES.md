# Windows修改记录

修改日期：2026-09-06。发布候选：0.9.2-win-preview.1。

本版衍生自Rion Wu的WeChat Intelligence Hub（AGPL-3.0-only），并保留原始版权、许可证及NOTICE。不代表Rion Wu或腾讯认可本兼容版。

## 从本机已验证安装迁移

- Reader：Windows ACL权限验证与私有写入；SQLCipher自检密钥ACL；关闭SQLite自检文件句柄，避免Windows锁文件。
- Reader：区分“能打开但业务类型未分类”的辅助数据库与“打不开”的数据库，错误密钥仍判失败。
- Hub：Windows原生入口识别；通过Python直接调用Reader，避免批处理参数进入命令解释器。
- Hub：读取Windows微信安装位置及PE版本信息，替代macOS应用包版本读取。
- windows_privacy.py：私有文件只允许当前用户、SYSTEM和管理员；不输出访问材料。

## 为独立发布补充

- 自包含源码布局，优先调用相邻Reader代码，不依赖原电脑安装目录。
- 中文子进程输出固定UTF-8；自定义Python Reader同样通过当前Python启动。
- 本目录虚拟环境、固定版本及wheel哈希安装；不覆盖已有环境或个人数据。
- Hub新建Profile／索引补充Windows ACL；单独的`WECHAT_HUB_COMPAT_DIR`支持隔离验证。
- 缺少PATH中的Pandoc时使用已固定安装的pypandoc-binary所带Pandoc。
- Windows技能入口与显式注册程序，同名技能不覆盖。
- 13项虚构数据验收，包含错误密钥、宽权限拒绝、中文读写、跨进程索引及HTML渲染。

本机专用的首次访问脚本没有复制进发布包：它包含本机路径和针对当次进程的选择，不适合作为公共工具。方法、上游固定版本及已知问题在docs/WINDOWS-ACCESS.md记录；没有因此改变只读Reader的范围。
