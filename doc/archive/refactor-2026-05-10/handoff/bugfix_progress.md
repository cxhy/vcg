# VCG Bug 修复进度记录

> 分支: `develop_refactor_parser`
> 日期: 2026-04-11

## 一、环境问题

| 编号 | 问题 | 修复 | 状态 |
|------|------|------|------|
| ENV-1 | `sympy` 未声明为依赖, 导致 5 个测试模块 import 失败 | `uv add sympy` 更新 pyproject.toml | done |

## 二、源码 Bug

| 编号 | 文件 | 问题 | 修复 | 状态 |
|------|------|------|------|------|
| SRC-1 | `vcg_wires_manager.py` | `_parse_verilog_file` 未主动检查文件存在性; `VerilogParser.parse_file` 内部吞掉 `FileNotFoundError` 返回 None, 导致最终抛出 `VCGParseError` 而非 `VCGFileError` | 在 `_parse_verilog_file` 开头新增 `Path(file_path).exists()` 检查, 主动抛 `FileNotFoundError` | done |
| SRC-2 | `vcg_wires_manager.py` | `generate_wires_def` 的 `except Exception` 吞掉了 `ValueError` 和 `VCGParseError`, 统一包装为 `VCGParseError`, 导致调用方无法区分异常类型 | 在通用 `except Exception` 前增加 `except ValueError: raise` 和 `except VCGParseError: raise` | done |

## 三、测试 Bug

| 编号 | 文件 | 测试用例 | 问题 | 修复 | 状态 |
|------|------|----------|------|------|------|
| TST-1 | `test_vcg_wires_manager.py` | `test_tc004_file_with_macros` | `with patch('...VerilogParser')` 在 `WiresManager.__init__` 之后执行, `self.parser` 已是真实实例, patch 无效; `MockParser.assert_called_with()` 断言必然失败 | 改为直接断言 `wires_manager.macros` 和 `parser.preprocessor.macros` | done |
| TST-2 | `test_vcg_wires_manager.py` | `test_bc002_empty_module_name` | 同 TST-1, patch 无效; 且 mock 返回值 `{}` 与 `VerilogAST` 接口不匹配, 导致 `resolve_wire_generation` 解包失败 | 改为使用真实 parser + mock rule_manager | done |
| TST-3 | `test_vcg_wires_manager.py` | `test_ss001_port_name_with_underscore` | 同 TST-1, patch 无效; 真实 parser 解析 `sample_verilog_file` 返回的端口不含 `data_valid` | 改为直接 mock `wires_manager.parser`, 显式设置 `mock_port.name` | done |
| TST-4 | `test_vcg_wires_manager.py` | `test_ss002_port_name_with_digits` | 同 TST-3, 端口不含 `port0` | 同 TST-3 | done |

## 四、测试结果

修复前: 524 passed, 8 failed (5 errors during collection)
修复后: **532 passed, 0 failed**

## 五、后续计划

- [ ] 进入 plan 模式, 规划 Parser 模块重构方案
  - 审查 Parser 架构合理性
  - 检查 Verilog-95 / Verilog-2001 支持完整性
  - 评估 ExpressionCalculator 健壮性
  - 检查错误恢复机制
- [ ] 执行重构
- [ ] 验证 examples/ 目录下所有 Verilog 文件可正确解析
