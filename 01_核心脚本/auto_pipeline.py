#!/usr/bin/env python3
"""
公众号文章 → 视频 半自动流水线
最大化减少人工操作，自动生成所有准备文件
"""

import os
import sys
import json
import subprocess
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from openai import OpenAI


class AutoVideoPipeline:
    """自动化视频生成流水线"""

    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.moonshot.cn/v1"
        )
        self.today = datetime.now().strftime("%Y%m%d")
        self.project_dir = None

    def read_article(self, file_path: str) -> str:
        """读取文章"""
        return Path(file_path).read_text(encoding='utf-8')

    def generate_all(self, article_content: str) -> dict:
        """一次性生成所有内容"""

        prompt = f"""你是一个自动化视频生成助手。请分析以下文章，一次性输出完整的视频制作方案。

文章：
```
{article_content}
```

请用JSON格式输出，包含：
1. 最佳选题（1个）
2. 完整分镜脚本（6-8个镜头）
3. Midjourney绘图提示词（每个镜头一个）
4. Runway视频生成提示词（3个关键镜头）
5. 剪映项目配置建议

格式：
{{
  "topic": {{
    "title": "标题",
    "hook": "开头钩子",
    "duration": "60s",
    "style": "财经快讯"
  }},
  "scenes": [
    {{
      "time": "0-3s",
      "type": "hook",
      "visual": "画面描述",
      "audio": "口播稿",
      "subtitle": "字幕文字",
      "mj_prompt": "Midjourney英文提示词",
      "need_video": true
    }}
  ],
  "runway_prompts": [
    "镜头1的视频提示词",
    "镜头2的视频提示词",
    "镜头3的视频提示词"
  ],
  "workflow": {{
    "mj_commands": ["/imagine prompt:...", "/imagine prompt:..."],
    "editing_order": ["步骤1", "步骤2"],
    "bgm_keywords": "紧张 电子乐"
  }}
}}"""

        response = self.client.chat.completions.create(
            model="moonshot-v1-32k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def create_project(self, article_path: str, data: dict) -> Path:
        """创建项目文件夹结构"""

        # 创建项目目录
        article_name = Path(article_path).stem
        self.project_dir = Path(f"projects/{self.today}_{article_name}")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (self.project_dir / "01_images").mkdir(exist_ok=True)
        (self.project_dir / "02_videos").mkdir(exist_ok=True)
        (self.project_dir / "03_audio").mkdir(exist_ok=True)
        (self.project_dir / "04_final").mkdir(exist_ok=True)

        return self.project_dir

    def generate_mj_commands(self, scenes: list) -> str:
        """生成Midjourney批量命令文件"""

        commands = []
        for i, scene in enumerate(scenes, 1):
            prompt = scene.get('mj_prompt', '')
            if prompt:
                # 添加Midjourney参数优化
                prompt_full = f"{prompt} --ar 9:16 --v 6.0 --s 750"
                commands.append(f"\n### 镜头{i}: {scene.get('time', '')}\n/imagine prompt: {prompt_full}\n")

        return "\n".join(commands)

    def generate_runway_prompts(self, prompts: list) -> str:
        """生成Runway提示词文档"""

        content = "# Runway Gen-3 视频生成提示词\n\n"
        content += "## 使用步骤\n"
        content += "1. 打开 https://runwayml.com\n"
        content += "2. 选择 Gen-3 Alpha\n"
        content += "3. 上传对应图片\n"
        content += "4. 粘贴下方提示词\n"
        content += "5. Motion Bucket: 50, Duration: 4s\n\n"

        for i, prompt in enumerate(prompts, 1):
            content += f"\n### 视频片段{i}\n"
            content += f"```\n{prompt}\n```\n"

        return content

    def generate_jianying_guide(self, data: dict) -> str:
        """生成剪映操作指南"""

        topic = data.get('topic', {})
        scenes = data.get('scenes', [])

        guide = f"""# 剪映剪辑指南

## 项目信息
- 主题: {topic.get('title', '')}
- 时长: {topic.get('duration', '')}
- 风格: {topic.get('style', '')}

## 剪辑步骤

### 1. 新建项目
- 比例: 9:16 (1080x1920)
- 帧率: 30fps

### 2. 导入素材
将以下文件拖入素材库:
"""

        for i, scene in enumerate(scenes, 1):
            guide += f"- scene_{i:02d}.png (或 .mp4)\n"

        guide += """
### 3. 按顺序排列时间轴
"""

        for scene in scenes:
            guide += f"\n**{scene.get('time', '')}** - {scene.get('type', '')}\n"
            guide += f"- 画面: {scene.get('visual', '')[:50]}...\n"
            guide += f"- 口播: {scene.get('audio', '')[:50]}...\n"
            guide += f"- 字幕: {scene.get('subtitle', '')}\n"

        guide += """
### 4. 添加配音
"""
        # 拼接所有口播稿
        full_script = "\n".join([s.get('audio', '') for s in scenes])
        guide += f"完整文案:\n```\n{full_script}\n```\n"

        guide += """
### 5. 添加BGM
搜索关键词: """ + data.get('workflow', {}).get('bgm_keywords', '紧张 电子乐') + """
音量调整至: 20-30%

### 6. 导出设置
- 分辨率: 1080P
- 帧率: 30fps
- 格式: MP4
- 文件名: final_video.mp4
"""

        return guide

    def open_browser_tabs(self):
        """自动打开需要的网页"""

        urls = [
            ("Midjourney", "https://discord.com/channels/@me"),
            ("Runway", "https://runwayml.com"),
            ("剪映", "https://www.capcut.cn"),
        ]

        print("\n🌐 正在打开工具网页...")
        for name, url in urls:
            print(f"  打开 {name}: {url}")
            webbrowser.open(url)

    def run(self, article_path: str):
        """执行完整流水线"""

        print("="*60)
        print("🎬 公众号文章 → 视频 自动流水线")
        print("="*60)

        # 1. 读取文章
        print(f"\n📖 读取文章: {article_path}")
        article = self.read_article(article_path)

        # 2. 生成所有内容
        print("\n🤖 Kimi正在生成完整方案...")
        data = self.generate_all(article)

        # 3. 创建项目
        project_dir = self.create_project(article_path, data)
        print(f"\n📁 项目已创建: {project_dir}")

        # 4. 保存数据文件
        json_path = project_dir / "project_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 5. 生成Midjourney命令文件
        mj_path = project_dir / "midjourney_commands.txt"
        mj_content = self.generate_mj_commands(data.get('scenes', []))
        with open(mj_path, 'w', encoding='utf-8') as f:
            f.write(mj_content)

        # 6. 生成Runway提示词文件
        runway_path = project_dir / "runway_prompts.md"
        runway_content = self.generate_runway_prompts(data.get('runway_prompts', []))
        with open(runway_path, 'w', encoding='utf-8') as f:
            f.write(runway_content)

        # 7. 生成剪映指南
        jianying_path = project_dir / "剪映剪辑指南.md"
        jianying_content = self.generate_jianying_guide(data)
        with open(jianying_path, 'w', encoding='utf-8') as f:
            f.write(jianying_content)

        # 8. 打开浏览器
        self.open_browser_tabs()

        # 9. 打印总结
        print("\n" + "="*60)
        print("✅ 自动化准备完成！")
        print("="*60)
        print(f"\n📂 项目位置: {project_dir}")
        print(f"\n📋 生成的文件:")
        print(f"  1. {json_path.name} - 完整数据")
        print(f"  2. {mj_path.name} - Midjourney命令（复制到Discord执行）")
        print(f"  3. {runway_path.name} - Runway提示词")
        print(f"  4. {jianying_path.name} - 剪辑指南")

        print(f"\n🎯 接下来的人工步骤:")
        print(f"  1. 在Discord执行Midjourney命令（已自动打开）")
        print(f"  2. 下载图片到 {project_dir}/01_images/")
        print(f"  3. 在Runway生成视频（已自动打开）")
        print(f"  4. 下载视频到 {project_dir}/02_videos/")
        print(f"  5. 按剪映指南剪辑（已自动打开剪映网页）")

        print(f"\n💡 提示:")
        print(f"  - 所有提示词已准备好，直接复制粘贴即可")
        print(f"  - 素材生成后，剪映指南会告诉你怎么剪")

        # 尝试用系统通知
        try:
            if sys.platform == "darwin":  # macOS
                os.system(f"""
                osascript -e 'display notification "项目准备完成！" with title "视频流水线"'
                """)
        except:
            pass

        return project_dir


def main():
    import argparse

    parser = argparse.ArgumentParser(description="自动化视频生成流水线")
    parser.add_argument("article", help="文章文件路径")
    parser.add_argument("--api-key", default=os.environ.get("MOONSHOT_API_KEY"),
                      help="Kimi API Key")

    args = parser.parse_args()

    if not args.api_key:
        print("❌ 错误: 需要提供 MOONSHOT_API_KEY")
        sys.exit(1)

    pipeline = AutoVideoPipeline(args.api_key)
    pipeline.run(args.article)


if __name__ == "__main__":
    main()
