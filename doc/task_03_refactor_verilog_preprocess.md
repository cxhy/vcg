# TASK-03: Refactor `src/VerilogPreprocess.py`

| 字段 | 值 |
|------|----|
| 负责 | vcg-python-dev -> vcg-python-tester -> vcg-verilog-checker |
| 依赖 | TASK-02 已完成 |
| 状态 | completed |
| 创建 | 2026-05-10 |

## 需求描述

重构 `src/VerilogPreprocess.py`，把当前“正则伪预处理器”的高风险状态机收敛成明确的 module header/端口/参数提取前置处理器。保留 `VerilogPreprocess` 类名和公开 API，避免影响 `VerilogParser` 调用链，但内部职责要明确：

- 支持条件编译过滤：``ifdef`` / ``ifndef`` / ``elsif`` / ``else`` / ``endif``。
- 支持 ``define`` / ``undef`` 影响后续条件判断。
- 不承诺完整宏体展开；宏引用（如 `` `WIDTH``）可保留给下游 Parser 或后续 TASK 处理。
- 提取 module 声明、参数声明、端口声明，去除模块体内部实现语句。

本任务依据：

- `doc/refactor_backlog_2026-05-10.md` P0 #2
- `doc/review/12_VerilogPreprocess.md`
- `CLAUDE.md` 异常层级、不可变对象、函数长度规范

## 范围

### 必须完成

1. 删除源文件尾部 `if __name__ == "__main__"` 调试入口和注释死代码。
2. 替换 `condition_stack` dict 为类型化数据结构，建议：

   ```python
   @dataclass(frozen=True)
   class ConditionalFrame:
       taken: bool
       active: bool
       line_no: int
   ```

3. 条件编译必须显式报告不平衡结构：
   - orphan ``else`` / ``elsif`` / ``endif`` 抛 `VCGParseError`
   - unterminated ``ifdef`` / ``ifndef`` 抛 `VCGParseError`
4. 处理 ``define NAME`` 与 ``undef NAME``，使其影响后续 ``ifdef`` / ``ifndef`` / ``elsif`` 判断。
5. 条件编译扫描必须忽略注释中的预处理指令，至少覆盖：
   - 整行 `//`
   - 行尾 `//`
   - 多行 `/* ... */`
6. `preprocess_file()` / `preprocess_string()` 不再用 `RuntimeError` 包装所有异常：
   - 读文件/编码问题抛 `VCGFileError`
   - 预处理结构问题抛 `VCGParseError`
   - 已有 `ValueError` 输入契约错误保持兼容
   - 包装未知异常时必须 `raise ... from e`
7. `read_file()` 使用 `Path` / `open` 的结构化异常处理；UTF-8 失败 fallback latin-1 时至少保留行为，不引入新依赖。
8. `extract_module_ports_section()` 重构为更清晰的阶段处理，避免裸状态变量堆叠；必须能正确处理：
   - ANSI module header 跨多行端口
   - `parameter` / `localparam`
   - `input` / `output` / `inout`
   - `wire` / `reg` / `logic` 等补充声明（如果它们属于端口/参数提取所需上下文）
   - 行尾注释或块注释里的 `;` 不应结束声明
9. `remove_pre_module_content()` 不应误删紧邻 module 之前的 Verilog attribute 行，例如 `(* keep_hierarchy = "yes" *)`。
10. 文件和函数应保持在项目规范内：文件 <800 行，函数 <50 行。

### 非目标

本任务不实现完整 Verilog 预处理器：

- 不展开函数式宏。
- 不展开跨文件 ``include``。
- 不解析所有 SystemVerilog 语法。
- 不改 `VerilogParser` 的公开接口。

如果实现发现必须改 `src/VerilogParser.py` 才能保持当前解析链路，写 `doc/feedback_03_refactor_verilog_preprocess.md`，不要直接扩大范围。

## 接口约束

必须保持以下公开 API 可调用：

```python
VerilogPreprocess(macros=None)
VerilogPreprocess.read_file(file_path: str) -> str
VerilogPreprocess.remove_pre_module_content(content: str) -> str
VerilogPreprocess.extract_module_ports_section(content: str) -> tuple[str, str]
VerilogPreprocess.process_conditional_compilation(content: str) -> str
VerilogPreprocess.preprocess_file(file_path: str) -> str
VerilogPreprocess.preprocess_string(verilog_code: str) -> str
VerilogPreprocess.clear_macros() -> None
VerilogPreprocess.get_macros() -> dict[str, str]
```

允许新增私有 helper、私有 dataclass、私有 enum；不新增第三方依赖。

## 兼容性要求

1. 现有合法用例输出语义保持：返回 module header + 端口/参数声明 + `endmodule`。
2. `macros` 输入仍支持：
   - `None`
   - `dict[str, str]`
   - `list[str]`
   - `list[tuple[str, str]]`
3. 旧测试中“unclosed ifdef 不崩溃 / extra endif 安全忽略”的宽松行为应更新为显式 `VCGParseError`。
4. `preprocess_file("missing.v")` 的异常应从旧 `RuntimeError` 收紧为 `VCGFileError`。
5. `VerilogParser.parse_string()` / `parse_file()` 的现有测试必须继续通过。

## 验收标准

### 静态/结构

- `src/VerilogPreprocess.py` 中不再出现 `if __name__ == "__main__"`。
- 不再出现 `raise RuntimeError("Preprocess Failed...")`。
- `condition_stack` 不再保存 dict。
- 核心函数 <50 行；必要时拆 helper。
- 无新增依赖。

### 行为

1. ``define`` 后的 ``ifdef`` 分支生效；``undef`` 后的 ``ifdef`` 分支失效。
2. ``ifndef`` / ``elsif`` / ``else`` 嵌套逻辑仍正确。
3. 注释中的 ``ifdef`` / ``endif`` 不影响条件栈。
4. orphan / unterminated 条件指令抛 `VCGParseError`。
5. module 前 attribute 行保留或至少不导致 module 丢失。
6. 块注释/行尾注释中的 `;` 不截断 module header 或声明。
7. `preprocess_file()` 文件缺失抛 `VCGFileError`。
8. `tests/test_VerilogParser.py` 仍通过，证明 Parser 链路未破坏。

## 验证命令

聚焦验证：

```bash
uv run pytest tests/test_VerilogPreprocess.py -v
uv run pytest tests/test_VerilogParser.py -v
```

回归验证：

```bash
uv run pytest tests/ -v
```

## 分阶段交付物

### vcg-python-dev

- 修改 `src/VerilogPreprocess.py`
- 写 `doc/delivery_03_refactor_verilog_preprocess.md`
- 不修改 `tests/`

### vcg-python-tester

- 更新 `tests/test_VerilogPreprocess.py`
- 可按需新增 parser 侧回归测试到 `tests/test_VerilogParser.py`
- 运行聚焦和全量测试
- 写 `doc/verification_03_refactor_verilog_preprocess.md`
- 如果发现产品代码问题，写 `doc/feedback_03_refactor_verilog_preprocess.md`

### vcg-verilog-checker

- 只读检查预处理输出对 AST/端口提取的影响
- 至少覆盖一个带条件编译、attribute、注释中分号的 module 样例
- 写 `doc/check_03_refactor_verilog_preprocess.md`

## 已知风险

- 当前测试对旧宽松异常行为有兼容断言，tester 需要更新。
- 完整 Verilog 预处理器范围很大，本任务故意不做宏体展开和 include 展开；文档和交付报告必须明确这一点。
- 如果 `VerilogParser` 依赖旧输出中的某些格式细节，可能需要反馈而不是直接改 Parser。
