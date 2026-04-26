#!/bin/bash
# Python 3.11 快捷运行脚本
# 使用方法: ./run_py311.sh script.py [args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 激活 conda 环境
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate py311

# 运行脚本
python "$@"
