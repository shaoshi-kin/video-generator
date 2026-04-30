#!/usr/bin/env python3
"""
script-to-video — 素材+配音口播视频工具

光伏和 AI 自媒体通用。把真实素材（照片/视频）+ 口播稿 → AI 配音 → 竖屏视频。

用法:
    python3 main.py init my-project --style pv
    python3 main.py polish "raw text..." --style pv -o my-project
    python3 main.py gen my-project
    python3 main.py run "raw text..." --style pv --media ./photos/
"""

import sys
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from presets import get_preset, list_presets, resolve_voice
from polish import polish, save_script, PROVIDERS
from tts import check_edge_tts, generate_audio, merge_audio, get_segment_timings
from composer import check_ffmpeg, compose, collect_materials


def cmd_init(args):
    """初始化项目目录"""
    name = args.name
    style = args.style
    preset = get_preset(style)
    project_dir = Path(name).resolve()

    if project_dir.exists():
        print(f"[ERROR] 目录已存在: {project_dir}")
        sys.exit(1)

    # 创建目录结构
    project_dir.mkdir(parents=True)
    (project_dir / 'materials').mkdir()
    (project_dir / 'audio').mkdir()
    (project_dir / 'output').mkdir()

    # 写入示例脚本
    sample_script = preset.get('sample_script', '# 示例口播稿\n\n@全局:女声\n\n开始编写你的口播稿。\n')
    (project_dir / 'script.md').write_text(sample_script, encoding='utf-8')

    # 写入配置文件
    config = {
        'style': style,
        'resolution': preset['resolution'],
        'fps': preset['fps'],
        'voice': preset['voice'],
        'rate': preset['rate'],
        'subtitle_font_size': preset['subtitle_font_size'],
        'subtitle_color': preset['subtitle_color'],
        'subtitle_position': preset['subtitle_position'],
        'subtitle_box': preset['subtitle_box'],
        'created': str(datetime.now()),
    }
    with open(project_dir / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    w, h = preset['resolution'].split('x')
    orientation = '竖屏' if int(h) > int(w) else '横屏'

    print(f"""
{'='*60}
✅ 项目已创建: {project_dir}
{'='*60}
风格:     {style}
方向:     {orientation} ({preset['resolution']})
配音:     {preset['voice']} ({preset['rate']})

📁 目录结构:
  script.md     ← 口播稿（已生成示例，请修改）
  materials/    ← 放入你的照片/视频素材
  audio/        ← AI 配音（自动生成）
  output/       ← 最终视频（自动生成）
  config.json   ← 项目配置

📋 下一步:
  1. 编辑 script.md 修改口播稿（或用 polish 命令让AI润色）
  2. 把你的照片/视频放入 materials/
  3. 运行: python3 main.py gen {name}
{'='*60}
""")


def cmd_polish(args):
    """AI 润色原始文稿"""
    # 读取输入
    raw_input = args.text.strip()
    if Path(raw_input).is_file():
        raw_text = Path(raw_input).read_text(encoding='utf-8')
        print(f"📄 从文件读取: {raw_input} ({len(raw_text)} 字)")
    else:
        raw_text = raw_input
        print(f"📝 从命令行读取 ({len(raw_text)} 字)")

    if len(raw_text) < 20:
        print("[ERROR] 文稿太短（少于20字），建议提供更多细节")
        sys.exit(1)

    if len(raw_text) > 2000:
        print(f"⚠️  原文较长 ({len(raw_text)} 字)，AI 将压缩至 200-400 字")

    # 调 LLM 润色
    print(f"🤖 正在调用 AI 润色（风格: {args.style}）...")
    result = polish(
        raw_text=raw_text,
        style=args.style,
        voice=args.voice,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        provider=args.provider,
    )

    if 'error' in result:
        print(f"\n[ERROR] {result['error']}")
        sys.exit(1)

    # 输出
    if args.output:
        output_dir = Path(args.output)
        saved = save_script(result['script'], output_dir)
        print(f"\n✅ 润色完成！已保存至: {saved}")
        print(f"   标题: {result['title']}")
        print(f"   字数: {result['char_count']} 字")
        print(f"   音色: {result['voice']}")
    else:
        print(f"\n{'='*60}")
        print(result['script'])
        print(f"{'='*60}")
        print(f"标题: {result['title']} | 字数: {result['char_count']} 字")
        print(f"\n💡 使用 --output 项目名 可直接保存到项目目录")


def cmd_gen(args):
    """生成视频：口播稿 + 素材 → AI配音 → 视频"""
    project_dir = Path(args.project).resolve()

    if not project_dir.exists():
        print(f"[ERROR] 项目目录不存在: {project_dir}")
        sys.exit(1)

    # 加载配置
    config_path = project_dir / 'config.json'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    else:
        config = {}

    # 读取口播稿
    script_path = project_dir / 'script.md'
    if not script_path.exists():
        print(f"[ERROR] 找不到口播稿: {script_path}")
        sys.exit(1)
    script = script_path.read_text(encoding='utf-8')

    # 检查素材
    materials_dir = project_dir / 'materials'
    materials = collect_materials(materials_dir)
    if not materials:
        print("[ERROR] materials/ 目录为空，请先放入照片或视频")
        sys.exit(1)

    # 检查依赖
    if not check_edge_tts():
        print("[ERROR] edge_tts 未安装。运行: pip install edge_tts")
        sys.exit(1)
    if not check_ffmpeg():
        print("[ERROR] ffmpeg 未安装。运行: brew install ffmpeg")
        sys.exit(1)

    # 解析参数
    resolution = config.get('resolution', '1080x1920')
    w, h = resolution.split('x')
    width, height = int(w), int(h)
    voice = args.voice or config.get('voice', 'zh-CN-YunyangNeural')
    rate = args.rate or config.get('rate', '+15%')
    fps = config.get('fps', 30)
    font_size = config.get('subtitle_font_size', 52)
    color = config.get('subtitle_color', 'white')
    box = config.get('subtitle_box', True)
    position = config.get('subtitle_position', 'bottom')

    orientation = '竖屏' if height > width else '横屏'
    print(f"""
{'='*60}
🎬 开始生成视频
{'='*60}
项目:     {project_dir.name}
方向:     {orientation} ({resolution})
音色:     {voice} ({rate})
素材:     {len(materials)} 个文件
""")

    # 第一步：生成配音
    print("🎙️  生成 AI 配音...")
    import asyncio
    audio_dir = project_dir / 'audio'
    audio_paths = asyncio.run(generate_audio(script, audio_dir, voice, rate))

    if not audio_paths:
        print("[ERROR] 配音生成失败")
        sys.exit(1)

    # 合并配音
    merged_audio = audio_dir / 'full.mp3'
    if not merge_audio(audio_paths, merged_audio):
        print("[ERROR] 配音合并失败")
        sys.exit(1)
    print(f"  配音已合并: {merged_audio}")

    # 第二步：合成视频
    print("\n🎥 合成视频...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = project_dir / 'output' / f'{project_dir.name}_{timestamp}.mp4'

    # 提取纯文本（去除 @标记）用于字幕
    script_text = script.split('\n')
    script_text = [l for l in script_text
                   if not l.startswith('#') and not l.startswith('@全局:') and not l.startswith('@默认图:')]
    clean_script = '\n'.join(script_text)
    # 移除 @音色: 标记保留文本
    import re
    clean_script = re.sub(r'@\S+[:：]\s*', '', clean_script)

    success = compose(
        materials_dir=materials_dir,
        audio_path=merged_audio,
        output_path=output_path,
        script=clean_script,
        width=width, height=height, fps=fps,
        font_size=font_size, color=color, box=box, position=position,
    )

    if success:
        print(f"""
{'='*60}
✅ 视频生成成功！
{'='*60}
  输出: {output_path}
  大小: {output_path.stat().st_size / 1024 / 1024:.1f} MB
{'='*60}
""")
    else:
        print("\n[ERROR] 视频合成失败，请检查 ffmpeg 和素材文件")
        sys.exit(1)


def cmd_run(args):
    """一键生成：润色 → 生成视频"""
    # Step 1: 润色
    raw_input = args.text.strip()
    if Path(raw_input).is_file():
        raw_text = Path(raw_input).read_text(encoding='utf-8')
    else:
        raw_text = raw_input

    project_name = args.name or f'video_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

    # 先创建项目
    args.name = project_name
    cmd_init(args)

    # 润色并保存
    print(f"🤖 AI 润色中（风格: {args.style}）...")
    result = polish(
        raw_text=raw_text,
        style=args.style,
        voice=args.voice,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        provider=args.provider,
    )

    if 'error' in result:
        print(f"\n[ERROR] {result['error']}")
        sys.exit(1)

    output_dir = Path(project_name)
    save_script(result['script'], output_dir)
    print(f"  标题: {result['title']} | 字数: {result['char_count']} 字")

    # 复制素材（如果指定了 --media）
    if args.media:
        media_src = Path(args.media)
        if media_src.exists():
            materials_dir = output_dir / 'materials'
            for f in media_src.iterdir():
                if f.is_file() and not f.name.startswith('.'):
                    shutil.copy(f, materials_dir / f.name)
            print(f"  素材已复制到 materials/")

            # 直接跑 gen
            args.project = project_name
            cmd_gen(args)
        else:
            print(f"\n⚠️  --media 指定的路径不存在: {args.media}")
            print(f"  项目已创建，放入素材后运行: python3 main.py gen {project_name}")
    else:
        print(f"\n✅ 润色完成！放入素材后运行: python3 main.py gen {project_name}")


def main():
    parser = argparse.ArgumentParser(
        description='script-to-video — 素材+配音口播视频工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 main.py init my-pv-video --style pv
  python3 main.py polish "今天去了一个项目..." --style pv -o my-pv-video
  python3 main.py gen my-pv-video
  python3 main.py run "项目经历..." --style pv --name my-video --media ./photos/
        """,
    )

    sub = parser.add_subparsers(dest='command', help='可用命令')

    # --- init ---
    p_init = sub.add_parser('init', help='初始化新项目')
    p_init.add_argument('name', help='项目名称/路径')
    p_init.add_argument('--style', '-s', default='general',
                        choices=list_presets(), help='风格预设')
    p_init.set_defaults(func=cmd_init)

    # --- polish ---
    p_polish = sub.add_parser('polish', help='AI 润色原始文稿')
    p_polish.add_argument('text', help='原始文稿，或文件路径')
    p_polish.add_argument('--style', '-s', default='general',
                          choices=list_presets(), help='风格预设')
    p_polish.add_argument('--output', '-o', help='输出项目目录')
    p_polish.add_argument('--voice', help='覆盖默认音色')
    p_polish.add_argument('--provider', default='deepseek',
                          choices=list(PROVIDERS.keys()), help='LLM 提供商')
    p_polish.add_argument('--api-key', help='LLM API Key')
    p_polish.add_argument('--base-url', help='LLM Base URL')
    p_polish.add_argument('--model', help='LLM 模型名')
    p_polish.set_defaults(func=cmd_polish)

    # --- gen ---
    p_gen = sub.add_parser('gen', help='生成视频')
    p_gen.add_argument('project', help='项目目录')
    p_gen.add_argument('--voice', help='覆盖默认音色')
    p_gen.add_argument('--rate', help='覆盖语速')
    p_gen.set_defaults(func=cmd_gen)

    # --- run ---
    p_run = sub.add_parser('run', help='一键生成：润色+配音+合成')
    p_run.add_argument('text', help='原始文稿，或文件路径')
    p_run.add_argument('--style', '-s', default='pv',
                       choices=list_presets(), help='风格预设')
    p_run.add_argument('--name', '-n', help='项目名称（默认自动生成）')
    p_run.add_argument('--media', '-m', help='素材目录路径（照片/视频）')
    p_run.add_argument('--voice', help='覆盖默认音色')
    p_run.add_argument('--provider', default='deepseek',
                       choices=list(PROVIDERS.keys()), help='LLM 提供商')
    p_run.add_argument('--api-key', help='LLM API Key')
    p_run.add_argument('--base-url', help='LLM Base URL')
    p_run.add_argument('--model', help='LLM 模型名')
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
