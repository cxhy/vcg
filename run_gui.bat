@echo off
REM VCG Streamlit GUI 启动脚本 (Windows)

REM 检查虚拟环境是否存在
if not exist "venv\" (
    echo 错误: 未找到虚拟环境 venv
    echo 请先创建虚拟环境: python -m venv venv
    exit /b 1
)

REM 激活虚拟环境
echo 激活虚拟环境...
call venv\Scripts\activate.bat

REM 检查依赖是否安装
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo 安装依赖...
    pip install -r requirements.txt
)

REM 启动 Streamlit
echo 启动 VCG GUI...
streamlit run vcg_gui_streamlit.py --server.port 8501 --server.headless true
