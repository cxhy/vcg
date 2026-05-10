# 2026-05-10: 重构技术决策管理约定

## 背景

本轮从 `refactor/review-driven-cleanup` 分支开始，输入材料包括：

- `CLAUDE.md` 中的项目协作和记忆系统约定。
- `PROJECT.md` 中的长期架构、历史决策和模块依赖说明。
- `doc/review/00_INDEX.md` 及 12 个单文件 Linus 风格 review 报告。
- `doc/archive/refactor-2026-05-10/` 中上一轮 TASK-01 到 TASK-08 的任务、交付、验证、检查和决策归档。

当前问题不是缺少文档目录，而是需要明确每类信息应该落在哪里，避免把短期重构前提、长期架构事实、任务交付记录混在一起。

## 分层规则

| 层级 | 文件或目录 | 写什么 | 不写什么 | 更新时机 |
|------|------------|--------|----------|----------|
| 协作规则 | `CLAUDE.md` / `AGENTS.md` | agent 分工、工作流、命令约束、文档协议 | 某次重构的技术取舍 | 协作机制变化时 |
| 长期记忆 | `PROJECT.md` | 已稳定的架构事实、模块依赖、已验证的重要决策结论 | 每天的争议、待验证假设、临时计划 | 里程碑完成或重大决策稳定后 |
| 短期决策 | `doc/decisions/YYYY-MM-DD_<slug>.md` | 当前会话或当前重构波次的前提、取舍、风险、非目标 | 任务执行流水账、测试完整输出 | 每次形成会影响后续任务的技术判断时 |
| 执行交接 | `doc/task_*` / `doc/delivery_*` / `doc/verification_*` / `doc/check_*` / `doc/feedback_*` | 单个任务的范围、实现、验证、反馈 | 跨任务通用前提的重复描述 | 每个任务阶段完成时 |
| 证据输入 | `doc/review/` | review 发现、风险排序、后续任务建议 | 已接受的最终决策 | review 轮次结束时 |
| 历史归档 | `doc/archive/<wave>/` | 已完成波次的原始记录和索引 | 当前活跃任务 | 波次完成后 |

## 本轮重构的决策记录策略

1. **先写短期决策，再写任务单**

   如果一个判断会影响多个 TASK，例如 Parser 成功边界、Lexer 错误通道、Preprocess 数据流、module_name 契约，就先写入 `doc/decisions/`。任务单只引用该 decision，不重复铺开背景。

2. **`PROJECT.md` 延迟更新**

   本轮重构开始阶段不直接把假设写进 `PROJECT.md`。等某个决策完成实现、验证和检查，再提炼成长期结论进入 `PROJECT.md`。这样可以避免把未验证方案变成项目事实。

3. **一个 decision 只回答一个核心问题**

   好的粒度是：

   - `2026-05-10_parser_error_contract.md`
   - `2026-05-10_preprocess_module_context.md`
   - `2026-05-10_manager_module_name_contract.md`
   - `2026-05-10_rule_substitution_semantics.md`

   不建议写一个巨大的 `all_refactor_decisions.md`，否则后续任务很难引用和废弃局部结论。

4. **区分事实、假设、决策**

   每个 decision 必须标清：

   - 事实：已经从代码、测试、review 或归档文档确认的内容。
   - 假设：当前合理但未完全验证的前提。
   - 决策：本轮明确采用的方向。
   - 后果：兼容性、测试、下游生成 Verilog 的影响。

5. **决策状态必须可变更**

   状态使用 `proposed / accepted / superseded / rejected`。如果后续测试或实现推翻该判断，不改历史为“从来没发生”，而是新增一条 decision 或在原文标记 `superseded` 并链接新文档。

## Decision 模板

新建短期决策时使用以下结构：

```markdown
# YYYY-MM-DD: <决策标题>

| 字段 | 值 |
|------|----|
| 状态 | proposed / accepted / superseded / rejected |
| 作用范围 | 影响的模块或任务 |
| 输入依据 | review、源码、测试、归档文档 |
| 关联任务 | TASK-xx（如有） |

## 问题

需要解决什么真实问题，不描述泛泛的“代码质量提升”。

## 已确认事实

- 从代码、测试、review 或归档中确认的事实。

## 当前假设

- 还没有完全验证，但本轮计划暂时采用的前提。

## 决策

- 明确选择的方向。
- 明确不选择的方向。

## 影响

- 对 API、错误语义、生成 Verilog、测试和迁移的影响。

## 验证要求

- 必须新增或更新的测试。
- 必须运行的回归命令。
- 如果涉及生成代码，说明 byte-for-byte 或语义等价检查要求。

## 后续处理

- 完成后是否进入 `PROJECT.md`。
- 是否需要归档或替换旧 decision。
```

## 当前建议的第一批决策文档

本轮 review 汇总指出的 P0 风险跨模块影响较大，建议先补以下短期 decision，再拆 TASK：

1. `doc/decisions/2026-05-10_parser_error_contract.md`
   - 主题：Lexer / Parser / Preprocess 的失败边界。
   - 核心前提：无法正确理解 Verilog 时必须 fail loud，不能返回脏 AST 或生成看似合法的代码。

2. `doc/decisions/2026-05-10_preprocess_module_context.md`
   - 主题：预处理和目标 module 抽取的顺序。
   - 核心前提：宏和条件编译上下文属于整文件语义，不能在抽取目标 module 前被裁掉。

3. `doc/decisions/2026-05-10_manager_module_name_contract.md`
   - 主题：`InstanceManager` / `WiresManager` 对目标 module 的契约。
   - 核心前提：`module_name` 不能只是日志文本，必须与 AST 中实际解析到的模块建立可验证关系。

4. `doc/decisions/2026-05-10_rule_substitution_semantics.md`
   - 主题：RuleManager 的 `*`、注释、字面量和函数替换语义。
   - 核心前提：字符串替换不能继续扩大特殊分支，应尽量 token 化或结构化处理危险语义。

## 本轮使用约定

- review 报告是输入证据，不直接等于决策。
- decision 文档确定跨任务前提。
- task 文档只执行一个已确认范围。
- delivery / verification / check 文档记录执行结果。
- 波次完成后，把仍然成立的 decision 摘要写入 `PROJECT.md`，原始文档留在 `doc/decisions/` 或随波次移入 `doc/archive/<wave>/decisions/`。
