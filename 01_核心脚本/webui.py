#!/usr/bin/env python3
"""
视频生成器 Web UI

启动方式:
    python3 01_核心脚本/webui.py
    默认在 http://127.0.0.1:7860 打开

兼容 Gradio 3.x / 4.x / 5.x
"""

import os
import sys
import json
import subprocess
import time
import shutil
from pathlib import Path

# 设置代理排除，避免 Gradio 内部 health check 请求被代理拦截导致 503
os.environ.setdefault('no_proxy', 'localhost,127.0.0.1,0.0.0.0')
os.environ.setdefault('NO_PROXY', 'localhost,127.0.0.1,0.0.0.0')

# 添加同级目录到路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    import gradio as gr
except ImportError:
    print("❌ 缺少 gradio，请安装: pip install gradio")
    sys.exit(1)

GRADIO_VERSION = int(gr.__version__.split('.')[0])
print(f"   Gradio 版本: {gr.__version__}")

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
    "subtitle_mode": "sentence",
    "subtitle_gap": 0.1,
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
    """加载项目信息：返回 article, info, video_path, config_text"""
    if not project_name:
        return "", "未选择项目", None, json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)

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

    # 素材统计
    images_dir = project_dir / '03_images'
    img_count = len([f for f in images_dir.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']]) if images_dir.exists() else 0
    videos_dir = project_dir / '04_videos'
    video_count = len([f for f in videos_dir.iterdir() if f.suffix.lower() in ['.mp4', '.mov', '.avi']]) if videos_dir.exists() else 0
    bgm_dir = project_dir / '02_bgm'
    bgm_count = len([f for f in bgm_dir.iterdir() if f.suffix.lower() in ['.mp3', '.wav', '.aac', '.m4a']]) if bgm_dir.exists() else 0
    info = f"图片: {img_count} 张 | 视频: {video_count} 个 | BGM: {bgm_count} 首"

    # 已有视频
    final_dir = project_dir / '07_final'
    latest_video = None
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

    return article_text, info, latest_video, config_text


def save_article(project_name: str, article_text: str):
    """保存文章"""
    if not project_name:
        return "❌ 请先选择项目"
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
        return "❌ 请先选择项目"
    project_dir = PROJECTS_DIR / project_name
    try:
        config = json.loads(config_text)
    except json.JSONDecodeError as e:
        return f"❌ JSON 格式错误: {e}"

    config_path = project_dir / '.video_config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return "✅ 配置已保存"


def _extract_file_path(file_obj):
    """兼容 Gradio 3.x/4.x/5.x/6.x 的文件路径提取"""
    if file_obj is None:
        return None
    if hasattr(file_obj, 'path'):
        return Path(file_obj.path)
    elif hasattr(file_obj, 'name'):
        return Path(file_obj.name)
    elif isinstance(file_obj, str):
        return Path(file_obj)
    elif hasattr(file_obj, '__fspath__'):
        return Path(file_obj)
    return None


def upload_images(project_name: str, files):
    """上传图片到项目"""
    if not project_name:
        return "❌ 请先选择项目", ""
    if not files:
        return "⚠️ 未选择文件", ""

    project_dir = PROJECTS_DIR / project_name
    images_dir = project_dir / '03_images'
    images_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for file in files:
        src_path = _extract_file_path(file)
        if src_path and src_path.exists():
            dest = images_dir / src_path.name
            shutil.copy(str(src_path), str(dest))
            count += 1

    total = len([f for f in images_dir.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']])
    info = f"图片: {total} 张"
    return f"✅ 已上传 {count} 张图片", info


def upload_bgm(project_name: str, file):
    """上传 BGM 到项目"""
    if not project_name:
        return "❌ 请先选择项目", ""
    src_path = _extract_file_path(file)
    if not src_path or not src_path.exists():
        return "⚠️ 未选择文件", ""

    project_dir = PROJECTS_DIR / project_name
    bgm_dir = project_dir / '02_bgm'
    bgm_dir.mkdir(parents=True, exist_ok=True)

    dest = bgm_dir / src_path.name
    shutil.copy(str(src_path), str(dest))

    total = len([f for f in bgm_dir.iterdir() if f.suffix.lower() in ['.mp3', '.wav', '.aac', '.m4a']])
    info = f"BGM: {total} 首"
    return f"✅ 已上传 BGM: {src_path.name}", info


def create_project_ui(project_name: str, template: str):
    """创建新项目"""
    if not project_name or not str(project_name).strip():
        return "❌ 项目名称不能为空", gr.update(choices=list_projects()), "", "", None, ""

    name = str(project_name).strip()
    project_dir = PROJECTS_DIR / name
    if project_dir.exists() and any(project_dir.iterdir()):
        return f"⚠️ 项目 {name} 已存在", gr.update(choices=list_projects()), "", "", None, ""

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

    article_path = project_dir / '01_article' / '文章.md'
    with open(article_path, 'w', encoding='utf-8') as f:
        f.write(f"# {name}\n\n")
        f.write("@全局:女声\n@默认图: 01\n\n")
        f.write("第一段文案内容...\n\n")
        f.write("第二段文案内容...\n")

    projects = list_projects()
    config_text = json.dumps(config, ensure_ascii=False, indent=2)
    return f"✅ 项目 {name} 创建成功", gr.update(choices=projects, value=name), "", "", None, config_text


def generate_video_stream(project_name: str, extra_args: str):
    """生成视频，实时 yield 日志"""
    if not project_name or not str(project_name).strip():
        yield "❌ 请先选择项目"
        return

    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        yield f"❌ 项目不存在: {project_name}"
        return

    cmd = [sys.executable, str(SCRIPT_PATH), '-p', str(project_dir)]
    extra = str(extra_args).strip() if extra_args else ""
    if extra:
        cmd.extend(extra.split())

    log_text = f"🚀 开始生成视频...\n命令: {' '.join(cmd)}\n{'─'*50}\n"
    yield log_text

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        last_yield_time = time.time()
        for line in proc.stdout:
            log_text += line
            now = time.time()
            if now - last_yield_time >= 0.5:
                yield log_text
                last_yield_time = now
        proc.wait()
        if proc.returncode == 0:
            log_text += "\n✅ 生成完成"
        else:
            log_text += f"\n❌ 生成失败 (exit code: {proc.returncode})"
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
    with gr.Blocks(title="视频生成器 Pro") as demo:
        gr.Markdown("# 🎬 视频生成器 Pro")
        gr.Markdown("可视化配置，一键生成视频")

        with gr.Row():
            # 左侧：项目管理和素材
            with gr.Column(scale=1, min_width=280):
                gr.Markdown("## 📁 项目管理")

                project_dropdown = gr.Dropdown(
                    choices=list_projects(),
                    label="选择项目",
                    value=None,
                    allow_custom_value=False
                )

                with gr.Row():
                    refresh_btn = gr.Button("🔄 刷新", size="sm")
                    load_btn = gr.Button("📂 加载", variant="primary", size="sm")

                gr.Markdown("---")
                with gr.Accordion("➕ 创建新项目", open=False):
                    new_project_name = gr.Textbox(label="项目名称", placeholder="my_video")
                    template_select = gr.Dropdown(
                        choices=['横屏 YouTube', '竖屏短视频', '新闻播报', '通用'],
                        value='通用',
                        label="模板"
                    )
                    create_btn = gr.Button("创建项目", variant="secondary")
                    create_status = gr.Textbox(label="状态", interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 📊 项目素材")
                project_info = gr.Textbox(label="素材统计", interactive=False)

                gr.Markdown("---")
                with gr.Accordion("🖼️ 上传图片", open=False):
                    image_uploader = gr.File(
                        label="选择图片（支持多选）",
                        file_count="multiple",
                        file_types=[".jpg", ".jpeg", ".png", ".webp", ".gif"]
                    )
                    upload_btn = gr.Button("📤 上传图片", size="sm")
                    upload_status = gr.Textbox(label="状态", interactive=False)

                with gr.Accordion("🎵 上传 BGM", open=False):
                    bgm_uploader = gr.File(
                        label="选择背景音乐",
                        file_count="single",
                        file_types=[".mp3", ".wav", ".aac", ".m4a"]
                    )
                    bgm_upload_btn = gr.Button("📤 上传 BGM", size="sm")
                    bgm_upload_status = gr.Textbox(label="状态", interactive=False)

            # 右侧：编辑、配置、生成、预览
            with gr.Column(scale=2, min_width=500):
                with gr.Tabs():
                    with gr.Tab("📝 文章"):
                        article_editor = gr.Textbox(
                            label="文章文案",
                            lines=22,
                            placeholder="# 标题\n\n@全局:女声\n@默认图: 01\n\n第一段内容...\n\n第二段内容..."
                        )
                        save_article_btn = gr.Button("💾 保存文章", variant="primary")
                        article_status = gr.Textbox(label="状态", interactive=False)

                    with gr.Tab("⚙️ 配置"):
                        config_editor = gr.Code(
                            label="项目配置 (.video_config.json)",
                            language="json",
                            lines=20,
                            value=json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2)
                        )
                        save_config_btn = gr.Button("💾 保存配置", variant="primary")
                        config_status = gr.Textbox(label="状态", interactive=False)

                        gr.Markdown("---")
                        gr.Markdown("#### 快速参数")
                        with gr.Row():
                            quick_res = gr.Dropdown(RESOLUTIONS, value='1920x1080', label="分辨率")
                            quick_style = gr.Dropdown(SUBTITLE_STYLES, value='news', label="字幕样式")
                            quick_transition = gr.Dropdown(TRANSITIONS, value='fade', label="转场")

                    with gr.Tab("🚀 生成"):
                        extra_args = gr.Textbox(
                            label="额外命令行参数（可选）",
                            placeholder="例如: --intro-text '欢迎' --outro-text '再见' --normalize-audio",
                            value=""
                        )
                        generate_btn = gr.Button("🎬 开始生成", variant="primary", size="lg")
                        log_output = gr.Textbox(
                            label="生成日志",
                            lines=28,
                            interactive=False
                        )

                    with gr.Tab("🎞️ 预览"):
                        video_player = gr.Video(label="最新视频", height=420)
                        with gr.Row():
                            refresh_video_btn = gr.Button("🔄 刷新视频", size="sm")

        # ========== 事件绑定 ==========

        def refresh_projects():
            return gr.update(choices=list_projects())

        refresh_btn.click(fn=refresh_projects, outputs=project_dropdown)

        def on_load(project_name):
            if not project_name:
                return "", "未选择项目", None, ""
            article, info, video, config = load_project_info(project_name)
            return article, info, video, config

        load_btn.click(
            fn=on_load,
            inputs=project_dropdown,
            outputs=[article_editor, project_info, video_player, config_editor]
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

        bgm_upload_btn.click(
            fn=upload_bgm,
            inputs=[project_dropdown, bgm_uploader],
            outputs=[bgm_upload_status, project_info]
        )

        save_config_btn.click(
            fn=save_config,
            inputs=[project_dropdown, config_editor],
            outputs=config_status
        )

        def update_config_json(config_text, res, style, transition):
            try:
                config = json.loads(config_text)
            except Exception:
                config = DEFAULT_CONFIG.copy()
            config['resolution'] = res
            config['subtitle_style'] = style
            config['transition'] = transition
            return json.dumps(config, ensure_ascii=False, indent=2)

        quick_res.change(fn=update_config_json, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)
        quick_style.change(fn=update_config_json, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)
        quick_transition.change(fn=update_config_json, inputs=[config_editor, quick_res, quick_style, quick_transition], outputs=config_editor)

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

    return demo


if __name__ == '__main__':
    print("🎬 启动视频生成器 Web UI...")
    print(f"   Gradio: {gr.__version__}")
    print("   地址: http://127.0.0.1:7860")
    demo = build_ui()
    if GRADIO_VERSION >= 4:
        launch_kwargs = dict(server_name="127.0.0.1", server_port=7860, show_error=True)
    else:
        launch_kwargs = dict(server_name="0.0.0.0", server_port=7860)
    demo.launch(**launch_kwargs)
