# CHECK: TASK-02

## 检查范围

- 读取文件：
  - `CLAUDE.md`
  - `doc/task_02_refactor_vcg_file_processor.md`
  - `doc/delivery_02_refactor_vcg_file_processor.md`
  - `doc/verification_02_refactor_vcg_file_processor.md`
  - `tests/test_vcg_file_processor.py`
  - `tests/test_top.v`
  - `tests/sub_module.v`
  - `src/vcg_file_processor.py`
- 未修改 `src/`、`tests/`、`examples/`、`tmp/`。
- 只写入本检查报告。

## 生成代码检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 生成块注入不会重复 | PASS | `tests/test_vcg_file_processor.py` 覆盖重复运行场景，断言 `//VCG_GEN_BEGIN_0` / `//VCG_GEN_END_0` 各只出现一次，且旧内容被替换。`src/vcg_file_processor.py` 基于 `gen_start_line` / `gen_end_line` 替换完整区间。 |
| 已有生成块替换区间完整 | PASS | `_inject_generated_content_for_blocks()` 在已有 begin/end 行号均存在时用 `lines[gen_start_line:gen_end_line + 1] = generated_lines` 替换，包含 begin/end marker 本身。 |
| 多块错序生成块不会错配 | PASS | 测试覆盖 `VCG_GEN_BEGIN_1` 先于 `VCG_GEN_BEGIN_0` 的场景，输出按显式 id 更新为对应内容。实现中 `_extract_vcg_blocks()` 将生成块区间绑定到 `blocks[gen_block_id]`。 |
| begin/end marker 成对 | PASS | `_extract_vcg_blocks()` 对 orphan、nested、unterminated、malformed `VCG_GEN_BEGIN/END` 均抛 `VCGParseError`；测试覆盖相关异常。 |
| `Instance("sub_module.v",...)` 输出结构 | PASS | `tests/test_top.v` 中已有生成结果为 `sub_module #(... ) u_sub_0 (...);`，参数 override、端口连接、末尾分号结构合理。 |
| `WiresDef("sub_module.v",...)` 输出结构 | PASS | `tests/test_top.v` 中已有生成结果为 `wire [WIDTH-1:0] data_out;` 与 `wire           valid;`，wire 声明语法结构合理。 |
| 相对路径行为 | PASS | tester 覆盖 `Instance("sub.v",...)` 与 `WiresDef("sub.v",...)` 在 `tmp_path` 中按被处理文件目录解析。主会话补跑临时端到端检查，确认从不同 cwd 处理复制出的 `tests/test_top.v` 时，`Instance("sub_module.v",...)` 与 `WiresDef("sub_module.v",...)` 均生成预期结构。 |

## 注入结果人工检查

`tests/test_top.v` 当前包含两个 VCG 块与两个生成块：

| block id | DSL | marker 状态 | 生成结果检查 |
|----------|-----|-------------|--------------|
| 0 | `Connect(...)` + `ConnectParam("WIDTH", "8")` + `Instance("sub_module.v", "sub_module", "u_sub_0")` | `VCG_GEN_BEGIN_0` / `VCG_GEN_END_0` 成对 | 生成 `sub_module #(.WIDTH(8)) u_sub_0 (...)`，端口 `.clk/.rst_n/.data_in/.data_out/.valid` 均有连接，结构合法。 |
| 1 | `WiresDef("sub_module.v", "sub_module", "output")` | `VCG_GEN_BEGIN_1` / `VCG_GEN_END_1` 成对 | 生成 output 端口对应 wire：`data_out` 和 `valid`，声明结构合法。 |

`tests/sub_module.v` 中 `sub_module` 的端口为 `clk`、`rst_n`、`data_in`、`data_out`、`valid`，与 `tests/test_top.v` block 0 生成例化端口一致。

## AST 正确性检查

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 目标模块端口数量 | PASS | `tests/sub_module.v` 声明 5 个端口，`tests/test_top.v` 例化连接 5 个端口。 |
| 端口方向 | PASS | 输入端口 `clk/rst_n/data_in`、输出端口 `data_out/valid` 与生成注释方向一致。 |
| 位宽表达式 | PASS | `data_in` / `data_out` 使用 `[WIDTH-1:0]`；生成注释中显示 `input [WIDTH - 1:0]` / `output [WIDTH - 1:0]`，wire 声明为 `wire [WIDTH-1:0] data_out;`。 |
| 参数 | PASS | `sub_module` 声明 `WIDTH` / `DEPTH`，例化仅覆盖 `WIDTH=8`，语法合理。 |

## 命令结果

| 命令 | 结果 |
|------|------|
| `Get-Content CLAUDE.md` | PASS |
| `Get-Content doc\task_02_refactor_vcg_file_processor.md` | PASS |
| `Get-Content doc\delivery_02_refactor_vcg_file_processor.md` | PASS |
| `Get-Content doc\verification_02_refactor_vcg_file_processor.md` | PASS |
| `Get-Content tests\test_vcg_file_processor.py` | PASS |
| `Get-Content tests\test_top.v` | PASS |
| `Get-Content tests\sub_module.v` | PASS |
| `Get-Content src\vcg_file_processor.py` | PASS |
| `Get-Content vcg.py` | PASS，仅用于确认 CLI 入口；未修改。 |
| `rg "verilator\|lint-only\|VCG_GEN\|Instance\(\|WiresDef\(" -n .` | PASS，用于定位相关生成/检查上下文。 |
| `Get-Command C:\Users\cxhy1\scoop\apps\msys2\current\mingw64\bin\verilator_bin.exe -ErrorAction SilentlyContinue` | PASS，verilator 可执行文件存在。 |
| `New-Item -ItemType Directory -Force C:\tmp\vcg-check-02 \| Out-Null` | FAIL，访问 `C:\tmp\vcg-check-02` 被拒绝。 |
| 提升权限重试创建 `C:\tmp\vcg-check-02` | 未完成，用户中断并要求停止扩展检查。 |

## 未完成项

- 未将 `tests/test_top.v` / `tests/sub_module.v` 复制到临时目录后运行 `uv run python vcg.py ...`。
- 未对临时生成结果运行 verilator。
- 原因：创建 `C:\tmp\vcg-check-02` 时被权限拒绝；按规则请求提升后，用户中断并要求立即停止扩展检查并收尾。

## 主会话补充端到端检查

checker 收尾后，主会话使用系统临时目录重新执行了等价端到端检查：

```text
uv run python -c "<copy tests/test_top.v and tests/sub_module.v to a temp dir; chdir to another dir; run VCGFileProcessor().process_file(top)>"
```

输出：

```text
1 1 True True
```

含义：

- `//VCG_GEN_BEGIN_0` 出现 1 次。
- `//VCG_GEN_BEGIN_1` 出现 1 次。
- `Instance("sub_module.v",...)` 生成了 `sub_module #(...)` 例化结构。
- `WiresDef("sub_module.v",...)` 生成了 `wire [WIDTH-1:0] data_out;`。

## 发现的问题

未发现需要反馈给 architect/dev 的生成 Verilog 或注入结构问题。

残余风险：

- checker 未完成独立端到端重跑 VCG 与 verilator lint；当前结论基于已读取源码、tester 通过报告、测试覆盖内容、以及 `tests/test_top.v` / `tests/sub_module.v` 当前生成结果的人工检查。
