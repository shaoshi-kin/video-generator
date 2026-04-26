#!/usr/bin/env python3
"""
AI配音生成器 - 零成本方案
支持：Edge-TTS（免费）+ ChatTTS（本地）

使用方法：
    # 方案1: Edge-TTS（推荐，免费，在线）
    python3 tts_generator.py --script "你的文案" --output voice.mp3

    # 方案2: ChatTTS（本地，高质量）
    python3 tts_generator.py --script "你的文案" --engine chattts --output voice.mp3

    # 从视频项目生成配音
    python3 tts_generator.py --from-project projects/2026-04-24_1_hybrid/plan.json
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Optional


def check_edge_tts():
    """检查edge-tts是否安装"""
    try:
        import edge_tts
        return True
    except ImportError:
        return False


def generate_edge_tts(text: str, output_path: str, voice: str = "zh-CN-XiaoxiaoNeural"):
    """
    使用Edge-TTS生成配音（免费，微软边缘TTS）

    可选声音：
    - zh-CN-XiaoxiaoNeural (晓晓，女声，默认)
    - zh-CN-YunxiNeural (云希，男声)
    - zh-CN-YunjianNeural (云健，男声，解说)
    - zh-HK-HiuMaanNeural (粤语，女声)
    - zh-TW-HsiaoChenNeural (台湾腔，女声)
    """

    try:
        import edge_tts
        import asyncio

        async def main():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)

        asyncio.run(main())
        return True

    except Exception as e:
        print(f"❌ Edge-TTS生成失败: {e}")
        return False


def generate_chattts(text: str, output_path: str):
    """
    使用ChatTTS生成本地配音（需要安装ChatTTS）
    效果更自然，但需要8GB+显存
    """

    # 检查ChatTTS是否可用
    chattts_path = Path("~/ChatTTS").expanduser()

    if not chattts_path.exists():
        print("❌ ChatTTS未安装")
        print("   安装指南: https://github.com/2noise/ChatTTS")
        print("   或使用: git clone https://github.com/2noise/ChatTTS ~/ChatTTS")
        return False

    try:
        # 调用ChatTTS（简化版，实际需要更复杂的集成）
        import sys
        sys.path.insert(0, str(chattts_path))

        import ChatTTS
        import torch
        import torchaudio

        chat = ChatTTS.Chat()
        chat.load(compile=False)  # 使用compile=True更快但需要CUDA

        texts = [text]
        wavs = chat.infer(texts)

        torchaudio.save(output_path, torch.from_numpy(wavs[0]), 24000)
        return True

    except Exception as e:
        print(f"❌ ChatTTS生成失败: {e}")
        print("   提示: ChatTTS需要8GB+显存和CUDA环境")
        return False


def generate_from_project(project_path: str, engine: str = "edge-tts"):
    """从视频项目生成完整配音"""

    print(f"📂 加载项目: {project_path}")

    with open(project_path, 'r', encoding='utf-8') as f:
        plan = json.load(f)

    scenes = plan.get('scenes', [])
    project_dir = Path(project_path).parent
    audio_dir = project_dir / "03_audio"
    audio_dir.mkdir(exist_ok=True)

    print(f"\n🎙️ 开始生成配音 ({len(scenes)} 段)")
    print(f"引擎: {engine}")
    print("="*60)

    generated = []

    for i, scene in enumerate(scenes, 1):
        text = scene.get('audio', '')
        if not text:
            continue

        print(f"\n[{i}/{len(scenes)}] 场景{i}: {scene.get('type', '')}")
        print(f"文案: {text[:50]}...")

        output_file = audio_dir / f"scene_{i:02d}.mp3"

        if engine == "edge-tts":
            # 根据场景类型选择声音
            voice = "zh-CN-XiaoxiaoNeural"  # 默认女声
            if scene.get('type') == 'hook':
                voice = "zh-CN-YunjianNeural"  # 开头用男声更有冲击力

            success = generate_edge_tts(text, str(output_file), voice)
        else:
            success = generate_chattts(text, str(output_file))

        if success:
            generated.append(output_file)
            print(f"✅ 已保存: {output_file}")
        else:
            print(f"❌ 失败")

        # 避免限流
        import time
        time.sleep(0.5)

    # 生成合并脚本
    concat_list = audio_dir / "concat_list.txt"
    with open(concat_list, 'w') as f:
        for mp3 in sorted(generated):
            f.write(f"file '{mp3.name}'\n")

    print("\n" + "="*60)
    print("✅ 配音生成完成!")
    print("="*60)
    print(f"\n📁 文件位置: {audio_dir}")
    print(f"生成文件: {len(generated)} 个")

    if len(generated) > 0:
        print(f"\n🔧 合并所有音频:")
        print(f"   ffmpeg -f concat -i {concat_list} -c copy final_voice.mp3")

    return generated


def list_voices():
    """列出所有可用声音"""

    voices = {
        "zh-CN-XiaoxiaoNeural": "晓晓 - 女声，年轻活泼 (推荐)",
        "zh-CN-XiaoyiNeural": "晓伊 - 女声，温柔",
        "zh-CN-YunxiNeural": "云希 - 男声，年轻",
        "zh-CN-YunjianNeural": "云健 - 男声，成熟稳重 (推荐)",
        "zh-CN-YunyangNeural": "云扬 - 男声，新闻播报",
        "zh-HK-HiuMaanNeural": "晓曼 - 粤语女声",
        "zh-TW-HsiaoChenNeural": "晓臻 - 台湾女声",
    }

    print("\n🎙️ 可用声音列表 (Edge-TTS):")
    print("="*60)
    for voice, desc in voices.items():
        print(f"  {voice}")
        print(f"      {desc}")


def main():
    parser = argparse.ArgumentParser(description="AI配音生成器")
    parser.add_argument("--script", help="要转换的文案")
    parser.add_argument("--output", default="output.mp3", help="输出文件名")
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural", help="声音选择")
    parser.add_argument("--engine", choices=["edge-tts", "chattts"], default="edge-tts", help="TTS引擎")
    parser.add_argument("--from-project", help="从视频项目生成")
    parser.add_argument("--list-voices", action="store_true", help="列出可用声音")

    args = parser.parse_args()

    # 列出声音
    if args.list_voices:
        list_voices()
        return

    # 从项目生成
    if args.from_project:
        if not Path(args.from_project).exists():
            print(f"❌ 项目文件不存在: {args.from_project}")
            sys.exit(1)
        generate_from_project(args.from_project, args.engine)
        return

    # 单条生成
    if not args.script:
        print("❌ 请提供 --script 文案 或 --from-project 项目路径")
        parser.print_help()
        sys.exit(1)

    # 检查依赖
    if args.engine == "edge-tts" and not check_edge_tts():
        print("❌ 请先安装依赖: pip3 install edge-tts")
        sys.exit(1)

    # 生成
    print(f"🎙️ 生成配音: {args.script[:50]}...")
    print(f"引擎: {args.engine}")
    print(f"声音: {args.voice}")
    print("="*60)

    if args.engine == "edge-tts":
        success = generate_edge_tts(args.script, args.output, args.voice)
    else:
        success = generate_chattts(args.script, args.output)

    if success:
        print(f"\n✅ 成功! 已保存: {args.output}")
    else:
        print(f"\n❌ 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
