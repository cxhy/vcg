#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCG Streamlit GUI - Verilog Code Generator Web 界面
提供可视化的代码生成、对比和配置功能
"""

import streamlit as st
import pandas as pd
import re
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Optional


# ==================== Verilog 解析模块 ====================

class VerilogParser:
    """Verilog 文件解析器"""

    @staticmethod
    def extract_modules(content: str) -> List[Dict]:
        """提取文件中的所有模块定义"""
        modules = []
        try:
            # 匹配 module 定义
            pattern = r'module\s+(\w+)\s*[#(;]'
            matches = re.finditer(pattern, content)

            for match in matches:
                module_name = match.group(1)
                start_pos = match.start()

                # 找到对应的 endmodule
                end_match = re.search(r'endmodule', content[start_pos:])
                if end_match:
                    end_pos = start_pos + end_match.end()
                    module_code = content[start_pos:end_pos]
                    modules.append({
                        'name': module_name,
                        'code': module_code,
                        'start': start_pos,
                        'end': end_pos
                    })

            return modules
        except Exception as e:
            st.error(f"解析文件失败: {e}")
            return []

    @staticmethod
    def identify_top_module(modules: List[Dict], filename: str) -> Optional[Dict]:
        """识别 Top 模块"""
        if not modules:
            return None

        # 策略1: 文件名包含 "top"
        filename_lower = filename.lower()
        if 'top' in filename_lower:
            for mod in modules:
                if 'top' in mod['name'].lower():
                    return mod

        # 策略2: 包含实例化的模块（简单检测）
        for mod in modules:
            if re.search(r'\w+\s+#?\s*\(', mod['code']):
                return mod

        # 策略3: 返回第一个模块
        return modules[0]

    @staticmethod
    def detect_vcg_blocks(code: str) -> List[Dict]:
        """检测 VCG 块位置"""
        blocks = []
        block_id = 0

        # 检测 VCG_BEGIN/END 块
        for match in re.finditer(r'//VCG_BEGIN.*?//VCG_END', code, re.DOTALL):
            block_id += 1
            line_num = code[:match.start()].count('\n') + 1
            blocks.append({
                'id': block_id,
                'line': line_num,
                'type': 'VCG_BEGIN',
                'start': match.start(),
                'end': match.end()
            })

        # 检测 VCG_GEN 块
        for match in re.finditer(r'//VCG_GEN_BEGIN_\d+.*?//VCG_GEN_END_\d+', code, re.DOTALL):
            line_num = code[:match.start()].count('\n') + 1
            blocks.append({
                'id': int(re.search(r'VCG_GEN_BEGIN_(\d+)', match.group()).group(1)),
                'line': line_num,
                'type': 'VCG_GEN',
                'start': match.start(),
                'end': match.end()
            })

        return blocks


# ==================== VCG 执行模块 ====================

def save_uploaded_file(uploaded_file) -> str:
    """保存上传的文件到临时目录"""
    temp_dir = tempfile.mkdtemp(prefix='vcg_')
    temp_path = os.path.join(temp_dir, uploaded_file.name)

    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.getbuffer())

    return temp_path


def execute_vcg_process(file_path: str, macros: Dict[str, str], log_level: str) -> Tuple[bool, str, str]:
    """
    执行 VCG 处理

    参数:
        file_path: Verilog 文件路径
        macros: 宏定义字典
        log_level: 日志级别

    返回:
        (成功标志, 标准输出, 标准错误)
    """
    cmd = [sys.executable, 'src/vcg.py', file_path]

    # 添加宏定义
    if macros:
        macro_str = ','.join([f"{k}={v}" for k, v in macros.items() if k and v])
        if macro_str:
            cmd.extend(['--macros', macro_str])

    # 添加日志级别
    cmd.extend(['--log-level', log_level])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        return (
            result.returncode == 0,
            result.stdout,
            result.stderr
        )
    except subprocess.TimeoutExpired:
        return False, "", "执行超时（60秒）"
    except Exception as e:
        return False, "", f"执行异常: {str(e)}"


def compute_statistics(original_code: str, generated_code: str, vcg_blocks: List[Dict]) -> Dict:
    """计算统计信息"""
    original_lines = original_code.count('\n')
    generated_lines = generated_code.count('\n')
    added_lines = generated_lines - original_lines

    return {
        'file_count': 1,
        'line_count': added_lines,
        'block_count': len([b for b in vcg_blocks if b['type'] == 'VCG_BEGIN']),
        'original_lines': original_lines,
        'generated_lines': generated_lines
    }


# ==================== 界面配置 ====================

def init_session_state():
    """初始化会话状态"""
    if 'original_code' not in st.session_state:
        st.session_state.original_code = ""

    if 'generated_code' not in st.session_state:
        st.session_state.generated_code = ""

    if 'temp_file_path' not in st.session_state:
        st.session_state.temp_file_path = None

    if 'execution_log' not in st.session_state:
        st.session_state.execution_log = ""

    if 'statistics' not in st.session_state:
        st.session_state.statistics = {
            'file_count': 0,
            'line_count': 0,
            'block_count': 0,
            'duration': 0.0
        }

    if 'vcg_blocks' not in st.session_state:
        st.session_state.vcg_blocks = []


def apply_custom_css():
    """应用自定义 CSS 样式"""
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1976D2;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .vcg-block-info {
        background-color: #E3F2FD;
        padding: 0.5rem;
        border-left: 4px solid #1976D2;
        margin-bottom: 0.5rem;
        border-radius: 0.25rem;
    }
    .vcg-gen-info {
        background-color: #C8E6C9;
        padding: 0.5rem;
        border-left: 4px solid #388E3C;
        margin-bottom: 0.5rem;
        border-radius: 0.25rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ==================== 主界面 ====================

def main():
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="VCG - Verilog Code Generator",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 初始化
    init_session_state()
    apply_custom_css()

    # 标题
    st.markdown('<div class="main-header">⚡ VCG - Verilog Code Generator</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">通过 Python 代码块自动生成 Verilog 代码</div>', unsafe_allow_html=True)

    # ==================== 侧边栏配置 ====================
    with st.sidebar:
        st.title("⚙️ 配置")

        # 宏定义管理
        st.subheader("📝 宏定义")

        # 使用 data_editor 创建可编辑表格
        if 'macros_df' not in st.session_state:
            st.session_state.macros_df = pd.DataFrame({
                '名称': ['WIDTH', 'DEPTH'],
                '值': ['32', '1024']
            })

        edited_df = st.data_editor(
            st.session_state.macros_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        st.session_state.macros_df = edited_df

        # 转换为字典
        macros = {}
        for _, row in edited_df.iterrows():
            name = str(row['名称']).strip()
            value = str(row['值']).strip()
            if name and value and name != 'nan' and value != 'nan':
                macros[name] = value

        st.divider()

        # 日志级别选择
        st.subheader("📊 日志级别")
        log_level = st.selectbox(
            "选择日志级别",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=2,
            help="控制日志输出的详细程度"
        )

        st.divider()

        # 执行统计
        st.subheader("📈 执行统计")
        stats = st.session_state.statistics

        col1, col2 = st.columns(2)
        with col1:
            st.metric("处理文件", stats['file_count'])
            st.metric("VCG 块数", stats['block_count'])
        with col2:
            st.metric("新增代码行", stats['line_count'])
            st.metric("执行耗时", f"{stats['duration']:.2f}s")

        st.divider()

        # VCG 块检测
        st.subheader("🔍 VCG 块检测")
        if st.session_state.vcg_blocks:
            for block in st.session_state.vcg_blocks:
                if block['type'] == 'VCG_BEGIN':
                    st.markdown(
                        f'<div class="vcg-block-info">🔵 块 {block["id"]} (行 {block["line"]})</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f'<div class="vcg-gen-info">🟢 生成区 {block["id"]} (行 {block["line"]})</div>',
                        unsafe_allow_html=True
                    )
        else:
            st.info("未检测到 VCG 块")

    # ==================== 主内容区 ====================

    # 文件上传
    uploaded_file = st.file_uploader(
        "📁 选择 Verilog 文件",
        type=['v'],
        help="支持 .v 格式的 Verilog 文件"
    )

    if uploaded_file:
        # 保存到临时文件
        if st.session_state.temp_file_path is None or not os.path.exists(st.session_state.temp_file_path):
            st.session_state.temp_file_path = save_uploaded_file(uploaded_file)

        # 解析文件内容
        file_content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        modules = VerilogParser.extract_modules(file_content)

        if not modules:
            st.warning("⚠️ 未找到有效的模块定义")
            return

        # 模块选择
        st.subheader("📦 模块选择")
        top_module = VerilogParser.identify_top_module(modules, uploaded_file.name)
        default_index = 0

        if top_module:
            try:
                default_index = [m['name'] for m in modules].index(top_module['name'])
            except ValueError:
                default_index = 0

        selected_module_name = st.selectbox(
            "选择要查看的模块",
            [m['name'] for m in modules],
            index=default_index,
            help="自动识别的 Top 模块会默认选中"
        )

        # 获取选中的模块
        selected_module = next((m for m in modules if m['name'] == selected_module_name), None)

        if selected_module:
            # 保存原始代码
            st.session_state.original_code = selected_module['code']

            # 检测 VCG 块
            st.session_state.vcg_blocks = VerilogParser.detect_vcg_blocks(selected_module['code'])

            st.divider()

            # 代码对比视图
            st.subheader("📄 代码对比")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**原始代码**")
                st.code(st.session_state.original_code, language='verilog', line_numbers=True)

            with col2:
                st.markdown("**生成代码**")
                if st.session_state.generated_code:
                    st.code(st.session_state.generated_code, language='verilog', line_numbers=True)
                else:
                    st.info("👇 点击下方的执行按钮生成代码")

            st.divider()

            # 执行按钮
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])

            with col_btn1:
                execute_button = st.button("▶️ 执行 VCG", type="primary", use_container_width=True)

            with col_btn2:
                if st.session_state.generated_code:
                    st.download_button(
                        label="💾 下载结果",
                        data=st.session_state.generated_code,
                        file_name=f"{selected_module_name}_generated.v",
                        mime="text/plain",
                        use_container_width=True
                    )

            # 执行 VCG 处理
            if execute_button:
                with st.spinner("⏳ 正在处理..."):
                    start_time = datetime.now()

                    success, stdout, stderr = execute_vcg_process(
                        st.session_state.temp_file_path,
                        macros,
                        log_level
                    )

                    duration = (datetime.now() - start_time).total_seconds()

                    # 保存日志
                    st.session_state.execution_log = stdout + stderr

                    if success:
                        st.success("✅ 执行成功！")

                        # 重新读取文件
                        with open(st.session_state.temp_file_path, 'r', encoding='utf-8') as f:
                            updated_content = f.read()

                        # 重新解析模块
                        updated_modules = VerilogParser.extract_modules(updated_content)
                        updated_module = next((m for m in updated_modules if m['name'] == selected_module_name), None)

                        if updated_module:
                            st.session_state.generated_code = updated_module['code']

                            # 计算统计信息
                            stats = compute_statistics(
                                st.session_state.original_code,
                                st.session_state.generated_code,
                                st.session_state.vcg_blocks
                            )
                            stats['duration'] = duration
                            st.session_state.statistics = stats

                            # 强制刷新页面
                            st.rerun()
                    else:
                        st.error("❌ 执行失败")
                        st.code(stderr, language='text')

            # 日志输出
            if st.session_state.execution_log:
                with st.expander("📜 执行日志", expanded=False):
                    st.text_area(
                        "日志内容",
                        st.session_state.execution_log,
                        height=300,
                        disabled=True
                    )

    else:
        # 未上传文件时的提示
        st.info("👆 请先上传一个 Verilog 文件开始使用")

        # 使用说明
        with st.expander("📖 使用说明", expanded=True):
            st.markdown("""
            ### 快速开始

            1. **上传文件**：点击上方的文件上传按钮，选择 `.v` 格式的 Verilog 文件
            2. **配置宏定义**：在左侧边栏添加或修改宏定义（可选）
            3. **选择模块**：从下拉菜单选择要处理的模块（自动识别 Top 模块）
            4. **执行处理**：点击"执行 VCG"按钮生成代码
            5. **查看结果**：在代码对比区域查看原始代码和生成代码
            6. **下载结果**：点击"下载结果"按钮保存生成的代码

            ### VCG 块语法

            在 Verilog 文件中使用以下标记定义 VCG 代码块：

            ```verilog
            //VCG_BEGIN
            //for i in range(4):
            //    print(f"wire [7:0] data_{i};")
            //VCG_END

            //VCG_GEN_BEGIN_0
            // 生成的代码会插入到这里
            //VCG_GEN_END_0
            ```

            ### 内置函数

            - `Instance(file, module, name)` - 模块实例化
            - `Connect(port, signal)` - 信号连接
            - `ConnectParam(param, value)` - 参数连接
            - `WiresDef(file, module)` - 生成线声明
            - `WiresRule(port, wire)` - 定义线规则

            ### 更多信息

            查看项目 README.md 获取完整文档。
            """)


if __name__ == "__main__":
    main()
