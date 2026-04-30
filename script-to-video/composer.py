"""FFmpeg 合成模块：素材 + 配音 + 字幕 → 竖/横屏视频"""

import subprocess
import re
from pathlib import Path
from typing import List, Optional


def check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _clean_text(text: str) -> str:
    """清理文本，移除特殊字符防止 ffmpeg drawtext 报错"""
    text = text.replace("'", "'").replace("'", "'")
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace('\\', '')
    text = text.replace('%', '%%')  # ffmpeg drawtext 转义
    text = text.replace(':', '：')   # 避免被误解析为 filter 参数
    return text


def _split_to_sentences(text: str) -> list:
    """按标点拆分句子"""
    sentences = re.split(r'(?<=[。！？；，.!?;,])', text)
    return [s.strip() for s in sentences if s.strip()]


def _build_subtitle_filter(sentences: list, duration: float,
                           font_size: int = 52, color: str = 'white',
                           box: bool = True, position: str = 'bottom',
                           width: int = 1080, height: int = 1920) -> str:
    """
    构建逐句字幕 filter。
    每句平均分配时长，居中显示。
    """
    if not sentences:
        return 'null'

    per_sentence_dur = max(duration / len(sentences), 1.5)

    filters = []
    y_pos = height * 0.7 if position == 'bottom' else height * 0.4

    for i, s in enumerate(sentences):
        s = _clean_text(s)
        start = i * per_sentence_dur
        end = start + per_sentence_dur

        font_file = _find_font()
        font_config = f"fontfile='{font_file}':" if font_file else ""

        if box:
            draw = (
                f"drawtext={font_config}"
                f"text='{s}':"
                f"fontsize={font_size}:"
                f"fontcolor={color}:"
                f"x=(w-text_w)/2:"
                f"y={y_pos}:"
                f"box=1:"
                f"boxcolor=black@0.6:"
                f"boxborderw=10:"
                f"enable='between(t,{start:.2f},{end:.2f})'"
            )
        else:
            draw = (
                f"drawtext={font_config}"
                f"text='{s}':"
                f"fontsize={font_size}:"
                f"fontcolor={color}:"
                f"bordercolor=black:"
                f"borderw=3:"
                f"x=(w-text_w)/2:"
                f"y={y_pos}:"
                f"enable='between(t,{start:.2f},{end:.2f})'"
            )
        filters.append(draw)

    return ','.join(filters)


def _find_font() -> Optional[str]:
    """查找可用的中文字体"""
    candidates = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    ]
    for f in candidates:
        if Path(f).exists():
            return f
    return None


def _get_video_duration(path: Path) -> float:
    """获取视频/音频时长"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def compose_image_mode(images: List[Path], audio_path: Path, output_path: Path,
                       script: str, width: int = 1080, height: int = 1920,
                       fps: int = 30, font_size: int = 52, color: str = 'white',
                       box: bool = True, position: str = 'bottom',
                       fade: float = 0.3) -> bool:
    """
    图片模式：将多张图片按配音时长拼接成视频。

    每张图片配合一段配音，图片之间淡入淡出。
    """
    if not images:
        print("[ERROR] 没有素材图片/视频")
        return False

    if not audio_path.exists():
        print(f"[ERROR] 配音文件不存在: {audio_path}")
        return False

    audio_dur = _get_video_duration(audio_path)
    if audio_dur <= 0:
        print("[ERROR] 无法获取配音时长")
        return False

    sentences = _split_to_sentences(script)
    subtitle_filter = _build_subtitle_filter(
        sentences, audio_dur, font_size, color, box, position, width, height
    )

    # 单张图片：循环展示 + 配音 + 字幕
    if len(images) == 1:
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-loop', '1', '-i', str(images[0]),
            '-i', str(audio_path),
            '-vf', (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"fade=in:0:{int(fade*30)},"
                f"{subtitle_filter},"
                f"format=yuv420p"
            ),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest', '-pix_fmt', 'yuv420p',
            str(output_path),
        ]
    else:
        # 多张图片：每张图片展示均等时长
        per_img_dur = audio_dur / len(images)
        img_inputs = []
        for img in images:
            img_inputs.extend(['-loop', '1', '-t', str(per_img_dur), '-i', str(img)])

        # 构建 concat filter
        scaled = []
        for i in range(len(images)):
            scaled.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},fade=in:0:{int(fade*30)},"
                f"fade=out:st={per_img_dur - fade}:d={fade},"
                f"setpts=PTS-STARTPTS[v{i}]"
            )
        concat_inputs = ''.join([f'[v{i}]' for i in range(len(images))])

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
        ] + img_inputs + [
            '-i', str(audio_path),
            '-filter_complex',
            f"{';'.join(scaled)};"
            f"{concat_inputs}concat=n={len(images)}:v=1:a=0[outv];"
            f"[outv]{subtitle_filter}[outv2]",
            '-map', '[outv2]', '-map', '1:a',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest', '-pix_fmt', 'yuv420p',
            str(output_path),
        ]

    try:
        subprocess.run(cmd, check=True, timeout=300)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg 合成失败: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] FFmpeg 超时（300秒）")
        return False


def compose_video_mode(videos: List[Path], audio_path: Path, output_path: Path,
                       script: str, width: int = 1080, height: int = 1920,
                       fps: int = 30, font_size: int = 52, color: str = 'white',
                       box: bool = True, position: str = 'bottom') -> bool:
    """
    视频模式：将原视频素材拼接，替换配音，添加字幕。
    """
    if not videos:
        print("[ERROR] 没有素材视频")
        return False
    if not audio_path.exists():
        print(f"[ERROR] 配音文件不存在: {audio_path}")
        return False

    audio_dur = _get_video_duration(audio_path)
    if audio_dur <= 0:
        print("[ERROR] 无法获取配音时长")
        return False

    sentences = _split_to_sentences(script)
    subtitle_filter = _build_subtitle_filter(
        sentences, audio_dur, font_size, color, box, position, width, height
    )

    if len(videos) == 1:
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', str(videos[0]), '-i', str(audio_path),
            '-vf', (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"{subtitle_filter},"
                f"format=yuv420p"
            ),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest', '-pix_fmt', 'yuv420p',
            str(output_path),
        ]
    else:
        # 多段视频拼接
        concat_file = output_path.parent / '_video_concat.txt'
        with open(concat_file, 'w') as f:
            for v in videos:
                f.write(f"file '{v.absolute()}'\n")

        # 先拼视频
        merged = output_path.parent / '_merged_temp.mp4'
        subprocess.run(
            ['ffmpeg', '-y', '-loglevel', 'error',
             '-f', 'concat', '-safe', '0', '-i', str(concat_file),
             '-c', 'copy', str(merged)],
            check=True, timeout=60,
        )
        concat_file.unlink(missing_ok=True)

        # 配音 + 字幕
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'error',
            '-i', str(merged), '-i', str(audio_path),
            '-vf', (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"{subtitle_filter},"
                f"format=yuv420p"
            ),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-shortest', '-pix_fmt', 'yuv420p',
            str(output_path),
        ]

    try:
        subprocess.run(cmd, check=True, timeout=300)
        # 清理临时文件
        if len(videos) > 1:
            merged.unlink(missing_ok=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg 合成失败: {e}")
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] FFmpeg 超时（300秒）")
        return False


def collect_materials(materials_dir: Path) -> List[Path]:
    """收集素材目录中的照片和视频，按文件名排序"""
    if not materials_dir.exists():
        return []

    extensions = {'.jpg', '.jpeg', '.png', '.webp', '.bmp',
                  '.mp4', '.mov', '.avi', '.mkv'}
    files = [f for f in materials_dir.iterdir()
             if f.suffix.lower() in extensions and not f.name.startswith('.')]
    files.sort(key=lambda f: f.name)
    return files


def has_videos(materials: List[Path]) -> bool:
    """检测素材中是否包含视频"""
    video_exts = {'.mp4', '.mov', '.avi', '.mkv'}
    return any(f.suffix.lower() in video_exts for f in materials)


def compose(materials_dir: Path, audio_path: Path, output_path: Path,
            script: str, width: int = 1080, height: int = 1920,
            fps: int = 30, font_size: int = 52, color: str = 'white',
            box: bool = True, position: str = 'bottom',
            fade: float = 0.3) -> bool:
    """
    合成最终视频。

    自动检测素材类型：
    - 有视频 → 视频模式
    - 只有图片 → 图片模式
    """
    materials = collect_materials(materials_dir)
    if not materials:
        print("[ERROR] materials/ 目录为空，请放入照片或视频")
        return False

    print(f"  素材: {len(materials)} 个文件")
    print(f"  配音: {audio_path.name} ({_get_video_duration(audio_path):.1f}s)")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if has_videos(materials):
        print(f"  模式: 视频模式")
        videos = [m for m in materials if m.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}]
        return compose_video_mode(videos, audio_path, output_path, script,
                                  width, height, fps, font_size, color, box, position)
    else:
        print(f"  模式: 图片模式")
        images = list(materials)
        return compose_image_mode(images, audio_path, output_path, script,
                                  width, height, fps, font_size, color, box, position, fade)
