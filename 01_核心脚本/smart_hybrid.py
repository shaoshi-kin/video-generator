#!/usr/bin/env python3
"""
智能混合方案 - 免费额度 + 人工
自动管理Replicate免费额度，额度用完自动切换人工方案

使用方法:
    export MOONSHOT_API_KEY='Kimi Key'
    export REPLICATE_API_TOKEN='Replicate Token'
    python3 smart_hybrid.py article.md
"""

import os
import sys
import json
import re
import time
import argparse
import requests
import webbrowser
from pathlib import Path
from datetime import datetime, date
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict


try:
    from openai import OpenAI
except ImportError:
    print("❌ 请安装依赖: pip3 install openai requests")
    sys.exit(1)


def robust_json_parse(content: str) -> dict:
    """健壮的JSON解析"""
    content = content.strip()

    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 去除Markdown代码块
    patterns = [
        r'^```json\s*(.*?)\s*```$',
        r'^```\s*(.*?)\s*```$',
    ]

    for pattern in patterns:
        match = re.match(pattern, content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                continue

    # 尝试清理后解析
    try:
        content_cleaned = content.strip().strip('`').strip()
        return json.loads(content_cleaned)
    except json.JSONDecodeError:
        pass

    raise ValueError(f"无法解析JSON: {content[:500]}")


@dataclass
class QuotaStatus:
    """配额状态"""
    date: str
    api_used: int
    api_limit: int
    manual_used: int
    remaining_api: int

    @property
    def api_available(self) -> bool:
        return self.api_used < self.api_limit


class SmartHybridPipeline:
    """智能混合流水线"""

    def __init__(self, kimi_key: str, replicate_key: Optional[str] = None):
        self.kimi = OpenAI(api_key=kimi_key, base_url="https://api.moonshot.cn/v1")
        self.replicate_key = replicate_key
        self.quota_file = Path("quota_tracker.json")
        self.today = date.today().isoformat()

    def load_quota(self) -> QuotaStatus:
        """加载今日配额"""
        if self.quota_file.exists():
            data = json.loads(self.quota_file.read_text())
            # 检查是否是今天的数据
            if data.get("date") == self.today:
                return QuotaStatus(**data)

        # 新的一天，重置配额
        return QuotaStatus(
            date=self.today,
            api_used=0,
            api_limit=8,  # Replicate免费额度约8张/天
            manual_used=0,
            remaining_api=8
        )

    def save_quota(self, quota: QuotaStatus):
        """保存配额状态"""
        self.quota_file.write_text(json.dumps(asdict(quota), indent=2))

    def generate_video_plan(self, article_content: str) -> dict:
        """生成视频方案，并标记哪些用API，哪些用人工"""

        quota = self.load_quota()
        remaining_api = quota.remaining_api

        # 构建prompt，避免f-string与大括号冲突
        json_template = """{
  "topic": {
    "title": "视频标题",
    "hook": "开头钩子",
    "priority": "high/medium/low"
  },
  "scenes": [
    {
      "index": 1,
      "time": "0-3s",
      "type": "hook/data/story/ending",
      "visual": "画面描述",
      "audio": "口播稿",
      "subtitle": "字幕",
      "importance": "critical/important/normal",
      "generate_method": "api 或 manual",
      "reason": "为什么选择这种方式",
      "api_prompt": "Replicate FLUX.1提示词（英文）",
      "mj_prompt": "Midjourney提示词（英文）"
    }
  ],
  "api_plan": {
    "total_scenes": 6,
    "api_scenes": [{"index": 1, "reason": "..."}],
    "manual_scenes": [{"index": 2, "reason": "..."}],
    "estimated_api_cost": "$0.00"
  },
  "workflow": {
    "step1": "先生成API图片（全自动）",
    "step2": "再制作人工图片（Midjourney）",
    "step3": "统一收集素材后剪辑"
  }
}"""

        prompt = f"""分析以下文章，生成视频制作方案。

文章：
```
{article_content}
```

重要信息：
- 今日API免费额度剩余: {remaining_api} 张图片
- 总共需要6张图片

请分析内容重要性，决定哪些图片用API生成（高质量），哪些用人工Midjourney。

输出JSON格式，参考如下：
{json_template}
    "estimated_api_cost": "$0.00"
  }},
  "workflow": {{
    "step1": "先生成API图片（全自动）",
    "step2": "再制作人工图片（Midjourney）",
    "step3": "统一收集素材后剪辑"
  }}
}}"""

        response = self.kimi.chat.completions.create(
            model="moonshot-v1-32k",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=8000
        )

        return robust_json_parse(response.choices[0].message.content)

    def generate_image_api(self, prompt: str, output_path: Path) -> bool:
        """使用Replicate API生成单张图片"""

        if not self.replicate_key:
            return False

        try:
            # 创建预测任务
            url = "https://api.replicate.com/v1/predictions"
            headers = {
                "Authorization": f"Token {self.replicate_key}",
                "Content-Type": "application/json"
            }

            data = {
                "version": "black-forest-labs/flux-dev",
                "input": {
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "output_format": "png",
                    "num_inference_steps": 50,
                    "guidance_scale": 3.5
                }
            }

            resp = requests.post(url, headers=headers, json=data)

            if resp.status_code == 402:
                print("   ⚠️  免费额度已用完")
                return False
            elif resp.status_code == 429:
                print("   ⏳ 触发限流，等待10秒...")
                time.sleep(10)
                return self.generate_image_api(prompt, output_path)

            resp.raise_for_status()
            prediction = resp.json()
            pred_id = prediction["id"]

            # 等待结果
            result_url = f"https://api.replicate.com/v1/predictions/{pred_id}"
            while True:
                result_resp = requests.get(result_url, headers=headers)
                result_resp.raise_for_status()
                result = result_resp.json()

                status = result.get("status")
                if status == "succeeded":
                    output_url = result["output"]
                    if isinstance(output_url, list):
                        output_url = output_url[0]

                    # 下载图片
                    img_data = requests.get(output_url).content
                    output_path.write_bytes(img_data)
                    return True

                elif status == "failed":
                    print(f"   ❌ 生成失败: {result.get('error')}")
                    return False
                elif status in ["starting", "processing"]:
                    time.sleep(1)
                else:
                    return False

        except Exception as e:
            print(f"   ❌ API错误: {e}")
            return False

    def run(self, article_path: str):
        """执行智能混合流水线"""

        print("="*60)
        print("🎬 智能混合方案 (免费额度 + 人工)")
        print("="*60)

        # 1. 加载配额
        quota = self.load_quota()
        print(f"\n📊 今日配额状态:")
        print(f"   API额度: {quota.api_used}/{quota.api_limit} 张")
        print(f"   人工制作: {quota.manual_used} 张")
        print(f"   剩余API: {quota.remaining_api} 张")

        if quota.api_available:
            print(f"   ✅ API可用")
        else:
            print(f"   ⚠️  API额度已用完，将使用纯人工方案")

        # 2. 读取文章
        print(f"\n📖 读取文章: {article_path}")
        article = Path(article_path).read_text(encoding='utf-8')

        # 3. 生成方案
        print("\n🤖 Kimi正在分析并制定方案...")
        plan = self.generate_video_plan(article)

        # 4. 创建项目
        article_name = Path(article_path).stem
        project_dir = Path(f"projects/{self.today}_{article_name}_hybrid")
        project_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (project_dir / "01_api_images").mkdir(exist_ok=True)
        (project_dir / "02_manual_images").mkdir(exist_ok=True)
        (project_dir / "03_videos").mkdir(exist_ok=True)
        (project_dir / "04_final").mkdir(exist_ok=True)

        # 保存方案
        with open(project_dir / "plan.json", 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

        print(f"\n📁 项目已创建: {project_dir}")

        # 5. 分析方案
        api_scenes = [s for s in plan['scenes'] if s.get('generate_method') == 'api']
        manual_scenes = [s for s in plan['scenes'] if s.get('generate_method') == 'manual']

        print(f"\n📋 制作方案:")
        print(f"   API自动生成: {len(api_scenes)} 张")
        print(f"   人工Midjourney: {len(manual_scenes)} 张")

        # 6. 执行API生成
        api_success = []
        if api_scenes and quota.api_available:
            print(f"\n🎨 开始API自动生成...")

            for scene in api_scenes:
                idx = scene['index']
                prompt = scene.get('api_prompt', '')

                if quota.api_used >= quota.api_limit:
                    print(f"   ⚠️  额度用完，跳过剩余API生成")
                    break

                print(f"\n   生成场景 {idx}: {scene.get('type', '')}")
                output_path = project_dir / "01_api_images" / f"scene_{idx:02d}.png"

                if self.generate_image_api(prompt, output_path):
                    api_success.append(idx)
                    quota.api_used += 1
                    quota.remaining_api -= 1
                    self.save_quota(quota)
                    print(f"   ✅ 成功 (剩余额度: {quota.remaining_api})")
                else:
                    print(f"   ❌ 失败，将转为人工制作")
                    scene['generate_method'] = 'manual'
                    manual_scenes.append(scene)

                time.sleep(2)  # 避免限流

        # 7. 生成人工制作包
        if manual_scenes:
            print(f"\n👤 准备人工制作包...")

            mj_commands = []
            manual_guide = ["# 人工制作指南 (Midjourney)\n"]
            manual_guide.append(f"## 需要制作的图片: {len(manual_scenes)}张\n")

            for scene in manual_scenes:
                idx = scene['index']
                mj_prompt = scene.get('mj_prompt', '')

                # Midjourney命令
                mj_cmd = f"/imagine prompt: {mj_prompt} --ar 9:16 --v 6.0 --s 750"
                mj_commands.append(f"\n### 场景{idx}: {scene.get('type', '')}\n{mj_cmd}\n")

                # 指南
                manual_guide.append(f"\n### 场景 {idx} ({scene.get('time', '')})")
                manual_guide.append(f"- 类型: {scene.get('type', '')}")
                manual_guide.append(f"- 画面: {scene.get('visual', '')}")
                manual_guide.append(f"- Midjourney提示词: `{mj_prompt}`")
                manual_guide.append(f"- 生成后保存为: `02_manual_images/scene_{idx:02d}.png`\n")

                quota.manual_used += 1

            # 保存文件
            with open(project_dir / "midjourney_commands.txt", 'w', encoding='utf-8') as f:
                f.writelines(mj_commands)

            with open(project_dir / "manual_guide.md", 'w', encoding='utf-8') as f:
                f.writelines(manual_guide)

            print(f"   ✅ 已生成 midjourney_commands.txt")
            print(f"   ✅ 已生成 manual_guide.md")

            # 打开Discord
            print(f"\n🌐 正在打开Midjourney...")
            webbrowser.open("https://discord.com/channels/@me")

        # 8. 更新配额
        self.save_quota(quota)

        # 9. 生成剪辑指南
        self._generate_editing_guide(plan, project_dir)

        # 10. 完成总结
        print("\n" + "="*60)
        print("✅ 方案准备完成!")
        print("="*60)
        print(f"\n📂 项目位置: {project_dir}")
        print(f"\n📊 今日配额更新:")
        print(f"   API已用: {quota.api_used}/{quota.api_limit}")
        print(f"   人工制作: {quota.manual_used}")
        print(f"   API剩余: {quota.remaining_api}")

        print(f"\n📋 文件清单:")
        for f in sorted(project_dir.iterdir()):
            if f.is_file():
                print(f"   - {f.name}")
            else:
                print(f"   - {f.name}/")

        print(f"\n🎯 下一步操作:")
        if api_success:
            print(f"   1. ✅ API图片已生成，查看 01_api_images/")
        if manual_scenes:
            print(f"   2. 👤 复制 midjourney_commands.txt 到Discord执行")
            print(f"   3. 📥 下载图片保存到 02_manual_images/")
        print(f"   4. ✂️ 按 editing_guide.md 剪辑视频")

        if quota.remaining_api <= 2:
            print(f"\n⚠️  提醒: API额度即将用完 ({quota.remaining_api}张)")
            print(f"   明天将重置为{quota.api_limit}张")

        return project_dir

    def _generate_editing_guide(self, plan: dict, project_dir: Path):
        """生成剪辑指南"""

        guide = ["# 剪映剪辑指南\n"]
        guide.append(f"## 视频主题: {plan['topic']['title']}\n")
        guide.append(f"## 优先级: {plan['topic'].get('priority', 'normal')}\n\n")

        guide.append("### 素材收集\n")
        guide.append("完成以下步骤后再开始剪辑:\n")
        guide.append("- [ ] 01_api_images/ 中的API生成图片")
        guide.append("- [ ] 02_manual_images/ 中的Midjourney图片")
        guide.append("- [ ] 口播配音文件 (自己录制或TTS)\n")

        guide.append("### 剪辑顺序\n")
        for scene in sorted(plan['scenes'], key=lambda x: x['index']):
            guide.append(f"\n**场景{scene['index']}: {scene['time']}**")
            guide.append(f"- 画面: {scene['visual'][:50]}...")
            guide.append(f"- 口播: {scene['audio']}")
            guide.append(f"- 字幕: {scene['subtitle']}")
            guide.append(f"- 素材来源: {scene.get('generate_method', 'unknown')}")
            guide.append("")

        guide.append("\n### 导出设置")
        guide.append("- 分辨率: 1080x1920 (9:16)")
        guide.append("- 帧率: 30fps")
        guide.append("- 格式: MP4")

        with open(project_dir / "editing_guide.md", 'w', encoding='utf-8') as f:
            f.writelines(guide)


def main():
    parser = argparse.ArgumentParser(description="智能混合方案 - 免费额度+人工")
    parser.add_argument("article", help="文章文件路径")
    parser.add_argument("--kimi-key", default=os.environ.get("MOONSHOT_API_KEY"))
    parser.add_argument("--replicate-key", default=os.environ.get("REPLICATE_API_TOKEN"))

    args = parser.parse_args()

    if not args.kimi_key:
        print("❌ 需要 MOONSHOT_API_KEY")
        sys.exit(1)

    pipeline = SmartHybridPipeline(
        kimi_key=args.kimi_key,
        replicate_key=args.replicate_key
    )

    pipeline.run(args.article)


if __name__ == "__main__":
    main()
