#!/usr/bin/env python3
"""
视频生成器 Web UI (Gradio)

启动方式:
    python3 01_核心脚本/webui.py
    默认在 http://127.0.0.1:7860 打开

功能:
    - 项目列表管理
    - 文章在线编辑
    - 图片批量上传
    - 可视化参数配置
    - 一键生成视频
    - 实时查看生成日志
    - 视频预览和下载
"""

import os
import sys
import json
import subprocess
import threading
import time
from pathlib import Path
from datetime import datetime

# 添加同级目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    import gradio as gr
except ImportError:
    print("❌ 缺少 gradio，请安装: pip3 install 'gradio<4.0'")
    sys.exit(1)

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
PROJECTS_DIR = ROOT_DIR / 'projects'
SCRIPT_PATH = ROOT_DIR / '01_核心脚本' / 'video_generator_pro.py'

# 默认配置
DEFAULT_CONFIG = {
    "mode": "image",
    "resolution": "1920x1080",
    "fps": 30,
    "subtitle": True,
    "subtitle_style": "news",
    "subtitle_animation": "none",
    "transition": "fade",
    "voice": "Xiaoxiao",
    "transition_duration": 0.5,
    "rate": "+18%",
    "scene_fade": 0.0,
    "bgm_volume": 0.25,
    "watermark": None,
    "watermark_position": "bottom-right",
    "sfx": False,
    "dual_version": False,
}

TRANSITIONS = [
    'fade', 'dissolve', 'wipeleft', 'wiperight', 'wipeup', 'wipedown',
    'slideleft', 'slideright', 'slideup', 'slidedown', 'circlecrop',
    'rectcrop', 'distance', 'fadeblack', 'fadewhite', 'radial',
    'fadegrays', 'hblur', 'wipetl', 'wipetr', 'wipebl', 'wipebr',
    'pixelize', 'diagtl', 'diagtr', 'hlslice', 'hrslice', 'vuslice', 'vdslice'
]

SUBTITLE_STYLES = ['news', 'youtube', 'minimal', 'tiktok']

VOICES = ['Xiaoxiao', 'Xiaoyi', 'Yunxi', 'Yunjian', 'Yunxia', 'Yunyang',
          '女声', '晓晓', '男声', '云扬', '新闻男']

ANIMATIONS = ['none', 'slide_up', 'fade_in']

WATERMARK_POSITIONS = ['top-left', 'top-right', 'bottom-left', 'bottom-right', 'center']

RESOLUTIONS = ['1920x1080', '1080x1920', '1080x1080', '1280x720']


def list_projects():
    """列出所有项目"""
    if not PROJECTS_DIR.exists():
        return []
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir() and (d / '.video_config.json').exists():
            projects.append(d.name)
    return projects


def load_project_info(project_name: str):
    """加载项目信息：文章、配置、已有视频"""
    if not project_name:
        return "", "", "", "", json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)

    project_dir = PROJECTS_DIR / project_name

    # 文章
    article_text = ""
    article_dir = project_dir / '01_article'
    if article_dir.exists():
        for ext in ['*.md', '*.txt']:
            files = list(article_dir.glob(ext))
            if files:
                try:
                    with open(files[0], 'r', encoding='utf-8') as f:
                        article_text = f.read()
                except Exception:
                    pass
                break

    # 图片数量
    images_dir = project_dir / '03_images'
    img_count = len([f for f in images_dir.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']]) if images_dir.exists() else 0

    # 视频数量
    videos_dir = project_dir / '04_videos'
    video_count = len([f for f in videos_dir.iterdir() if f.suffix.lower() in ['.mp4', '.mov', '.avi']]) if videos_dir.exists() else 0

    # 已有输出视频
    final_dir = project_dir / '07_final'
    latest_video = ""
    if final_dir.exists():
        mp4_files = sorted([f for f in final_dir.iterdir() if f.suffix == '.mp4' and f.name != 'preview.mp4'])
        if mp4_files:
            latest_video = str(mp4_files[-1])

    # 配置
    config_path = project_dir / '.video_config.json'
    config_text = json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            config_text = json.dumps(config, ensure_ascii=False, indent=2)
        except Exception:
            pass

    info = f"图片: {img_count} 张 | 视频: {video_count} 个"
    return project_name, article_text, info, latest_video, config_text


def save_article(project_name: str, article_text: str):
    """保存文章"""
    if not project_name:
        return "❌ 请先选择或创建项目"
    project_dir = PROJECTS_DIR / project_name
    article_dir = project_dir / '01_article'
    article_dir.mkdir(parents=True, exist_ok=True)
    article_path = article_dir / '文章.md'
    with open(article_path, 'w', encoding='utf-8') as f:
        f.write(article_text)
    return f"✅ 文章已保存 ({len(article_text)} 字符)"


def save_config(project_name: str, config_text: str):
    """保存配置"""
    if not project_name:
        return "❌ 请先选择或创建项目"
    project_dir = PROJECTS_DIR / project_name
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as e:
        return f"❌ JSON 格式错误: {e}"

    config_path = project_dir / '.video_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return "✅ 配置已保存"


def upload_images(project_name: str, files):
    """上传图片到项目"""
    if not project_name:
        return "❌ 请先选择或创建项目", ""
    if not files:
        return "⚠️ 未选择文件", ""

    project_dir = PROJECTS_DIR / project_name
    images_dir = project_dir / '03_images'
    images_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for file in files:
        if file is None:
            continue
        src = Path(file.name) if hasattr(file, 'name') else Path(file)
        if src.exists():
            dest = images_dir / src.name
            import shutil
            shutil.copy(str(src), str(dest))
            count += 1

    info = f"图片: {len([f for f in images_dir.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']])} 张"
    return f"✅ 已上传 {count} 张图片", info


def create_project_ui(project_name: str, template: str):
    """创建新项目"""
    if not project_name.strip():
        return "❌ 项目名称不能为空", gr.update(choices=list_projects()), "", "", "", ""

    project_dir = PROJECTS_DIR / project_name.strip()
    if project_dir.exists() and any(project_dir.iterdir()):
        return f"⚠️ 项目 {project_name} 已存在", gr.update(choices=list_projects()), "", "", "", ""

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / '01_article').mkdir(exist_ok=True)
    (project_dir / '03_images').mkdir(exist_ok=True)
    (project_dir / '02_bgm').mkdir(exist_ok=True)

    config = DEFAULT_CONFIG.copy()
    if template == '竖屏短视频':
        config['resolution'] = '1080x1920'
        config['subtitle_style'] = 'tiktok'
    elif template == '横屏 YouTube':
        config['resolution'] = '1920x1080'
        config['subtitle_style'] = 'youtube'
    elif template == '新闻播报':
        config['resolution'] = '1920x1080'
        config['subtitle_style'] = 'news'
        config['voice'] = '新闻男'

    config_path = project_dir / '.video_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 初始化文章模板
    article_path = project_dir / '01_article' / '文章.md'
    with open(article_path, 'w', encoding='utf-8') as f:
        f.write(f"# {project_name}\n\n")
        f.write("@全局:女声\n@默认图: 01\n\n")
        f.write("第一段文案内容...\n\n")
        f.write("第二段文案内容...\n")

    projects = list_projects()
    return f"✅ 项目 {project_name} 创建成功", gr.update(choices=projects, value=project_name), "", "", "", ""


def generate_video_task(project_name: str, extra_args: str, log_box):
    """在后台线程中运行视频生成"""
    if not project_name:
        return "❌ 请先选择项目"

    project_dir = PROJECTS_DIR / project_name

    cmd = [sys.executable, str(SCRIPT_PATH), '-p', str(project_dir)]
    if extra_args.strip():
        cmd.extend(extra_args.strip().split())

    log_text = ""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            log_text += line
            # 通过全局变量传递（gradio 实时更新需要 yield）
        proc.wait()
        if proc.returncode == 0:
            log_text += "\n✅ 生成完成"
        else:
            log_text += "\n❌ 生成失败"
    except Exception as e:
        log_text += f"\n❌ 异常: {e}"

    return log_text


def generate_video_stream(project_name: str, extra_args: str):
    """生成视频，实时 yield 日志（Gradio 支持 generator）"""
    if not project_name:
        yield "❌ 请先选择项目"
        return

    project_dir = PROJECTS_DIR / project_name
    cmd = [sys.executable, str(SCRIPT_PATH), '-p', str(project_dir)]
    if extra_args.strip():
        cmd.extend(extra_args.strip().split())

    log_text = ""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in proc.stdout:
            log_text += line
            yield log_text
        proc.wait()
        if proc.returncode == 0:
            log_text += "\n✅ 生成完成"
        else:
            log_text += "\n❌ 生成失败"
    except Exception as e:
        log_text += f"\n❌ 异常: {e}"

    yield log_text


def get_latest_video_path(project_name: str):
    """获取项目最新视频路径"""
    if not project_name:
        return None
    final_dir = PROJECTS_DIR / project_name / '07_final'
    if not final_dir.exists():
        return None
    mp4_files = sorted([f for f in final_dir.iterdir() if f.suffix == '.mp4' and f.name != 'preview.mp4'])
    return str(mp4_files[-1]) if mp4_files else None


def build_ui():
    """构建 Gradio UI"""
    with gr.Blocks(title="视频生成器 Pro", css="""
        .gradio-container { max-width: 1200px; }
        #log-box { font-family: monospace; font-size: 13px; }
    """) as demo:
        gr.Markdown("# 🎬 视频生成器 Pro - Web UI")
        gr.Markdown("可视化配置，一键生成视频")

        with gr.Row():
            with gr.Column(scale=1):
                # 左侧：项目管理
                gr.Markdown("## 📁 项目管理")
                project_dropdown = gr.Dropdown(
                    choices=list_projects(),
                    label="选择项目",
                    value=None
                )
                with gr.Row():
                    refresh_btn = gr.Button("🔄 刷新")
                    load_btn = gr.Button("📂 加载", variant="primary")

                gr.Markdown("### ➕ 创建新项目")
                new_project_name = gr.Textbox(label="项目名称", placeholder="my_video")
                template_select = gr.Dropdown(
                    choices=['横屏 YouTube', '竖屏短视频', '新闻播报', '通用'],
                    value='通用',
                    label="模板"
                )
                create_btn = gr.Button("创建项目", variant="secondary")
                create_status = gr.Textbox(label="状态", interactive=False)

                # 项目信息
                project_info = gr.Textbox(label="项目信息", interactive=False)

            with gr.Column(scale=2):
                # 右侧：编辑和生成
                with gr.Tabs():
                    with gr.TabItem("📝 文章"):
                        article_editor = gr.Textbox(
                            label="文章文案",
                            lines=20,
                            placeholder="# 标题\n\n@全局:女声\n@默认图: 01\n\n第一段内容...\n\n第二段内容..."
                        )
                        save_article_btn = gr.Button("💾 保存文章", variant="primary")
                        article_status = gr.Textbox(label="状态", interactive=False)

                    with gr.TabItem("🖼️ 图片"):
                        image_uploader = gr.File(
                            label="上传图片（支持多选）",
                            file_count="multiple",
                            file_types=["image"]
                        )
                        upload_btn = gr.Button("📤 上传")
                        upload_status = gr.Textbox(label="状态", interactive=False)

                    with gr.TabItem("⚙️ 配置"):
                        config_editor = gr.Textbox(
                            label="项目配置 (.video_config.json)",
                            lines=25,
                            value=json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)
                        )
                        save_config_btn = gr.Button("💾 保存配置", variant="primary")
                        config_status = gr.Textbox(label="状态", interactive=False)

                        gr.Markdown("### 快速参数")
                        with gr.Row():
                            quick_res = gr.Dropdown(RESOLUTIONS, value='1920x1080', label="分辨率")
                            quick_style = gr.Dropdown(SUBTITLE_STYLES, value='news', label="字幕样式")
                            quick_transition = gr.Dropdown(TRANSITIONS, value='fade', label="转场")

                    with gr.TabItem("🚀 生成"):
                        extra_args = gr.Textbox(
                            label="额外命令行参数（可选）",
                            placeholder="例如: --intro-text '欢迎' --outro-text '再见' --normalize-audio",
                            value=""
                        )
                        generate_btn = gr.Button("🎬 开始生成", variant="primary")
                        log_output = gr.Textbox(
                            label="生成日志",
                            lines=30,
                            interactive=False,
                            elem_id="log-box"
                        )

                    with gr.TabItem("🎞️ 预览"):
                        video_player = gr.Video(label="最新视频")
                        refresh_video_btn = gr.Button("🔄 刷新")

        # 事件绑定
        refresh_btn.click(fn=lambda: gr.update(choices=list_projects()), outputs=project_dropdown)

        load_btn.click(
            fn=load_project_info,
            inputs=project_dropdown,
            outputs=[new_project_name, article_editor, project_info, video_player, config_editor]
        )

        create_btn.click(
            fn=create_project_ui,
            inputs=[new_project_name, template_select],
            outputs=[create_status, project_dropdown, article_editor, project_info, video_player, config_editor]
        )

        save_article_btn.click(
            fn=save_article,
            inputs=[project_dropdown, article_editor],
            outputs=article_status
        )

        upload_btn.click(
            fn=upload_images,
            inputs=[project_dropdown, image_uploader],
            outputs=[upload_status, project_info]
        )

        save_config_btn.click(
            fn=save_config,
            inputs=[project_dropdown, config_editor],
            outputs=config_status
        )

        generate_btn.click(
            fn=generate_video_stream,
            inputs=[project_dropdown, extra_args],
            outputs=log_output
        )

        refresh_video_btn.click(
            fn=get_latest_video_path,
            inputs=project_dropdown,
            outputs=video_player
        )

        # 快捷参数更新配置
        def update_config_from_quick(config_text, res, style, transition):
            try:
                config = json.loads(config_text)
            except Exception:
                config = DEFAULT_CONFIG.copy()
            config['resolution'] = res
            config['subtitle_style'] = style
            config['transition'] = transition
            return json.dumps(config, ensure_ascii=False, indent=2)

        quick_res.change(fn=update_config_from_quick, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)
        quick_style.change(fn=update_config_from_quick, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)
        quick_transition.change(fn=update_config_from_quick, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)

    return demo


if __name__ == '__main__':
    print("🎬 启动视频生成器 Web UI...")
    print("   地址: http://127.0.0.1:7860")
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)
