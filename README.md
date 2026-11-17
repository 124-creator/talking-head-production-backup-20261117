# 两条口播工程：跨电脑恢复备份

> 传输状态见 [STATUS.md](STATUS.md)。Release 发布并完成远端校验前，不要把文本克隆视为完整备份。

这是 **Windows x64** 的制作状态备份，不是只保存成片的展示仓库。

- 私有仓库：<https://github.com/124-creator/talking-head-production-backup-20261117>
- 快照 / Release 标签：`snapshot-20261117-current`（2026-11-17）
- 当前交付：第一条 **overlay_v5**，第二条 **production_v2 完整成片**。
- 首先阅读：[当前制作状态](RESTORE_CONTEXT.md)；继续编辑前遵守 [AGENTS.md](AGENTS.md)。

## 另一台电脑怎么恢复

准备 Windows x64、Git、GitHub CLI（`gh`），建议至少预留 **70 GB 本地空闲空间**，用于传输块、合并后的 ZIP、独立恢复文件、运行环境与临时文件。首次下载需要网络；项目恢复后，已打包的渲染和 ASR 依赖可离线安装。请用有权访问此私有仓库的 GitHub 账户登录，**不要从旧电脑复制 token 或登录文件**。

在 PowerShell 中执行：

```powershell
gh auth login
gh repo clone 124-creator/talking-head-production-backup-20261117
Set-Location .\talking-head-production-backup-20261117
powershell -NoProfile -ExecutionPolicy Bypass -File .\Restore.ps1 -Destination 'D:\TalkingHeadStudio'
```

`D:\TalkingHeadStudio` 是示例，可以换成有足够空间的本地盘新目录；不要选择已有其他工程的目录。无需恢复旧电脑的 `E:` 盘符或 `Dreamboat` 用户名。登录已完成时可跳过 `gh auth login`。

**只执行 `git clone` 不会取回视频、图片、模型和缓存。** `Restore.ps1` 默认下载全部 Release 传输块，逐块校验并自动合并成 19 个逻辑 ZIP，再校验 ZIP 和恢复文件，最后恢复路径和独立运行环境。**不需要手工拼接**。传输块每个不超过 48 MiB，减少长连接中断时需要重传的数据量。

如果已经有全部 19 个原始逻辑 ZIP，可直接复用本地归档。也可以只准备完整的 286 个 `transfer-snapshot-*.bin` 传输块，放在指定目录内或其 `transport/` 子目录内，恢复工具会离线校验、合并：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Restore.ps1 `
  -Destination 'D:\TalkingHeadStudio' -ArchivesDirectory 'D:\TalkingHeadArchives'
```

下载时优先使用当前进程已有的代理环境变量；未设置时，包装脚本可读取**新电脑当前用户**已启用的 Windows HTTP/HTTPS 静态代理，仅供本次进程使用，不修改系统代理，也不迁移旧电脑的代理配置或认证凭证。PAC / SOCKS 等配置不等于可用的静态 HTTP 代理，网络不通时需检查新电脑自己的连接设置。

脚本优先使用兼容的 Python 3.13；没有时校验随包 Python 3.13.5 x64 安装器的 SHA-256 和签名，再安装到当前用户目录，不修改全局 PATH、文件关联或启动器。渲染与 ASR 分别使用新建的隔离 venv，不复制旧电脑不可迁移的 venv，也不向全局 Python 安装包。

正常恢复流程包含已有成片哈希、素材、FFprobe 和浏览器随机 seek 检查，**不会为了验证而重渲染或覆盖已有成片**。`-SkipSmoke` 只用于排障，不代表完整恢复验证通过。新电脑若缺少系统字体或字体版本不同，必须处理提示并重新做视觉检查。

## 恢复后的目录

```text
TalkingHeadStudio/
  workspace/
    onetake_tests/speech_7c1fa1f1/   第一条：全部历史版本、素材、缓存、成片
    第二个口播/                    第二条：原素材、V1、测试、V2、全部缓存
    enterprise_demo/runtime_status.json
  skills/                          三个相关 skill 的独立快照
  reference/                       用户认可视频、风格参考、原视频和四张图别名
  runtimes/                        FFmpeg、Playwright 浏览器、离线 wheels、Python 安装器
  models/                          本地 faster-whisper-small 模型快照
  environment/                     依赖锁、原环境与字体校验记录、两个新 venv
  tools/                           恢复、重定位及验证工具
  .relocation/                     重定位前原文及修改日志
  AGENTS.md / RESTORE_CONTEXT.md / Activate-Project.ps1
```

开始工作前可加载本项目环境：

```powershell
$Studio = 'D:\TalkingHeadStudio'
. "$Studio\Activate-Project.ps1"
& "$Studio\environment\.venv-render\Scripts\python.exe" "$Studio\tools\smoke_restored.py" $Studio
```

然后让新电脑上的 agent 读取恢复目录的 `AGENTS.md` 和 `RESTORE_CONTEXT.md`，从当前 V5 / V2 状态继续制作。skill 副本在 `skills/`；**不要直接覆盖新电脑已有的同名 skill 或 `.codex/skills/.system`**。旧插件指南中若出现原安装目录引用，读取所带的 `references/` 文件即可；这里不依赖旧电脑 ChatCut 插件登录。

## 备份了什么

清单 `manifests/snapshot.json` 为本快照的恢复依据：

| 项目 | 数量 / 大小 |
| --- | --- |
| 完整恢复文件 | 12,099 个 |
| 文件逻辑总大小（含重复副本） | 21,330,443,319 B，约 19.87 GiB |
| SHA-256 去重后唯一对象 | 8,519 个，14,810,894,438 B |
| 逻辑 ZIP 分卷 | 19 个：4 个 core、15 个 cache |
| Release 传输块 | 286 个有序 `.bin` 块，每块不超过 48 MiB |
| 传输块合计（等于逻辑 ZIP 总大小） | 14,163,795,658 B，约 13.19 GiB |

ZIP 内保存按 SHA-256 命名的对象，清单将其还原成原目录结构。重复内容只传一份；恢复时每个文件都独立复制，**不使用硬链接**，避免修改某个版本时影响其他版本。**默认包含 cache 分卷**，不会因为可重新渲染就省略历史帧、解码帧、QA 或渲染缓存。

传输块只是把逻辑 ZIP 的原始字节按顺序切开，不改变 ZIP、工程文件或 `snapshot.json`。`archives.json` 的 `parts` 列表规定合并顺序与每块哈希；例如 `transfer-snapshot-core-001-001.bin` 是 `snapshot-core-001.zip` 的第一个传输块，不是可直接解压的独立 ZIP。表中大小不含少量清单文件，以及单独提供、用于首次启动的 Python 安装器。

- 第一条完整 `speech_7c1fa1f1`，包括早期版本、`ending_v2`、`raw_v3`、`overlay_v4`、`overlay_v5`。
- 第二条整个项目，包括原视频、`1.txt`、人物图片、分析文件、`production_v1`、`production_v2_tests`、`production_v2` 和根目录交付副本。
- `onetake`、ChatCut Desktop 1.10.14 的 `talking-head-guide`、历史辅助 `skill-installer` 原目录快照与已有许可文件。
- FFmpeg 9.0.2、Playwright 对应 Chromium 1208 / headless、Python 3.13 离线 wheel 包、Whisper small 模型及依赖锁。详见 `environment/` 与 [第三方说明](THIRD_PARTY_NOTICES.md)。

`sources/` 是便于 Git 查看差异的小文本镜像，**不是可直接渲染的完整项目**，不要把它与恢复后的工作目录混用。媒体、字体、模型和完整缓存由 Release 提供。[GitHub Release 下载机制](https://cli.github.com/manual/gh_release_download)与普通 Git 克隆不同。

## 完整性与边界

- `manifests/snapshot.json` 是不变的工程内容清单，记录每个恢复文件的原始哈希；`manifests/archives.json` 是归档 / 传输索引，记录逻辑 ZIP 的大小与 SHA-256，以及有序 `parts` 的名称、大小与 SHA-256。Release 的 `SHA256SUMS` 记录逻辑 ZIP 校验值；校验不能只做到传输块，还必须合并后核对原 ZIP，再核对恢复文件。
- 恢复先校验原始文件，再把旧 `E:` 路径、失效微信路径、skill / 模型 / FFmpeg 路径改为当前恢复目录。修改前原文和独立哈希日志保存在 `.relocation/`，**不会伪改旧记录里的历史校验值**。因此重定位后的少数文本不再与原快照字节相同，这是有记录的迁移，不是媒体损坏。
- 四张首条口播图片原微信 Temp 路径已经失效；工程内精确副本已保留，恢复工具使用这些副本，不创建假的微信目录。
- 不包括不相关项目、整个微信资料、Windows 系统、账户凭证、GitHub token、Codex 登录文件或聊天数据库。恢复的是**项目文件、制作环境和明确的交接上下文**，不是原聊天窗口或账户登录状态。
- Windows 的微软雅黑 / Consolas 系统字体不在包内，只记录版本对应哈希。不同 Windows 字体或图形环境可能影响新渲染的像素；已有成片可按哈希精确恢复，不保证跨机器重渲染逐像素一致。
- 第三方材料沿用原许可，尤其 `onetake` 带非商业使用限制；私有备份不等于获得额外商用或公开分发权。

若验证失败，保留日志并修复当前安全分支，不要删除原归档、改写历史哈希或覆盖已交付视频来制造“通过”。
