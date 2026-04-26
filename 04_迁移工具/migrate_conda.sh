#!/bin/bash
# 使用Conda安装Python 3.11（无需Xcode）

set -e

echo "=========================================="
echo "🚀 Conda方式安装 Python 3.11"
echo "=========================================="
echo ""

# 检查是否已安装conda
if ! command -v conda &> /dev/null; then
    echo "📦 安装 Miniconda..."
    echo "------------------------------------------"

    # 下载Miniconda
    CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
    CONDA_INSTALLER="$HOME/miniconda.sh"

    echo "下载中..."
    curl -sL "$CONDA_URL" -o "$CONDA_INSTALLER"

    echo "安装中..."
    bash "$CONDA_INSTALLER" -b -p "$HOME/miniconda3"
    rm "$CONDA_INSTALLER"

    # 初始化
    "$HOME/miniconda3/bin/conda" init zsh
    "$HOME/miniconda3/bin/conda" init bash

    echo "✅ Miniconda安装完成"
    echo "⚠️  请重新打开终端，或运行: source ~/.zshrc"

    # 临时添加到PATH
    export PATH="$HOME/miniconda3/bin:$PATH"
fi

echo ""
echo "🐍 创建 Python 3.11 环境..."
echo "------------------------------------------"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 创建环境
conda create -n py311 python=3.11 -y

echo ""
echo "📦 安装依赖..."
echo "------------------------------------------"

# 激活并安装
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate py311

pip install openai requests edge-tts replicate

echo ""
echo "✅ 安装完成！"
echo ""
echo "使用方法:"
echo "   conda activate py311"
echo "   python tts_simple.py --script '测试' --output test.mp3"
