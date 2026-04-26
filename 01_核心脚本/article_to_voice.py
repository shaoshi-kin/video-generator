#!/usr/bin/env python3
"""
文章转音频 - 整篇生成
把整篇文章一次性转换成单个音频文件

使用方法:
    python3 article_to_voice.py <文章.md> [--output 输出.mp3]

示例:
    python3 article_to_voice.py article.md
    python3 article_to_voice.py article.md --output 我的音频.mp3
"""

import os
import sys
import argparse
import time
from pathlib import Path


def check_gtts():
    """检查gTTS是否安装"""
    try:
        from gtts import gTTS
        return True
    except ImportError:
        print("❌ gTTS未安装，请运行: pip3 install gtts")
        return False


def read_article(file_path: str) -> str:
    """读取文章文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content


def clean_text(text: str) -> str:
    """清理文本，保留纯文本内容"""
    import re

    # 移除代码块
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 移除行内代码
    text = re.sub(r'`[^`]*`', '', text)
    # 移除图片链接
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    # 移除普通链接，保留文字
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # 移除HTML标签
    text = re.sub(r'<[^>]+>', '', text)
    # 移除标题符号
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # 移除列表符号
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 移除多余空行，保留段落
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 移除行首行尾空白
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def split_text(text: str, max_length: int = 500) -> list:
    """将长文本分段，每段不超过max_length字符"""
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


def generate_voice_with_retry(text: str, output_path: str, lang: str = "zh-cn", slow: bool = False, max_retries: int = 5):
    """使用gTTS生成配音，带自动重试"""
    from gtts import gTTS

    for attempt in range(max_retries):
        try:
            tts = gTTS(text=text, lang=lang, slow=slow)
            tts.save(output_path)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 递增等待时间
                print(f"   ⚠️  失败，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"   ❌ 最终失败: {e}")
                return False


def merge_audio_files(audio_files: list, output_path: str):
    """使用ffmpeg合并音频文件"""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for audio_file in audio_files:
            escaped = audio_file.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
        concat_file = f.name

    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    finally:
        os.unlink(concat_file)


def main():
    parser = argparse.ArgumentParser(
        description="文章转音频 - 整篇生成",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 article_to_voice.py article.md
  python3 article_to_voice.py article.md --output 我的音频.mp3
  python3 article_to_voice.py article.md --slow  # 慢速朗读
        """
    )
    parser.add_argument("article", help="文章文件路径(.md或.txt)")
    parser.add_argument("--output", "-o", help="输出音频文件名")
    parser.add_argument("--lang", default="zh-cn", help="语言代码 (默认: zh-cn)")
    parser.add_argument("--slow", action="store_true", help="放慢语速")
    parser.add_argument("--clean", action="store_true", default=True, help="清理markdown格式(默认开启)")
    parser.add_argument("--no-clean", action="store_true", help="不清理格式，原文朗读")
    parser.add_argument("--max-retries", type=int, default=5, help="失败重试次数(默认5)")

    args = parser.parse_args()

    if not check_gtts():
        sys.exit(1)

    article_path = Path(args.article)
    if not article_path.exists():
        print(f"❌ 文件不存在: {args.article}")
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        output_path = article_path.stem + ".mp3"

    print("=" * 60)
    print("🎙️  文章转音频")
    print("=" * 60)
    print(f"📖 输入文件: {article_path}")
    print(f"🎵 输出文件: {output_path}")
    print()

    print("📖 读取文章...")
    raw_text = read_article(str(article_path))
    print(f"   原始长度: {len(raw_text)} 字符")

    if args.no_clean:
        text = raw_text
        print("   格式清理: 跳过")
    else:
        text = clean_text(raw_text)
        print(f"   清理后长度: {len(text)} 字符")

    if not text.strip():
        print("❌ 文章内容为空")
        sys.exit(1)

    segments = split_text(text, max_length=500)
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

        if generate_voice_with_retry(segment, temp_file, args.lang, args.slow, args.max_retries):
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
        success = merge_audio_files(audio_files, output_path)

    import shutil
    shutil.rmtree(temp_dir)

    if success and Path(output_path).exists():
        final_size = Path(output_path).stat().st_size / 1024
        print(f"\n✅ 完成!")
        print(f"   输出文件: {output_path}")
        print(f"   文件大小: {final_size:.1f} KB")
        print(f"   成功生成: {len(audio_files)}/{len(segments)} 段")
        print()
        print("▶️  播放命令:")
        print(f"   afplay '{output_path}'")
    else:
        print("\n❌ 合并失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
