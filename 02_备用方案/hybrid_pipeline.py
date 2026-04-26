#!/usr/bin/env python3
"""
混合方案视频流水线
- 日常内容：Replicate + Pika API（全自动）
- 精品内容：Midjourney + Runway（人工操作）

使用方法:
    python hybrid_pipeline.py article.md --mode auto    # API全自动
    python hybrid_pipeline.py article.md --mode manual  # 生成人工方案
"""

import os
import sys
import json
import time
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional

# 可选依赖，未安装时给出提示
try:
    from openai import OpenAI
except ImportError:
    print("❌ 请先安装依赖: pip3 install openai")
    sys.exit(1)


def check_replicate():
    """检查Replicate是否安装"""
    try:
        import replicate
        return True
    except ImportError:
        return False


class HybridVideoPipeline:
    """混合方案视频流水线"""

    def __init__(self, kimi_key: str, replicate_key: Optional[str] = None, pika_key: Optional[str] = None):
        # Kimi客户端
        self.kimi = OpenAI(api_key=kimi_key, base_url="https://api.moonshot.cn/v1")

        # Replicate（可选）
        self.replicate_key = replicate_key
        self.replicate = None
        if replicate_key and check_replicate():
            import replicate
            self.replicate = replicate.Client(api_token=replicate_key)

        # Pika（可选）
        self.pika_key = pika_key

        self.today = datetime.now().strftime("%Y%m%d")
        self.project_dir = None

    def read_article(self, file_path: str) -> str:
        """读取文章"""
        return Path(file_path).read_text(encoding='utf-8')

    def generate_video_plan(self, article_content: str) -> dict:
        """生成视频方案"""

        prompt = f"""分析以下文章，生成视频制作方案。

文章：
```
{article_content}
```

请输出JSON格式：
{{
  "mode_recommendation": "auto 或 manual",
  "reason": "推荐理由",
  "topic": {{
    "title": "视频标题",
    "hook": "开头钩子",
    "duration": "60s"
  }},
  "scenes": [
    {{
      "time": "0-5s",
      "visual": "画面描述",
      "audio": "口播稿",
      "subtitle": "字幕",
      "replicate_prompt": "英文提示词，用于FLUX.1",
      "pika_prompt": "英文视频提示词",
      "quality": "standard 或 high"
    }}
  ],
  "mj_alternative": [
    "Midjourney提示词1",
    "Midjourney提示词2"
  ]
}}"""

        response = self.kimi.chat.completions.create(
            model="moonshot-v1-32k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def generate_images_replicate(self, scenes: list, project_dir: Path) -> list:
        """使用Replicate生成图片（全自动）"""

        if not self.replicate:
            print("❌ Replicate未配置，跳过图片生成")
            return []

        print("\n🎨 使用Replicate生成图片...")
        images_dir = project_dir / "01_images"
        images_dir.mkdir(exist_ok=True)

        generated = []
        for i, scene in enumerate(scenes, 1):
            prompt = scene.get('replicate_prompt', '')
            if not prompt:
                continue

            print(f"  生成图片 {i}/{len(scenes)}...")

            try:
                # 使用FLUX.1 [dev]模型
                output = self.replicate.run(
                    "black-forest-labs/flux-dev",
                    input={
                        "prompt": prompt,
                        "aspect_ratio": "9:16",
                        "output_format": "png",
                        "num_inference_steps": 50
                    }
                )

                # 下载图片
                import urllib.request
                img_path = images_dir / f"scene_{i:02d}.png"
                urllib.request.urlretrieve(output[0], img_path)
                generated.append(img_path)
                print(f"    ✅ 已保存: {img_path}")

                time.sleep(1)  # 避免限流

            except Exception as e:
                print(f"    ❌ 失败: {e}")

        return generated

    def generate_videos_pika(self, scenes: list, project_dir: Path) -> list:
        """使用Pika API生成视频（全自动）"""

        if not self.pika_key:
            print("❌ Pika未配置，跳过视频生成")
            return []

        print("\n🎬 使用Pika生成视频...")
        videos_dir = project_dir / "02_videos"
        videos_dir.mkdir(exist_ok=True)

        # Pika API调用（需要requests）
        try:
            import requests
        except ImportError:
            print("❌ 请先安装requests: pip3 install requests")
            return []

        generated = []
        for i, scene in enumerate(scenes, 1):
            if not scene.get('pika_prompt'):
                continue

            print(f"  生成视频 {i}...")

            # 找到对应的图片
            img_path = project_dir / "01_images" / f"scene_{i:02d}.png"
            if not img_path.exists():
                print(f"    ⚠️  跳过: 图片不存在")
                continue

            try:
                # Pika API调用
                url = "https://api.pika.art/v1/generations"
                headers = {
                    "Authorization": f"Bearer {self.pika_key}",
                    "Content-Type": "application/json"
                }

                # 先上传图片获取URL（简化版，实际需要先上传）
                # 这里使用base64或先上传到图床
                data = {
                    "prompt": scene['pika_prompt'],
                    "image": str(img_path),  # 实际需要URL
                    "motion": 2,  # 运动强度 1-5
                    "duration": 4
                }

                response = requests.post(url, headers=headers, json=data)

                if response.status_code == 200:
                    result = response.json()
                    video_url = result.get('video_url')

                    # 下载视频
                    video_path = videos_dir / f"clip_{i:02d}.mp4"
                    urllib.request.urlretrieve(video_url, video_path)
                    generated.append(video_path)
                    print(f"    ✅ 已保存: {video_path}")
                else:
                    print(f"    ❌ API错误: {response.text}")

                time.sleep(2)  # 避免限流

            except Exception as e:
                print(f"    ❌ 失败: {e}")

        return generated

    def create_manual_package(self, data: dict, project_dir: Path):
        """创建人工操作包（Midjourney + Runway）"""

        print("\n📦 创建人工操作包...")

        # 1. Midjourney命令文件
        mj_file = project_dir / "midjourney_commands.txt"
        with open(mj_file, 'w', encoding='utf-8') as f:
            f.write("# Midjourney 命令\n\n")
            for i, prompt in enumerate(data.get('mj_alternative', []), 1):
                f.write(f"\n### 镜头{i}\n/imagine prompt: {prompt} --ar 9:16 --v 6.0 --s 750\n")

        # 2. 操作指南
        guide_file = project_dir / "操作指南.md"
        with open(guide_file, 'w', encoding='utf-8') as f:
            f.write(f"""# 视频制作指南

## 项目信息
- 主题: {data['topic']['title']}
- 推荐模式: 人工精品
- 原因: {data['reason']}

## 步骤

### 1. Midjourney生成图片
1. 打开 Discord
2. 复制 `midjourney_commands.txt` 中的命令
3. 下载生成的图片到 `01_images/` 文件夹

### 2. Runway生成视频
1. 打开 https://runwayml.com
2. 上传图片
3. 使用以下提示词：
""")
            for i, scene in enumerate(data['scenes'], 1):
                f.write(f"\n**镜头{i}**: {scene.get('pika_prompt', 'N/A')}\n")

            f.write("""
### 3. 剪映剪辑
按 `project_data.json` 中的场景顺序剪辑
""")

        print(f"  ✅ 已创建: {mj_file.name}")
        print(f"  ✅ 已创建: {guide_file.name}")

        # 打开相关网页
        webbrowser.open("https://discord.com/channels/@me")
        webbrowser.open("https://runwayml.com")

    def run(self, article_path: str, mode: str = "auto"):
        """执行流水线"""

        print("="*60)
        print(f"🎬 混合方案视频流水线 (模式: {mode})")
        print("="*60)

        # 1. 读取文章
        print(f"\n📖 读取文章: {article_path}")
        article = self.read_article(article_path)

        # 2. 生成方案
        print("\n🤖 Kimi正在生成视频方案...")
        data = self.generate_video_plan(article)

        recommended_mode = data.get('mode_recommendation', 'manual')
        reason = data.get('reason', '')

        print(f"\n💡 AI推荐模式: {recommended_mode}")
        print(f"   原因: {reason}")

        # 使用AI推荐或用户指定
        final_mode = mode if mode != "auto" else recommended_mode

        # 3. 创建项目
        article_name = Path(article_path).stem
        self.project_dir = Path(f"projects/{self.today}_{article_name}_{final_mode}")
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # 保存数据
        json_path = self.project_dir / "project_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"\n📁 项目已创建: {self.project_dir}")

        # 4. 根据模式执行
        if final_mode == "auto":
            # API全自动模式
            print("\n🚀 启动API全自动模式...")

            if not self.replicate or not self.pika_key:
                print("\n⚠️  API密钥未配置，将只生成方案文件")
                print("    如需全自动，请配置：")
                print("    - REPLICATE_API_TOKEN")
                print("    - PIKA_API_KEY")

            # 生成图片
            images = self.generate_images_replicate(data['scenes'], self.project_dir)
            print(f"\n  ✅ 生成 {len(images)} 张图片")

            # 生成视频
            if images:
                videos = self.generate_videos_pika(data['scenes'], self.project_dir)
                print(f"  ✅ 生成 {len(videos)} 个视频片段")

            # 成本统计
            cost_estimate = len(data['scenes']) * 0.03 + len([s for s in data['scenes'] if s.get('pika_prompt')]) * 0.6
            print(f"\n💰 预估成本: ${cost_estimate:.2f}")

        else:
            # 人工精品模式
            self.create_manual_package(data, self.project_dir)
            print("\n✅ 人工操作包已创建")
            print("   已自动打开Midjourney和Runway网页")

        # 5. 完成总结
        print("\n" + "="*60)
        print("✅ 方案准备完成！")
        print("="*60)
        print(f"\n📂 项目位置: {self.project_dir}")
        print(f"\n📋 文件清单:")
        for f in self.project_dir.iterdir():
            print(f"   - {f.name}")

        return self.project_dir


def main():
    parser = argparse.ArgumentParser(description="混合方案视频流水线")
    parser.add_argument("article", help="文章文件路径")
    parser.add_argument("--mode", choices=["auto", "manual", "smart"], default="smart",
                      help="模式: auto=API全自动, manual=人工方案, smart=AI推荐(默认)")
    parser.add_argument("--kimi-key", default=os.environ.get("MOONSHOT_API_KEY"),
                      help="Kimi API Key")
    parser.add_argument("--replicate-key", default=os.environ.get("REPLICATE_API_TOKEN"),
                      help="Replicate API Token")
    parser.add_argument("--pika-key", default=os.environ.get("PIKA_API_KEY"),
                      help="Pika API Key")

    args = parser.parse_args()

    # 检查必需参数
    if not args.kimi_key:
        print("❌ 错误: 需要提供 MOONSHOT_API_KEY")
        print("   export MOONSHOT_API_KEY='your-key'")
        sys.exit(1)

    # 创建流水线
    pipeline = HybridVideoPipeline(
        kimi_key=args.kimi_key,
        replicate_key=args.replicate_key,
        pika_key=args.pika_key
    )

    # 运行
    pipeline.run(args.article, mode=args.mode)


if __name__ == "__main__":
    main()
