# 古籍校勘版分页

校勘版古籍的页下注会反向挤占正文容量。本项目把「篇章结构 + 页容量 + 注记」作为输入，
在**全部合法分页方案**中按字典序目标求出唯一最优解，并提供结构化编辑器与真实联调的分页预览：

- **求解目标（依次最小化）**：页数 → 各页剩余容量平方和 → 全局结束行号序列的字典序。
- **人工版式指令**：在段界与合法段内行位标注「必须保留」（锁定断点）或「禁止断开」（禁断段内位置或段界），
  指令嵌入容量 / 页注 / 寡行 / 与下段保持约束一起求解，而非求解后的装饰。
  原文档可分页但指令不能同时满足时，求**释放数量最少**的一组指令（同数量按录入序号序列裁决，建议唯一），
  页面可一次确认释放并重算。
- **无解时**：按段落顺序定位**最短不可行前缀**，返回其末段与前缀内全部注记编号
  （按标记行、录入序号排序；无注记时返回空数组，界面不作单独归责）。
  原文档本身无解时不混入指令归因。
- 技术栈：Python 3.13 + FastAPI + Pydantic（计算 API），TypeScript + React + Vite（编辑器与预览），
  Docker Compose 一键启动前端、后端与一次性 verify 服务。

## 目录结构

```
api/            FastAPI 应用与求解器
  app/solver.py   分页求解器（动态规划 + 指令约束 + 最小释放枚举 + 最短不可行前缀定位）
  app/models.py   Pydantic 请求/响应模型
  app/main.py     路由与响应装配（无指令旧请求响应保持原样）
  tests/          pytest：单元、穷举核对（≤12 行）、指令穷举（断点 × 释放集合）、API 契约、联调冒烟
web/            React + TypeScript + Vite 前端
  src/lib/        草稿模型、请求构建、格式化、API 客户端
  src/components/ 段落/注记编辑器、页预览、失败定位面板
  src/tests/      Vitest 单元测试
  e2e/            Playwright 端到端测试（真实前后端联调）
docker/         api / web / verify 三个 Dockerfile 与 nginx 配置
docker-compose.yml
```

## 快速开始（Docker Compose）

```bash
docker compose up --build
```

- 前端：http://localhost:8080 （容器内 nginx 提供静态资源并把 `/api` 反代到 `api:8000`）
- 后端：http://localhost:8000 （`GET /api/health`、`POST /api/paginate`）
- `verify` 为一次性服务：待 `api` 健康检查后运行完整 pytest 套件
  （含对运行中 API 的真实 HTTP 冒烟），跑完即退出，退出码即测试结果：

```bash
docker compose up --build --exit-code-from verify verify
```

宿主端口可用环境变量覆盖：

```bash
WEB_PORT=9000 API_PORT=9001 docker compose up --build
```

## 本地开发

后端（Python ≥ 3.11 即可开发，镜像使用 3.13）：

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r api/requirements-dev.txt
uvicorn app.main:app --app-dir api --reload --port 8000
```

前端（Node ≥ 20）：

```bash
cd web
npm install
npm run dev        # http://localhost:5173 ，/api 代理到 http://localhost:8000
```

Vite 代理目标可用 `VITE_API_PROXY_TARGET` 覆盖（Playwright 即借此指向临时后端）。

## 测试

```bash
# 后端：单元 + 穷举核对（≤12 行全部合法分页）+ API 契约
cd api && pytest

# 后端联调冒烟（对运行中的服务发真实 HTTP；未设置时自动跳过）
API_BASE_URL=http://localhost:8000 pytest api/tests/test_live_smoke.py

# 前端单元测试（Vitest）
cd web && npm run test

# 端到端（Playwright，自动拉起 uvicorn 与 vite dev 真实联调）
cd web && npx playwright install chromium
E2E_PYTHON=../.venv/bin/python npm run test:e2e   # E2E_PYTHON 指向装好依赖的解释器
```

穷举核对（`api/tests/test_exhaustive.py`）用独立实现的暴力枚举器列出 ≤ 12 行文档的
全部合法分页，逐案比对求解器的页数、剩余容量平方和与结束行号序列；对不可行文档，
再逐前缀暴力复核「最短不可行前缀」的末段与注记列表。

指令穷举核对（`api/tests/test_exhaustive_directives.py`，≤ 8 行）用另一份独立实现枚举
**全部断点掩码 × 全部指令释放子集**（以位集交叉求每个释放集下的最优分页），逐案核对：
兼容解的目标三元组、唯一最小释放数量与录入序号裁决、部分确认后的最小追加释放、
失效定位（段落失配 / 越界 / 非法位置）、原文档无解时不混入指令归因，以及无指令回归。

## 输入模型

`POST /api/paginate` 请求体：

```json
{
  "capacity": 10,
  "paragraphs": [
    { "id": "p1", "lines": 5, "keep_with_next": true },
    { "id": "p2", "lines": 6, "keep_with_next": false }
  ],
  "footnotes": [
    { "id": "n1", "marker_line": 2, "height": 2 },
    { "id": "n2", "marker_line": 9, "height": 3 }
  ]
}
```

| 字段 | 含义 | 约束 |
| --- | --- | --- |
| `capacity` | 页容量 H（单位：行高） | 正整数 |
| `paragraphs[].lines` | 段落行数 | 正整数，至少一段 |
| `paragraphs[].keep_with_next` | 「与下段保持」 | 末段的该标记无下段可引，忽略 |
| `footnotes[].marker_line` | 注记标记行（全局 1 基行号） | 1 ≤ marker_line ≤ 总行数 |
| `footnotes[].height` | 注记高度 | 正整数 |

段落 id、注记 id 各自唯一；同一标记行可挂多条注记。校验失败返回 422。

## 分页规则（复算依据）

1. **容量**：正文每行占 1 单位；注记不可拆分，整体计入其标记行所在页，占 `height` 单位。
   每页 `正文行数 + 页内注记高度和 ≤ H`。
2. **段内断点**：段落被拆分到多页时，其在每一页上的片段均须 ≥ 2 行
   （首片段、中间片段、末片段同样约束；段界处断页不受此限）。
3. **保持约束**：段 i 标记「与下段保持」时，其末行与下段前两行须同页
   （下段仅一行时即其唯一行）。由于段内断点规则已禁止在下段第 1 行后断页，
   该约束等价于「禁止在段 i 末行处断页」；末段的保持标记忽略。
4. **目标**：在全部合法方案中依次最小化
   ① 页数；② 各页剩余容量平方和 `Σ(H − 已用)²`（含末页）；③ 全局结束行号序列的字典序。
   三者确定后解唯一，可逐页复算：每页卡片直接给出算式
   `正文 x 行 × 1 + 注记 h₁ + … = 已用 / 容量 H（剩余 s）`。
5. **无解定位**：整篇不可行时，按段落顺序取**最短不可行前缀**（不可行性随前缀单调，
   该前缀唯一）；前缀内仅当「与下段保持」所引用的下一段已进入前缀时才检查该约束。
   返回前缀末段（`paragraph_id`、序号、前缀结束行），以及前缀内全部注记编号，
   按 `(标记行, 录入序号)` 排序；前缀内无注记时返回空数组。
   该列表是「前缀范围内的注记清单」，不构成对某一注记的归责。

### 人工版式指令（必须保留 / 禁止断开）

排印人员在分页预览上给出人工版式指令，求解器把它们与容量、页注、寡行（段内片段 ≥ 2 行）、
与下段保持约束**一起**求解，而不是在解上做事后标注。请求中以 `directives` 数组给出，
数组下标即录入序号：

```json
{ "kind": "lock_break", "paragraph_id": "p1", "line_in_paragraph": 5 }
```

| kind | 含义 | 合法位置 |
| --- | --- | --- |
| `lock_break` | **必须保留**：该位置必须是页末断点 | 非末段的段界（`line = 段落行数`），或段内第 i 行后且 `2 ≤ i ≤ 行数−2`（保证两侧片段均 ≥ 2 行） |
| `no_split` | **禁止断开**：该位置不得断页 | 段内第 i 行后且 `1 ≤ i ≤ 行数−1`；或非末段的段界（`line = 段落行数`，禁止在该段界断页，效果同「与下段保持」）。末段段界即文档结束，无断页可禁，判失效 |

- 指令以「段落 id + 段内行号」为**持久身份**；草稿修改后仍按此保存，目标行删除、行号越界或
  段落 id 失配（含段落改名、删除）时，该指令在响应中**就地判失效**（`invalid_directives`，
  原因 `paragraph_not_found` / `line_out_of_range` / `illegal_position`），
  不参与约束，其余编辑内容照常求解。改名即构成 id 失配——指令不随名称迁移，需重新指定。
- 原文档本身无解时，继续返回既有最短不可行前缀，**不混入指令归因**（失效指令仅作定位附注）。
- 原文档可分页但全部有效指令不可同时满足时：
  1. 在所有可行分页中找出**释放数量最少**的一组指令；
  2. 数量相同，按被释放指令的**录入序号序列字典序**裁决，建议唯一；
  3. 响应仍按既有目标（页数 → 余量平方和 → 结束行号序列）给出可复算预览，
     `released_directives` 列出建议释放的指令，`release_confirmed=false`。
  页面可一次确认：带 `release_directives: [序号…]` 重算，求解器在其外再求最小追加释放；
  全部释放项均经确认时 `release_confirmed=true`。
- **向后兼容**：请求不带 `directives` 字段时，行为与响应字节级保持原样，
  不出现任何指令相关字段；前端指令按「段落 id + 段内行号」持久化，
  段落改名 / 删除即 id 失配并就地标出，不随名称迁移。

### 复算示例

默认草稿：`H=10`，`p1=5 行（保持）`，`p2=6 行`；`n1` 标记第 2 行高 2，`n2` 标记第 9 行高 3。

- 合法断点：第 2 行后（p1 内 2/3）、第 7、8 行后（p2 内 2/4、3/3）；第 5 行后因保持约束禁止。
- 总占用 16 > 10，至少 2 页。候选：`[1–7, 8–11]` 平方和 `1² + 3² = 10`；
  `[1–8, 9–11]` 平方和 `0² + 4² = 16`；其余方案页数 ≥ 3。
- 最优解：结束行号序列 `(7, 11)`，平方和 10。
  第 1 页算式 `正文 7 行 × 1 + 注记 2 = 9 / 容量 10（剩余 1）`，断点为段内断点（p2 第 2 行后）。

## API 契约

成功（`status: "ok"`）：`summary`（容量、总行数、页数、剩余容量平方和、结束行号序列）
与 `pages[]`。每页含起止行、逐行归属（段落 id + 段内行号）、页内注记（按标记行与录入
序号排序）、正文/注记/合计/剩余容量，以及页后断点（`paragraph_boundary` 段界 /
`paragraph_split` 段内 / `end` 文档结束）。

失败（`status: "infeasible"`）：`failure` 含最短不可行前缀的末段
（`paragraph_id`、`paragraph_index`、`prefix_end_line`）与前缀内注记
（`footnote_ids` 按标记行、录入序号排序；`footnotes` 为同序明细；无注记时为空数组）。

携带 `directives` 的请求在上述基础上附加（不带 `directives` 的旧请求不出现这些字段）：

- 成功：`directives_satisfied`（是否无需释放任何指令即满足）、`active_directive_count`（有效指令数）、
  `invalid_directives[]`（失效项：`order`、`kind`、`paragraph_id`、`line_in_paragraph`、
  `reason ∈ paragraph_not_found | line_out_of_range | illegal_position`）、
  `released_directives[]`（未作为约束生效的有效指令）、`release_confirmed`
  （`false` = 待确认的最小释放建议；`true` = 全部已随 `release_directives` 确认）。
- 失败（原文档本身无解）：`failure.invalid_directives[]` 仅作失效定位附注；
  无解仍只归因于最短不可行前缀，不返回释放建议。
- 确认释放：请求增加 `release_directives: number[]`（指令录入序号，越界返回 422）；
  求解器把已确认释放剔除后再求最小追加释放集，支持页面一次确认并重算。

## 前端

- 左侧为结构化篇章编辑器：页容量、段落表（id、行数、「与下段保持」，末段复选框禁用并提示）、
  注记表（标记段落 + 段内行号 + 高度，提交时换算为全局行号）。
- 版式指令表：操作（必须保留 / 禁止断开）、目标段落、段内行号；指令按段落 id + 段内行号
  持久化（非编辑器内部键），段落改名 / 删除即 id 失配，指令就地保留并标出失效（行高亮 +
  原因说明），不随名称迁移，其余编辑不受影响。
- 右侧为分页预览：每页卡片展示正文行、页下注、容量算式、断点说明，
  生效中的锁定断点带「锁定断点」标记。
- 指令无法同时满足时，预览上方显示唯一的最小释放建议（逐条列出指令与位置），
  可一次「确认释放并重算」；确认后建议条消失，状态显示已确认释放。
- 失败时高亮最短不可行前缀的末段，并以前缀范围清单形式列出注记（不单独归责），
  同时在面板下方附注失效指令。
