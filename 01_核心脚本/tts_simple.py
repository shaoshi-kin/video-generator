#!/usr/bin/env python3
"""
AI配音生成器 - 简化版
使用edge-tts命令行工具（避免import兼容性问题）
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path


def generate_voice(text, output_path, voice="zh-CN-XiaoxiaoNeural"):
    """使用edge-tts命令行生成配音"""

    try:
        cmd = [
            "edge-tts",
            "--voice", voice,
            "--text", text,
            "--write-media", output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0:
            return True
        else:
            print(f"❌ 错误: {result.stderr}")
            return False

    except FileNotFoundError:
        print("❌ edge-tts未安装，请先运行: pip3 install edge-tts")
        return False
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False


def generate_from_project(project_path):
    """从视频项目生成完整配音"""

    print(f"📂 加载项目: {project_path}")

    with open(project_path, 'r', encoding='utf-8') as f:
        plan = json.load(f)

    scenes = plan.get('scenes', [])
    project_dir = Path(project_path).parent
    audio_dir = project_dir / "03_audio"
    audio_dir.mkdir(exist_ok=True)

    print(f"\n🎙️ 开始生成配音 ({len(scenes)} 段)")
    print("="*60)

    generated = []

    # 声音选择策略
    voice_map = {
        "hook": "zh-CN-YunjianNeural",
        "data": "zh-CN-XiaoxiaoNeural",
        "story": "zh-CN-XiaoxiaoNeural",
        "ending": "zh-CN-YunyangNeural"
    }

    for i, scene in enumerate(scenes, 1):
        text = scene.get('audio', '')
        if not text:
            continue

        scene_type = scene.get('type', 'story')
        voice = voice_map.get(scene_type, "zh-CN-XiaoxiaoNeural")

        print(f"\n[{i}/{len(scenes)}] 场景{i}: {scene_type}")
        print(f"文案: {text[:40]}...")

        output_file = audio_dir / f"scene_{i:02d}.mp3"

        if generate_voice(text, str(output_file), voice):
            generated.append(output_file)
            print(f"✅ 已保存 ({voice})")
        else:
            print(f"❌ 失败")

    if generated:
        concat_file = audio_dir / "concat.txt"
        with open(concat_file, 'w') as f:
            for mp3 in sorted(generated):
                f.write(f"file '{mp3.name}'\n")

        print("\n" + "="*60)
        print("✅ 配音生成完成!")
        print(f"生成文件: {len(generated)} 个")
        print(f"位置: {audio_dir}")
        print(f"\n🔧 合并所有音频:")
        print(f"   ffmpeg -f concat -i {concat_file} -c copy final_voice.mp3")

    return generated


def main():
    parser = argparse.ArgumentParser(description="AI配音生成器")
    parser.add_argument("--script", help="要转换的文案")
    parser.add_argument("--output", default="output.mp3", help="输出文件名")
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural",
                       help="声音选择")
    parser.add_argument("--from-project", help="从视频项目生成")

    args = parser.parse_args()

    if args.from_project:
        if not Path(args.from_project).exists():
            print(f"❌ 项目不存在: {args.from_project}")
            sys.exit(1)
        generate_from_project(args.from_project)
        return

    if not args.script:
        print("❌ 请提供 --script 文案")
        sys.exit(1)

    print(f"🎙️ 生成配音...")
    print(f"文案: {args.script}")
    print("="*60)

    if generate_voice(args.script, args.output, args.voice):
        print(f"\n✅ 成功! 已保存: {args.output}")
    else:
        print("\n❌ 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
