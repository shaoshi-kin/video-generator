"""Edge TTS 配音模块：口播稿 → MP3 配音"""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

try:
    import edge_tts
    EDGE_TTS_OK = True
except ImportError:
    EDGE_TTS_OK = False

from presets import resolve_voice


def check_edge_tts() -> bool:
    """检查 edge_tts 是否可用"""
    return EDGE_TTS_OK


def parse_segments(script: str) -> List[Tuple[str, str]]:
    """
    解析口播稿中的 @音色 标记，返回 [(音色, 文本段落), ...]。

    支持：
    - @全局:女声 — 设置全局默认音色
    - @男声: 文本内容 — 指定当前段落音色

    返回的每段文本会被清理（去标记、合并短段落）。
    """
    lines = script.split('\n')
    default_voice = 'zh-CN-XiaoxiaoNeural'

    # 提取全局音色
    first_line = lines[0] if lines else ''
    global_match = re.match(r'@全局:(\S+)', first_line)
    if global_match:
        default_voice = resolve_voice(global_match.group(1))

    # 过滤掉 Markdown 标题行和空行、@全局标记行
    content_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            content_lines.append('')  # 保留空行作为段落分隔
        elif line.startswith('#'):
            continue
        elif line.startswith('@全局:'):
            continue
        else:
            content_lines.append(line)

    text = '\n'.join(content_lines)

    # 按 @音色: 标记分段
    segments = []
    pattern = re.compile(r'@([^\s:：]+)[:：]\s*')
    pos = 0
    current_voice = default_voice

    for m in pattern.finditer(text):
        pre_text = text[pos:m.start()].strip()
        if pre_text:
            segments.append((current_voice, pre_text))
        current_voice = resolve_voice(m.group(1))
        pos = m.end()

    # 剩余文本
    remaining = text[pos:].strip()
    if remaining:
        segments.append((current_voice, remaining))

    # 如果没有任何 @音色 标记，整篇作为一个段落
    if not segments:
        cleaned = text.strip()
        if cleaned:
            segments.append((default_voice, cleaned))

    # 合并短段落
    merged = []
    buffer_text = ''
    buffer_voice = None
    for voice, txt in segments:
        txt = txt.strip()
        if not txt:
            continue
        if buffer_voice is None:
            buffer_voice = voice
            buffer_text = txt
        elif buffer_voice == voice:
            buffer_text += '\n' + txt
        else:
            merged.append((buffer_voice, buffer_text))
            buffer_voice = voice
            buffer_text = txt
    if buffer_text:
        merged.append((buffer_voice, buffer_text))

    return merged


async def _gen_one(text: str, voice_id: str, rate: str, output_path: Path) -> bool:
    """生成单个音频片段"""
    try:
        comm = edge_tts.Communicate(text, voice=voice_id, rate=rate)
        await comm.save(str(output_path))
        return True
    except Exception as e:
        print(f"  [WARN] TTS 生成失败: {e}")
        return False


async def generate_audio(script: str, output_dir: Path, voice: str = 'zh-CN-YunyangNeural',
                         rate: str = '+15%', max_concurrent: int = 3) -> Optional[List[Path]]:
    """
    异步生成配音文件。

    返回生成的 MP3 文件路径列表，失败返回 None。
    """
    if not EDGE_TTS_OK:
        print("[ERROR] 请先安装 edge_tts: pip install edge_tts")
        return None

    output_dir.mkdir(parents=True, exist_ok=True)

    segments = parse_segments(script)

    if not segments:
        print("[ERROR] 口播稿中没有有效文本")
        return None

    print(f"  共 {len(segments)} 个配音段落")

    # 并发生成
    sem = asyncio.Semaphore(max_concurrent)
    audio_paths = []

    async def worker(idx, voice_name, text):
        async with sem:
            path = output_dir / f'seg_{idx:03d}.mp3'
            success = await _gen_one(text, voice_name, rate, path)
            if success:
                audio_paths.append((idx, path))
                dur = get_audio_duration(path)
                print(f"  [{idx+1}/{len(segments)}] {len(text)}字 → {dur:.1f}s")
            return success

    tasks = [worker(i, v, t) for i, (v, t) in enumerate(segments)]
    await asyncio.gather(*tasks)

    if not audio_paths:
        print("[ERROR] 所有配音段落生成失败")
        return None

    # 按序号排序
    audio_paths.sort(key=lambda x: x[0])
    return [p for _, p in audio_paths]


def get_audio_duration(path: Path) -> float:
    """获取音频时长（秒），使用 ffprobe"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def merge_audio(audio_paths: List[Path], output_path: Path) -> bool:
    """合并多个 MP3 文件"""
    if len(audio_paths) == 1:
        import shutil
        shutil.copy(audio_paths[0], output_path)
        return True

    # 使用 ffmpeg concat demuxer
    concat_file = output_path.parent / '_concat.txt'
    with open(concat_file, 'w') as f:
        for p in audio_paths:
            f.write(f"file '{p.absolute()}'\n")

    try:
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error',
             '-f', 'concat', '-safe', '0', '-i', str(concat_file),
             '-c', 'copy', str(output_path)],
            check=True, timeout=30,
        )
        concat_file.unlink()
        return True
    except subprocess.CalledProcessError:
        concat_file.unlink(missing_ok=True)
        return False


def get_segment_timings(audio_paths: List[Path]) -> List[dict]:
    """返回每个配音段落的时长信息，用于字幕分句"""
    timings = []
    for p in audio_paths:
        timings.append({
            'path': str(p),
            'duration': get_audio_duration(p),
        })
    return timings
