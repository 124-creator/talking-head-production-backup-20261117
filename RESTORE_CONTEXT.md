# 制作状态交接：2026-11-17

## 用户要达到什么结果

把**第一条口播、第二条口播，以及制作时使用的相关 skill 和材料全部保存在私有 GitHub**。另一台已确认是 Windows x64 的电脑应能下载完整工程，恢复当前制作状态，再由 agent 继续优化。不是只导出 MP4，也不是仅备份几个脚本。

此文件提供可移交的制作记忆。它不恢复原 Codex / ChatGPT 聊天窗口、账户、插件登录或操作系统。

## 最新成片与身份核对

以下路径相对恢复根目录：

| 工程 | 最新文件 | 核对 |
| --- | --- | --- |
| 第一条 | `workspace/onetake_tests/speech_7c1fa1f1/overlay_v5/output/onetake_overlay_v5_1080p30.mp4` | 1920×1080，30 fps，454 帧，15.133333 秒 |
| 第二条 | `workspace/第二个口播/第二个口播_优化成片_v2_1080p30.mp4` | 1920×1080，30 fps，2,118 帧，70.60 秒；33,435,849 B |

第一条最新成片 SHA-256：

```text
aaf606e5a03a4d927763e5272d3767e6598bd84ebe8dc06f29ffe546b6f658a4
```

第二条最新成片 SHA-256（与 `production_v2/output/` 内同名文件一致）：

```text
bdb63a29a513195bd5bdd6529f4463b0ef48f1509332ffc145bf2bcf2da55fb1
```

`reference/approved_first.mp4` 是用户认可的微信副本，原文件名 `a7a87b4c54f8a1abe5efd6f6834decef_raw.mp4`。其封装哈希与 V5 不同，历史核对确认 454 个解码视频帧及 652 个 AAC 内容包一致；不要仅因容器哈希不同判断它不是同一条成片。

`reference/style_reference.mp4` 是用户后来要求学习动画与字体的参考，原文件名 `fd430e380a94fa855533d80b9f71fe1b_raw.mp4`。它用于第二条下一版本的字体 / 动效研究，不是第一条原片，也不是第二条口播原视频。

## 第一条口播

工程根：`workspace/onetake_tests/speech_7c1fa1f1`。

- 保留顶层早期版本、`ending_v2`、`raw_v3`、`overlay_v4` 和 `overlay_v5` 全部目录，包含源素材、帧、字体、字幕 / 转录、QA、预览及输出。
- 最新 V5 使用 `raw_v3/assets/source.mp4` 的原始 4K 素材。其 SHA-256 为 `93dfe4aeddead66652af44422e2b643a9b6f258deaf683874f700955b2e03bd1`。**顶层 `assets/source.mp4` 是较早的 720p 副本，不能误当成最新版本的高清源。**
- 外部参考还包含 `reference/first_original_4k.mp4` 与 `first_original_720p.mp4`，按清单恢复，不依赖原微信位置。
- 四张素材图已在 `assets/image_01.png`～`image_04.png` 保存完整副本，并另有 `reference/first_image_01.png`～`first_image_04.png` 别名。原微信 Temp 位置已失效；迁移时映射到副本，不要求找回微信 Temp。
- V4 / V5 的历史缓存与源帧有关联，不能只保留最后一版脚本或删除较早帧目录。

## 第二条口播

工程根：`workspace/第二个口播`。

- `原视频.mp4` 是 1280×720、30 fps 的 H.264 原片，2,117 个视频帧，原视频流约 70.566667 秒，原音频流约 70.589002 秒。源文件 SHA-256：`ea2eb6cebb0a7c98c8d83514289c54c196ac6ff5b0fef75cca13badf8b1328cf`。
- `1.txt` 是带标注的口播稿；`第二部分人物/第二部分人物/` 有 24 张 PNG、23 份唯一内容，M11 / M12 为同内容文件。
- `production_v1` 是第一版及共享资源库，不是可删除的废稿。V2 引用其中 `motion.js`、`data.js`、图片、Smiley Sans 字体、字幕和 `assets/speech_frames/` 的 2,117 张解码帧。
- `production_v2_tests` 保留风格参考研究、三种短实验及对比；这些小样**不能冒充完整 V2 交付**。
- `production_v2` 是最新完整工程，入口 `comp.html`，核心代码 `full.js`、`full.css`、`styles.css`，验证 / 渲染脚本含 `check_comp.py`、`run_render.py`、`verify_final.py`。新裁图 `assets/M08_front.png`、`M01_front.png` 也在包中。
- V2 全片保留 2,118 张最终帧及精确静帧缓存等渲染证据；历史 V1 根目录交付、所有测试、分析和 QA 均保留。
- V2 使用根目录完整原视频的声音，**不是短测试的 AAC**。历史核对中，原 3,041 个 AAC 包及 PTS / DTS、解码 PCM 均保持；PCM SHA-256 为 `0a3fa03e24b7604bc6a9d5c1b67bcb4a59d8276c6d6c1317cbca61f3b09b9b40`。后续不得悄悄缩短、重新配音或改口播节奏。

用户要求在上一版基础上学习参考的动画与字体并做优化，不是照搬参考视频内容。当前 V2 已是完整优化版；下一轮改动应从该版本新建分支目录，而非退回仅做分析或短测试。

### 保持的内容约束

- 原声、原时间顺序、停顿、语义与素材顺序不变，不自加 BGM / 新配音。
- 正面图 1→6 对应 M02→M07，`6461`（M18）先于 `5921`（M17）。
- 真实人像不做皮肤 AI 美化、身形拉伸或捏造量化对比；`1:7` / `1:8` 只是口述引用，保留非量化说明。
- `换分镜.png` 主要是人物及三视图材料，不据此编造不存在的前后效果故事。

## 使用的 skill 与制作方式

1. `skills/onetake/`：实际本地制作主工具。HTML composition 的值由时间确定，通过 `__seek(t)` 定位，以逐帧快门采样生成运动模糊，再用 FFmpeg 合成。完整库、脚本、参考、模板、案例、字体和许可证都保留。
2. `skills/talking-head-guide/`：来自 ChatCut Desktop 插件 **1.10.14** 的口播剪辑指导及六个 references。用来约束语音节奏、动画 / 字幕保护区域和验证；**本工程不依赖 ChatCut 云端项目 / 在线时间线恢复**。旧指南中的安装绝对路径不应在新机照搬，使用本包 `references/`。
3. `skills/skill-installer/`：历史安装辅助脚本的快照，不是视频渲染依赖。不把它自动覆盖到新电脑 `.codex/skills/.system`。

这不是整个 Codex 配置备份，未包含账户、插件授权、所有其他 skill 或聊天数据库。工程脚本优先指向所带 skill 路径，不要求覆盖新机现有全局安装。

## 运行环境如何恢复

- 原环境为 Python 3.13.5；旧 ASR venv 包含系统包，不能直接跨机复制使用。恢复时从锁文件和随包 wheels 分别建立 `.venv-render`、`.venv-asr`，要求 `include-system-site-packages=false`。
- 图像包以 `opencv-python-headless==4.13.0.92` 为准，不盲装旧环境同时存在的多个冲突 OpenCV 包。实际依赖锁和采集记录在 `environment/`。
- FFmpeg / FFprobe 9.0.2 已保留。旧机器 WinGet `Links` 下有失效指针，新机应使用包内 `runtimes/ffmpeg/bin/`，重建 `workspace/enterprise_demo/runtime_status.json` 的有效路径。
- Chromium / headless 1208 及对应 Playwright 辅助程序在 `runtimes/playwright/`；设置 `PLAYWRIGHT_BROWSERS_PATH` 指向这里，不依赖用户全局浏览器缓存。
- Whisper 模型在 `models/faster-whisper-small/536b0662742c02347bc0e980a01041f333bce120/`，仅四个实际模型文件，不需要旧 Hugging Face 用户目录或令牌。离线加载该本地目录；无 TTS / Kokoro 生成依赖。
- Smiley Sans 与 onetake 自带字体及已有许可已保留；Windows `msyh.ttc`、`msyhbd.ttc`、`consola.ttf`、`consolab.ttf` 不分发，仅在 `environment/system-fonts.json` 留哈希。新电脑字体不同会影响新渲染版式 / 像素，需复核。

## 路径迁移与验证顺序

完整快照 `2026-11-17-current` 记录 12,099 个文件、21,330,443,319 B 逻辑大小。19 个内容寻址分卷包含缓存，恢复不需要旧机器仍在线。

1. 从 Release 下载所有 core 与 cache 分卷，按 `manifests/archives.json` 验证归档大小和 SHA-256。
2. 根据 `manifests/snapshot.json` 恢复目录与每个原始文件，验证源哈希。
3. `tools/relocate_workspace.py <恢复根> --apply` 将旧 `E:\Agent员工\研究自动剪辑`、微信引用、skill、模型、FFmpeg 路径改到当前根；默认不带 `--apply` 时只查看计划。
4. `.relocation/originals/` 留修改前文本，`.relocation/relocation_log.json` 记原文与新文 SHA。原快照校验和与历史渲染 SHA 保持不动。
5. 建立离线隔离 venv，以新 render Python 运行 `tools/smoke_restored.py <恢复根>`；再核对 ASR 的本地模型加载。浏览器检查应只用恢复目录内的项目资源（系统字体例外），不偷读旧工程目录。

媒体与未修改文件可精确恢复；重定位后的文本有意产生新哈希。已有视频恢复精确，不等于更换字体 / GPU 后重新渲染必然逐像素一致。

## 下一个 agent 应如何开始

先报告两条最新文件是否存在、哈希是否匹配、环境 smoke 是否通过及字体差异；再根据用户下一条要求进入新版本编辑。原有 `run_render.py` 等含“输出不得已存在”的保护，**不要删保护、覆盖交付文件或抹掉历史缓存来让脚本运行**。

用户若要求完整新片：短测试用于选型和验证，之后继续完成全片、全片检查和新输出交付，不能在测试完成后就停下。所有新增产物使用明确新版本目录 / 文件名，并更新交接状态及验证证据。
