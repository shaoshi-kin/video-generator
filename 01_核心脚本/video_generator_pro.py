#!/usr/bin/env python3
"""
视频合成工具 Pro 版
支持：字幕样式自定义、多种转场、片头片尾、批量处理

使用方法:
    python3 video_generator_pro.py --project 项目路径 [选项]

示例:
    # 基础用法（自动使用 04_videos 或 05_audio + 图片）
    python3 video_generator_pro.py --project projects/XXX

    # 带字幕 + 片头片尾 + 转场
    python3 video_generator_pro.py --project projects/XXX \
        --subtitle --subtitle-style news \
        --transition fade \
        --intro intro.mp4 --outro outro.mp4

    # 批量处理
    python3 video_generator_pro.py --batch projects/*
"""

import os
import sys
import json
import subprocess
import argparse
import asyncio
import re
import time
import datetime
import concurrent.futures
import logging
import traceback
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import tempfile
import shutil
from dataclasses import dataclass

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


# 字幕样式预设
SUBTITLE_STYLES = {
    'news': {
        'font': 'SourceHanSansSC-Bold',
        'size': 48,
        'color': 'white',
        'box': 1,
        'boxcolor': 'black@0.7',
        'boxborderw': 10,
        'borderw': 2,
        'bordercolor': 'black',
        'position': 'bottom',
        'y_offset': 100
    },
    'youtube': {
        'font': 'Arial-Bold',
        'size': 42,
        'color': 'yellow',
        'box': 0,
        'borderw': 3,
        'bordercolor': 'black',
        'position': 'bottom',
        'y_offset': 80
    },
    'minimal': {
        'font': 'SourceHanSansSC-Regular',
        'size': 40,
        'color': 'white',
        'box': 0,
        'borderw': 2,
        'bordercolor': 'black@0.5',
        'position': 'center',
        'y_offset': 0
    },
    'tiktok': {
        'font': 'SourceHanSansSC-Bold',
        'size': 52,
        'color': 'white',
        'box': 1,
        'boxcolor': 'black@0.5',
        'boxborderw': 8,
        'borderw': 3,
        'bordercolor': 'black',
        'position': 'center',
        'y_offset': 100
    }
}


# 转场效果预设（基于 ffmpeg xfade 滤镜，需 ffmpeg 4.3+）
TRANSITIONS = {
    'fade': 'fade',
    'dissolve': 'dissolve',
    'wipeleft': 'wipeleft',
    'wiperight': 'wiperight',
    'wipeup': 'wipeup',
    'wipedown': 'wipedown',
    'slideleft': 'slideleft',
    'slideright': 'slideright',
    'slideup': 'slideup',
    'slidedown': 'slidedown',
    'smoothleft': 'smoothleft',
    'smoothright': 'smoothright',
    'smoothup': 'smoothup',
    'smoothdown': 'smoothdown',
    'circlecrop': 'circlecrop',
    'rectcrop': 'rectcrop',
    'circleclose': 'circleclose',
    'circleopen': 'circleopen',
    'horzclose': 'horzclose',
    'horzopen': 'horzopen',
    'vertclose': 'vertclose',
    'vertopen': 'vertopen',
    'diagbl': 'diagbl',
    'diagbr': 'diagbr',
    'diagtl': 'diagtl',
    'diagtr': 'diagtr',
    'hlslice': 'hlslice',
    'hrslice': 'hrslice',
    'vuslice': 'vuslice',
    'vdslice': 'vdslice',
    'pixelize': 'pixelize',
    'radial': 'radial',
    'distance': 'distance',
    'fadeblack': 'fadeblack',
    'fadewhite': 'fadewhite',
    'none': None
}


# 项目模板预设
PROJECT_TEMPLATES = {
    'news': {
        'mode': 'image',
        'resolution': '1920x1080',
        'fps': 30,
        'subtitle_style': 'news',
        'transition': 'fade',
        'voice': 'Yunjian',
        'article': """# 今日新闻

@全局:云健
@默认图: 新闻台标

欢迎收看今日新闻。

@女声: @图:现场 记者现场报道，投资者情绪高涨。

@云健: 第二条新闻：国际油价回落。

@女声: @图:油价 布伦特原油跌至80美元。

@云健: 第三条新闻：央行宣布降准。

感谢收看今日新闻。
"""
    },
    'food': {
        'mode': 'image',
        'resolution': '1080x1920',
        'fps': 30,
        'subtitle_style': 'tiktok',
        'transition': 'pixelize',
        'voice': 'Xiaoxiao',
        'article': """# 美食探店

@全局:女声
@默认图: 餐厅环境

@男声: 大家好，欢迎来到美食探店。

@图:招牌菜
@男声: 这是我们的招牌菜，色香味俱全。

回到女声介绍餐厅环境。

@图:厨师
@男声: 我们的大厨有20年经验。

@图:食材
@女声: 所有食材都是当天采购。

@图:价格
@男声: 价格非常亲民。

@女声: 欢迎来品尝！
"""
    },
    'tutorial': {
        'mode': 'image',
        'resolution': '1920x1080',
        'fps': 30,
        'subtitle_style': 'youtube',
        'transition': 'slideleft',
        'voice': 'Xiaoyi',
        'article': """# Python入门课程

@全局:晓伊
@默认图: 课程封面

欢迎来到Python入门课程。我是主讲老师李老师。

@云希: 我是助教小张，负责解答大家的问题。

今天我们先了解什么是Python。

@云希: Python是一种简单易学但功能强大的编程语言。

接下来我们安装Python环境。
"""
    },
    'education': {
        'mode': 'image',
        'resolution': '1920x1080',
        'fps': 30,
        'subtitle_style': 'minimal',
        'transition': 'fade',
        'voice': 'Yunyang',
        'article': """# 历史知识科普

@全局:男声
@默认图: 历史背景

今天我们来聊聊三国时期的故事。

@图:诸葛亮
@女声: 诸葛亮是蜀汉的丞相，以智慧著称。

@男声: 他草船借箭、空城计的故事家喻户晓。

@图:赤壁
@女声: 赤壁之战是三国时期最著名的战役之一。

@男声: 感谢收听，我们下期再见！
"""
    }
}


@dataclass
class Scene:
    """场景数据类"""
    index: int
    audio_path: Optional[Path]
    video_path: Optional[Path]
    image_path: Optional[Path]
    subtitle: str
    duration: float


class Tee:
    """同时输出到终端和文件的 stdout 重定向器"""
    def __init__(self, file_path: Path, encoding='utf-8'):
        self.terminal = sys.stdout
        self.log_file = open(file_path, 'w', encoding=encoding, buffering=1)

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        if self.log_file and not self.log_file.closed:
            self.log_file.close()


def setup_logging(project_dir: Path, preview_mode: bool = False) -> Optional[Tee]:
    """设置日志：同时输出到终端和日志文件"""
    final_dir = project_dir / '07_final'
    final_dir.mkdir(exist_ok=True)

    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_name = f"generate_{now}.log"
    log_path = final_dir / log_name

    tee = Tee(log_path)
    sys.stdout = tee

    print(f"\n📝 运行日志已保存: {log_path}")
    return tee


# ffprobe 时长缓存（避免重复调用）
_DURATION_CACHE: Dict[str, float] = {}


def get_media_duration(path: str) -> float:
    """获取媒体时长（秒），带缓存"""
    # 使用路径+修改时间作为缓存键，文件变更自动失效
    try:
        mtime = str(os.path.getmtime(path))
    except OSError:
        mtime = '0'
    cache_key = f"{path}:{mtime}"

    if cache_key in _DURATION_CACHE:
        return _DURATION_CACHE[cache_key]

    cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        duration = float(result.stdout.strip())
        _DURATION_CACHE[cache_key] = duration
        return duration
    except:
        _DURATION_CACHE[cache_key] = 0.0
        return 0.0


def run_ffmpeg(cmd: list, max_retries: int = 2, check_output: bool = True) -> subprocess.CompletedProcess:
    """运行 ffmpeg 命令，支持失败重试"""
    for attempt in range(1, max_retries + 1):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return result
        if attempt < max_retries:
            stderr_short = result.stderr[:200].replace('\n', ' ')
            print(f"   ⚠️  ffmpeg 失败 (尝试 {attempt}/{max_retries}): {stderr_short}")
            print(f"   ⏳  2秒后重试...")
            time.sleep(2)
        else:
            print(f"   ❌ ffmpeg 最终失败 (已重试 {max_retries} 次)")
            if check_output and result.stderr:
                print(f"   错误详情: {result.stderr[:500]}")
    return result


def build_subtitle_filter(
    subtitle: str,
    subtitle_style: Dict,
    width: int,
    height: int,
    animation: str = 'none',
    anim_duration: float = 0.5
) -> str:
    """构建字幕滤镜字符串，支持动画效果"""
    y_pos = height - subtitle_style['y_offset'] if subtitle_style['position'] == 'bottom' else height // 2

    # 基础 drawtext 参数
    base = (
        f"drawtext=fontfile=/System/Library/Fonts/STHeiti\\ Medium.ttc:"
        f"text='{subtitle}':"
        f"fontcolor={subtitle_style['color']}:"
        f"fontsize={subtitle_style['size']}:"
        f"borderw={subtitle_style['borderw']}:"
        f"bordercolor={subtitle_style['bordercolor']}"
    )

    # 动画效果
    if animation == 'slide_up':
        start_y = height + 100
        y_expr = f"if(lt(t\\,{anim_duration})\\,{start_y}-({start_y}-{y_pos})/{anim_duration}*t\\,{y_pos})"
        base += f":y={y_expr}:x=(w-text_w)/2"
    elif animation == 'fade_in':
        alpha_expr = f"if(lt(t\\,{anim_duration})\\,t/{anim_duration}\\,1)"
        base += f":y={y_pos}:x=(w-text_w)/2:alpha={alpha_expr}"
    else:
        base += f":x=(w-text_w)/2:y={y_pos}"

    if subtitle_style.get('box'):
        base += f":box=1:boxcolor={subtitle_style['boxcolor']}:boxborderw={subtitle_style['boxborderw']}"

    return base


def build_fade_filter(duration: float, fade_duration: float) -> str:
    """构建淡入淡出滤镜"""
    if fade_duration <= 0 or duration <= fade_duration * 2:
        return ""
    fade_out_start = max(0, duration - fade_duration)
    return f",fade=t=in:st=0:d={fade_duration},fade=t=out:st={fade_out_start}:d={fade_duration}"


# 音色映射表
VOICE_MAP = {
    # 官方名称
    'Xiaoxiao': 'zh-CN-XiaoxiaoNeural',
    'Xiaoyi': 'zh-CN-XiaoyiNeural',
    'Yunxi': 'zh-CN-YunxiNeural',
    'Yunjian': 'zh-CN-YunjianNeural',
    'Yunxia': 'zh-CN-YunxiaNeural',
    'Yunyang': 'zh-CN-YunyangNeural',
    # 别名 - 女声
    '女声': 'zh-CN-XiaoxiaoNeural',
    '晓晓': 'zh-CN-XiaoxiaoNeural',
    '晓伊': 'zh-CN-XiaoyiNeural',
    '云夏': 'zh-CN-YunxiaNeural',
    '成熟女': 'zh-CN-XiaoyiNeural',
    '年轻女': 'zh-CN-YunxiaNeural',
    # 别名 - 男声
    '男声': 'zh-CN-YunyangNeural',
    '云扬': 'zh-CN-YunyangNeural',
    '云希': 'zh-CN-YunxiNeural',
    '云健': 'zh-CN-YunjianNeural',
    '成熟男': 'zh-CN-YunyangNeural',
    '年轻男': 'zh-CN-YunxiNeural',
    '新闻男': 'zh-CN-YunjianNeural',
}


def parse_voice_segments(text: str, default_voice: str = 'Xiaoxiao') -> list:
    """解析文章中的 @音色 标记

    返回: [(voice_key, content), ...]

    支持格式:
    - @女声: 内容
    - @男声: 内容
    - @晓晓: 内容
    - @云扬: 内容
    - @全局:女声  (设置默认音色，不生成音频)
    """
    segments = []
    current_voice = default_voice

    # 检查全局设置 @全局:音色
    global_match = re.search(r'@全局[:：](\w+)', text)
    if global_match:
        global_voice = global_match.group(1)
        if global_voice in VOICE_MAP:
            current_voice = global_voice
            print(f"   🎭 全局音色设置: {global_voice}")
        # 从文本中移除全局设置行，避免被当成普通标记处理
        text = re.sub(r'@全局[:：]\w+\n?', '', text)
    return segments, text, current_voice


def parse_article_segments(text: str, default_voice: str = 'Xiaoxiao') -> tuple:
    """解析文章，提取音色和图片分配信息

    返回: (segments, default_image)
    segments: [(voice_key, content, image_ref), ...]
    default_image: str 或 None (默认图片引用)

    支持格式:
    - @女声: 内容
    - @男声: 内容
    - @图:01 / @图片:02 / @img:03  - 指定图片
    - @默认图:01 / @默认图:bg.jpg   - 设置默认图片
    """
    segments = []
    current_voice = default_voice
    current_image = None  # 当前段落指定的图片
    default_image = None  # 全局默认图片

    # 检查全局设置
    # 1. 全局音色设置
    global_voice_match = re.search(r'@全局[:：](\w+)', text)
    if global_voice_match:
        global_voice = global_voice_match.group(1)
        if global_voice in VOICE_MAP:
            current_voice = global_voice
            default_voice = global_voice  # 同时更新 default_voice，空行重置时用
            print(f"   🎭 全局音色设置: {global_voice}")
        text = re.sub(r'@全局[:：]\w+\n?', '', text)

    # 2. 默认图片设置 @默认图:xx 或 @默认图片:xx
    default_img_match = re.search(r'@默认图(?:片)?[:：]\s*(\S+)', text)
    if default_img_match:
        default_image = default_img_match.group(1)
        print(f"   🖼️  默认图片设置: {default_image}")
        text = re.sub(r'@默认图(?:片)?[:：]\s*\S+\n?', '', text)

    # 初始化 current_image 为 default_image
    current_image = default_image

    # 按行分割并解析
    lines = text.split('\n')
    current_content = []

    for line in lines:
        line = line.strip()
        if not line:
            # 空行，保存当前段落
            if current_content:
                content = ' '.join(current_content).strip()
                if content and len(content) >= 3:
                    segments.append((current_voice, content, current_image))
                current_content = []
            # 重置当前图片和音色为默认值
            current_image = default_image
            current_voice = default_voice
            continue

        # 跳过 Markdown 标题行
        if line.startswith('#'):
            continue

        # 检查是否是图片标记行 @图:xx / @图片:xx / @img:xx
        img_match = re.match(r'@(图|图片|img)[:：]\s*(\S+)(.*)', line, re.IGNORECASE)
        if img_match:
            img_ref = img_match.group(2).strip()
            remaining_content = img_match.group(3).strip()

            # 保存之前的内容（使用之前的图片设置）
            if current_content:
                content = ' '.join(current_content).strip()
                if content and len(content) >= 3:
                    segments.append((current_voice, content, current_image))
                current_content = []

            # 更新当前图片设置
            current_image = img_ref

            # 如果有剩余内容，添加到当前段落
            if remaining_content and len(remaining_content) >= 3:
                current_content.append(remaining_content)
            continue

        # 检查是否是音色标记行 @音色:内容
        voice_match = re.match(r'@(\w+)[:：](.*)', line)
        if voice_match:
            voice_key = voice_match.group(1)
            content = voice_match.group(2).strip()

            # 如果是有效音色
            if voice_key in VOICE_MAP:
                # 先保存之前的内容
                if current_content:
                    prev_content = ' '.join(current_content).strip()
                    if prev_content and len(prev_content) >= 3:
                        segments.append((current_voice, prev_content, current_image))
                    current_content = []

                # 更新音色并添加当前内容
                current_voice = voice_key
                if content and len(content) >= 3:
                    # 检查内容中是否嵌套图片标记 @图:xx
                    img_in_content = re.match(r'@(图|图片|img)[:：]\s*(\S+)(.*)', content, re.IGNORECASE)
                    if img_in_content:
                        img_ref = img_in_content.group(2).strip()
                        remaining = img_in_content.group(3).strip()
                        current_image = img_ref  # 更新当前图片
                        if remaining and len(remaining) >= 3:
                            segments.append((current_voice, remaining, current_image))
                    else:
                        segments.append((current_voice, content, current_image))
            else:
                # 不是有效音色，当作普通内容
                line = re.sub(r'^#+\s*', '', line)
                line = re.sub(r'^\s*[-*+\d]\s+', '', line)
                if line:
                    current_content.append(line)
        else:
            # 普通内容行
            line = re.sub(r'^#+\s*', '', line)
            line = re.sub(r'^\s*[-*+\d]\s+', '', line)
            if line:
                current_content.append(line)

    # 保存最后一段
    if current_content:
        content = ' '.join(current_content).strip()
        if content and len(content) >= 3:
            segments.append((current_voice, content, current_image))

    return segments, default_image


async def generate_tts_with_retry(content: str, voice_id: str, output_path: Path, rate: str = '+0%', max_retries: int = 3) -> bool:
    """生成单段TTS音频，支持网络重试"""
    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(content, voice=voice_id, rate=rate)
            await communicate.save(str(output_path))
            return True
        except Exception as e:
            if attempt < max_retries:
                wait = attempt * 2  # 递增等待: 2s, 4s, 6s
                print(f"   ⚠️  TTS生成失败 (尝试 {attempt}/{max_retries}): {e}")
                print(f"   ⏳  {wait}秒后重试...")
                await asyncio.sleep(wait)
            else:
                print(f"   ❌ TTS生成最终失败 (已重试 {max_retries} 次): {e}")
                traceback.print_exc()
                return False
    return False


async def generate_audio_from_article(article_path: Path, output_dir: Path, voice: str = 'Xiaoxiao', rate: str = '+0%', video_mode: bool = False) -> tuple:
    """从文章自动生成音频，支持 @音色 多角色标记和 @图 图片分配

    Args:
        video_mode: True=生成单个合并音频(视频模式), False=生成分段音频(图片模式)

    Returns:
        (success, segments_info)
        success: bool - 是否成功
        segments_info: list of dict - 每段的音色和图片分配信息
    """
    if not EDGE_TTS_AVAILABLE:
        print("   ⚠️  未安装 edge_tts，跳过音频生成")
        return False, []

    # 读取文章
    with open(article_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    # 统一换行符（处理 Windows CRLF）
    raw_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')

    # 清理文本（保留 @标记）
    text = re.sub(r'```[\s\S]*?```', '', raw_text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    if not text.strip():
        return False, []

    print(f"   🎙️  正在生成音频: {article_path.name}")

    # 解析带音色和图片标记的段落
    segments, default_image = parse_article_segments(text, default_voice=voice)

    if not segments:
        print("   ❌ 未找到有效内容")
        return False, []

    # 显示音色分配
    voice_summary = {}
    image_summary = {}
    for v, _, img in segments:
        voice_summary[v] = voice_summary.get(v, 0) + 1
        img_key = img if img else '顺序分配'
        image_summary[img_key] = image_summary.get(img_key, 0) + 1
    print(f"   🎭 音色分配: {', '.join([f'{v}({n}段)' for v, n in voice_summary.items()])}")
    if len(image_summary) > 1 or default_image:
        print(f"   🖼️  图片分配: {', '.join([f'{k}({n}段)' for k, n in image_summary.items()])}")

    try:
        segments_info = []
        semaphore = asyncio.Semaphore(3)

        async def _gen_one(i, voice_key, content, img_ref, output_path, label='场景'):
            """单个音频生成，受 semaphore 限流"""
            async with semaphore:
                voice_id = VOICE_MAP.get(voice_key, VOICE_MAP.get(voice, 'zh-CN-XiaoxiaoNeural'))
                success = await generate_tts_with_retry(content, voice_id, output_path, rate)
                if success:
                    segments_info.append({'voice': voice_key, 'image': img_ref or default_image, 'text': content, 'index': i})
                    img_info = f" [图:{img_ref}]" if img_ref else ""
                    print(f"      ✓ {label} {i}: [{voice_key}]{img_info} {content[:25]}...")
                return success

        if video_mode:
            # 视频模式：合并所有段落，但按音色分段生成后合并
            print(f"   📝 视频模式：合并 {len(segments)} 个音色段落")

            if len(segments) == 1:
                # 只有一个段落，直接生成
                voice_key, content, img_ref = segments[0]
                voice_id = VOICE_MAP.get(voice_key, VOICE_MAP.get(voice, 'zh-CN-XiaoxiaoNeural'))
                output_path = output_dir / "scene_01.mp3"
                if await generate_tts_with_retry(content, voice_id, output_path, rate):
                    print(f"   ✅ 音频生成完成: {output_path.name} ({len(content)} 字, {voice_key})")
                    segments_info.append({'voice': voice_key, 'image': img_ref or default_image, 'text': content, 'index': 1})
                else:
                    return False, []
            else:
                # 多音色，并行生成临时文件
                temp_files = []
                tasks = []
                for i, (voice_key, content, img_ref) in enumerate(segments, 1):
                    temp_path = output_dir / f"_temp_{i:02d}.mp3"
                    temp_files.append(temp_path)
                    tasks.append(_gen_one(i, voice_key, content, img_ref, temp_path, label='段落'))

                results = await asyncio.gather(*tasks)
                if not all(results):
                    # 清理已生成的临时文件
                    for tf in temp_files:
                        if tf.exists():
                            tf.unlink()
                    return False, []

                # 合并音频
                output_path = output_dir / "scene_01.mp3"
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    for temp_file in temp_files:
                        escaped = str(temp_file).replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                    concat_file = f.name

                try:
                    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                           '-i', concat_file, '-c', 'copy', str(output_path)]
                    result = run_ffmpeg(cmd, max_retries=2)
                    success = result.returncode == 0
                finally:
                    os.unlink(concat_file)
                    for temp_file in temp_files:
                        if temp_file.exists():
                            temp_file.unlink()

                if success:
                    print(f"   ✅ 音频生成完成: {output_path.name} ({len(segments)} 个音色段落)")
                return success, segments_info

            return True, segments_info
        else:
            # 图片模式：并行生成每个段落音频
            print(f"   🚀 并行生成 {len(segments)} 段音频（最多3并发）...")
            tasks = []
            for i, (voice_key, content, img_ref) in enumerate(segments, 1):
                output_path = output_dir / f"scene_{i:02d}.mp3"
                tasks.append(_gen_one(i, voice_key, content, img_ref, output_path))

            results = await asyncio.gather(*tasks)
            if not all(results):
                return False, []

            print(f"   ✅ 音频生成完成: {len(segments)} 个场景")
            return True, segments_info
    except Exception as e:
        print(f"   ❌ 音频生成失败: {e}")
        traceback.print_exc()
        return False, []


def auto_generate_audio(project_dir: Path, voice: str = 'Xiaoxiao', rate: str = '+0%', force: bool = False) -> tuple:
    """检查并自动生成音频

    Args:
        force: True=强制重新生成，删除已有音频

    Returns:
        (success, segments_info)
        success: bool - 是否成功
        segments_info: list of dict - 每段的音色和图片分配信息（图片模式）
    """
    audio_dir = project_dir / '05_audio'
    article_dir = project_dir / '01_article'

    # 如果已经有音频且非强制模式，跳过
    if not force and audio_dir.exists() and list(audio_dir.glob('*.mp3')):
        return False, []

    # 强制模式：删除已有音频
    if force and audio_dir.exists():
        for f in audio_dir.glob('*.mp3'):
            f.unlink()
        print(f"🔄 强制重新生成音频，已清理旧音频")

    # 查找文章文件
    if not article_dir.exists():
        return False, []

    article_files = list(article_dir.glob('*.md')) + list(article_dir.glob('*.txt'))
    if not article_files:
        return False, []

    # 检测模式：如果有视频目录且包含视频文件，则为视频模式
    videos_dir = project_dir / '04_videos'
    video_mode = videos_dir.exists() and any(videos_dir.iterdir())

    # 创建音频目录
    audio_dir.mkdir(exist_ok=True)

    # 选择第一个文章文件
    article_path = article_files[0]
    print(f"\n📄 发现文章: {article_path.name}")
    if video_mode:
        print("🎬 视频模式：生成单个完整音频")
    else:
        print("🖼️ 图片模式：生成多段音频")
    print("🎙️  正在自动生成音频...")

    # 运行异步生成
    try:
        return asyncio.run(generate_audio_from_article(article_path, audio_dir, voice, rate, video_mode))
    except Exception as e:
        print(f"   ❌ 生成失败: {e}")
        traceback.print_exc()
        return False, []


def find_image_by_ref(project_dir: Path, image_ref: str) -> Optional[Path]:
    """根据图片引用查找图片文件

    image_ref 可以是:
    - 数字: "01", "1" -> 查找 scene_01.jpg / 01.jpg / 1.jpg
    - 文件名: "bg.jpg" -> 查找 bg.jpg
    """
    if not image_ref:
        return None

    # 支持的图片目录和扩展名（包含大小写）
    img_dirs = ['03_images', '03_manual_images', '01_api_images']
    exts = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.gif',
            '.JPG', '.JPEG', '.PNG', '.WEBP', '.HEIC', '.GIF']

    for img_dir in img_dirs:
        img_dir_path = project_dir / img_dir
        if not img_dir_path.exists():
            continue

        # 如果是纯数字，尝试多种格式
        if image_ref.isdigit():
            num = int(image_ref)
            for ext in exts:
                # scene_XX.ext (scene_01.jpg)
                candidate = img_dir_path / f"scene_{num:02d}{ext}"
                if candidate.exists():
                    return candidate
                # XX.ext (01.jpg)
                candidate = img_dir_path / f"{num:02d}{ext}"
                if candidate.exists():
                    return candidate
                # X.ext (1.jpg) - 无前导零
                candidate = img_dir_path / f"{num}{ext}"
                if candidate.exists():
                    return candidate
        else:
            # 当作文件名处理
            for ext in exts:
                candidate = img_dir_path / f"{image_ref}{ext}"
                if candidate.exists():
                    return candidate
            # 如果用户已经带了扩展名
            candidate = img_dir_path / image_ref
            if candidate.exists():
                return candidate

    return None


def find_scenes(project_dir: Path, image_assignments: list = None) -> List[Scene]:
    """
    自动发现项目中的所有场景
    优先级：04_videos > 05_audio + 图片

    Args:
        image_assignments: 可选，每段音频对应的图片分配信息
            [{'index': 1, 'voice': '女声', 'image': '01'}, ...]
    """
    scenes = []

    # 先查找 04_videos 目录
    videos_dir = project_dir / '04_videos'
    if videos_dir.exists():
        video_files = sorted([f for f in videos_dir.iterdir()
                            if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']])

        for i, video_file in enumerate(video_files, 1):
            duration = get_media_duration(str(video_file))
            # 尝试找对应的音频
            audio_path = project_dir / '05_audio' / f"scene_{i:02d}.mp3"
            if not audio_path.exists():
                audio_path = None

            # 从图片分配信息中获取字幕文本
            subtitle_text = ''
            if image_assignments and i <= len(image_assignments):
                subtitle_text = image_assignments[i - 1].get('text', '')

            scenes.append(Scene(
                index=i,
                audio_path=audio_path,
                video_path=video_file,
                image_path=None,
                subtitle=subtitle_text,
                duration=duration
            ))

    # 如果没有视频，查找音频+图片
    if not scenes:
        audio_dir = project_dir / '05_audio'
        if audio_dir.exists():
            audio_files = sorted([f for f in audio_dir.iterdir()
                                if f.suffix == '.mp3'])

            for i, audio_file in enumerate(audio_files, 1):
                duration = get_media_duration(str(audio_file))

                # 查找对应图片
                image_path = None

                # 优先使用图片分配信息
                if image_assignments and i <= len(image_assignments):
                    assignment = image_assignments[i - 1]  # index 从 1 开始
                    img_ref = assignment.get('image')
                    if img_ref:
                        image_path = find_image_by_ref(project_dir, img_ref)
                        if image_path:
                            print(f"   🖼️  场景 {i}: 使用指定图片 [{img_ref}] -> {image_path.name}")

                # 如果没有指定图片或找不到，使用顺序分配
                if not image_path:
                    exts = ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.gif',
                            '.JPG', '.JPEG', '.PNG', '.WEBP', '.HEIC', '.GIF']
                    for img_dir in ['03_images', '03_manual_images', '01_api_images']:
                        img_dir_path = project_dir / img_dir
                        if img_dir_path.exists():
                            # 1. 尝试标准命名 scene_XX.ext
                            for ext in exts:
                                candidate = img_dir_path / f"scene_{i:02d}{ext}"
                                if candidate.exists():
                                    image_path = candidate
                                    break
                            # 2. 尝试数字命名 XX.ext
                            if not image_path:
                                for ext in exts:
                                    candidate = img_dir_path / f"{i:02d}{ext}"
                                    if candidate.exists():
                                        image_path = candidate
                                        break
                            # 3. 尝试无前导零 X.ext
                            if not image_path:
                                for ext in exts:
                                    candidate = img_dir_path / f"{i}{ext}"
                                    if candidate.exists():
                                        image_path = candidate
                                        break
                            # 4. 回退到目录中第 i 个图片（支持中文名任意命名）
                            if not image_path:
                                all_images = sorted([
                                    f for f in img_dir_path.iterdir()
                                    if f.is_file() and f.suffix.lower() in
                                       ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic', '.bmp', '.tiff']
                                ])
                                # 有默认图时用默认图，否则按顺序取第 i 个
                                # 注意：这里需要获取 default_image 的值
                                # 但由于当前上下文没有 default_image，我们在外层处理
                                if i <= len(all_images):
                                    image_path = all_images[i - 1]
                            if image_path:
                                break

                # 从图片分配信息中获取字幕文本
                subtitle_text = ''
                if image_assignments and i <= len(image_assignments):
                    subtitle_text = image_assignments[i - 1].get('text', '')

                scenes.append(Scene(
                    index=i,
                    audio_path=audio_file,
                    video_path=None,
                    image_path=image_path,
                    subtitle=subtitle_text,
                    duration=duration
                ))

    return scenes


def create_scene_with_effects(
    scene: Scene,
    output_path: Path,
    resolution: Tuple[int, int],
    fps: int,
    add_subtitle: bool = False,
    subtitle_style: Dict = None,
    preview: bool = False,
    scene_fade: float = 0.0,
    subtitle_animation: str = 'none'
) -> bool:
    """创建单个场景视频，支持缩放效果、字幕、淡入淡出"""

    width, height = resolution

    if scene.video_path:
        # 视频素材 - 静音原视频，使用生成的配音音频
        video_input = str(scene.video_path)

        # 构建视频滤镜（缩放+字幕+淡入淡出）
        vf_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"

        if add_subtitle and subtitle_style and scene.subtitle:
            vf_filter += "," + build_subtitle_filter(
                scene.subtitle, subtitle_style, width, height,
                animation=subtitle_animation
            )

        vf_filter += build_fade_filter(scene.duration, scene_fade)

        # 如果有生成的音频，使用生成的音频；否则保留原视频音频
        if scene.audio_path:
            # 获取音频时长
            audio_duration = get_media_duration(str(scene.audio_path))
            video_duration = scene.duration

            if audio_duration > video_duration:
                # 音频比视频长，需要循环视频
                loop_count = int(audio_duration / video_duration) + 1
                print(f"   🔄 视频循环: {loop_count} 次 (音频{audio_duration:.1f}s > 视频{video_duration:.1f}s)")

                cmd = [
                    'ffmpeg', '-y',
                    '-stream_loop', str(loop_count),
                    '-i', video_input,
                    '-i', str(scene.audio_path),
                    '-vf', vf_filter,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-map', '0:v:0', '-map', '1:a:0',
                    '-t', str(audio_duration),
                    '-shortest',
                    str(output_path)
                ]
            else:
                # 音频比视频短或相等，直接复制
                cmd = [
                    'ffmpeg', '-y',
                    '-i', video_input,
                    '-i', str(scene.audio_path),
                    '-vf', vf_filter,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-map', '0:v:0', '-map', '1:a:0',
                    '-t', str(audio_duration),
                    str(output_path)
                ]
        else:
            # 没有生成音频，直接复制原视频
            cmd = [
                'ffmpeg', '-y',
                '-i', video_input,
                '-vf', vf_filter,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'copy',
                '-t', str(scene.duration),
                str(output_path)
            ]

    elif scene.image_path:
        # 图片素材 - 添加缩放动画效果
        duration = scene.duration
        total_frames = int(duration * fps)

        # 智能裁剪：等比放大到完全覆盖目标尺寸，居中裁剪，减少黑边
        crop_vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,"

        # Ken Burns 效果：缓慢缩放和平移
        vf_filter = (
            crop_vf +
            f"zoompan=z='min(zoom+0.0005,1.1)':d={total_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},"
            f"fps={fps},format=yuv420p,trim=duration={duration}"
        )

        # 添加字幕
        if add_subtitle and subtitle_style and scene.subtitle:
            vf_filter += "," + build_subtitle_filter(
                scene.subtitle, subtitle_style, width, height,
                animation=subtitle_animation
            )

        # 淡入淡出
        vf_filter += build_fade_filter(duration, scene_fade)

        # 编码参数：预览模式快速编码，正式模式高质量
        if preview:
            video_preset = 'ultrafast'
            video_crf = '28'
            audio_bitrate = '128k'
        else:
            video_preset = 'veryslow'
            video_crf = '15'
            audio_bitrate = '256k'

        # 添加音频（如果有）
        if scene.audio_path:
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', str(scene.image_path),
                '-i', str(scene.audio_path),
                '-vf', vf_filter,
                '-c:v', 'libx264',
                '-preset', video_preset,
                '-crf', video_crf,
                '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'aac',
                '-b:a', audio_bitrate,
                '-movflags', '+faststart',
                '-shortest',
                str(output_path)
            ]
        else:
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1',
                '-i', str(scene.image_path),
                '-vf', vf_filter,
                '-c:v', 'libx264',
                '-preset', video_preset,
                '-crf', video_crf,
                '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-t', str(duration),
                '-an',
                str(output_path)
            ]
    else:
        return False

    try:
        result = run_ffmpeg(cmd, max_retries=2)
        if result.returncode != 0:
            print(f"   ⚠️ ffmpeg: {result.stderr[:200]}")
        return output_path.exists()
    except Exception as e:
        print(f"   ❌ 生成失败: {e}")
        traceback.print_exc()
        return False


def _generate_scene_worker(task):
    """并行场景生成工作函数"""
    scene, scene_output, width, height, fps, add_subtitle, subtitle_style, preview, scene_fade, subtitle_animation = task
    try:
        success = create_scene_with_effects(
            scene, scene_output, (width, height), fps,
            add_subtitle, subtitle_style, preview=preview,
            scene_fade=scene_fade, subtitle_animation=subtitle_animation
        )
        media_name = None
        if scene.image_path:
            media_name = scene.image_path.name
        elif scene.video_path:
            media_name = scene.video_path.name
        return {
            'index': scene.index,
            'success': success and scene_output.exists(),
            'output': scene_output,
            'error': None,
            'duration': scene.duration,
            'media_name': media_name
        }
    except Exception as e:
        media_name = None
        if scene.image_path:
            media_name = scene.image_path.name
        elif scene.video_path:
            media_name = scene.video_path.name
        traceback.print_exc()
        return {
            'index': scene.index,
            'success': False,
            'output': scene_output,
            'error': str(e),
            'duration': scene.duration,
            'media_name': media_name
        }


def add_transition(
    video1: Path,
    video2: Path,
    output: Path,
    transition_type: str,
    duration: float = 0.5,
    sfx_path: Optional[Path] = None
) -> bool:
    """添加转场效果，可选转场音效"""

    if transition_type == 'none' or not TRANSITIONS.get(transition_type):
        # 无转场，直接拼接
        return simple_concat([video1, video2], output)

    # 使用 xfade 滤镜实现转场
    # 获取两段视频的时长
    dur1 = get_media_duration(str(video1))
    dur2 = get_media_duration(str(video2))

    # 转场参数
    transition_name = TRANSITIONS[transition_type]
    offset = dur1 - duration

    # 构建命令
    inputs = ['-i', str(video1), '-i', str(video2)]
    audio_filter = f"[0:a][1:a]acrossfade=d={duration}[a]"

    # 混入转场音效
    if sfx_path and sfx_path.exists():
        sfx_dur = get_media_duration(str(sfx_path))
        use_dur = min(sfx_dur, duration * 2)
        inputs.extend(['-i', str(sfx_path)])
        audio_filter = (
            f"[0:a][1:a]acrossfade=d={duration}[mix];"
            f"[2:a]atrim=0:{use_dur},volume=0.6,adelay=0s[se];"
            f"[mix][se]amix=inputs=2:duration=first[a]"
        )

    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex',
        f"[0:v][1:v]xfade=transition={transition_name}:duration={duration}:offset={offset}[v];"
        + audio_filter,
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-preset', 'veryslow', '-crf', '15',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '256k',
        str(output)
    ]

    try:
        result = run_ffmpeg(cmd, max_retries=2)
        if result.returncode != 0:
            print(f"   ⚠️  转场失败，使用简单拼接: {result.stderr[:100]}")
            return simple_concat([video1, video2], output)
        return output.exists()
    except Exception as e:
        print(f"   ⚠️  转场失败: {e}，使用简单拼接")
        return simple_concat([video1, video2], output)


def simple_concat(videos: List[Path], output: Path) -> bool:
    """简单拼接视频"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for video in videos:
            f.write(f"file '{str(video)}'\n")
        concat_file = f.name

    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            str(output)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return output.exists()
    finally:
        os.unlink(concat_file)


def add_intro_outro(
    main_video: Path,
    intro: Optional[Path],
    outro: Optional[Path],
    output: Path,
    transition: str = 'fade'
) -> bool:
    """添加片头片尾"""

    videos = []

    if intro and intro.exists():
        videos.append(intro)

    videos.append(main_video)

    if outro and outro.exists():
        videos.append(outro)

    if len(videos) == 1:
        shutil.copy(str(main_video), str(output))
        return True

    # 使用转场连接
    if len(videos) == 2:
        return add_transition(videos[0], videos[1], output, transition)

    if len(videos) == 3:
        temp = Path(tempfile.mktemp(suffix='.mp4'))
        try:
            if add_transition(videos[0], videos[1], temp, transition):
                return add_transition(temp, videos[2], output, transition)
            return False
        finally:
            if temp.exists():
                temp.unlink()

    return False


def add_bgm(video: Path, bgm: Path, output: Path, volume: float = 0.3) -> bool:
    """添加背景音乐"""

    duration = get_media_duration(str(video))

    cmd = [
        'ffmpeg', '-y',
        '-i', str(video),
        '-stream_loop', '-1',
        '-i', str(bgm),
        '-filter_complex',
        f"[0:a]volume=1.0[va];[1:a]volume={volume},atrim=0:{duration}[bgm];[va][bgm]amix=inputs=2:duration=first[a]",
        '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        str(output)
    ]

    try:
        result = run_ffmpeg(cmd, max_retries=2)
        if result.returncode != 0:
            print(f"   ⚠️ BGM添加失败，使用原视频")
            shutil.copy(str(video), str(output))
            return True
        return output.exists()
    except Exception as e:
        print(f"   ⚠️ BGM添加失败: {e}")
        traceback.print_exc()
        shutil.copy(str(video), str(output))
        return True


def add_watermark(
    video: Path,
    watermark: Path,
    position: str,
    output: Path,
    opacity: float = 0.75
) -> bool:
    """添加水印/Logo"""

    positions = {
        'top-left': '10:10',
        'top-right': 'W-w-10:10',
        'bottom-left': '10:H-h-10',
        'bottom-right': 'W-w-10:H-h-10',
        'center': '(W-w)/2:(H-h)/2',
    }
    pos = positions.get(position, 'W-w-10:H-h-10')

    cmd = [
        'ffmpeg', '-y',
        '-i', str(video),
        '-i', str(watermark),
        '-filter_complex',
        f"[1:v]format=rgba,colorchannelmixer=aa={opacity}[wm];"
        f"[0:v][wm]overlay={pos}[v]",
        '-map', '[v]', '-map', '0:a',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-c:a', 'copy',
        str(output)
    ]

    try:
        result = run_ffmpeg(cmd, max_retries=2)
        if result.returncode != 0:
            print(f"   ⚠️ 水印添加失败: {result.stderr[:100]}")
            shutil.copy(str(video), str(output))
            return True
        return output.exists()
    except Exception as e:
        print(f"   ⚠️ 水印添加失败: {e}")
        traceback.print_exc()
        shutil.copy(str(video), str(output))
        return True


def generate_dual_version(source_video: Path, output_video: Path, target_resolution: str) -> bool:
    """生成相反比例版本（横屏↔竖屏），居中裁剪保留核心内容"""
    try:
        tw, th = map(int, target_resolution.split('x'))
    except ValueError:
        print(f"   ⚠️  无效目标分辨率: {target_resolution}")
        return False

    # ffmpeg: 等比放大让短边填满目标，然后居中裁剪
    vf = (
        f"scale=iw*max({tw}/iw\\,{th}/ih):ih*max({tw}/iw\\,{th}/ih),"
        f"crop={tw}:{th}"
    )

    cmd = [
        'ffmpeg', '-y', '-i', str(source_video),
        '-vf', vf,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'copy',
        '-movflags', '+faststart',
        str(output_video)
    ]

    try:
        result = run_ffmpeg(cmd, max_retries=1, check_output=False)
        if result.returncode != 0:
            print(f"   ⚠️  双版本生成失败: {result.stderr[:200]}")
            return False
        if output_video.exists():
            size_mb = output_video.stat().st_size / (1024 * 1024)
            dur = get_media_duration(str(output_video))
            print(f"   ✅ 双版本完成: {output_video.name} ({dur:.1f}s, {size_mb:.1f}MB)")
            return True
        return False
    except Exception as e:
        print(f"   ⚠️  双版本异常: {e}")
        traceback.print_exc()
        return False


def process_project(
    project_dir: Path,
    args
) -> Optional[Path]:
    """处理单个项目"""

    tee = None
    try:
        tee = setup_logging(project_dir, preview_mode=getattr(args, 'preview', False))

        # 预览模式
        preview_mode = getattr(args, 'preview', False)
        start_time = time.time()
        stage_times = {}

        print(f"\n{'='*60}")
        if preview_mode:
            print(f"👁️  预览模式: {project_dir.name}")
            print(f"   只生成第一个场景，快速预览效果")
        else:
            print(f"🎬 处理项目: {project_dir.name}")
        print(f"{'='*60}")

        # 检查输出目录
        final_dir = project_dir / '07_final'
        final_dir.mkdir(exist_ok=True)

        # 创建场景片段目录（保存中间产物，支持断点续传）
        scenes_dir = project_dir / '06_scenes'
        scenes_dir.mkdir(exist_ok=True)

        if preview_mode:
            output_path = final_dir / 'preview.mp4'
        else:
            if args.output:
                output_name = args.output
            else:
                now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                output_name = f"{project_dir.name}_{now}.mp4"
            output_path = final_dir / output_name

        # 自动从文章生成音频（如果没有音频但有文章）
        # 返回音频分段信息，包含音色和图片分配
        audio_t0 = time.time()
        regenerate_audio = getattr(args, 'regenerate_audio', False)
        audio_success, segments_info = auto_generate_audio(
            project_dir,
            voice=getattr(args, 'voice', 'Xiaoxiao'),
            rate=getattr(args, 'rate', '+0%'),
            force=regenerate_audio
        )
        stage_times['audio'] = time.time() - audio_t0

        # 如果已有音频但没有分段信息，从文章中解析字幕文本
        if not segments_info:
            article_dir = project_dir / '01_article'
            if article_dir.exists():
                article_files = list(article_dir.glob('*.md')) + list(article_dir.glob('*.txt'))
                if article_files:
                    try:
                        with open(article_files[0], 'r', encoding='utf-8') as f:
                            raw_text = f.read()
                        raw_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
                        text = re.sub(r'```[\s\S]*?```', '', raw_text)
                        text = re.sub(r'`[^`]*`', '', text)
                        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
                        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
                        text = re.sub(r'<[^>]+>', '', text)
                        text = re.sub(r'\n{3,}', '\n\n', text)
                        parsed_segments, _ = parse_article_segments(text, default_voice=getattr(args, 'voice', 'Xiaoxiao'))
                        segments_info = [
                            {'voice': v, 'image': img, 'text': content, 'index': i}
                            for i, (v, content, img) in enumerate(parsed_segments, 1)
                        ]
                    except Exception:
                        pass

        # 发现场景（传递图片分配信息）
        scenes = find_scenes(project_dir, image_assignments=segments_info)
        if not scenes:
            print("❌ 未找到任何场景素材")
            return None

        # 预览模式只取第一个场景
        if preview_mode:
            scenes = scenes[:1]
            print(f"📁 发现 {len(scenes)} 个场景 (预览模式只取第一个)")
        else:
            print(f"📁 发现 {len(scenes)} 个场景")
        print(f"📂 场景片段保存到: {scenes_dir}")

        # 字幕样式
        subtitle_style = None
        if args.subtitle:
            subtitle_style = SUBTITLE_STYLES.get(args.subtitle_style, SUBTITLE_STYLES['news'])
            print(f"📝 字幕样式: {args.subtitle_style}")

        if not preview_mode:
            print(f"✨ 转场效果: {args.transition}")

        # 处理每个场景（支持断点续传）
        scene_videos = []
        failed_scenes = []
        skipped_scenes = []
        pending_tasks = []
        width, height = map(int, args.resolution.split('x'))

        for i, scene in enumerate(scenes):
            scene_output = scenes_dir / f"scene_{scene.index:02d}.mp4"

            # 预览模式跳过断点续传（每次预览都重新生成）
            if not preview_mode:
                # 断点续传：检查是否已存在且有效
                if scene_output.exists() and scene_output.stat().st_size > 1024:
                    # 验证文件是否有效（可播放）
                    try:
                        verify_duration = get_media_duration(str(scene_output))
                        if verify_duration > 0:
                            scene_videos.append(scene_output)
                            skipped_scenes.append(scene.index)
                            print(f"\n[{i+1}/{len(scenes)}] 场景 {scene.index:02d}...")
                            print(f"   ⏭️  已存在，跳过生成 ({verify_duration:.1f}s)")
                            continue
                    except:
                        pass  # 文件损坏，重新生成

            print(f"\n[{i+1}/{len(scenes)}] 场景 {scene.index:02d}...")

            if scene.video_path:
                print(f"   🎥 视频: {scene.video_path.name}")
            elif scene.image_path:
                print(f"   🖼️  图片: {scene.image_path.name}")
            else:
                print(f"   ⚠️  跳过: 无素材")
                failed_scenes.append(scene.index)
                continue

            if scene.audio_path:
                print(f"   🎵 音频: {scene.audio_path.name}")

            scene_fade = getattr(args, 'scene_fade', 0.0)
            subtitle_animation = getattr(args, 'subtitle_animation', 'none')
            pending_tasks.append((scene, scene_output, width, height, args.fps, args.subtitle, subtitle_style, preview_mode, scene_fade, subtitle_animation))

        # 执行生成（支持并行）
        total_pending = len(pending_tasks)
        scene_t0 = time.time()
        if not args.no_parallel and total_pending > 1 and not preview_mode:
            print(f"\n🚀 并行生成 {total_pending} 个场景（最多3并发）...")
            with concurrent.futures.ProcessPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(_generate_scene_worker, task) for task in pending_tasks]
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    idx = result['index']
                    media = result.get('media_name') or '无素材'
                    if result['success']:
                        scene_videos.append(result['output'])
                        print(f"   ✅ [{len(scene_videos)}/{total_pending}] 场景 {idx:02d} ({media}) 完成 ({result['duration']:.1f}s)")
                    else:
                        failed_scenes.append(idx)
                        print(f"   ❌ [{len(scene_videos)+1}/{total_pending}] 场景 {idx:02d} ({media}) 失败: {result['error'] or '未知错误'}")
        else:
            # 顺序生成（预览模式也用顺序）
            for task_idx, task in enumerate(pending_tasks, 1):
                scene, scene_output, width, height, fps, add_subtitle, subtitle_style, preview, scene_fade, subtitle_animation = task
                media = scene.image_path.name if scene.image_path else (scene.video_path.name if scene.video_path else '无素材')
                try:
                    success = create_scene_with_effects(
                        scene, scene_output, (width, height), fps,
                        add_subtitle, subtitle_style, preview=preview,
                        scene_fade=scene_fade, subtitle_animation=subtitle_animation
                    )
                    if success and scene_output.exists():
                        scene_videos.append(scene_output)
                        print(f"   ✅ [{task_idx}/{total_pending}] 场景 {scene.index:02d} ({media}) 完成 ({scene.duration:.1f}s)")
                    else:
                        print(f"   ❌ [{task_idx}/{total_pending}] 场景 {scene.index:02d} ({media}) 生成失败")
                        failed_scenes.append(scene.index)
                except Exception as e:
                    print(f"   ❌ [{task_idx}/{total_pending}] 场景 {scene.index:02d} ({media}) 异常: {e}")
                    traceback.print_exc()
                    failed_scenes.append(scene.index)
        stage_times['scenes'] = time.time() - scene_t0

        # 汇总生成结果
        print(f"\n{'─'*60}")
        print(f"📊 场景生成统计:")
        print(f"   ✅ 成功: {len(scene_videos)} 个")
        if skipped_scenes:
            print(f"   ⏭️  跳过(已存在): {len(skipped_scenes)} 个 {skipped_scenes}")
        if failed_scenes:
            print(f"   ❌ 失败: {len(failed_scenes)} 个 {failed_scenes}")
        print(f"{'─'*60}")

        if not scene_videos:
            print("❌ 没有成功生成任何场景")
            return None

        # 预览模式：直接复制第一个场景，跳过合并/转场/片头片尾/BGM
        if preview_mode:
            main_video = scene_videos[0]
            shutil.copy(str(main_video), str(output_path))
            final_duration = get_media_duration(str(output_path))
            final_size = output_path.stat().st_size / (1024 * 1024)

            print(f"\n{'='*60}")
            print("✅ 预览视频生成完成!")
            print(f"{'='*60}")
            print(f"📁 输出: {output_path}")
            print(f"⏱️  时长: {final_duration:.1f} 秒")
            print(f"📦 大小: {final_size:.1f} MB")
            print(f"🎞️  场景: 1 个（预览模式）")
            print(f"📂 场景片段: {scenes_dir}")

            return output_path

        # 查找转场音效
        sfx_path = None
        if getattr(args, 'sfx', False):
            sfx_dir = project_dir / '02_sfx'
            if sfx_dir.exists():
                sfx_exts = ['.mp3', '.wav', '.aac', '.m4a', '.ogg']
                sfx_files = sorted([f for f in sfx_dir.iterdir() if f.suffix.lower() in sfx_exts])
                if sfx_files:
                    sfx_path = sfx_files[0]
                    print(f"🔊 自动发现转场音效: {sfx_path.name}")

        # 合并场景（带转场）
        print(f"\n🎞️  合并场景（转场: {args.transition}）...")

        merge_state_path = final_dir / '.merge_state.json'
        merge_t0 = time.time()

        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            if len(scene_videos) == 1:
                main_video = scene_videos[0]
            elif args.transition == 'none' or not TRANSITIONS.get(args.transition):
                # 无转场，一次性拼接（速度最快）
                concat_output = temp_dir / 'concat_all.mp4'
                print(f"   🔄 [1/1] 拼接 {len(scene_videos)} 个场景（无需重新编码）...")
                if simple_concat(scene_videos, concat_output):
                    main_video = concat_output
                    print(f"   ✅ 拼接完成")
                else:
                    print(f"   ❌ 拼接失败")
                    return None
            else:
                # 有转场，逐步合并，支持断点续传
                resume_idx = 1
                main_video = scene_videos[0]

                # 检查是否有未完成的合并
                if merge_state_path.exists():
                    try:
                        with open(merge_state_path, 'r', encoding='utf-8') as f:
                            state = json.load(f)
                        state_scenes = state.get('scene_names', [])
                        current_scenes = [s.name for s in scene_videos]
                        if state_scenes == current_scenes and state.get('transition') == args.transition:
                            partial_file = final_dir / state.get('output', '')
                            if partial_file.exists():
                                duration = get_media_duration(str(partial_file))
                                if duration > 0:
                                    resume_idx = state.get('resume_idx', 1)
                                    main_video = partial_file
                                    print(f"⏭️  恢复未完成的合并，从 [{resume_idx}/{len(scene_videos)}] 继续")
                    except Exception:
                        traceback.print_exc()
                        pass  # 状态文件损坏，重新合并

                for i in range(resume_idx, len(scene_videos)):
                    next_video = scene_videos[i]
                    partial_file = final_dir / f'_partial_merged_{i}.mp4'
                    from_name = main_video.name if hasattr(main_video, 'name') else str(main_video)
                    to_name = next_video.name

                    print(f"   🔄 [{i+1}/{len(scene_videos)}] 合并: {from_name} → {to_name}")

                    prev_video = main_video
                    success = add_transition(prev_video, next_video, partial_file, args.transition, args.transition_duration, sfx_path)

                    if success:
                        # 保存合并状态
                        state = {
                            'scene_names': [s.name for s in scene_videos],
                            'transition': args.transition,
                            'output': partial_file.name,
                            'resume_idx': i + 1,
                            'timestamp': datetime.datetime.now().isoformat()
                        }
                        with open(merge_state_path, 'w', encoding='utf-8') as f:
                            json.dump(state, f, ensure_ascii=False, indent=2)

                        # 清理旧的 partial 文件（如果是 partial 且不是当前输入）
                        if isinstance(prev_video, Path) and prev_video.name.startswith('_partial_merged_'):
                            try:
                                prev_video.unlink()
                            except OSError:
                                pass

                        main_video = partial_file
                    else:
                        print(f"   ❌ 合并失败，终止")
                        return None

            stage_times['merge'] = time.time() - merge_t0

            # 添加片头片尾
            if args.intro or args.outro:
                print("🎬 添加片头片尾...")
                with_intro_outro = temp_dir / 'with_intro_outro.mp4'
                intro_path = Path(args.intro) if args.intro else None
                outro_path = Path(args.outro) if args.outro else None

                if add_intro_outro(main_video, intro_path, outro_path, with_intro_outro, args.transition):
                    main_video = with_intro_outro
                    print("✅ 片头片尾添加完成")

            # 添加背景音乐
            bgm_path = None
            if args.bgm:
                # 显式指定 BGM 路径
                bgm_path = Path(args.bgm)
            else:
                # 自动查找项目 02_bgm/ 目录下的音乐文件
                bgm_dir = project_dir / '02_bgm'
                if bgm_dir.exists():
                    music_exts = ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg']
                    music_files = sorted([f for f in bgm_dir.iterdir() if f.suffix.lower() in music_exts])
                    if music_files:
                        bgm_path = music_files[0]
                        print(f"🎵 自动发现 BGM: {bgm_path.name}")

            if bgm_path and bgm_path.exists():
                print(f"🎵 添加背景音乐 (音量: {int(args.bgm_volume * 100)}%)...")
                with_bgm = temp_dir / 'with_bgm.mp4'
                if add_bgm(main_video, bgm_path, with_bgm, args.bgm_volume):
                    main_video = with_bgm
                    print("✅ BGM添加完成")

            # 添加水印
            watermark_path = getattr(args, 'watermark', None)
            if watermark_path:
                watermark_path = Path(watermark_path)
                if not watermark_path.is_absolute():
                    watermark_path = project_dir / watermark_path
            if watermark_path and watermark_path.exists():
                print(f"🏷️ 添加水印 ({getattr(args, 'watermark_position', 'bottom-right')})...")
                watermarked = temp_dir / 'watermarked.mp4'
                if add_watermark(main_video, watermark_path, getattr(args, 'watermark_position', 'bottom-right'), watermarked):
                    main_video = watermarked
                    print("✅ 水印添加完成")

            # 复制到输出位置
            shutil.copy(str(main_video), str(output_path))

            # 双版本生成（横竖屏）
            if getattr(args, 'dual_version', False) and not preview_mode:
                cw, ch = map(int, args.resolution.split('x'))
                alt_res = f"{ch}x{cw}"
                if cw > ch:
                    alt_name = output_path.stem + '_portrait' + output_path.suffix
                    label = '竖屏版'
                else:
                    alt_name = output_path.stem + '_landscape' + output_path.suffix
                    label = '横屏版'
                alt_path = output_path.parent / alt_name
                print(f"\n📱 生成双版本 ({label} {alt_res})...")
                generate_dual_version(output_path, alt_path, alt_res)

            # 清理中间合并文件和状态
            for f in final_dir.glob('_partial_merged_*.mp4'):
                try:
                    f.unlink()
                except OSError:
                    pass
            if merge_state_path.exists():
                try:
                    merge_state_path.unlink()
                except OSError:
                    pass

            # 显示结果
            final_duration = get_media_duration(str(output_path))
            final_size = output_path.stat().st_size / (1024 * 1024)
            total_time = time.time() - start_time

            print(f"\n{'='*60}")
            print("✅ 视频合成完成!")
            print(f"{'='*60}")
            print(f"📁 输出: {output_path}")
            print(f"⏱️  时长: {final_duration:.1f} 秒")
            print(f"📦 大小: {final_size:.1f} MB")
            print(f"🎞️  场景: {len(scene_videos)}/{len(scenes)}")
            if skipped_scenes:
                print(f"⏭️  跳过: {len(skipped_scenes)} 个（已存在）")
            if failed_scenes:
                print(f"❌ 失败: {len(failed_scenes)} 个 {failed_scenes}")
            print(f"📂 场景片段: {scenes_dir}")

            # 详细报告
            print(f"\n{'─'*60}")
            print("📊 生成详细报告:")
            print(f"{'─'*60}")
            print(f"  ⏱️  总耗时:       {total_time:.1f}s")
            if 'audio' in stage_times:
                print(f"  🎙️  音频生成:     {stage_times['audio']:.1f}s")
            if 'scenes' in stage_times:
                print(f"  🎬 场景生成:     {stage_times['scenes']:.1f}s")
            if 'merge' in stage_times:
                print(f"  🔗 合并转场:     {stage_times['merge']:.1f}s")
            print(f"  📹 最终时长:     {final_duration:.1f}s")
            print(f"  📦 文件大小:     {final_size:.1f} MB")
            if final_duration > 0:
                print(f"  📊 平均码率:     {final_size * 8 / final_duration:.1f} Mbps")
            # 场景详情
            if len(scene_videos) > 1:
                print(f"\n  📋 各场景详情:")
                for i, sv in enumerate(scene_videos, 1):
                    sv_duration = get_media_duration(str(sv))
                    sv_size = sv.stat().st_size / (1024 * 1024)
                    print(f"     场景{i:02d}: {sv_duration:5.1f}s | {sv_size:5.1f}MB")
            print(f"{'─'*60}")

            # 自动提取封面
            if not preview_mode and output_path.exists():
                cover_path = final_dir / 'cover.jpg'
                try:
                    # 提取中间帧作为封面
                    mid_time = final_duration / 2 if final_duration > 0 else 1
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', str(output_path),
                        '-ss', str(mid_time),
                        '-vframes', '1',
                        '-q:v', '2',
                        str(cover_path)
                    ]
                    result = run_ffmpeg(cmd, max_retries=2, check_output=False)
                    if cover_path.exists():
                        print(f"\n🖼️  封面已提取: {cover_path.name}")
                except Exception as e:
                    pass  # 封面提取失败不影响主流程

            return output_path

    finally:
        # 恢复 stdout 并关闭日志（临时目录由 TemporaryDirectory 自动清理）
        if tee:
            sys.stdout = tee.terminal
            tee.close()


def init_project_wizard(project_dir: Path, template: str = None) -> bool:
    """交互式项目初始化向导

    Args:
        template: 可选，使用预设模板（news/food/tutorial/education）
    """
    # 检查是否使用模板
    template_config = None
    if template and template in PROJECT_TEMPLATES:
        template_config = PROJECT_TEMPLATES[template]
        print(f"\n{'='*60}")
        print(f"🚀 项目初始化向导 - 使用模板: {template}")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("🚀 项目初始化向导")
        print(f"{'='*60}")

    print(f"📁 项目路径: {project_dir}")

    if project_dir.exists() and any(project_dir.iterdir()):
        print(f"\n⚠️  目录已存在且不为空: {project_dir}")
        confirm = input("是否继续初始化? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("已取消")
            return False

    project_dir.mkdir(parents=True, exist_ok=True)

    if template_config:
        # 使用模板预设
        mode = template_config['mode']
        resolution = template_config['resolution']
        fps = template_config['fps']
        subtitle_style = template_config['subtitle_style']
        transition = template_config['transition']
        voice = template_config['voice']
        print(f"\n📋 模板配置:")
        print(f"  模式: {mode}")
        print(f"  分辨率: {resolution}")
        print(f"  字幕: {subtitle_style}")
        print(f"  转场: {transition}")
        print(f"  音色: {voice}")
    else:
        # 1. 选择模式
        print("\n📋 请选择项目模式:")
        print("  1) 🖼️  图片模式 - 文章 + 图片素材")
        print("  2) 🎥 视频模式 - 文章 + 原视频素材")
        print("  3) 🔀 混合模式 - 文章 + 图片 + 视频")
        mode_choice = input("选择 [1/2/3] (默认: 1): ").strip() or '1'

        modes = {'1': 'image', '2': 'video', '3': 'hybrid'}
        mode = modes.get(mode_choice, 'image')

        # 2. 选择平台（支持多选）
        print("\n📱 请选择目标平台（可多选，如 1,2 或 12）:")
        print("  1) 📱 抖音/快手 - 1080×1920 (9:16)")
        print("  2) 🎬 B站/YouTube - 1920×1080 (16:9)")
        print("  3) 💬 视频号 - 1920×1080 (16:9)")
        print("  4) ⚙️  自定义")
        platform_input = input("选择 [1/2/3/4] (默认: 2): ").strip() or '2'

        # 解析多选（支持 "1,2" "1 2" "12"）
        selected = []
        for c in platform_input.replace(',', ' ').split():
            selected.extend(list(c.strip()))
        selected = list(dict.fromkeys(selected))  # 去重保序

        platforms = {
            '1': ('1080x1920', 'tiktok', 'pixelize', 30),
            '2': ('1920x1080', 'youtube', 'fade', 30),
            '3': ('1920x1080', 'youtube', 'fade', 30),
            '4': None
        }

        dual_version = False
        if '4' in selected:
            # 自定义
            resolution = input("分辨率 (如 1920x1080): ").strip() or '1920x1080'
            subtitle_style = input("字幕样式 [news/youtube/tiktok/minimal] (默认: news): ").strip() or 'news'
            transition = input("转场效果 [fade/wipeleft/wiperight/slideleft/pixelize/none] (默认: fade): ").strip() or 'fade'
            fps = int(input("帧率 (默认: 30): ").strip() or '30')
        else:
            # 取第一个有效平台为主配置
            first = next((s for s in selected if s in platforms and s != '4'), '2')
            resolution, subtitle_style, transition, fps = platforms[first]
            # 如果选了多个不同比例的平台，开启双版本
            unique_res = set()
            for s in selected:
                if s in platforms and platforms[s]:
                    unique_res.add(platforms[s][0])
            if len(unique_res) > 1:
                dual_version = True
                print(f"   🔀 已选多平台，将同时生成横竖双版本")

        # 3. 选择音色
        print("\n🎙️  请选择默认AI音色:")
        print("  1) 👩 晓晓 - 活泼女声 (推荐)")
        print("  2) 👨 云扬 - 成熟男声")
        print("  3) 👦 云希 - 年轻男声")
        print("  4) 👩 晓伊 - 成熟女声")
        print("  5) 👩 云夏 - 年轻女声")
        print("  6) 👨 云健 - 新闻播报男声")
        voice_choice = input("选择 [1-6] (默认: 1): ").strip() or '1'

        voices = {
            '1': 'Xiaoxiao', '2': 'Yunyang', '3': 'Yunxi',
            '4': 'Xiaoyi', '5': 'Yunxia', '6': 'Yunjian'
        }
        voice = voices.get(voice_choice, 'Xiaoxiao')

    # 4. 创建目录结构
    print(f"\n📂 创建目录结构...")
    dirs = ['01_article']
    if mode in ('image', 'hybrid'):
        dirs.append('03_images')
    if mode in ('video', 'hybrid'):
        dirs.append('04_videos')
    dirs.extend(['06_scenes', '07_final', '02_bgm', '02_sfx'])

    for d in dirs:
        (project_dir / d).mkdir(exist_ok=True)
        print(f"  ✅ {d}/")

    # 5. 创建示例文章
    article_path = project_dir / '01_article' / '文章.md'
    if not article_path.exists():
        article_templates = {
            'image': f"""# 示例文章

@全局:{'女声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '男声'}
@默认图: 01

@{'男声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '女声'}: 大家好，欢迎收看今天的节目。

这是第二段内容，使用默认图片。

@{'男声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '女声'}: 感谢观看，我们下期再见！
""",
            'video': f"""# 示例文章

@全局:{'女声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '男声'}

这是视频配音文案。

第一段内容。

第二段内容。

结尾部分。
""",
            'hybrid': f"""# 示例文章

@全局:{'女声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '男声'}
@默认图: 01

@{'男声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '女声'}: 大家好，欢迎收看。

这是第二段内容。

@{'男声' if voice in ['Xiaoxiao', 'Xiaoyi', 'Yunxia'] else '女声'}: 感谢观看！
"""
        }
        if template_config:
            article_path.write_text(template_config['article'], encoding='utf-8')
        else:
            article_path.write_text(article_templates[mode], encoding='utf-8')
        print(f"  ✅ 01_article/文章.md")

    # 6. 生成项目配置文件
    config_path = project_dir / '.video_config.json'
    config = {
        'mode': mode,
        'resolution': resolution,
        'fps': fps,
        'subtitle': True,
        'subtitle_style': subtitle_style,
        'subtitle_animation': 'none',
        'transition': transition,
        'voice': voice,
        'transition_duration': 0.5,
        'rate': '+18%',
        'scene_fade': 0.0,
        'bgm_volume': 0.25,
        'watermark': None,
        'watermark_position': 'bottom-right',
        'sfx': False,
        'dual_version': dual_version,
        'created': str(datetime.datetime.now())
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  ✅ .video_config.json")

    # 7. 生成参数说明文档
    param_doc_path = project_dir / '参数说明.md'
    if not param_doc_path.exists():
        param_doc = f"""# 项目参数说明

> 本文件由初始化向导自动生成，可直接编辑 `.video_config.json` 修改参数，
> 无需每次在命令行输入。

## 当前配置

```json
{json.dumps(config, ensure_ascii=False, indent=2)}
```

## 参数详解

### 基础参数

| 参数 | 当前值 | 中文说明 |
|------|--------|----------|
| `mode` | `{mode}` | 项目模式: `image`(图片+配音) / `video`(视频+配音) / `hybrid`(混合) |
| `resolution` | `{resolution}` | 输出分辨率，如 `1920x1080`(横屏) / `1080x1920`(竖屏) |
| `fps` | `{fps}` | 帧率，默认 30 |
| `voice` | `{voice}` | 默认AI配音音色 |
| `rate` | `+18%` | 语速调节，如 `+10%`(加快) / `-10%`(放慢) |

### 视觉参数

| 参数 | 当前值 | 中文说明 |
|------|--------|----------|
| `subtitle` | `true` | 是否启用字幕，`true`(开启) / `false`(关闭) |
| `subtitle_style` | `{subtitle_style}` | 字幕样式预设，见下表 |
| `subtitle_animation` | `none` | 字幕动画: `none`(无) / `slide_up`(上滑进入) / `fade_in`(淡入) |
| `transition` | `{transition}` | 场景转场效果，见下表 |
| `transition_duration` | `0.5` | 转场时长(秒)，建议 0.3~1.0 |
| `scene_fade` | `0.0` | 场景淡入淡出(秒)，建议 0.2~0.5，0 为关闭 |
| `watermark` | `null` | 水印图片路径，如 `logo.png`，`null` 为不添加 |
| `watermark_position` | `bottom-right` | 水印位置: `top-left`(左上) / `top-right`(右上) / `bottom-left`(左下) / `bottom-right`(右下) / `center`(居中) |

### 音频参数

| 参数 | 当前值 | 中文说明 |
|------|--------|----------|
| `bgm_volume` | `0.25` | 背景音乐音量，范围 0.0~1.0，0 为静音 |
| `sfx` | `false` | 是否启用转场音效，`true`(开启，自动读取 `02_sfx/` 目录) / `false`(关闭) |
| `dual_version` | `{dual_version}` | 是否同时生成横竖双版本，`true`(开启) / `false`(关闭) |

## 字幕样式列表

| 样式名 | 中文名 | 特点 |
|--------|--------|------|
| `news` | 新闻 | 底部黑底白字，带边框，适合新闻/解说 |
| `youtube` | YouTube | 底部黄色大字，黑色描边，适合英文/教程 |
| `tiktok` | 抖音 | 居中白色大字，半透黑底，适合竖屏短视频 |
| `minimal` | 极简 | 细边框，无背景框，适合文艺/纪录片风格 |

## 转场效果列表

| 效果名 | 中文名 | 效果名 | 中文名 |
|--------|--------|--------|--------|
| `fade` | 淡入淡出 | `dissolve` | 溶解 |
| `wipeleft` | 向左擦除 | `wiperight` | 向右擦除 |
| `wipeup` | 向上擦除 | `wipedown` | 向下擦除 |
| `slideleft` | 向左滑动 | `slideright` | 向右滑动 |
| `slideup` | 向上滑动 | `slidedown` | 向下滑动 |
| `smoothleft` | 平滑向左 | `smoothright` | 平滑向右 |
| `smoothup` | 平滑向上 | `smoothdown` | 平滑向下 |
| `circlecrop` | 圆形裁剪 | `rectcrop` | 矩形裁剪 |
| `circleclose` | 圆形收缩 | `circleopen` | 圆形展开 |
| `horzclose` | 水平收缩 | `horzopen` | 水平展开 |
| `vertclose` | 垂直收缩 | `vertopen` | 垂直展开 |
| `pixelize` | 像素化 | `radial` | 径向扩散 |
| `distance` | 距离模糊 | `fadeblack` | 黑场淡出 |
| `fadewhite` | 白场淡出 | `diagtl` | 对角线(左上) |
| `diagtr` | 对角线(右上) | `diagbl` | 对角线(左下) |
| `diagbr` | 对角线(右下) | `hlslice` | 水平左切片 |
| `hrslice` | 水平右切片 | `vuslice` | 垂直上切片 |
| `vdslice` | 垂直下切片 | `none` | 无转场(直接切换) |

## 音色列表

| 音色名 | 中文名 | 特点 |
|--------|--------|------|
| `Xiaoxiao` | 晓晓 | 活泼温暖女声（默认女声） |
| `Xiaoyi` | 晓伊 | 成熟稳重女声 |
| `Yunxia` | 云夏 | 年轻女声 |
| `Yunyang` | 云扬 | 成熟稳重男声（默认男声） |
| `Yunxi` | 云希 | 年轻男声 |
| `Yunjian` | 云健 | 新闻播报男声 |

## 快速修改方法

### 方法1：直接改配置文件（推荐）
编辑 `.video_config.json`，修改对应值，下次运行即可生效：

```bash
python3 video_generator_pro.py -p {project_dir}
```

### 方法2：命令行覆盖
命令行参数优先级高于配置文件，适合临时调试：

```bash
python3 video_generator_pro.py -p {project_dir} \
    --scene-fade 0.3 \
    --subtitle --subtitle-animation slide_up \
    --transition pixelize \
    --watermark logo.png \
    --watermark-position bottom-right \
    --sfx
```

---
*生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        param_doc_path.write_text(param_doc, encoding='utf-8')
        print(f"  ✅ 参数说明.md")

    # 7. 显示后续步骤
    print(f"\n{'='*60}")
    print("✅ 项目初始化完成!")
    print(f"{'='*60}")
    print(f"📁 项目路径: {project_dir}")
    print(f"\n📋 后续步骤:")
    if mode in ('image', 'hybrid'):
        print(f"  1. 放入图片到: {project_dir}/03_images/")
        print(f"     命名: 01.jpg, 02.jpg, ... 或 吃饭.jpg, 睡觉.png, ...")
    if mode in ('video', 'hybrid'):
        print(f"  1. 放入视频到: {project_dir}/04_videos/")
        print(f"     命名: scene_01.mp4, scene_02.mp4, ...")
    print(f"  2. 编辑文章: {project_dir}/01_article/文章.md")
    print(f"  3. (可选) 放入 BGM 到: {project_dir}/02_bgm/")
    print(f"     支持: .mp3 .wav .aac .m4a，自动循环播放")
    print(f"  4. (可选) 放入转场音效到: {project_dir}/02_sfx/")
    print(f"     支持: .mp3 .wav，自动在转场时混入")
    print(f"  5. 生成视频:")
    print(f"     python3 video_generator_pro.py -p {project_dir} --voice {voice}")

    if mode in ('image', 'hybrid'):
        print(f"\n💡 提示: 需要 {resolution} 比例的图片素材")

    return True


def merge_project_config(args, project_dir: Path):
    """加载项目 .video_config.json，命令行参数优先级 > 配置文件 > argparse 默认值"""
    config_path = project_dir / '.video_config.json'
    if not config_path.exists():
        return args

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception:
        return args

    # 解析命令行中显式指定的参数（长参数和短参数）
    explicit = set()
    i = 0
    argv = sys.argv[1:]
    while i < len(argv):
        arg = argv[i]
        if arg.startswith('--'):
            # --key=value 或 --key
            key = arg[2:].split('=')[0].replace('-', '_')
            explicit.add(key)
        elif arg.startswith('-') and len(arg) == 2:
            # 短参数 -k，跳过下一个值（如果是的话）
            explicit.add(arg[1:])  # 简单映射
            if i + 1 < len(argv) and not argv[i + 1].startswith('-'):
                i += 1
        i += 1

    # 支持的配置键映射（配置文件键名 -> args 属性名）
    config_keys = [
        'voice', 'resolution', 'fps', 'subtitle_style', 'transition',
        'transition_duration', 'rate', 'bgm_volume', 'subtitle', 'output',
        'scene_fade', 'watermark', 'watermark_position', 'sfx', 'subtitle_animation',
        'dual_version'
    ]

    applied = []
    for key in config_keys:
        if key in config and key not in explicit:
            if hasattr(args, key):
                old_val = getattr(args, key)
                new_val = config[key]
                if old_val != new_val:
                    setattr(args, key, new_val)
                    applied.append(f"{key}={new_val}")

    if applied:
        print(f"   📋 已加载项目配置: {', '.join(applied)}")

    return args


def check_project_materials(project_dir: Path, image_assignments: list = None) -> dict:
    """检查项目素材完整性

    Returns:
        dict: 检查结果
    """
    print(f"\n{'='*60}")
    print("🔍 素材检查报告")
    print(f"{'='*60}")

    result = {
        'project_dir': str(project_dir),
        'valid': True,
        'warnings': [],
        'errors': [],
        'stats': {}
    }

    # 1. 检查文章
    article_dir = project_dir / '01_article'
    article_files = list(article_dir.glob('*.md')) + list(article_dir.glob('*.txt')) if article_dir.exists() else []
    if article_files:
        result['stats']['articles'] = len(article_files)
        print(f"  ✅ 文章: {len(article_files)} 个")
        for f in article_files:
            print(f"     - {f.name}")
    else:
        result['warnings'].append("未找到文章文件（01_article/*.md 或 *.txt）")
        print(f"  ⚠️  未找到文章文件")

    # 2. 检查音频
    audio_dir = project_dir / '05_audio'
    audio_files = sorted([f for f in audio_dir.iterdir() if f.suffix == '.mp3']) if audio_dir.exists() else []
    result['stats']['audio_files'] = len(audio_files)
    if audio_files:
        total_duration = sum(get_media_duration(str(f)) for f in audio_files)
        print(f"  ✅ 音频: {len(audio_files)} 个 (总时长: {total_duration:.1f}s)")
    else:
        if article_files:
            result['warnings'].append("音频将自动生成（运行时）")
            print(f"  ⏳ 音频: 未找到，将自动生成")
        else:
            result['errors'].append("无音频且无文章，无法生成")
            print(f"  ❌ 音频: 无音频且无文章")
            result['valid'] = False

    # 3. 检查图片/视频素材
    images_dir = project_dir / '03_images'
    videos_dir = project_dir / '04_videos'

    images = []
    videos = []

    if images_dir.exists():
        images = sorted([f for f in images_dir.iterdir()
                        if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.heic']])
    if videos_dir.exists():
        videos = sorted([f for f in videos_dir.iterdir()
                        if f.suffix.lower() in ['.mp4', '.mov', '.avi', '.mkv']])

    result['stats']['images'] = len(images)
    result['stats']['videos'] = len(videos)

    if videos:
        print(f"  ✅ 视频: {len(videos)} 个")
        for v in videos:
            duration = get_media_duration(str(v))
            print(f"     - {v.name} ({duration:.1f}s)")
    if images:
        print(f"  ✅ 图片: {len(images)} 张")
        for img in images:
            print(f"     - {img.name}")

    # 4. 检查场景片段
    scenes_dir = project_dir / '06_scenes'
    existing_scenes = sorted([f for f in scenes_dir.iterdir() if f.suffix == '.mp4']) if scenes_dir.exists() else []
    result['stats']['existing_scenes'] = len(existing_scenes)
    if existing_scenes:
        print(f"  ✅ 场景片段: {len(existing_scenes)} 个 (将跳过生成)")

    # 5. 检查 BGM
    bgm_dir = project_dir / '02_bgm'
    bgm_files = []
    if bgm_dir.exists():
        music_exts = ['.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg']
        bgm_files = sorted([f for f in bgm_dir.iterdir() if f.suffix.lower() in music_exts])
    result['stats']['bgm'] = len(bgm_files)
    if bgm_files:
        print(f"  ✅ BGM: {len(bgm_files)} 个")
        for bgm in bgm_files:
            duration = get_media_duration(str(bgm))
            print(f"     - {bgm.name} ({duration:.1f}s)")

    # 6. 匹配检查
    if audio_files:
        audio_count = len(audio_files)
        if videos:
            # 视频模式
            video_count = len(videos)
            if audio_count != video_count:
                result['warnings'].append(f"音频({audio_count})和视频({video_count})数量不匹配")
                print(f"  ⚠️  音频({audio_count})和视频({video_count})数量不匹配")
        elif images:
            # 图片模式
            img_count = len(images)
            if audio_count > img_count:
                result['warnings'].append(f"音频({audio_count})多于图片({img_count})，部分场景将复用图片")
                print(f"  ⚠️  音频({audio_count})多于图片({img_count})，部分场景将复用图片")

    # 6. 加载项目配置
    config_path = project_dir / '.video_config.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"\n📋 项目配置:")
        print(f"  模式: {config.get('mode', '未设置')}")
        print(f"  分辨率: {config.get('resolution', '1920x1080')}")
        print(f"  帧率: {config.get('fps', 30)}")
        print(f"  字幕: {config.get('subtitle_style', 'news')}")
        print(f"  转场: {config.get('transition', 'fade')}")
        print(f"  音色: {config.get('voice', 'Xiaoxiao')}")

    print(f"\n{'─'*60}")
    if result['errors']:
        print(f"❌ 发现 {len(result['errors'])} 个错误，无法生成")
        for e in result['errors']:
            print(f"   - {e}")
        result['valid'] = False
    elif result['warnings']:
        print(f"⚠️  发现 {len(result['warnings'])} 个警告，但可以生成")
        for w in result['warnings']:
            print(f"   - {w}")
    else:
        print(f"✅ 素材检查通过，可以生成")
    print(f"{'─'*60}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="视频合成工具 Pro 版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
项目文件夹结构:
  01_article/  - 文章文件 (.md 或 .txt)，自动生成音频
  03_images/   - 图片素材 (.jpg/.png)，配合音频生成视频
  04_videos/   - 视频素材 (.mp4/.mov)，配合音频替换原声
  05_audio/    - 音频文件 (.mp3)，手动放置或自动生成
  04_final/    - 最终输出视频

字幕样式 (--subtitle-style):
  news     - 新闻风格 (白字黑底)
  youtube  - YouTube风格 (黄字黑边)
  minimal  - 极简风格 (白字)
  tiktok   - 抖音风格 (大字居中)

转场效果 (--transition):
  fade        - 淡入淡出
  wipeleft    - 向左擦除
  wiperight   - 向右擦除
  slideleft   - 向左滑动
  slideright  - 向右滑动
  pixelize    - 像素化
  none        - 无转场

AI配音音色 (--voice):
  Xiaoxiao  - 晓晓女声 (默认)
  Yunyang   - 云扬男声
  Yunxi     - 云希年轻男声
  Xiaoyi    - 晓伊成熟女声

示例:
  # 基础用法 (自动识别图片/视频+音频)
  python3 video_generator_pro.py -p projects/XXX

  # 从文章自动生成音频并合成
  python3 video_generator_pro.py -p projects/XXX --voice Xiaoxiao --rate +0%

  # 快速预览（只生成第一个场景，低画质，快速验证）
  python3 video_generator_pro.py -p projects/XXX --preview

  # 完整功能
  python3 video_generator_pro.py -p projects/XXX \\
    --subtitle --subtitle-style news \\
    --transition fade \\
    --intro intro.mp4 --outro outro.mp4 \\
    --bgm music.mp3 --bgm-volume 0.2

  # 批量处理（自动发现当前目录项目）
  python3 video_generator_pro.py --batch

  # 队列处理（指定多个项目，失败自动继续）
  python3 video_generator_pro.py --queue projects/A projects/B projects/C
        """
    )

    parser.add_argument('--project', '-p', help='项目路径')
    parser.add_argument('--batch', action='store_true', help='批量处理多个项目')
    parser.add_argument('--subtitle', '-s', action='store_true', help='添加字幕')
    parser.add_argument('--subtitle-style', default='news',
                       choices=list(SUBTITLE_STYLES.keys()),
                       help='字幕样式 (默认: news)')
    parser.add_argument('--transition', '-t', default='fade',
                       choices=list(TRANSITIONS.keys()),
                       help='转场效果 (默认: fade)')
    parser.add_argument('--transition-duration', type=float, default=0.5,
                       help='转场时长 (秒, 默认: 0.5)')
    parser.add_argument('--intro', help='片头视频路径')
    parser.add_argument('--outro', help='片尾视频路径')
    parser.add_argument('--bgm', '-b', help='背景音乐路径')
    parser.add_argument('--bgm-volume', type=float, default=0.25,
                       help='背景音乐音量 (0.0-1.0, 默认: 0.25)')
    parser.add_argument('--resolution', default='1920x1080',
                       help='分辨率 (默认: 1920x1080)')
    parser.add_argument('--fps', type=int, default=30, help='帧率 (默认: 30)')
    parser.add_argument('--output', '-o', help='输出文件名')
    parser.add_argument('--voice', default='Xiaoxiao',
                       choices=['Xiaoxiao', 'Xiaoyi', 'Yunxi', 'Yunjian', 'Yunxia', 'Yunyang',
                               'HsiaoChen', 'HsiaoYu', 'YunJhe', 'HiuMaan', 'HiuGaai', 'WanLung'],
                       help='AI配音音色 (默认: Xiaoxiao)')
    parser.add_argument('--rate', default='+18%',
                       help='语速调节 (默认: +18%%)')
    parser.add_argument('--init', action='store_true',
                       help='交互式初始化新项目')
    parser.add_argument('--template',
                       choices=list(PROJECT_TEMPLATES.keys()),
                       help='使用预设模板初始化 (news/food/tutorial/education)')
    parser.add_argument('--check', action='store_true',
                       help='只检查素材，不生成视频')
    parser.add_argument('--no-parallel', action='store_true',
                       help='关闭并行生成（默认开启，最多3并发）')
    parser.add_argument('--preview', action='store_true',
                       help='预览模式：只生成第一个场景，快速验证效果')
    parser.add_argument('--regenerate-audio', action='store_true',
                       help='强制重新生成音频（保留已有场景）')
    parser.add_argument('--queue', nargs='+', metavar='PATH',
                       help='队列模式：顺序处理多个项目，失败自动继续下一个')
    parser.add_argument('--scene-fade', type=float, default=0.0,
                       help='场景淡入淡出时长 (秒, 默认: 0.0, 建议 0.3-0.5)')
    parser.add_argument('--watermark', help='水印图片路径')
    parser.add_argument('--watermark-position', default='bottom-right',
                       choices=['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'],
                       help='水印位置 (默认: bottom-right)')
    parser.add_argument('--sfx', action='store_true',
                       help='启用转场音效 (自动查找项目 02_sfx/ 目录)')
    parser.add_argument('--subtitle-animation', default='none',
                       choices=['none', 'slide_up', 'fade_in'],
                       help='字幕动画效果 (默认: none)')
    parser.add_argument('--dual-version', action='store_true',
                       help='同时生成横竖双版本（如当前为横屏则额外生成竖屏，反之亦然）')

    args = parser.parse_args()

    # 检查 ffmpeg
    if not shutil.which('ffmpeg'):
        print("❌ 未找到 ffmpeg，请先安装: brew install ffmpeg")
        sys.exit(1)

    # 项目初始化向导
    if args.init or args.template:
        if args.project:
            project_dir = Path(args.project)
        else:
            project_dir = Path(input("请输入项目路径: ").strip())
        if init_project_wizard(project_dir, template=args.template):
            if input("\n是否立即检查素材? [y/N]: ").strip().lower() == 'y':
                check_project_materials(project_dir)
        sys.exit(0)

    # 批量处理 / 队列处理
    if args.batch or args.queue:
        if args.queue:
            # 队列模式：从命令行获取指定项目列表
            queue_paths = [Path(p) for p in args.queue]
            projects = []
            for p in queue_paths:
                if p.exists() and p.is_dir():
                    projects.append(p)
                else:
                    print(f"⚠️  跳过不存在的项目: {p}")
        else:
            # 批量模式：自动发现当前目录下的项目
            projects = [p for p in Path('.').iterdir() if p.is_dir() and ((p / '04_videos').exists() or (p / '05_audio').exists())]

        if not projects:
            print("❌ 未找到项目文件夹")
            sys.exit(1)

        mode_label = "队列" if args.queue else "批量"
        print(f"\n{'='*60}")
        print(f"🔄 {mode_label}处理 {len(projects)} 个项目...")
        print(f"{'='*60}")

        queue_start = time.time()
        results = []
        success_count = 0
        fail_count = 0
        skip_count = 0

        for i, project in enumerate(projects, 1):
            print(f"\n📌 [{i}/{len(projects)}] 项目: {project.name}")
            print(f"{'─'*60}")

            # 加载项目配置
            merge_project_config(args, project)

            try:
                result = process_project(project, args)
                if result:
                    results.append((project.name, True, str(result)))
                    success_count += 1
                else:
                    results.append((project.name, False, None))
                    fail_count += 1
            except KeyboardInterrupt:
                print(f"\n⛔ 用户中断，终止{mode_label}处理")
                sys.exit(1)
            except Exception as e:
                print(f"\n❌ 项目异常: {e}")
                traceback.print_exc()
                results.append((project.name, False, None))
                fail_count += 1

        queue_total = time.time() - queue_start

        # 汇总报告
        print(f"\n{'='*60}")
        print(f"📊 {mode_label}处理完成报告")
        print(f"{'='*60}")
        print(f"  📁 总项目: {len(projects)} 个")
        print(f"  ✅ 成功:   {success_count} 个")
        print(f"  ❌ 失败:   {fail_count} 个")
        print(f"  ⏱️  总耗时:  {queue_total:.1f}s")
        if success_count > 0:
            print(f"  ⏱️  平均耗时: {queue_total / success_count:.1f}s/项目")
        print(f"\n  📋 项目明细:")
        for name, ok, path in results:
            status = "✅" if ok else "❌"
            detail = f" → {path}" if ok else ""
            print(f"    {status} {name}{detail}")
        print(f"{'='*60}")

    elif args.project:
        # 单个项目
        project_dir = Path(args.project)
        if not project_dir.exists():
            print(f"❌ 项目不存在: {args.project}")
            sys.exit(1)

        # 加载项目配置（命令行参数优先级 > 配置文件）
        merge_project_config(args, project_dir)

        # 素材检查
        if args.check:
            check_project_materials(project_dir)
            sys.exit(0)

        result = process_project(project_dir, args)

        if result:
            print(f"\n▶️  播放命令: open '{result}'")
        else:
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
