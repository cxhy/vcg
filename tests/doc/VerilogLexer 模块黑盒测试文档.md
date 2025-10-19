# VerilogLexer 模块黑盒测试文档

## 1. 模块概述

VerilogLexer 是一个基于 PLY (Python Lex-Yacc) 的 Verilog 词法分析器，用于将 Verilog 代码文本解析为Token 流。该模块仅解析部分 Verilog 语法元素，不支持完整的 Verilog 语法。

---

## 2. 编程接口

### 2.1 类初始化

```python
lexer = VerilogLexer()
```

**说明**：创建词法分析器实例，此时词法分析器尚未构建。

---

### 2.2 构建词法分析器

```python
lexer.build(**kwargs)
```

**功能**：构建词法分析器，必须在使用 `input()` 和 `token()` 方法前调用。

**参数**：
- `**kwargs`：传递给 PLY 的 lex.lex() 的可选参数

**异常**：无

---

### 2.3 输入源代码

```python
lexer.input(data)
```

**功能**：设置待解析的 Verilog 源代码。

**参数**：
- `data` (str)：待解析的 Verilog 源代码字符串

**异常**：
- `RuntimeError`：如果在调用 `build()` 之前调用此方法

---

### 2.4 获取下一个 Token

```python
token = lexer.token()
```

**功能**：返回下一个解析的 Token 对象。

**返回值**：
- Token 对象（包含 `type`、`value`、`lineno`、`lexpos` 属性）
- `None`：输入结束，无更多 Token

**异常**：
- `RuntimeError`：如果在调用 `build()` 之前调用此方法

---

### 2.5 典型使用流程

```python
lexer = VerilogLexer()
lexer.build()
lexer.input("module test; endmodule")

while True:
    tok = lexer.token()
    if not tok:
        break
    print(tok)
```

---

## 3. Token 类型清单

### 3.1 关键字 Token（14个）

| Token类型 | Verilog 关键字 | 说明 |
|-----------|---------------|------|
| MODULE | module | 模块声明 |
| ENDMODULE | endmodule | 模块结束 |
| BEGIN | begin | 块开始 |
| END | end | 块结束 |
| INPUT | input | 输入端口 |
| INOUT | inout | 双向端口 |
| OUTPUT | output | 输出端口 |
| REG | reg | 寄存器类型 |
| LOGIC | logic | 逻辑类型 |
| WIRE | wire | 线网类型 |
| PARAMETER | parameter | 参数声明 |
| LOCALPARAM | localparam | 本地参数 |
| ASSIGN | assign | 连续赋值 |
| ALWAYS | always | 时序块 |

**注意**：关键字不区分大小写，`MODULE`、`Module`、`module` 都会被识别为 `MODULE` token。

---

### 3.2 运算符 Token（25个）

#### 3.2.1 算术运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| PLUS | + | 加法 |
| MINUS | - | 减法 |
| TIMES | * | 乘法 |
| DIVIDE | / | 除法 |
| MOD | % | 取模 |
| POWER | ** | 幂运算 |

#### 3.2.2 位运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| NOT | ~ | 按位取反 |
| OR | \| | 按位或 |
| AND | & | 按位与 |
| XOR | ^ | 按位异或 |
| XNOR | ^~或 ~^ | 按位同或 |

#### 3.2.3 逻辑运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| LAND | && | 逻辑与 |
| LOR | \|\| | 逻辑或 |
| LNOT | ! | 逻辑非 |

#### 3.2.4 移位运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| LSHIFT | << | 左移 |
| RSHIFT | >> | 右移 |

#### 3.2.5 比较运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| LT | < | 小于 |
| GT | > | 大于 |
| LE | <= | 小于等于 |
| GE | >= | 大于等于 |
| EQ | == | 等于 |
| NE | != | 不等于 |

#### 3.2.6 其他运算符

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| EQUALS | = | 赋值 |
| COND | ? | 条件运算符 |

---

### 3.3 分隔符与括号 Token（9个）

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| LPAREN | ( | 左圆括号 |
| RPAREN | ) | 右圆括号 |
| LBRACKET | [ | 左方括号 |
| RBRACKET | ] | 右方括号 |
| LBRACE | { | 左花括号 |
| RBRACE | } | 右花括号 |
| COMMA | , | 逗号 |
| SEMICOLON | ; | 分号 |
| COLON | : | 冒号 |

---

### 3.4 字面量 Token

#### 3.4.1 标识符（ID）

**格式**：以字母、下划线、反引号或美元符号开头，后跟字母、数字、下划线、反引号或美元符号的组合。

**正则表达式**：`[a-zA-Z_`$][a-zA-Z_0-9`$]*`

**示例**：
- `clk`
- `_reset`
- `data_in`
- `` `define``
- `$display`

---

#### 3.4.2 数字字面量（4种进制）

##### INTNUMBER_DEC（十进制）

**格式**：
- `数字序列`：如 `123`、`456`
- `位宽'd数字序列`：如 `8'd255`、`32'd100`
- `'d数字序列`：如 `'d255`
- 支持下划线分隔符：`32'd1000_0000`

**正则表达式**：`(?:\d+'d\d+(?:_\d+)*|'d\d+(?:_\d+)*|\d+(?:_\d+)*)`

**示例**：
- `123`
- `8'd255`
- `'d100`
- `32'd1_000_000`

---

##### INTNUMBER_HEX（十六进制）

**格式**：
- `位宽'h十六进制数字`：如 `8'hFF`、`16'hABCD`
- `'h十六进制数字`：如 `'hFF`
- 支持下划线分隔符：`32'hDEAD_BEEF`

**正则表达式**：`(?:\d+'h[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*|'h[0-9a-fA-F]+(?:_[0-9a-fA-F]+)*)`

**示例**：
- `8'hFF`
- `'hAB`
- `32'hDEAD_BEEF`

---

##### INTNUMBER_OCT（八进制）

**格式**：
- `位宽'o八进制数字`：如 `8'o377`
- `'o八进制数字`：如 `'o77`
- 支持下划线分隔符

**正则表达式**：`(?:\d+'o[0-7]+(?:_[0-7]+)*|'o[0-7]+(?:_[0-7]+)*)`

**示例**：
- `8'o377`
- `'o77`

---

##### INTNUMBER_BIN（二进制）

**格式**：
- `位宽'b二进制数字`：如 `8'b11111111`
- `'b二进制数字`：如 `'b1010`
- 支持下划线分隔符：`8'b1111_0000`

**正则表达式**：`(?:\d+'b[01]+(?:_[01]+)*|'b[01]+(?:_[01]+)*)`

**示例**：
- `8'b11111111`
- `'b1010`
- `4'b10_11`

---

#### 3.4.3 字符串字面量（STRING_LITERAL）

**格式**：双引号包围的字符序列，支持转义字符。

**支持的转义字符**：
- `\"` → `"`
- `\\` → `\`
- `\n` → 换行符
- `\t` → 制表符

**示例**：
- `"Hello World"`
- `"Line1\nLine2"`
- `"Tab\there"`

---

### 3.5 其他 Token

| Token 类型 | 符号 | 说明 |
|-----------|-----|------|
| HASH | # | 井号（用于延迟或参数传递） |

---

## 4. 特殊处理规则

### 4.1 注释处理

#### 单行注释
- **格式**：`//注释内容`
- **处理**：被忽略，不生成 Token

#### 多行注释
- **格式**：`/* 注释内容 */`
- **处理**：被忽略，不生成 Token，会正确统计换行符更新行号

---

### 4.2 空白字符处理

- **空格**（` `）和**制表符**（`\t`）：被忽略
- **换行符**（`\n`）：更新行号计数，不生成 Token

---

### 4.3 Token 值预处理

#### 数字字面量
所有数字字面量中的下划线 `_` 会被移除：
- 输入：`32'hDEAD_BEEF`
- Token.value：`32'hDEADBEEF`

#### 字符串字面量
- 去除首尾双引号
- 处理转义字符

---

### 4.4 关键字识别

-关键字**不区分大小写**
- 如果标识符匹配关键字（小写形式），则识别为关键字 Token
- 示例：`Module`、`MODULE`、`module` →全部识别为 `MODULE` token

---

## 5. 边界条件与特殊情况

### 5.1 异常情况

#### 5.1.1 未构建词法分析器

**场景**：在调用 `build()` 之前调用 `input()` 或 `token()`

**行为**：抛出 `RuntimeError` 异常，提示信息为：
```
"Lexer not built. Call build() first."
```

---

#### 5.1.2 非法字符

**场景**：输入包含无法识别的字符

**行为**：
1. 打印错误信息到标准输出：
   ```Lexical error at line X, column Y: Illegal character 'C' (0xHH)
   ```其中 X 是行号，Y 是列号，C 是非法字符，HH 是十六进制 ASCII 码
2. 跳过该字符，继续解析后续内容

**示例**：
```python
lexer.input("module @test;")
# 输出：Lexical error at line 1, column 8: Illegal character '@' (0x40)
# @ 被跳过，继续解析
```

---

### 5.2 运算符优先级与歧义

#### 5.2.1 多字符运算符需在单字符运算符之前匹配

以下是关键的匹配顺序：

| 优先级 | Token | 符号 | 说明 |
|-------|-------|------|------|
| 高 | POWER | ** | 必须在 TIMES (*) 之前匹配 |
| 高 | LOR | \|\| | 必须在 OR(\|) 之前匹配 |
| 高 | LAND | && | 必须在 AND (&) 之前匹配 |
| 高 | LSHIFT | << | 必须在 LT (<) 之前匹配 |
| 高 | RSHIFT | >> | 必须在 GT (>) 之前匹配 |
| 高 | LE | <= | 必须在 LT (<) 之前匹配 |
| 高 | GE | >= | 必须在 GT (>) 之前匹配 |
| 高 | EQ | == | 必须在 EQUALS (=) 之前匹配 |
| 高 | NE | != | 必须在 LNOT (!) 之前匹配 |
| 高 | XNOR | ^~ 或 ~^ | 必须在 XOR (^) 和 NOT (~) 之前匹配 |

---

#### 5.2.2 数字字面量的匹配顺序

**匹配顺序**：HEX → OCT → BIN → DEC

**关键测试点**：
- `8'hFF`：应识别为 INTNUMBER_HEX
- `8'o77`：应识别为 INTNUMBER_OCT
- `8'b11`：应识别为 INTNUMBER_BIN
- `8'd99`：应识别为 INTNUMBER_DEC
- `123`：应识别为 INTNUMBER_DEC

---

### 5.3 边界值测试

#### 5.3.1 空输入

```python
lexer.input("")
tok = lexer.token()  # 返回 None
```

---

#### 5.3.2仅包含注释

```python
lexer.input("// only comment")
tok = lexer.token()  # 返回 None

lexer.input("/* multi-line\ncomment */")
tok = lexer.token()  # 返回 None
```

---

#### 5.3.3 仅包含空白字符

```python
lexer.input("   \t\n   ")
tok = lexer.token()  # 返回 None
```

---

#### 5.3.4 标识符边界

**有效标识符**：
-`` `define``（以反引号开头）
- `$display`（以美元符号开头）
- `_reset`（以下划线开头）
- `clk123`（包含数字）

**无效标识符**：
- `123abc`（不能以数字开头，会被识别为数字+标识符）

---

#### 5.3.5 字符串边界

**有效字符串**：
- `""`（空字符串）
- `"a"`（单字符）
- `"Line1\nLine2"`（包含转义字符）
- `"Quote: \"text\""`（包含转义的引号）

---

### 5.4 特殊符号组合

#### 5.4.1 XNOR 的两种写法

```python
# 测试 ^~
lexer.input("a ^~ b")
# 应生成：ID('a'), XNOR('^~'), ID('b')

# 测试 ~^
lexer.input("a ~^ b")
# 应生成：ID('a'), XNOR('~^'), ID('b')
```

---

## 6. 功能点测试清单

### 6.1 基础功能测试

| 测试项 | 测试用例 | 期望结果 |
|-------|---------|----------|
| 实例化 | `lexer = VerilogLexer()` | 成功创建实例 |
| 构建 | `lexer.build()` | 无异常 |
| 未构建调用 input | 不调用 `build()`，直接调用 `input()` | 抛出 RuntimeError |
| 未构建调用 token | 不调用 `build()`，直接调用 `token()` | 抛出 RuntimeError |

---

### 6.2 关键字测试（14个分支）

对每个关键字进行以下测试：

| 关键字 | 小写 | 大写 | 混合大小写 |
|-------|------|------|-----------|
| module | `module` | `MODULE` | `Module` |
| endmodule | `endmodule` | `ENDMODULE` | `EndModule` |
| begin | `begin` | `BEGIN` | `Begin` |
| end | `end` | `END` | `End` |
| input | `input` | `INPUT` | `Input` |
| inout | `inout` | `INOUT` | `Inout` |
| output | `output` | `OUTPUT` | `Output` |
| reg | `reg` | `REG` | `Reg` |
| logic | `logic` | `LOGIC` | `Logic` |
| wire | `wire` | `WIRE` | `Wire` |
| parameter | `parameter` | `PARAMETER` | `Parameter` |
| localparam | `localparam` | `LOCALPARAM` | `LocalParam` |
| assign | `assign` | `ASSIGN` | `Assign` |
| always | `always` | `ALWAYS` | `Always` |

**期望**：所有变体都应识别为对应的关键字 Token。

---

### 6.3 运算符测试（25 个分支）

#### 6.3.1 算术运算符（6 个）
- `+` → PLUS
- `-` → MINUS
- `*` → TIMES
- `/` → DIVIDE
- `%` → MOD
- `**` → POWER

#### 6.3.2 位运算符（5 个）
- `~` → NOT
- `|` → OR
- `&` → AND
- `^` → XOR
- `^~` 和 `~^` → XNOR（2 种写法）

#### 6.3.3 逻辑运算符（3 个）
- `&&` → LAND
- `||` → LOR
- `!` → LNOT

#### 6.3.4 移位运算符（2 个）
- `<<` → LSHIFT
- `>>` → RSHIFT

#### 6.3.5 比较运算符（6 个）
- `<` → LT
- `>` → GT
- `<=` → LE
- `>=` → GE
- `==` → EQ
- `!=` → NE

#### 6.3.6 其他运算符（3 个）
- `=` → EQUALS
- `?` → COND
- `#` → HASH

---

### 6.4 数字字面量测试（4 种进制 × 多种格式）

#### 6.4.1 十进制（INTNUMBER_DEC）
- `123` → 纯数字
- `8'd255` → 带位宽
- `'d100` → 无位宽前缀
- `1_000_000` → 带下划线

#### 6.4.2 十六进制（INTNUMBER_HEX）
- `8'hFF` → 带位宽
- `'hAB` → 无位宽
- `32'hDEAD_BEEF` → 带下划线
- `16'haBcD` → 大小写混合

#### 6.4.3 八进制（INTNUMBER_OCT）
- `8'o377` → 带位宽
- `'o77` → 无位宽
- `16'o1_234` → 带下划线

#### 6.4.4 二进制（INTNUMBER_BIN）
- `8'b11111111` → 带位宽
- `'b1010` → 无位宽
- `4'b10_11` → 带下划线

---

### 6.5 字符串字面量测试

| 测试用例 | 期望结果 |
|---------|----------|
| `"Hello"` | 普通字符串 |
| `""` | 空字符串 |
| `"Line1\nLine2"` | 包含换行转义 |
| `"Tab\there"` | 包含制表符转义 |
| `"Quote: \"text\""` | 包含引号转义 |
| `"Backslash: \\"` | 包含反斜杠转义 |

---

### 6.6 标识符测试

| 测试用例 | 期望结果 |
|---------|----------|
| `clk` | 普通标识符 |
| `_reset` | 下划线开头 |
| `` `define`` | 反引号开头 |
| `$display` | 美元符开头 |
| `data123` | 包含数字 |
| `a_b_c` | 包含下划线 |
| `CLK` | 大写字母 |

---

### 6.7 分隔符与括号测试（9 个）

| 符号 | Token | 测试用例 |
|-----|-------|----------|
| `(` | LPAREN | `()` |
| `)` | RPAREN | `()` |
| `[` | LBRACKET | `[]` |
| `]` | RBRACKET | `[]` |
| `{` | LBRACE | `{}` |
| `}` | RBRACE | `{}` |
| `,` | COMMA | `a, b` |
| `;` | SEMICOLON | `a;` |
| `:` | COLON | `a:b` |

---

### 6.8 注释测试

| 测试用例 | 期望结果 |
|---------|----------|
| `// comment` | 被忽略，无 Token |
| `/* comment */` | 被忽略，无 Token |
| `/* line1\nline2 */` | 被忽略，行号正确更新 |
| `a // comment\nb` | 生成 ID('a'), ID('b') |

---

### 6.9 空白字符测试

| 测试用例 | 期望结果 |
|---------|----------|
| `   ` | 无Token |
| `\t` | 无 Token |
| `\n` | 无 Token，行号+1 |
| `a   b` | ID('a'), ID('b') |

---

### 6.10 错误处理测试

| 测试用例 | 期望行为 |
|---------|----------|
| 包含非法字符 `@` | 打印错误信息，跳过字符 |
| 包含非 ASCII 字符 | 打印错误信息，跳过字符 |

---

### 6.11 组合与边界测试

| 测试场景 | 测试用例 | 期望 Token 序列 |
|---------|---------|----------------|
| 完整模块 | `module test; endmodule` | MODULE, ID, SEMICOLON, ENDMODULE |
| 端口声明 | `input [7:0] data` | INPUT, LBRACKET, INTNUMBER_DEC, COLON, INTNUMBER_DEC, RBRACKET, ID |
| 赋值语句 | `assign a = b + c` | ASSIGN, ID, EQUALS, ID, PLUS, ID |
| 条件表达式 | `a ? b : c` | ID, COND, ID, COLON, ID |
| 复杂表达式 | `(a && b) \|\| c` | LPAREN, ID, LAND, ID, RPAREN, LOR, ID |
| 参数声明 | `parameter SIZE = 8` | PARAMETER, ID, EQUALS, INTNUMBER_DEC |

---

### 6.12 运算符歧义测试

| 测试用例 | 期望Token | 说明 |
|---------|-----------|------|
| `**` | POWER | 不应识别为两个 TIMES |
| `<<` | LSHIFT | 不应识别为两个 LT |
| `>>` | RSHIFT | 不应识别为两个 GT |
| `<=` | LE | 不应识别为 LT + EQUALS |
| `>=` | GE | 不应识别为 GT + EQUALS |
| `==` | EQ | 不应识别为两个 EQUALS |
| `!=` | NE | 不应识别为 LNOT + EQUALS |
| `&&` | LAND | 不应识别为两个 AND |
| `\|\|` | LOR | 不应识别为两个 OR |
| `^~` | XNOR | 不应识别为 XOR + NOT |
| `~^` | XNOR | 不应识别为 NOT + XOR |

---

## 7. 测试策略建议

### 7.1 单元测试

为每一类Token 编写独立的测试用例，确保覆盖：
1. 基本功能
2. 边界值
3. 错误情况

### 7.2 集成测试

使用真实的 Verilog 代码片段进行测试：
```verilog
module adder(
    input [7:0] a,
    input [7:0] b,
    output [8:0] sum
);
    assign sum = a + b;
endmodule
```

### 7.3 回归测试

- 保存所有测试用例作为回归测试套件
- 代码变更后重新运行全部测试

---

## 8. 已知限制

### 8.1 不支持的 Verilog 语法元素

以下元素在代码中已被注释，**不支持解析**：

#### 不支持的关键字
- `posedge`、`negedge`（边沿触发）
- `or`（敏感列表）
- `if`、`else`（条件语句）
- `case`、`casex`、`casez`、`endcase`、`default`（case 语句）

#### 不支持的运算符
- `<<<`、`>>>`（算术移位）
- `~|`（或非）
- `~&`（与非）
- `===`、`!==`（全等、不全等）
- `+:`、`-:`（位选择运算符）

#### 不支持的符号
- `.`（点，用于模块端口连接）
- `@`（事件控制）
- `$`（系统任务，虽然在 ID 中可以出现，但无专门 Token）

### 8.2 其他限制

- 不支持实数（浮点数）字面量
- 不支持时间单位字面量（如 `1ns`）
- 不支持编译器指令（如 `` `include``、`` `timescale``）

---

## 9. Token 属性说明

每个 Token 对象包含以下属性：

| 属性 | 类型 | 说明 |
|-----|------|------|
| `type` | str | Token 类型（如 'MODULE'、'ID'、'PLUS'） |
| `value` | str/int | Token 的值（经过预处理，如移除下划线） |
| `lineno` | int | Token 所在行号（从 1 开始） |
| `lexpos` | int | Token 在输入字符串中的起始位置（从 0 开始） |

---

## 10. 测试检查清单

### 10.1 功能完整性
- [ ] 所有 14 个关键字可正确识别
- [ ] 所有 25 个运算符可正确识别
- [ ] 所有 9 个分隔符/括号可正确识别
- [ ] 4 种进制数字均可正确识别
- [ ] 标识符可正确识别（包括特殊开头字符）
- [ ] 字符串字面量可正确识别（包括转义字符）
- [ ] 单行和多行注释可正确忽略
- [ ] 空白字符可正确忽略

### 10.2 边界条件
- [ ] 空输入返回 None
- [ ] 仅注释输入返回 None
- [ ] 仅空白字符输入返回 None
- [ ] 未构建即调用抛出异常

### 10.3 错误处理
- [ ] 非法字符打印错误并跳过
- [ ] 错误信息包含正确的行号和列号

### 10.4 运算符优先级
- [ ] 多字符运算符正确匹配（不拆分）
- [ ] 所有歧义运算符组合测试通过

### 10.5 数值处理
- [ ] 下划线正确移除
- [ ] 各进制数字值正确保留

---

## 附录：快速参考表

### Token 总数统计
- **关键字**：14 个
- **运算符**：25 个
- **分隔符/括号**：9 个
- **其他**：5 个（ID、STRING_LITERAL、4 种数字类型）
- **总计**：48 个 Token 类型

---

本文档提供了 VerilogLexer 模块的完整黑盒测试指南，覆盖所有功能点、边界条件和测试场景，可支持验证人员在不了解内部实现的情况下完成全面的功能验证。