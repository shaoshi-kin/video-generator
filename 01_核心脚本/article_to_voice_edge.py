#!/usr/bin/env python3
"""
文章转音频 - Edge-TTS版本 (Python 3.11+)
支持多音色选择、语速调节

使用方法:
    python3 article_to_voice_edge.py <文章.md> [--voice 音色] [--rate 语速]

示例:
    python3 article_to_voice_edge.py article.md
    python3 article_to_voice_edge.py article.md --voice Xiaoxiao --rate +10%
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

import edge_tts


# 中文可用音色
VOICES = {
    # 女声
    'Xiaoxiao': 'zh-CN-XiaoxiaoNeural',      # 晓晓 - 活泼温暖
    'Xiaoyi': 'zh-CN-XiaoyiNeural',          # 晓伊 - 成熟稳重
    'Yunxi': 'zh-CN-YunxiNeural',            # 云希 - 年轻男声
    'Yunjian': 'zh-CN-YunjianNeural',        # 云健 - 新闻播报风格
    'Yunxia': 'zh-CN-YunxiaNeural',          # 云夏 - 年轻女声
    'Yunyang': 'zh-CN-YunyangNeural',        # 云扬 - 成熟男声
    # 台湾
    'HsiaoChen': 'zh-TW-HsiaoChenNeural',    # 晓晨 - 台湾女声
    'HsiaoYu': 'zh-TW-HsiaoYuNeural',        # 晓雨 - 台湾女声
    'YunJhe': 'zh-TW-YunJheNeural',          # 云哲 - 台湾男声
    # 香港
    'HiuMaan': 'zh-HK-HiuMaanNeural',        # 晓曼 - 粤语女声
    'HiuGaai': 'zh-HK-HiuGaaiNeural',        # 晓佳 - 粤语女声
    'WanLung': 'zh-HK-WanLungNeural',        # 云龙 - 粤语男声
}


def read_article(file_path: str) -> str:
    """读取文章文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def clean_text(text: str) -> str:
    """清理文本"""
    import re
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join(lines).strip()


def split_text(text: str, max_length: int = 3000) -> list:
    """将长文本分段"""
    if len(text) <= max_length:
        return [text]

    segments = []
    current = ""
    import re
    sentences = re.split(r'([。！？.!?\n])', text)

    i = 0
    while i < len(sentences):
        sentence = sentences[i]
        if i + 1 < len(sentences) and sentences[i + 1] in '。！？.!?\n':
            sentence += sentences[i + 1]
            i += 1

        if len(current) + len(sentence) <= max_length:
            current += sentence
        else:
            if current:
                segments.append(current.strip())
            current = sentence
        i += 1

    if current:
        segments.append(current.strip())

    return segments


async def generate_voice(text: str, output_path: str, voice: str, rate: str):
    """使用 Edge-TTS 生成配音"""
    try:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False


async def main_async():
    parser = argparse.ArgumentParser(
        description="文章转音频 - Edge-TTS版本 (支持音色选择)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
可用音色 (中文):
  女声:
    Xiaoxiao  - 晓晓 (默认，活泼温暖)
    Xiaoyi    - 晓伊 (成熟稳重)
    Yunxia    - 云夏 (年轻女声)
  男声:
    Yunxi     - 云希 (年轻男声)
    Yunjian   - 云健 (新闻播报风格)
    Yunyang   - 云扬 (成熟男声)
  台湾:
    HsiaoChen - 晓晨 (台湾女声)
    YunJhe    - 云哲 (台湾男声)
  粤语:
    HiuMaan   - 晓曼 (粤语女声)
    WanLung   - 云龙 (粤语男声)

语速调节:
  --rate -50%   慢速 (0.5倍)
  --rate -20%   稍慢
  --rate +0%    正常 (默认)
  --rate +20%   稍快
  --rate +50%   快速

示例:
  python3 article_to_voice_edge.py article.md
  python3 article_to_voice_edge.py article.md --voice Xiaoxiao --rate +10%
  python3 article_to_voice_edge.py article.md --voice Yunyang --rate -10%
        """
    )
    parser.add_argument("article", help="文章文件路径(.md或.txt)")
    parser.add_argument("--output", "-o", help="输出音频文件名")
    parser.add_argument("--voice", default="Xiaoxiao",
                       choices=list(VOICES.keys()),
                       help="音色选择 (默认: Xiaoxiao)")
    parser.add_argument("--rate", default="+0%",
                       help="语速调节 (默认: +0%, 范围: -50% 到 +100%)")
    parser.add_argument("--list-voices", action="store_true",
                       help="列出所有可用音色")

    args = parser.parse_args()

    if args.list_voices:
        print("可用音色列表:")
        print("=" * 50)
        for name, voice_id in VOICES.items():
            category = ""
            if "Xiaoxiao" in name or "Xiaoyi" in name or "Yunxia" in name:
                category = "女声"
            elif "Yun" in name and name not in ["Yunxia"]:
                category = "男声"
            elif "Hsiao" in name or "Hiu" in name:
                category = "女声"
            elif "WanLung" in name or "YunJhe" in name:
                category = "男声"
            print(f"  {name:12} - {voice_id:35} {category}")
        return

    article_path = Path(args.article)
    if not article_path.exists():
        print(f"❌ 文件不存在: {args.article}")
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        output_path = article_path.stem + "_edge.mp3"

    voice = VOICES[args.voice]

    print("=" * 60)
    print("🎙️  文章转音频 (Edge-TTS)")
    print("=" * 60)
    print(f"📖 输入文件: {article_path}")
    print(f"🎵 输出文件: {output_path}")
    print(f"🔊 音色: {args.voice} ({voice})")
    print(f"⏱️  语速: {args.rate}")
    print()

    print("📖 读取文章...")
    raw_text = read_article(str(article_path))
    print(f"   原始长度: {len(raw_text)} 字符")

    text = clean_text(raw_text)
    print(f"   清理后长度: {len(text)} 字符")

    if not text.strip():
        print("❌ 文章内容为空")
        sys.exit(1)

    segments = split_text(text, max_length=3000)
    print(f"\n📦 文章分段: {len(segments)} 段")
    print("-" * 60)

    import tempfile
    temp_dir = tempfile.mkdtemp()
    audio_files = []

    for i, segment in enumerate(segments, 1):
        print(f"\n[{i}/{len(segments)}] 生成音频...")
        print(f"   长度: {len(segment)} 字符")
        print(f"   内容: {segment[:50]}...")

        temp_file = os.path.join(temp_dir, f"segment_{i:03d}.mp3")

        if await generate_voice(segment, temp_file, voice, args.rate):
            size_kb = Path(temp_file).stat().st_size / 1024
            print(f"   ✅ 已保存 ({size_kb:.1f} KB)")
            audio_files.append(temp_file)
        else:
            print(f"   ❌ 失败，跳过此段")

    if not audio_files:
        print("\n❌ 没有生成任何音频")
        import shutil
        shutil.rmtree(temp_dir)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("🔧 合并音频文件...")

    if len(audio_files) == 1:
        import shutil
        shutil.copy(audio_files[0], output_path)
        success = True
    else:
        import subprocess
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for audio_file in audio_files:
                escaped = audio_file.replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
            concat_file = f.name

        try:
            cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                   '-i', concat_file, '-c', 'copy', output_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            success = result.returncode == 0
        finally:
            os.unlink(concat_file)

    import shutil
    shutil.rmtree(temp_dir)

    if success and Path(output_path).exists():
        final_size = Path(output_path).stat().st_size / 1024
        print(f"\n✅ 完成!")
        print(f"   输出文件: {output_path}")
        print(f"   文件大小: {final_size:.1f} KB")
        print(f"   成功生成: {len(audio_files)}/{len(segments)} 段")
        print(f"   音色: {args.voice}")
        print(f"   语速: {args.rate}")
        print()
        print("▶️  播放命令:")
        print(f"   afplay '{output_path}'")
    else:
        print("\n❌ 合并失败")
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
