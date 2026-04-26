#!/usr/bin/env python3
"""
AI配音生成器 - gTTS版本（Google TTS）
特点：免费、兼容Python 3.9、无需升级、安装简单

使用方法：
    pip3 install gtts
    python3 tts_gtts.py --script "你的文案" --output voice.mp3

    # 从项目生成完整配音
    python3 tts_gtts.py --from-project projects/XXX/plan.json
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional


def check_gtts():
    """检查gTTS是否安装"""
    try:
        from gtts import gTTS
        return True
    except ImportError:
        print("❌ gTTS未安装，请运行: pip3 install gtts")
        return False


def generate_voice(text: str, output_path: str, lang: str = "zh-cn", slow: bool = False):
    """
    使用gTTS生成配音

    参数:
        text: 要转换的文字
        output_path: 输出文件路径
        lang: 语言代码 (zh-cn=中文, en=英文, ja=日语等)
        slow: 是否放慢语速
    """
    try:
        from gtts import gTTS

        # 创建gTTS对象
        tts = gTTS(text=text, lang=lang, slow=slow)

        # 保存文件
        tts.save(output_path)

        return True

    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return False


def generate_from_project(project_path: str):
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

    for i, scene in enumerate(scenes, 1):
        text = scene.get('audio', '')
        if not text:
            continue

        print(f"\n[{i}/{len(scenes)}] 场景{i}: {scene.get('type', '')}")
        print(f"文案: {text[:40]}...")

        output_file = audio_dir / f"scene_{i:02d}.mp3"

        # 财经内容用正常语速
        if generate_voice(text, str(output_file), lang="zh-cn", slow=False):
            generated.append(output_file)
            print(f"✅ 已保存")

            # 显示文件大小
            size_kb = output_file.stat().st_size / 1024
            print(f"   大小: {size_kb:.1f} KB")
        else:
            print(f"❌ 失败")

    # 生成合并脚本
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

        # 生成简单播放器脚本（macOS）
        play_script = audio_dir / "play_all.sh"
        with open(play_script, 'w') as f:
            f.write("#!/bin/bash\n")
            for mp3 in sorted(generated):
                f.write(f'afplay "{mp3.name}"\n')
        play_script.chmod(0o755)

        print(f"\n▶️  顺序播放所有音频:")
        print(f"   cd {audio_dir} && ./play_all.sh")

    return generated


def main():
    parser = argparse.ArgumentParser(
        description="AI配音生成器 (gTTS版本 - 免费兼容Python 3.9)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单条配音
  python3 tts_gtts.py --script "普华永道血赔10亿" --output voice.mp3

  # 从项目生成完整配音
  python3 tts_gtts.py --from-project projects/2026-04-24_1_hybrid/plan.json

  # 播放试听
  afplay voice.mp3  # macOS
        """
    )
    parser.add_argument("--script", help="要转换的文案")
    parser.add_argument("--output", default="output.mp3", help="输出文件名 (默认: output.mp3)")
    parser.add_argument("--lang", default="zh-cn", help="语言代码 (默认: zh-cn)")
    parser.add_argument("--slow", action="store_true", help="放慢语速")
    parser.add_argument("--from-project", help="从视频项目生成完整配音")

    args = parser.parse_args()

    # 检查依赖
    if not check_gtts():
        sys.exit(1)

    # 从项目生成
    if args.from_project:
        if not Path(args.from_project).exists():
            print(f"❌ 项目文件不存在: {args.from_project}")
            sys.exit(1)
        generate_from_project(args.from_project)
        return

    # 单条生成
    if not args.script:
        print("❌ 请提供 --script 文案 或 --from-project 项目路径")
        parser.print_help()
        sys.exit(1)

    # 生成
    print(f"🎙️ 生成配音 (gTTS)")
    print(f"文案: {args.script}")
    print(f"语言: {args.lang}")
    if args.slow:
        print(f"语速: 慢速")
    print("="*60)

    if generate_voice(args.script, args.output, args.lang, args.slow):
        print(f"\n✅ 成功! 已保存: {args.output}")

        # 文件大小
        size_kb = Path(args.output).stat().st_size / 1024
        print(f"   文件大小: {size_kb:.1f} KB")

        # 播放提示
        print(f"\n▶️  播放试听:")
        print(f"   macOS: afplay {args.output}")
        print(f"   Linux: mpg123 {args.output}")
        print(f"   通用:  open {args.output}")
    else:
        print("\n❌ 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
