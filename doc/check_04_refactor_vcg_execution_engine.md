# CHECK: TASK-04

## 检查范围

- 读取 `doc/task_04_refactor_vcg_execution_engine.md`、`doc/delivery_04_refactor_vcg_execution_engine.md`、`doc/verification_04_refactor_vcg_execution_engine.md`。
- 读取 `src/vcg_execution_engine.py`、`tests/test_vcg_execution_engine.py`。
- 只读运行 `uv run python -` 做真实 DSL 输出 smoke 检查。

## 生成代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| `print(...)` 输出顺序 | PASS | smoke 输出以 `// header` 开头，随后是 `Instance` 输出、空行和 `WiresDef` 输出。 |
| `Instance(...)` 例化语法 | PASS | 输出为 `sub #(...) u_sub (...) ;` 结构，参数 override `.WIDTH(16)`，端口连接 `.clk/.data_in/.data_out/.done` 均存在。 |
| `Connect(...)` 规则消费 | PASS | `.clk(sys_clk)`、`.data_in(bus_data)`、`.data_out(bus_out)`、`.done(done)` 均按规则生成。 |
| `ConnectParam(...)` 规则消费 | PASS | `.WIDTH(16)` 出现在例化参数区。 |
| `WiresDef(...)` wire 声明 | PASS | 输出 `wire [WIDTH-1:0] data_out;` 和 `wire           done;`，结构合法。 |
| 空行保留 | PASS | `Instance` 输出和 `WiresDef` 输出之间保留一个空行。 |

## AST 正确性检查

TASK-04 不修改 Parser / AST / VerilogPreprocess。checker 对本任务只验证 DSL 执行后生成的 Verilog 片段是否保持原输出形态；AST 正确性由既有 Parser 和 manager 测试覆盖。

## 命令结果

| 命令 | 结果 |
|------|------|
| `uv run python -` | 退出码 0：真实 DSL smoke PASS；输出包含合法例化、参数 override、端口连接和 wire 声明。 |

备注：首次 checker smoke 在 sandbox 内因本机 uv cache 权限失败，提升权限后同一脚本通过。

## 发现的问题

未发现 Verilog 输出或 AST 相关产品问题。

## 残余风险

- `VCGExecutionEngine` 仍执行完整 Python builtins，这是 TASK-04 明确保留的可信脚本边界；不属于本次 checker 阻断项。
- 本次未执行 verilator。TASK-04 生成片段是例化和 wire 声明，不是完整 Verilog module；以结构检查和现有 manager/parser 回归为主要依据。

## 结论

TASK-04 checker 阶段通过。重构后的 execution engine 保持 `print` / `Connect` / `ConnectParam` / `Instance` / `WiresDef` 输出顺序和生成 Verilog 片段结构，未发现输出格式回归。
