# 第三方材料与许可说明

此仓库是用户工程的私有跨电脑状态备份。第三方代码、字体、模型、浏览器、工具和参考视频的权利仍属于各权利人；本文件不是新的授权，也不表示所有素材已完成商用 / 再分发权利审查。保持仓库私有，不因能下载就推定可公开发布或任意商用。

## onetake：必须保留的声明

```text
Required Notice: Copyright (c) 2026 Patrick. onetake is free for noncommercial use only.
```

完整原文位于恢复后的 `skills/onetake/LICENSE`，Git 文本镜像为 `sources/skills/onetake/LICENSE`。该快照采用 **PolyForm Noncommercial License 1.0.0**；请阅读原文确认允许用途及分发条件。私有备份不移除其非商业限制；需要超出该许可的用途时应另行确认授权，不把本工程文件的存在视为商用许可。

onetake 自带字体许可说明在 `skills/onetake/looks/fonts/LICENSES.txt`，随字体一同保留；不可只复制字体而丢弃说明。

## 已随原文件保留的说明

| 内容 | 快照中的许可 / 说明位置 | 备注 |
| --- | --- | --- |
| onetake | `skills/onetake/LICENSE` | 保留上面的 Required Notice 和完整原文 |
| onetake 字体 | `skills/onetake/looks/fonts/LICENSES.txt` | 原字体各自许可，不被工程许可取代 |
| Smiley Sans | 第一条 `assets/SmileySans-LICENSE.txt`、第二条 `production_v1/assets/SmileySans-LICENSE.txt` | 与 `SmileySans-Oblique.otf` 一同恢复 |
| 历史 skill-installer | `skills/skill-installer/LICENSE.txt` | 原目录包含 Apache License 2.0 文本；不覆盖新机系统 skill |
| FFmpeg 9.0.2 分发构建 | `runtimes/ffmpeg/LICENSE`、`README.txt`、`doc/` | 以该构建和所含库的实际许可为准；不是只由可执行文件名判断许可 |
| Chromium headless shell | `runtimes/playwright/chromium_headless_shell-1208/chrome-headless-shell-win64/LICENSE.headless_shell` | 保留浏览器原有材料 |
| Playwright 辅助 FFmpeg | `runtimes/playwright/ffmpeg-1011/COPYING.LGPLv2.1` | 与独立 FFmpeg 9.0.2 不是同一项文件 |
| Python 3.13.5 安装器 | `runtimes/python-installer/python-3.13.5-amd64.exe`、`environment/python-bootstrap.json` | 官方来源与校验记录保留；[Python 3.13 许可](https://docs.python.org/3.13/license.html) |
| Python wheel 依赖 | `runtimes/wheels/render/`、`runtimes/wheels/asr/` | 保留 wheel 内原有 `.dist-info` 许可 / 元数据，依各包许可使用 |

这里只索引本地已有的许可材料，不能代替逐个依赖及构建配置的合规核查。对 FFmpeg 等工具进行后续再分发时，应另行核对适用的源码提供、告知等义务，不能以本索引代替这些义务。

`skills/talking-head-guide/` 保留来自已安装 ChatCut Desktop 插件 1.10.14 的七个指南文件，未将整套插件、账户或授权信息打包。该局部目录本身没有独立 LICENSE，**不因此视为公共领域或授予任意再分发权**。

`models/faster-whisper-small/536b0662742c02347bc0e980a01041f333bce120/` 是原机器 Systran faster-whisper-small 缓存的四个模型文件。原局部缓存未含独立许可文本；恢复使用不改变模型来源与上游条款。公开分发或扩大用途前，应核对相应上游仓库 / 模型说明与权利范围，而非从“已备份”推断授权。

## 未分发的 Windows 系统字体

微软雅黑 `msyh.ttc`、`msyhbd.ttc` 与 Consolas `consola.ttf`、`consolab.ttf` **未复制进备份**。`environment/system-fonts.json` 只记录原文件名称、大小与 SHA-256。新电脑应使用其合法安装的 Windows 字体；不同版本可能改变排版与新渲染像素，需要重新视觉验收。

## 用户媒体与隐私

工程原视频、人物照片、声音、示例成片和风格参考均按用户要求保存，用于恢复其制作状态。备份不转移肖像、声音、音乐、商标、视频或照片的第三方权利。对外发布内容或把私有仓库改为公开前，应单独核对这些权利及个人信息。

备份范围不含整个微信文件夹、GitHub token、API key、Codex 账户文件或插件凭证；使用新电脑自身的授权。历史文本中保留的旧用户名 / 路径是迁移证据，不是访问凭证；不要把这些路径公开当作项目需求。
