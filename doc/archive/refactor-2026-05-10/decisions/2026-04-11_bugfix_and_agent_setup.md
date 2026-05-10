# 2026-04-11: Bug 修复详细记录

> 从 doc/bugfix_progress.md 归档

## 环境问题

| 编号 | 问题 | 修复 |
|------|------|------|
| ENV-1 | sympy 未声明为依赖 | `uv add sympy` |

## 源码 Bug

**SRC-1**: `vcg_wires_manager.py:_parse_verilog_file`
- 问题：VerilogParser.parse_file 内部吞掉 FileNotFoundError 返回 None
- 修复：在 _parse_verilog_file 开头新增 Path 存在性检查
- 影响测试：test_tc002, test_bc001

**SRC-2**: `vcg_wires_manager.py:generate_wires_def`
- 问题：`except Exception` 把 ValueError/VCGParseError 包装为 VCGParseError
- 修复：在通用 except 前分别 catch 并 re-raise
- 影响测试：test_tc105, test_tc207

## 测试 Bug

**TST-1~4**: `test_vcg_wires_manager.py` 中 4 个测试的 mock 策略错误
- 根因：`with patch('...VerilogParser')` 在 `__init__` 之后执行，self.parser 已创建
- 修复：直接 mock 实例属性而非 patch 类
- 教训：测试"通过"不等于正确，需要确认 mock 是否真的生效

## 结果

修复前: 524 passed, 8 failed
修复后: 532 passed, 0 failed
