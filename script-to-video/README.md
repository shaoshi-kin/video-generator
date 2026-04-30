# script-to-video

> 素材+配音 → 口播视频，光伏和 AI 自媒体通用。

一句话说清楚：**你把真实照片/视频丢进去，把经历说一遍，工具帮你 AI 配音、加字幕、合成视频。**

---

## 目录

- [安装](#安装)
- [五分钟上手](#五分钟上手)
- [核心流程图](#核心流程图)
- [四种命令详解](#四种命令详解)
  - [init — 创建项目](#1-init--创建项目)
  - [polish — AI 润色文稿](#2-polish--ai-润色文稿)
  - [gen — 生成视频](#3-gen--生成视频)
  - [run — 一键生成](#4-run--一键生成)
- [项目结构](#项目结构)
- [口播稿格式](#口播稿格式)
- [横竖屏素材管理](#横竖屏素材管理)
- [三种风格预设](#三种风格预设)
- [真实使用场景](#真实使用场景)
- [FAQ](#faq)

---

## 安装

### 1. 安装依赖

```bash
cd /Users/kingshaoshi/Desktop/claudeCode/script-to-video
pip install -r requirements.txt
```

### 2. 确认 ffmpeg 已安装

```bash
ffmpeg -version
# 如果没有：brew install ffmpeg
```

### 3. 配置 AI 润色（可选）

润色功能需要 LLM API Key。如果暂时不配，也能手动写稿+生成视频。

```bash
echo 'export DEEPSEEK_API_KEY="sk-your-key"' >> ~/.zshrc
source ~/.zshrc
```

### 4. 全局命令（可选）

```bash
# ~/.zshrc 里已有：
alias s2v="/Users/kingshaoshi/Desktop/claudeCode/script-to-video/s2v"
```

重新打开终端后，在任何目录都能用 `s2v`。

---

## 五分钟上手

### 最快路径：一条命令出片

```bash
s2v run "今天去看了惠州陈老板的工厂屋顶，800平..." --style pv -n 陈老板项目 -m ~/Desktop/电站照片/
```

`-n` 是项目名，`-m` 是你的素材文件夹。工具自动完成：润色→配音→横竖双版视频。

### 分步路径：手动控制每一步

```bash
# 1. 创建项目
s2v init 光伏合同避坑 --style pv
# → 生成 光伏合同避坑/ 目录，包含示例脚本和空素材夹

# 2. AI 润色你口述的经历
s2v polish "签了光伏租赁合同三年，厂房拆迁才发现..." --style pv -o 光伏合同避坑
# → AI 改写为结构化口播稿，保存到项目的 script.md

# 3. 把你的照片/视频拖进素材夹
# 竖屏素材 → 光伏合同避坑/materials-portrait/
# 横屏素材 → 光伏合同避坑/materials-landscape/

# 4. 生成视频
s2v gen 光伏合同避坑 --dual
# → 横竖双版本输出到 output/
```

---

## 核心流程图

```
┌─────────────────────────────────────────────────────────┐
│                    script-to-video                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  你的经历 ──→ polish ──→ 结构化口播稿 (script.md)        │
│                              │                          │
│  你的素材 ──────────────────┼──→ gen ──→ 成品视频        │
│  (照片/视频)                 │              │            │
│                              │          ┌───┴───┐       │
│                              │          │       │       │
│                              │      竖屏.mp4  横屏.mp4   │
│                              │    (1080x1920)(1920x1080) │
└─────────────────────────────────────────────────────────┘

详细流水线：

  口述/文字                    照片/视频
      │                            │
      ▼                            │
  ┌───────┐                        │
  │ polish │  LLM 润色              │
  └───┬───┘                        │
      │                            │
      ▼                            │
  ┌────────────────┐               │
  │  script.md     │               │
  │  @全局:男声    │               │
  │  @男声: 文本   │               │
  └───────┬────────┘               │
          │                        │
          ▼                        │
  ┌──────────────┐                 │
  │  tts.py      │  Edge TTS 配音   │
  │  解析@标记    │                 │
  └──────┬───────┘                 │
         │                         │
         ▼                         ▼
     full.mp3              materials/
         │                    │
         └────────┬───────────┘
                  │
                  ▼
          ┌──────────────┐
          │  composer.py │  FFmpeg 合成
          │  缩放+字幕    │
          └──────┬───────┘
                 │
         ┌───────┴───────┐
         ▼               ▼
    portrait.mp4    landscape.mp4
```

---

## 四种命令详解

### 1. `init` — 创建项目

```bash
s2v init 项目名 --style pv
```

**做了什么：**

```
项目名/
├── script.md              ← 风格对应的示例口播稿
├── materials/             ← 通用素材（横竖屏都用）
├── materials-portrait/    ← 竖屏专用素材
├── materials-landscape/   ← 横屏专用素材
├── audio/                 ← AI 配音（gen 时自动生成）
├── output/                ← 最终视频（gen 时自动生成）
└── config.json            ← 项目配置（分辨率/音色/字幕等）
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `项目名` | 必填，项目文件夹名称 | 任意名称 |
| `--style -s` | 风格预设 | `pv` / `ai` / `general` |

### 2. `polish` — AI 润色文稿

```bash
# 从命令行直接输入
s2v polish "我昨天去看了东莞陈老板的工厂屋顶..." --style pv -o 项目名

# 从文件读取
s2v polish ~/Desktop/口述记录.txt --style ai -o 项目名
```

**做了什么：**

```
原始文稿（你口述的经历）
    │
    ▼
┌─────────────────────┐
│  polish.py          │
│  发送给 LLM 润色    │
│  保留所有事实细节   │
│  添加开头钩子       │
│  口语化改写         │
│  结构化分段         │
│  添加结尾行动号召   │
└────────┬────────────┘
         │
         ▼
  项目名/script.md（自动备份旧版本）
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `text` | 原始文稿或文件路径 | 必填 |
| `--style -s` | 风格预设 | `general` |
| `--output -o` | 保存到哪个项目 | 不指定则打印到屏幕 |
| `--voice` | 覆盖默认音色 | 风格默认 |
| `--provider` | LLM 提供商 | `deepseek` |

**润色规则：**
- 人名、地名、数字、金额、日期**原封保留**，绝不编造
- 自动加开头钩子（争议/数据冲击/反常识/提问）
- 每句 15-25 字，长句自动拆短
- 总字数控制在 200-400 字（约 60-90 秒朗读）
- 结尾自动加行动号召

### 3. `gen` — 生成视频

```bash
# 只生成主方向（风格默认）
s2v gen 项目名

# 横竖屏双版本
s2v gen 项目名 --dual

# 只要竖屏 / 只要横屏
s2v gen 项目名 --portrait
s2v gen 项目名 --landscape
```

**做了什么：**

```
script.md ──→ tts.py ──→ full.mp3 ──┐
                                     │
materials/ ──────────────────────────┼──→ composer.py ──→ output/*.mp4
materials-portrait/ ─────────────────┤
materials-landscape/ ────────────────┘
```

**分步说明：**

| 步骤 | 做了什么 | 耗时 |
|------|---------|------|
| 读配置 | 加载 config.json | < 0.1s |
| 解析脚本 | 识别 @音色 标记，拆分段落 | < 0.1s |
| AI 配音 | Edge TTS 并发生成（3 段同时） | ~5-15s |
| 合并音频 | ffmpeg 合并为 full.mp3 | < 1s |
| 合成视频 | 素材缩放 + 配音 + 逐句字幕 + 编码 | ~5-15s |

**配音只生成一次**，横竖双版本共用同一份音频，不浪费时间。

| 参数 | 说明 |
|------|------|
| `project` | 项目目录路径 |
| `--dual` | 生成横屏+竖屏双版本 |
| `--portrait` | 仅生成竖屏 |
| `--landscape` | 仅生成横屏 |
| `--voice` | 覆盖默认音色 |
| `--rate` | 覆盖语速 |

### 4. `run` — 一键生成

```bash
s2v run "你的经历..." --style pv -n 项目名 -m 素材文件夹 --dual
```

**相当于自动执行：**

```
init → polish → 复制素材 → gen
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `text` | 原始文稿 | 必填 |
| `--style -s` | 风格 | `pv` |
| `--name -n` | 项目名 | 自动生成时间戳名 |
| `--media -m` | 素材文件夹路径 | 无 |
| `--dual` | 横竖屏双版本 | 仅主方向 |
| `--voice` | 覆盖音色 | 风格默认 |

---

## 项目结构

```
光伏合同避坑/                    ← 项目根目录
│
├── script.md                   ← 口播稿（你写的，或 AI 润色的）
│
├── materials/                  ← 通用素材，横竖屏都用
│   ├── 电站全景.jpg
│   ├── 施工细节.mp4
│   └── 业主合影.png
│
├── materials-portrait/         ← 竖屏专用（抖音/视频号）
│   └── 竖屏封面.jpg
│
├── materials-landscape/        ← 横屏专用（B站/YouTube）
│   └── 横屏封面.jpg
│
├── audio/                      ← AI 配音（gen 时自动生成）
│   ├── seg_000.mp3
│   ├── seg_001.mp3
│   └── full.mp3                ← 合并后的完整配音
│
├── output/                     ← 最终视频（gen 时自动生成）
│   ├── 光伏合同避坑_portrait_20260430_132714.mp4
│   └── 光伏合同避坑_landscape_20260430_132723.mp4
│
└── config.json                 ← 项目配置
```

**config.json 内容：**

```json
{
  "style": "pv",
  "primary_orientation": "portrait",
  "resolution": "1080x1920",
  "alt_resolution": "1920x1080",
  "fps": 30,
  "voice": "zh-CN-YunyangNeural",
  "rate": "+15%",
  "subtitle_font_size": 52,
  "subtitle_color": "white",
  "subtitle_position": "bottom",
  "subtitle_box": true,
  "created": "2026-04-30 13:15:16"
}
```

直接改 config.json 可以调整分辨率、音色、语速等。

---

## 口播稿格式

用 `@标记` 控制音色，空行分隔段落。

### 基础写法

```markdown
# 视频标题（可选，不影响输出）

@全局:男声

开头钩子，一句话抓注意力。开头最重要。

第二段展开讲问题和背景，2-3 句讲清楚。

第三段讲核心信息或真实案例。

第四段行动号召，引导互动。
```

### 多音色切换

```markdown
@全局:男声

@女声: 以一个提问开头，把观众抓住。

回答这个问题，男声讲核心观点。

@新闻男: 播报关键数据：25 年回本，年均收益 8%。

最后回到男声，给出行动建议。
```

### 支持的音色

| 别名 | 对应音色 | 风格 |
|------|---------|------|
| `女声` | zh-CN-XiaoxiaoNeural | 活泼女声 |
| `男声` | zh-CN-YunyangNeural | 成熟男声 |
| `新闻男` | zh-CN-YunjianNeural | 新闻播报 |
| `年轻男` | zh-CN-YunxiNeural | 年轻男生 |

---

## 横竖屏素材管理

### 素材优先级

```
生成竖屏视频时:
  ① materials-portrait/ 有文件？→ 用它的
  ② 没有？→ 用 materials/

生成横屏视频时:
  ① materials-landscape/ 有文件？→ 用它的
  ② 没有？→ 用 materials/
```

### 典型用法

```bash
# 场景 1：同一批素材横竖屏都适合
# → 全放 materials/，然后 s2v gen xxx --dual

# 场景 2：竖屏是近景特写，横屏是全景航拍
# → 竖屏照片放 materials-portrait/
# → 横屏照片放 materials-landscape/
# → s2v gen xxx --dual

# 场景 3：只发抖音
# → 素材全放 materials-portrait/
# → s2v gen xxx --portrait
```

### 支持的格式

| 类型 | 格式 |
|------|------|
| 图片 | .jpg .jpeg .png .webp .bmp |
| 视频 | .mp4 .mov .avi .mkv |

---

## 三种风格预设

| | pv（光伏） | ai（AI科技） | general（通用） |
|---|---|---|---|
| **主方向** | 竖屏 9:16 | 横屏 16:9 | 横屏 16:9 |
| **分辨率** | 1080x1920 | 1920x1080 | 1920x1080 |
| **音色** | 成熟男声 | 年轻男声 | 女声 |
| **语速** | +15% | +18% | +18% |
| **字幕** | 白字半透黑底 | 黄字描边 | 白字半透黑底 |
| **钩子风格** | 钱/合同陷阱/案例 | 圈内人视角/效率 | 通用吸引 |
| **适用平台** | 抖音/视频号 | B站/YouTube | 通用 |
| **AI 润色倾向** | 可信赖、行业老手 | 干货感、直接 | 自然口语化 |

---

## 真实使用场景

### 场景 A：光伏号 — 合同避坑系列

```bash
# 准备工作：导出手机里的合同截图（打码）、工地照片、电表数据截图

# 方式一：先口述再润色
s2v init 合同避坑-拆迁条款 --style pv
# 口述一段话，录成文字粘贴：
s2v polish "有个业主签了三年光伏租赁合同，去年厂房拆迁，发现合同里..." --style pv -o 合同避坑-拆迁条款
# 把竖屏素材放进去
cp ~/Desktop/合同对比图.png 合同避坑-拆迁条款/materials-portrait/
cp ~/Desktop/工地照片.jpg 合同避坑-拆迁条款/materials-portrait/
# 生成
s2v gen 合同避坑-拆迁条款 --dual

# 方式二：一键到底
s2v run "有个业主签了三年光伏租赁合同..." --style pv -n 合同避坑-拆迁条款 -m ~/Desktop/素材/ --dual
```

### 场景 B：AI 号 — 工具实测系列

```bash
# 横屏为主，发 B站/YouTube
s2v init cursor-真实体验 --style ai
# 写稿或润色
s2v polish "用了三个月Cursor，说点真话。最大的优点不是补全..." --style ai -o cursor-真实体验
# 放入录屏 GIF/截图
cp ~/Desktop/cursor截图*.png cursor-真实体验/materials-landscape/
# 生成
s2v gen cursor-真实体验 --landscape
```

### 场景 C：纯手动写稿（不用 AI 润色）

```bash
s2v init 电站巡检日记 --style pv
# 直接编辑 script.md 写稿
vim 电站巡检日记/script.md
# 放素材
cp ~/Desktop/巡检照片/*.jpg 电站巡检日记/materials-portrait/
# 生成
s2v gen 电站巡检日记 --dual
```

---

## FAQ

### Q: 不配 API Key 能用吗？
能。`gen` 命令不需要 API Key，只有 `polish` 润色需要。你可以手动写 `script.md`，直接用 `gen` 出片。

### Q: 一个视频多少钱？
配音走微软 Edge TTS，**完全免费**。只有润色调用 LLM，DeepSeek 约 ¥0.01/次。

### Q: 支持什么音色？
11 种中文音色：女声/男声/新闻男/年轻男，以及台湾女声、粤语等。

### Q: 能自己录配音吗？
可以。把 `audio/full.mp3` 替换为你自己的录音文件（同文件名），再跑一次 `gen` 就行。

### Q: 字体怎么换？
修改 `composer.py` 里 `_find_font()` 函数的候选字体路径，或在 config.json 里加 `font_path` 字段。

### Q: 视频太长/太短怎么办？
控制口播稿字数：
- 200 字 ≈ 40-50 秒
- 300 字 ≈ 60-70 秒
- 400 字 ≈ 80-90 秒
