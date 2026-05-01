#!/bin/bash
# VCG Streamlit GUI 启动脚本 (macOS/Linux)

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "错误: 未找到虚拟环境 venv"
    echo "请先创建虚拟环境: python3 -m venv venv"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 检查依赖是否安装
if ! python -c "import streamlit" 2>/dev/null; then
    echo "安装依赖..."
    pip install -r requirements.txt
fi

# 启动 Streamlit
echo "启动 VCG GUI..."
streamlit run vcg_gui_streamlit.py --server.port 8501 --server.headless true
