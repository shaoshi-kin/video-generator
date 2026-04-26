# 视频自动化合成工具 Pro 版

## 功能特性

- ✅ 自动识别 03_videos 视频素材或 03_audio + 图片
- ✅ 4种字幕样式（新闻/YouTube/极简/抖音）
- ✅ 12种转场效果（淡入淡出/滑动/缩放等）
- ✅ 片头片尾模板支持
- ✅ 背景音乐自动循环
- ✅ 批量处理多个项目
- ✅ Ken Burns 图片动画效果

## 快速开始

### 1. 基础用法（自动识别素材）

```bash
python video_generator_pro.py --project 项目路径
```

### 2. 使用 03_videos 里的视频素材

将视频放入项目文件夹：
```
projects/2026-04-26_article/
├── 03_videos/
│   ├── scene_01.mp4    # 你的实拍素材
│   ├── scene_02.mp4
│   └── scene_03.mov
└── plan.json
```

运行：
```bash
python video_generator_pro.py -p projects/2026-04-26_article
```

### 3. 完整功能示例

```bash
python video_generator_pro.py -p projects/2026-04-26_article \
    --subtitle \
    --subtitle-style news \
    --transition fade \
    --intro templates/intro.mp4 \
    --outro templates/outro.mp4 \
    --bgm music/background.mp3 \
    --bgm-volume 0.2
```

## 字幕样式

| 样式 | 特点 | 适用场景 |
|------|------|----------|
| `news` | 白字黑底 | 新闻播报、严肃内容 |
| `youtube` | 黄字黑边 | 短视频、Vlog |
| `minimal` | 纯白文字 | 极简风格、访谈 |
| `tiktok` | 大字居中 | 抖音/快手风格 |

## 转场效果

| 效果 | 说明 |
|------|------|
| `fade` | 淡入淡出 |
| `wipeleft` | 向左擦除 |
| `wiperight` | 向右擦除 |
| `slideleft` | 向左滑动 |
| `slideright` | 向右滑动 |
| `zoomin` | 放大进入 |
| `zoomout` | 缩小退出 |
| `none` | 无转场 |

## 批量处理

```bash
# 处理所有项目
python video_generator_pro.py --batch projects/*

# 处理指定项目列表
python video_generator_pro.py --batch project1 project2 project3
```

## 完整工作流

```bash
# 1. 准备素材
# 将视频放入 03_videos/ 或图片放入 02_manual_images/

# 2. 准备片头片尾（可选）
# 创建 templates/intro.mp4 和 templates/outro.mp4

# 3. 生成视频
python video_generator_pro.py -p projects/2026-04-26_article \
    --subtitle \
    --subtitle-style news \
    --transition fade

# 4. 查看输出
open projects/2026-04-26_article/04_final/final_video_pro.mp4
```

## 输出文件

生成文件位置：`项目路径/04_final/final_video_pro.mp4`
