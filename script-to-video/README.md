# script-to-video

> 素材+配音 → 口播视频，光伏和 AI 自媒体通用

## 解决的问题

你不会写稿、不会配音、不会剪视频，但你有真实的项目照片和经验。

把照片丢进 `materials/`，把你的经历说一遍——AI 帮你润色成口播稿、自动配音、合成竖屏视频。

## 安装

```bash
pip install -r requirements.txt
# 系统需要安装 ffmpeg: brew install ffmpeg
```

需要配置 LLM API Key（润色功能需要）：

```bash
export DEEPSEEK_API_KEY="sk-your-key"   # 推荐，便宜
# 或
export KIMI_API_KEY="sk-your-key"
```

## 快速开始

### 方式一：一键生成

```bash
python3 main.py run "今天去看了惠州陈老板的工厂屋顶，800平..." --style pv --name my-video --media ~/Desktop/photos/
```

### 方式二：分步操作

```bash
# 1. 创建项目
python3 main.py init my-video --style pv

# 2. 编辑口播稿（或用 AI 润色）
python3 main.py polish "你的经历..." --style pv -o my-video

# 3. 把照片/视频放入 my-video/materials/

# 4. 生成视频
python3 main.py gen my-video
```

## 三种风格

| 风格 | 方向 | 音色 | 适用 |
|------|------|------|------|
| `pv` | 竖屏 9:16 | 成熟男声 | 光伏/新能源/工地现场 |
| `ai` | 横屏 16:9 | 年轻男声 | AI工具/编程/科技 |
| `general` | 横屏 16:9 | 女声 | 通用 |

## 项目结构

```
my-video/
├── script.md         # 口播稿（支持 @全局:男声 @男声: 标记）
├── materials/        # 照片/视频素材
├── audio/            # AI 配音（自动生成）
├── output/           # 最终视频（自动生成）
└── config.json       # 项目配置
```

## 口播稿格式

```markdown
# 视频标题

@全局:男声

第一段：开头钩子，一句话抓注意力。

第二段：展开问题，2-3句讲清楚。

第三段：核心信息或案例。

第四段：行动号召，引导互动。
```

## 依赖

- Python 3.8+
- edge-tts（微软免费 TTS，11 种中文音色）
- ffmpeg（视频合成）
- requests（调 LLM API）
