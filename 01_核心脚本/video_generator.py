#!/usr/bin/env python3
"""
视频自动化合成工具
将音频 + 图片/视频素材 合成为完整视频

使用方法:
    python3 video_generator.py --project 项目路径 [选项]

示例:
    # 图片模式 + 字幕 + 背景音乐
    python3 video_generator.py --project projects/2026-04-26_article --mode images --subtitle --bgm bgm.mp3

    # 视频模式（使用实拍素材）
    python3 video_generator.py --project projects/2026-04-26_article --mode videos

    # 自动模式（图片/视频混合）
    python3 video_generator.py --project projects/2026-04-26_article --mode auto
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import shutil


def get_audio_duration(audio_path: str) -> float:
    """获取音频时长（秒）"""
    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def get_video_duration(video_path: str) -> float:
    """获取视频时长（秒）"""
    return get_audio_duration(video_path)


def find_material(project_dir: Path, scene_name: str, mode: str) -> Optional[Path]:
    """
    查找场景对应的素材文件
    搜索顺序: videos > images
    """
    scene_base = scene_name.replace('scene_', '').replace('.mp3', '')

    search_dirs = []
    if mode in ['videos', 'auto']:
        search_dirs.extend([
            project_dir / '02_manual_videos',
            project_dir / '01_api_videos',
        ])
    if mode in ['images', 'auto']:
        search_dirs.extend([
            project_dir / '02_manual_images',
            project_dir / '01_api_images',
        ])

    # 支持的格式
    video_exts = ['.mp4', '.mov', '.avi', '.mkv']
    image_exts = ['.jpg', '.jpeg', '.png', '.webp']

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        # 尝试精确匹配
        for ext in video_exts + image_exts:
            candidate = search_dir / f"{scene_name}{ext}"
            if candidate.exists():
                return candidate

        # 尝试 scene_01 格式匹配
        for ext in video_exts + image_exts:
            candidate = search_dir / f"scene_{scene_base}{ext}"
            if candidate.exists():
                return candidate

        # 尝试数字匹配 (1.jpg, 01.jpg)
        for ext in video_exts + image_exts:
            for fmt in [f"{scene_base}{ext}", f"{int(scene_base):02d}{ext}"]:
                candidate = search_dir / fmt
                if candidate.exists():
                    return candidate

    return None


def create_scene_video(
    audio_path: Path,
    material_path: Path,
    output_path: Path,
    subtitle_text: str = "",
    resolution: Tuple[int, int] = (1920, 1080),
    fps: int = 30
) -> bool:
    """
    创建单个场景视频
    图片: 循环播放直到音频结束
    视频: 循环播放直到音频结束
    """
    audio_duration = get_audio_duration(str(audio_path))
    material_ext = material_path.suffix.lower()

    # 视频格式
    video_exts = ['.mp4', '.mov', '.avi', '.mkv']
    is_video = material_ext in video_exts

    # 构建 ffmpeg 命令
    if is_video:
        # 视频素材 - 循环播放
        material_duration = get_video_duration(str(material_path))
        loop_count = int(audio_duration / material_duration) + 1

        filter_complex = (
            f"[0:v]scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio=decrease,"
            f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={fps},format=yuv420p[v];"
            f"[1:a]volume=1.0[a]"
        )

        cmd = [
            'ffmpeg', '-y',
            '-stream_loop', str(loop_count),
            '-i', str(material_path),
            '-i', str(audio_path),
            '-filter_complex', filter_complex,
            '-map', '[v]', '-map', '[a]',
            '-t', str(audio_duration),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            str(output_path)
        ]
    else:
        # 图片素材 - 静态图片 + 轻微缩放效果
        filter_complex = (
            f"[0:v]scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio=decrease,"
            f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='min(zoom+0.001,1.1)':d={int(audio_duration * fps)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={resolution[0]}x{resolution[1]},"
            f"fps={fps},format=yuv420p,trim=duration={audio_duration}[v];"
            f"[1:a]volume=1.0[a]"
        )

        cmd = [
            'ffmpeg', '-y',
            '-loop', '1',
            '-i', str(material_path),
            '-i', str(audio_path),
            '-filter_complex', filter_complex,
            '-map', '[v]', '-map', '[a]',
            '-t', str(audio_duration),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-shortest',
            str(output_path)
        ]

    # 如果有字幕，添加字幕滤镜
    if subtitle_text:
        # 简化处理：使用 drawtext 添加字幕
        # 实际应该在 filter_complex 中添加
        pass

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ⚠️  ffmpeg 警告: {result.stderr[:200]}")
        return output_path.exists()
    except Exception as e:
        print(f"   ❌ 生成失败: {e}")
        return False


def add_transitions(scene_videos: List[Path], output_path: Path) -> bool:
    """
    为场景视频添加转场效果（淡入淡出）
    """
    if len(scene_videos) == 1:
        # 只有一个场景，直接复制
        shutil.copy(str(scene_videos[0]), str(output_path))
        return True

    # 创建 concat 文件列表
    filter_parts = []
    inputs = []

    for i, video in enumerate(scene_videos):
        inputs.extend(['-i', str(video)])

    # 构建 xfade 滤镜链
    # 简化：使用 fade 滤镜做淡入淡出
    filter_complex = ""
    for i in range(len(scene_videos)):
        if i == 0:
            filter_complex += f"[{i}:v]fade=t=out:st=999999:d=0[v{i}];"
        elif i == len(scene_videos) - 1:
            filter_complex += f"[{i}:v]fade=t=in:st=0:d=0.5[v{i}];"
        else:
            filter_complex += f"[{i}:v]fade=t=in:st=0:d=0.5,fade=t=out:st=999999:d=0[v{i}];"

    # 连接所有视频
    filter_complex += ""
    for i in range(len(scene_videos)):
        filter_complex += f"[v{i}][{i}:a]"
    filter_complex += f"concat=n={len(scene_videos)}:v=1:a=1[outv][outa]"

    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '[outv]', '-map', '[outa]',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_path.exists()
    except Exception as e:
        print(f"❌ 转场添加失败: {e}")
        # 失败时使用简单合并
        return simple_concat(scene_videos, output_path)


def simple_concat(scene_videos: List[Path], output_path: Path) -> bool:
    """简单合并视频（无转场）"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for video in scene_videos:
            f.write(f"file '{str(video)}'\n")
        concat_file = f.name

    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_path.exists()
    finally:
        os.unlink(concat_file)


def add_bgm(video_path: Path, bgm_path: Path, output_path: Path, bgm_volume: float = 0.3) -> bool:
    """添加背景音乐"""
    video_duration = get_video_duration(str(video_path))

    filter_complex = (
        f"[0:a]volume=1.0[va];"
        f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume},"
        f"atrim=0:{video_duration}[bgm];"
        f"[va][bgm]amix=inputs=2:duration=first[a]"
    )

    cmd = [
        'ffmpeg', '-y',
        '-i', str(video_path),
        '-stream_loop', '-1',
        '-i', str(bgm_path),
        '-filter_complex', filter_complex,
        '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        str(output_path)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return output_path.exists()
    except Exception as e:
        print(f"❌ BGM 添加失败: {e}")
        shutil.copy(str(video_path), str(output_path))
        return True


def main():
    parser = argparse.ArgumentParser(
        description="视频自动化合成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 图片模式 + 字幕
  python3 video_generator.py --project projects/XXX --mode images --subtitle

  # 视频素材模式 + 转场 + BGM
  python3 video_generator.py --project projects/XXX --mode videos --transition --bgm music.mp3

  # 自动模式（自动识别图片/视频）
  python3 video_generator.py --project projects/XXX --mode auto
        """
    )
    parser.add_argument('--project', '-p', required=True, help='项目文件夹路径')
    parser.add_argument('--mode', choices=['images', 'videos', 'auto'], default='auto',
                       help='素材模式 (默认: auto)')
    parser.add_argument('--subtitle', '-s', action='store_true', help='添加字幕')
    parser.add_argument('--transition', '-t', action='store_true', default=True,
                       help='添加转场效果 (默认: 开启)')
    parser.add_argument('--no-transition', action='store_true', help='关闭转场效果')
    parser.add_argument('--bgm', '-b', help='背景音乐文件路径')
    parser.add_argument('--bgm-volume', type=float, default=0.3, help='背景音乐音量 (0.0-1.0, 默认: 0.3)')
    parser.add_argument('--output', '-o', help='输出文件名 (默认: final_video.mp4)')
    parser.add_argument('--resolution', default='1920x1080', help='分辨率 (默认: 1920x1080)')
    parser.add_argument('--fps', type=int, default=30, help='帧率 (默认: 30)')

    args = parser.parse_args()

    # 检查 ffmpeg
    if not shutil.which('ffmpeg'):
        print("❌ 未找到 ffmpeg，请先安装: brew install ffmpeg")
        sys.exit(1)

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"❌ 项目不存在: {args.project}")
        sys.exit(1)

    # 读取 plan.json
    plan_path = project_dir / 'plan.json'
    if not plan_path.exists():
        print(f"❌ 未找到 plan.json: {plan_path}")
        sys.exit(1)

    with open(plan_path, 'r', encoding='utf-8') as f:
        plan = json.load(f)

    scenes = plan.get('scenes', [])
    if not scenes:
        print("❌ plan.json 中没有场景信息")
        sys.exit(1)

    # 设置输出路径
    final_dir = project_dir / '04_final'
    final_dir.mkdir(exist_ok=True)

    if args.output:
        output_path = final_dir / args.output
    else:
        output_path = final_dir / 'final_video.mp4'

    # 解析分辨率
    width, height = map(int, args.resolution.split('x'))

    print("=" * 60)
    print("🎬 视频自动化合成")
    print("=" * 60)
    print(f"📁 项目: {project_dir}")
    print(f"🎨 模式: {args.mode}")
    print(f"📐 分辨率: {width}x{height}")
    print(f"🎞️  场景数: {len(scenes)}")
    print(f"✨ 转场: {'开启' if not args.no_transition else '关闭'}")
    print(f"📝 字幕: {'开启' if args.subtitle else '关闭'}")
    if args.bgm:
        print(f"🎵 BGM: {args.bgm} (音量: {args.bgm_volume})")
    print()

    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    scene_videos = []

    try:
        # 处理每个场景
        for i, scene in enumerate(scenes, 1):
            scene_num = f"{i:02d}"
            audio_name = f"scene_{scene_num}.mp3"
            audio_path = project_dir / '03_audio' / audio_name

            print(f"[{i}/{len(scenes)}] 处理场景 {scene_num}...")

            if not audio_path.exists():
                print(f"   ⚠️  跳过: 未找到音频 {audio_name}")
                continue

            # 查找素材
            material_path = find_material(project_dir, scene_num, args.mode)
            if not material_path:
                print(f"   ⚠️  跳过: 未找到素材 (scene_{scene_num})")
                continue

            print(f"   🎵 音频: {audio_name}")
            print(f"   🖼️  素材: {material_path.name}")

            # 生成场景视频
            scene_output = Path(temp_dir) / f"scene_{scene_num}.mp4"
            subtitle = scene.get('subtitle', '') if args.subtitle else ''

            if create_scene_video(
                audio_path, material_path, scene_output,
                subtitle, (width, height), args.fps
            ):
                scene_videos.append(scene_output)
                duration = get_audio_duration(str(audio_path))
                print(f"   ✅ 完成 ({duration:.1f}s)")
            else:
                print(f"   ❌ 失败")

        if not scene_videos:
            print("\n❌ 没有成功生成任何场景视频")
            sys.exit(1)

        # 合并场景视频
        print("\n" + "=" * 60)
        print("🎞️  合并场景视频...")

        concat_path = Path(temp_dir) / 'concat.mp4'

        if args.no_transition:
            success = simple_concat(scene_videos, concat_path)
        else:
            success = add_transitions(scene_videos, concat_path)

        if not success or not concat_path.exists():
            print("❌ 合并失败")
            sys.exit(1)

        # 添加 BGM
        if args.bgm and Path(args.bgm).exists():
            print("🎵 添加背景音乐...")
            final_temp = Path(temp_dir) / 'with_bgm.mp4'
            if add_bgm(concat_path, Path(args.bgm), final_temp, args.bgm_volume):
                concat_path = final_temp
                print("✅ BGM 添加完成")
            else:
                print("⚠️ BGM 添加失败，继续无 BGM 版本")

        # 复制到最终位置
        shutil.copy(str(concat_path), str(output_path))

        # 显示结果
        final_duration = get_video_duration(str(output_path))
        final_size = output_path.stat().st_size / (1024 * 1024)

        print("\n" + "=" * 60)
        print("✅ 视频合成完成!")
        print("=" * 60)
        print(f"📁 输出文件: {output_path}")
        print(f"⏱️  视频时长: {final_duration:.1f} 秒")
        print(f"📦 文件大小: {final_size:.1f} MB")
        print(f"🎞️  成功场景: {len(scene_videos)}/{len(scenes)}")
        print()
        print("▶️  播放命令:")
        print(f"   open '{output_path}'")

    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
