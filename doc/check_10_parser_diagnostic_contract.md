# CHECK: TASK-10

| 字段 | 值 |
|------|----|
| 任务 | `doc/task_10_parser_diagnostic_contract.md` |
| 设计 | `doc/design_10_parser_diagnostic_contract.md` |
| 交付 | `doc/delivery_10_parser_diagnostic_contract.md` |
| 验证 | `doc/verification_10_parser_diagnostic_contract.md` |
| 负责 | vcg-architect |
| 日期 | 2026-05-11 |
| 状态 | passed_pending_user_final_confirmation |

## 架构核对

| 项目 | 结论 |
|------|------|
| 范围是否限于 TASK-10 | PASS。仅建立诊断模型和 fail-loud 边界，未实现新 grammar。 |
| `@` / `generate` 语义是否正确 | PASS。归类为 `recognized_unsupported`，未写成永久非法 Verilog。 |
| 未来扩展是否受阻 | PASS。未来支持 token 时可从 unsupported 表迁移到 supported token + grammar。 |
| Parser 是否仍可能返回带错误 AST | PASS。lexer/parser/AST diagnostics 任一 error 会阻止 AST 返回。 |
| stale AST 风险 | PASS。parse 失败前清空 `self.ast`，测试覆盖复用同一 parser 实例。 |
| BNF 是否同步 | PASS。`src/verilog.bnf` 已补充 unsupported/invalid 诊断契约。 |
| 下游 manager 是否被误改 | PASS。未修改 InstanceManager / WiresManager / RuleManager。 |

## 功能点关闭情况

| 功能点 | 状态 |
|--------|------|
| F10.1 结构化 frontend diagnostic | done |
| F10.2 Lexer diagnostics | done |
| F10.3 Parser 唯一成功边界 | done |
| F10.4 Parser 状态重置 | done |
| F10.5 错误消息聚合 | done |
| F10.6 BNF 同步 | done |

## 验证证据

采用 `doc/verification_10_parser_diagnostic_contract.md` 的验证结果：

- TASK-10 focused lexer tests: `3 passed`
- TASK-10 focused parser tests: `4 passed`
- Lexer + Parser: `245 passed`
- Preprocess + Parser: `184 passed`
- Full suite: `703 passed`

## 架构结论

TASK-10 达到关闭标准。当前应进入用户最终确认门禁。用户确认后可以提交本任务并把
`doc/parser_refactor_tasks.json` 中 TASK-10 标记为 `done`。

## 后续约束

- TASK-11 继续处理 token spelling 和关键字大小写契约。
- TASK-13 继续处理 parser grammar cleanup 和 `p_error()` 恢复策略。
- 后续如支持 `always`、`generate`、`.`、`::`，必须从 recognized unsupported 表迁移，
  同步更新 BNF 和测试。
