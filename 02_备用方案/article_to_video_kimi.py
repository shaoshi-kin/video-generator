#!/usr/bin/env python3
"""
公众号文章 → 视频号短视频 自动化工具 (Kimi版本)
功能：
1. 读取markdown文章
2. Kimi AI分析提取最佳选题
3. 生成视频脚本
4. 可选：生成图片/视频提示词
5. 输出结构化JSON

使用方法：
    python article_to_video_kimi.py /path/to/article.md
    python article_to_video_kimi.py /path/to/article.md --output video_script.json
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
from openai import OpenAI


def robust_json_parse(content: str) -> dict:
    """
    健壮的JSON解析，处理各种格式问题
    """
    content = content.strip()

    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 去除Markdown代码块标记
    patterns = [
        r'^```json\s*(.*?)\s*```$',
        r'^```\s*(.*?)\s*```$',
        r'^`{3}json\s*([\s\S]*?)\s*`{3}$',
        r'^`{3}\s*([\s\S]*?)\s*`{3}$',
    ]

    for pattern in patterns:
        match = re.match(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 尝试去除开头和结尾的空白和换行后解析
    try:
        content_cleaned = content.strip().strip('`').strip()
        return json.loads(content_cleaned)
    except json.JSONDecodeError:
        pass

    # 如果还是失败，抛出异常
    raise ValueError(f"无法解析JSON内容: {content[:500]}...")


@dataclass
class VideoTopic:
    """视频选题"""
    title: str
    summary: str
    hook: str
    why_good: str
    difficulty: str  # easy/medium/hard
    suggested_duration: str  # 30s/60s/90s


@dataclass
class VideoScript:
    """完整视频脚本"""
    topic: str
    duration: str
    target_platform: str
    scenes: List[dict]
    full_script: str
    bmg_suggestion: str
    subtitle_tips: str


@dataclass
class VideoProject:
    """视频项目完整输出"""
    source_article: str
    extracted_topics: List[VideoTopic]
    selected_topic: VideoTopic
    script: VideoScript
    image_prompts: List[str]
    video_prompts: List[str]


class ArticleToVideo:
    """文章转视频核心类（Kimi版本）"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化

        Args:
            api_key: Kimi API Key，默认从环境变量 MOONSHOT_API_KEY 读取
        """
        self.client = OpenAI(
            api_key=api_key or os.environ.get("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1"
        )
        # Kimi模型选择：8k/32k/128k 根据文章长度自动选择
        self.model = "moonshot-v1-32k"  # 默认32k上下文足够处理大部分公众号文章

    def read_article(self, file_path: str) -> str:
        """读取markdown文章"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文章不存在: {file_path}")
        return path.read_text(encoding='utf-8')

    def extract_topics(self, article_content: str) -> List[VideoTopic]:
        """
        Kimi AI分析文章，提取适合视频的选题
        """
        # 根据文章长度选择合适的模型
        token_estimate = len(article_content) * 0.5  # 粗略估算token数
        if token_estimate > 30000:
            model = "moonshot-v1-128k"
        elif token_estimate > 6000:
            model = "moonshot-v1-32k"
        else:
            model = "moonshot-v1-8k"

        prompt = f"""你是一个专业的短视频内容策划师。请分析以下公众号文章，提取2-3个最适合做成短视频的选题。

文章原文：
```
{article_content}
```

要求：
1. 每个选题必须是文章中真实存在的内容点，不要编造
2. 优先选择有冲突、有数字、有情绪、有故事性的内容
3. 排除纯数据、太专业、太泛、时效性太短的题材
4. 每个选题需要包含：title, summary, hook, why_good, difficulty, suggested_duration
5. difficulty只能是: easy/medium/hard
6. suggested_duration只能是: 30s/60s/90s

请用JSON格式输出，必须严格遵循以下格式：
{{
  "topics": [
    {{
      "title": "标题（15字以内）",
      "summary": "摘要（30字以内）",
      "hook": "开头钩子（3秒吸引观众）",
      "why_good": "推荐理由",
      "difficulty": "easy",
      "suggested_duration": "30s"
    }}
  ]
}}"""

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = robust_json_parse(content)

        topics = []
        for t in data["topics"]:
            topics.append(VideoTopic(
                title=t["title"],
                summary=t["summary"],
                hook=t["hook"],
                why_good=t["why_good"],
                difficulty=t["difficulty"],
                suggested_duration=t["suggested_duration"]
            ))

        return topics

    def generate_script(self, article_content: str, topic: VideoTopic) -> VideoScript:
        """
        基于选定的选题，生成完整视频脚本
        """
        token_estimate = len(article_content) * 0.5
        if token_estimate > 30000:
            model = "moonshot-v1-128k"
        elif token_estimate > 6000:
            model = "moonshot-v1-32k"
        else:
            model = "moonshot-v1-8k"

        prompt = f"""你是一个专业的短视频编剧。请基于以下公众号文章和选定选题，生成一份完整的视频拍摄脚本。

文章原文：
```
{article_content}
```

选定选题：
- 标题：{topic.title}
- 摘要：{topic.summary}
- 开头钩子：{topic.hook}
- 建议时长：{topic.suggested_duration}

要求：
1. 脚本必须是{topic.suggested_duration}的短视频
2. 适合视频号9:16竖屏格式
3. 包含完整的分镜脚本，每个镜头包含：time（时间）、visual（画面内容）、audio（口播稿）、subtitle（字幕文案）
4. 口播稿要口语化，像朋友聊天，每句话不超过15字
5. 结尾要有引导关注的话术
6. 提供BGM建议和字幕制作建议

请用JSON格式输出，必须严格遵循以下格式：
{{
  "topic": "选题标题",
  "duration": "建议时长",
  "target_platform": "视频号",
  "scenes": [
    {{
      "time": "0-3s",
      "visual": "画面描述",
      "audio": "口播稿",
      "subtitle": "字幕文字"
    }}
  ],
  "full_script": "完整的口播稿（用于配音）",
  "bmg_suggestion": "BGM建议",
  "subtitle_tips": "字幕制作建议"
}}"""

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = robust_json_parse(content)

        return VideoScript(
            topic=data["topic"],
            duration=data["duration"],
            target_platform=data["target_platform"],
            scenes=data["scenes"],
            full_script=data["full_script"],
            bmg_suggestion=data["bmg_suggestion"],
            subtitle_tips=data["subtitle_tips"]
        )

    def generate_image_prompts(self, script: VideoScript) -> List[str]:
        """
        为每个分镜生成AI绘图提示词
        """
        model = "moonshot-v1-8k"  # 这个任务较短，用8k即可

        scenes_text = "\n".join([
            f"镜头{i+1} ({s['time']}): {s['visual']}"
            for i, s in enumerate(script.scenes)
        ])

        prompt = f"""你是AI绘画提示词专家。请为以下视频分镜生成Midjourney风格的绘图提示词。

视频分镜：
{scenes_text}

要求：
1. 为每个镜头生成一个英文提示词
2. 提示词要包含：主体、场景、风格、光线、色彩
3. 使用电影级画质风格，适合财经/新闻类短视频
4. 统一风格，保持画面一致性
5. 每个提示词长度控制在80词以内

请用JSON格式输出，格式如下：
{{
  "prompts": [
    "镜头1的Midjourney提示词",
    "镜头2的Midjourney提示词",
    ...
  ]
}}"""

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = robust_json_parse(content)
        return data["prompts"]

    def generate_video_prompts(self, script: VideoScript) -> List[str]:
        """
        为关键镜头生成图生视频提示词
        """
        model = "moonshot-v1-8k"

        prompt = f"""你是AI视频生成提示词专家。请为以下视频脚本中的关键镜头（开头、转折、结尾）生成图生视频提示词（Runway Gen-3或Luma风格）。

视频脚本：{script.topic}
时长：{script.duration}

关键场景：
1. 开头场景（0-3s）：{script.scenes[0]['visual'] if script.scenes else 'N/A'}
2. 转折场景（中间）：{script.scenes[len(script.scenes)//2]['visual'] if len(script.scenes) > 2 else 'N/A'}
3. 结尾场景（最后）：{script.scenes[-1]['visual'] if script.scenes else 'N/A'}

要求：
1. 生成3个视频提示词，分别对应：开头、转折、结尾
2. 提示词描述画面运动、镜头运动、氛围变化
3. 使用英文，简洁明了
4. 每个提示词控制在30词以内

请用JSON格式输出，格式如下：
{{
  "prompts": [
    "开头镜头的视频提示词",
    "转折镜头的视频提示词",
    "结尾镜头的视频提示词"
  ]
}}"""

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        data = robust_json_parse(content)
        return data["prompts"]

    def process(self, article_path: str, select_topic: int = 0) -> VideoProject:
        """
        完整处理流程

        Args:
            article_path: 文章文件路径
            select_topic: 选择第几个选题（0-based），默认0（第一个）

        Returns:
            VideoProject: 完整的视频项目数据
        """
        print(f"📖 正在读取文章: {article_path}")
        article_content = self.read_article(article_path)

        print("🤖 Kimi正在分析文章，提取选题...")
        topics = self.extract_topics(article_content)

        if not topics:
            raise ValueError("未能提取到有效选题")

        print(f"\n✅ 找到 {len(topics)} 个候选选题:")
        for i, t in enumerate(topics):
            marker = "⭐" if i == select_topic else "  "
            print(f"{marker} [{i}] {t.title} ({t.suggested_duration}, 难度: {t.difficulty})")
            print(f"      钩子: {t.hook}")
            print(f"      推荐理由: {t.why_good}")
            print()

        selected = topics[select_topic]
        print(f"🎯 已选择选题: {selected.title}")

        print("📝 正在生成视频脚本...")
        script = self.generate_script(article_content, selected)

        print("🎨 正在生成AI绘图提示词...")
        image_prompts = self.generate_image_prompts(script)

        print("🎬 正在生成图生视频提示词...")
        video_prompts = self.generate_video_prompts(script)

        project = VideoProject(
            source_article=article_path,
            extracted_topics=topics,
            selected_topic=selected,
            script=script,
            image_prompts=image_prompts,
            video_prompts=video_prompts
        )

        return project


def video_project_to_dict(project: VideoProject) -> dict:
    """将VideoProject转换为可JSON序列化的字典"""
    return {
        "source_article": project.source_article,
        "extracted_topics": [
            {
                "title": t.title,
                "summary": t.summary,
                "hook": t.hook,
                "why_good": t.why_good,
                "difficulty": t.difficulty,
                "suggested_duration": t.suggested_duration
            }
            for t in project.extracted_topics
        ],
        "selected_topic": {
            "title": project.selected_topic.title,
            "summary": project.selected_topic.summary,
            "hook": project.selected_topic.hook,
            "why_good": project.selected_topic.why_good,
            "difficulty": project.selected_topic.difficulty,
            "suggested_duration": project.selected_topic.suggested_duration
        },
        "script": {
            "topic": project.script.topic,
            "duration": project.script.duration,
            "target_platform": project.script.target_platform,
            "scenes": project.script.scenes,
            "full_script": project.script.full_script,
            "bmg_suggestion": project.script.bmg_suggestion,
            "subtitle_tips": project.script.subtitle_tips
        },
        "image_prompts": project.image_prompts,
        "video_prompts": project.video_prompts
    }


def main():
    parser = argparse.ArgumentParser(
        description="公众号文章 → 视频号短视频 自动化工具 (Kimi版本)"
    )
    parser.add_argument(
        "article",
        help="公众号文章Markdown文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        default="video_project_kimi.json",
        help="输出文件路径 (默认: video_project_kimi.json)"
    )
    parser.add_argument(
        "-t", "--topic",
        type=int,
        default=0,
        help="选择第几个选题 (0-based，默认0)"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("MOONSHOT_API_KEY"),
        help="Kimi API Key (默认从环境变量MOONSHOT_API_KEY读取)"
    )

    args = parser.parse_args()

    if not args.api_key:
        print("❌ 错误: 需要提供Kimi API Key")
        print("可以通过以下方式提供:")
        print("  1. 环境变量: export MOONSHOT_API_KEY='your-key'")
        print("  2. 命令行参数: --api-key 'your-key'")
        print("\n获取Kimi API Key: https://platform.moonshot.cn")
        sys.exit(1)

    try:
        converter = ArticleToVideo(api_key=args.api_key)
        project = converter.process(args.article, select_topic=args.topic)

        # 保存为JSON
        output_path = Path(args.output)
        output_data = video_project_to_dict(project)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 完成! 项目已保存到: {output_path.absolute()}")
        print(f"\n📋 生成的内容摘要:")
        print(f"   - 选题: {project.selected_topic.title}")
        print(f"   - 时长: {project.script.duration}")
        print(f"   - 分镜数: {len(project.script.scenes)}")
        print(f"   - AI绘图提示词: {len(project.image_prompts)}个")
        print(f"   - 视频生成提示词: {len(project.video_prompts)}个")

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
