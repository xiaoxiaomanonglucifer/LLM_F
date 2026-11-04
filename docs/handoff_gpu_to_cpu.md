# GPU → CPU 演示交接文档

> 交接人：R2 曾平 ｜ 交付基线：GitHub `main` @ `a3352a0`
> 适用：CPU 笔记本 / 工作站，不跑模型，只做**离线结果回放**与**Neo4j 图谱可视化**
> 逐幕讲稿与时间分配见 [`docs/demo_manual.md`](demo_manual.md)

---

## 0. 一句话结论

代码、数据、正式实验结果和图谱 Cypher 已经推到 GitHub。CPU 机器拉下来后：

- **可以**回放 `case-main-v1` 的五组结果，不需要 GPU、模型或向量索引；
- **可以**安装 Neo4j 导入案件图，做交互式图谱演示；
- **不可以**直接跑实时 `ask_case`，因为仓库没有模型权重和向量索引。

---

## 1. 从 GitHub 拉取

### 1.1 仓库地址

```text
HTTPS: https://github.com/xiaoxiaomanonglucifer/LLM_F.git
SSH:   git@github.com:xiaoxiaomanonglucifer/LLM_F.git
```

公开仓库直接 clone：

```bash
git clone https://github.com/xiaoxiaomanonglucifer/LLM_F.git
cd LLM_F
```

私有仓库需要 CPU 机器自己的 GitHub 认证：

```bash
git clone git@github.com:xiaoxiaomanonglucifer/LLM_F.git
cd LLM_F
```

注意：GPU 服务器上的 `~/.ssh/id_ed25519_llm_f_github` 是**仓库级 Deploy key**，只留在 GPU 服务器，不要拷到 CPU 机器，也不要用它替代 CPU 机器自己的 GitHub 密钥。

### 1.2 确认版本

```bash
git log -1 --oneline
git status -sb
```

交接基线应包含：

```text
a3352a0 chore: 补充演示手册、回放脚本与实验结果
```

`git status` 显示 `## main...origin/main` 即可。后续如果 R3/R1 继续提交，以实际 `git log` 为准，但本文命令不变。

### 1.3 确认关键文件存在

Linux / macOS：

```bash
test -f results/case-main-v1/run_meta.json && echo OK
test -f scripts/demo_replay.py && echo OK
test -f data/cases/v1/graph/neo4j.cypher && echo OK
test -f docs/demo_manual.md && echo OK
```

Windows PowerShell：

```powershell
Test-Path results/case-main-v1/run_meta.json
Test-Path scripts/demo_replay.py
Test-Path data/cases/v1/graph/neo4j.cypher
Test-Path docs/demo_manual.md
```

四项都应为 `True` / 输出 `OK`。

---

## 2. CPU 机器环境要求

### 2.1 回放所需

| 项目 | 要求 |
|---|---|
| Python | 3.9+ 可跑回放；完整工程建议 3.10 / 3.11 |
| 第三方依赖 | **回放不需要**，只用标准库 |
| GPU | 不需要 |
| 模型权重 | 不需要 |
| 向量索引 / BM25 | 不需要 |
| 网络 | 只在 clone 时需要，演示时可离线 |

### 2.2 Windows 中文输出

`demo_replay.py` 会输出中文。如果 Windows 终端报 `UnicodeEncodeError`：

```powershell
$env:PYTHONUTF8=1
chcp 65001
```

或 CMD：

```bat
set PYTHONUTF8=1
chcp 65001
```

### 2.3 可选：跑单元测试

回放不需要这一步。如果要验证工程完整性：

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -U pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

预期 32 项测试通过。安装依赖会拉取 torch 等大包，演示机时间紧可以跳过。

---

## 3. 拉取后的 3 分钟自检

### 3.1 列出题目

```bash
python3 scripts/demo_replay.py --list
```

Windows 用 `python`：

```powershell
python scripts/demo_replay.py --list
```

预期输出：`共 17 题；结果目录按题号回放。`，并能看到 `hn-case-q01` 到 `hn-case-q17`。

### 3.2 单题回放

```bash
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G2
```

预期看到五段结构：

```text
【模型答案】
一、事实
二、行为定性
三、法条适用
四、裁量计算
五、结论

【五步中间结果】
【引用】
【类案】
```

### 3.3 五组对比

```bash
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare
```

预期看到 G0 / G1 / G2 / G2-case / G2-graph 五行对比，包含答案字数、引用数、类案数、罚款区间和置信度。

### 3.4 常用参数

```text
--run-dir RUN_DIR     指定结果目录，默认 results/case-main-v1
--repeat N            指定重复轮次，默认 1
--group GROUP         指定组别，默认 G2
--question-id ID      指定题号，默认题库第一题
--list                列出全部题目
--compare             五组对比
--json                输出原始 JSON
```

---

## 4. 仓库里有什么、没有什么

### 4.1 已包含

| 路径 | 内容 |
|---|---|
| `results/case-main-v1/` | 正式结果：5 组 × 17 题 = 85 条，`mock=false` |
| `results/dev-server-v1/` | 联调结果，**不是正式结论** |
| `results/repro-server-1/` | 复现验证结果，**不是正式结论** |
| `data/v1/` | 全国法规 v1：75 部、4,104 条 |
| `data/v2/` | 湖南法规 v2：11 部、597 条 |
| `data/cases/v1/` | 11 份脱敏案例、17 道案件题、案件图谱 |
| `data/cases/v1/graph/neo4j.cypher` | 案件图：30 节点 / 180 边 |
| `data/v2/graph/neo4j_import.cypher` | v2 法条图：707 节点 / 4,327 关系 |
| `docs/demo_manual.md` | 10 分钟演示流程与逐幕讲稿 |
| `scripts/demo_replay.py` | 无 GPU 离线回放脚本 |

### 4.2 未包含

| 路径 | 原因 |
|---|---|
| `models/` | 模型权重约 5.2 GB，超过 GitHub 限制 |
| `data/v1/index/chroma/`、`data/v2/index/chroma/` | 派生索引，可由 `articles.jsonl` 重建 |
| `data/v1/index/bm25.pkl`、`data/v2/index/bm25.pkl` | 同上 |
| `.env` | 密钥，禁止入库 |
| `大模型开题报告-...docx` | 含姓名/学号，未公开 |

因此：

- **能演示**：离线回放、Neo4j 图谱查看；
- **不能演示**：实时 `ask_case`、重新生成答案、重新跑正式实验；
- 如果确实要在 CPU 上实时问答，需要重建索引并准备生成模型/API，见 [`docs/demo_manual.md`](demo_manual.md) 第 4 节。

---

## 5. 演示路线 A：离线回放（推荐）

### 5.1 五组含义

| 组别 | 法条检索 | 类案 | 法条图谱 | 用途 |
|---|---|---|---|---|
| G0 | 无 | 无 | 无 | 基座模型直接作答 |
| G1 | 稠密 + BM25 | 无 | 无 | 仅法条 RAG |
| G2 | 稠密 + BM25 | 有 | 有 | 完整系统 |
| G2-case | 稠密 + BM25 | 无 | 有 | 去掉类案 |
| G2-graph | 稠密 + BM25 | 有 | 无 | 去掉法条图谱 |

### 5.2 推荐演示顺序

```bash
# 1. 看题目和题型
python3 scripts/demo_replay.py --list

# 2. 完整组：五步链路
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G2

# 3. 五组消融对比
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare

# 4. 边界题：地类缺失
python3 scripts/demo_replay.py --question-id hn-case-q06 --compare

# 5. 边界题：排除情形
python3 scripts/demo_replay.py --question-id hn-case-q12 --compare

# 6. 原始 JSON，便于二次处理
python3 scripts/demo_replay.py --question-id hn-case-q01 --json
```

详细讲稿、每幕时间和评委问答见 [`docs/demo_manual.md`](demo_manual.md)。

---

## 6. 演示路线 B：Neo4j 图谱可视化（可选）

### 6.1 版本

- Neo4j **5.26 Community**
- Docker 镜像 `neo4j:5.26-community`，镜像自带 Java，宿主机不需要 JDK
- 如果不用 Docker，改用 Neo4j Desktop 或 5.26 tarball；tarball 需要 **JDK 17**

### 6.2 Docker 启动

```bash
cd deploy/neo4j
cp .env.example .env
```

编辑 `.env`，把 `change-me-please` 改成自己的密码。`.env` 已被 gitignore，不要提交。

```bash
docker compose up -d
docker compose ps
docker compose logs -f neo4j
```

看到 `Started` 后 `Ctrl+C` 退出日志。浏览器打开：

```text
http://localhost:7474
```

连接信息：

```text
Connect URL: bolt://localhost:7687
Username:    neo4j
Password:    .env 中的 NEO4J_PASSWORD
Database:    neo4j
```

### 6.3 导入案件图

```bash
cd deploy/neo4j

docker cp ../../data/cases/v1/graph/neo4j.cypher \
  legal-rag-neo4j:/var/lib/neo4j/import/

docker exec legal-rag-neo4j cypher-shell \
  -u neo4j -p '你的密码' \
  -f /var/lib/neo4j/import/neo4j.cypher
```

校验：

```cypher
MATCH (n) RETURN labels(n)[0] AS 标签, count(*) AS 数量 ORDER BY 数量 DESC;
MATCH ()-[r]->() RETURN type(r) AS 关系, count(*) AS 数量 ORDER BY 数量 DESC;
```

案件图预期：

```text
Case 11
Article 6
PenaltyType 5
LandType 3
Factor 3
Behavior 2

总节点：30
总关系：180
```

### 6.4 常用展示查询

整体图：

```cypher
MATCH p=(c:Case)-[*1..1]-(n)
RETURN p
LIMIT 100;
```

单个案例：

```cypher
MATCH p=(c:Case {case_id:'hn-yongzhou-2025-5'})-[*1..2]-(n)
RETURN p;
```

行为 → 法条 → 处罚主链：

```cypher
MATCH p1=(c:Case)-[:ALLEGED_BEHAVIOR]->(:Behavior)
MATCH p2=(c)-[:CITES_BASIS]->(:Article)-[:PRESCRIBES]->(:PenaltyType)
RETURN p1, p2
LIMIT 60;
```

被引用最多的法条：

```cypher
MATCH (c:Case)-[:CITES_BASIS]->(a:Article)
RETURN a.label AS 法条, count(DISTINCT c) AS 案件数
ORDER BY 案件数 DESC;
```

行为分布：

```cypher
MATCH (c:Case)-[:ALLEGED_BEHAVIOR]->(b:Behavior)
RETURN b.label AS 行为, count(c) AS 案件数
ORDER BY 案件数 DESC;
```

在结果面板切到 **Graph** 视图；点击节点查看属性；节点标题建议设为 `label`；加 `LIMIT` 避免“毛线球”。

### 6.5 v2 法条图（可选，只报规模）

```bash
docker cp ../../data/v2/graph/neo4j_import.cypher \
  legal-rag-neo4j:/var/lib/neo4j/import/

docker exec legal-rag-neo4j cypher-shell \
  -u neo4j -p '你的密码' \
  -f /var/lib/neo4j/import/neo4j_import.cypher
```

预期 707 节点 / 4,327 关系。v1 法条图 4,106 节点 / 25,648 关系，不建议现场导入，只报数字即可。

### 6.6 不用 Docker 的替代方案

- **Neo4j Desktop**：新建 5.x DBMS，启动后打开 Browser，用 Terminal 里的 `cypher-shell -f` 导入；
- **Linux tarball**：安装 JDK 17，解压 Neo4j 5.26 Community，首次启动前执行 `neo4j-admin dbms set-initial-password`，再用 `cypher-shell -f` 导入。

---

## 7. 正式结果口径

`results/case-main-v1/run_meta.json` 关键字段：

| 字段 | 值 |
|---|---|
| `run_id` | `case-main-v1` |
| `mock` | `false` |
| `groups` | G0、G1、G2、G2-case、G2-graph |
| `repeats` | 1 |
| `questions_count` | 17 |
| 生成模型 | `Qwen/Qwen2.5-7B-Instruct`（AWQ int4） |
| 生成服务 | vLLM |
| 嵌入模型 | `BAAI/bge-m3`，1024 维 |
| `temperature` / `top_p` / `seed` / `max_tokens` | 0.1 / 0.9 / 42 / 1024 |
| 运行时间 | 2026-11-03 18:24–18:44（+08:00） |
| 运行时提交 | `980da77569b7` |

说明：

- 当前 GitHub 基线 `a3352a0` 只增加演示文档和结果，没有改实验代码；
- `results/dev-server-v1/` 和 `results/repro-server-1/` 只用于联调/复现验证，**不能当作正式结论**；
- 这批结果用于演示五步链路与五组消融，不支撑 H1 统计结论；正式评测集（≥60 题）与重复实验由 R3/R1 继续完成。

---

## 8. 常见问题

### 8.1 `python` 找不到

用 `python3`；Windows 上通常是 `python`。

### 8.2 中文乱码或 `UnicodeEncodeError`

```powershell
$env:PYTHONUTF8=1
chcp 65001
```

### 8.3 题号不存在

先跑：

```bash
python3 scripts/demo_replay.py --list
```

题号必须与列表完全一致，例如 `hn-case-q01`。

### 8.4 找不到结果文件

检查：

```bash
ls results/case-main-v1/
```

应包含 `G0_r1.jsonl`、`G1_r1.jsonl`、`G2_r1.jsonl`、`G2-case_r1.jsonl`、`G2-graph_r1.jsonl`、`run_meta.json`。如果使用 `--run-dir`，路径要指到包含这些文件的目录。

### 8.5 Neo4j 连不上

- 确认容器在运行：`docker compose ps`
- 确认端口 7474 / 7687 没被占用
- 确认用户名 `neo4j`、密码与 `.env` 一致
- 如果改过 compose 端口映射，Browser 里的地址也要相应改

### 8.6 Neo4j 报 Java 版本错误

Docker 镜像不需要宿主机 JDK。只有 tarball / 嵌入式方式才需要 **JDK 17**；Neo4j 5.x 不支持 JDK 11。

### 8.7 clone 私有仓库失败

CPU 机器需要自己的 GitHub SSH key，或者使用 HTTPS + PAT。GPU 服务器上的 Deploy key 是仓库级密钥，不要复制到其他机器。

---

## 9. 交接验收清单

- [ ] `git clone` 成功，`git log -1` 能看到 `a3352a0`
- [ ] `python3 scripts/demo_replay.py --list` 输出 17 题
- [ ] `--question-id hn-case-q01 --group G2` 能看到五步答案
- [ ] `--question-id hn-case-q01 --compare` 能看到五组对比
- [ ] 确认正式结果目录是 `results/case-main-v1/`
- [ ] 明确 `dev-server-v1` / `repro-server-1` 不作为正式结论
- [ ] 选做：Neo4j 导入案件图，count 为 30 节点 / 180 关系
- [ ] 选做：提前导出 2–3 张图谱截图，防止现场环境故障
- [ ] 演示前关闭需要联网的依赖，确认离线也能跑

---

## 10. 一页命令速查

```bash
# 1. 拉取
git clone https://github.com/xiaoxiaomanonglucifer/LLM_F.git
cd LLM_F

# 2. 自检
python3 scripts/demo_replay.py --list

# 3. 单题
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G2

# 4. 五组对比
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare

# 5. 边界题
python3 scripts/demo_replay.py --question-id hn-case-q06 --compare
python3 scripts/demo_replay.py --question-id hn-case-q12 --compare

# 6. 可选：Neo4j
cd deploy/neo4j
cp .env.example .env
# 编辑 .env 设置 NEO4J_PASSWORD
docker compose up -d
docker cp ../../data/cases/v1/graph/neo4j.cypher \
  legal-rag-neo4j:/var/lib/neo4j/import/
docker exec legal-rag-neo4j cypher-shell \
  -u neo4j -p '你的密码' \
  -f /var/lib/neo4j/import/neo4j.cypher
```

---

## 附录：相关文档

- 演示逐幕讲稿：[`docs/demo_manual.md`](demo_manual.md)
- R3 评测交接：[`docs/r3_handoff.md`](r3_handoff.md)
- R2 交付说明：[`docs/r2_delivery.md`](r2_delivery.md)
- 接口字段契约：[`docs/data_contract.md`](data_contract.md)
- v2 技术路线与边界：[`docs/route_v2_hunan_illegal_land.md`](route_v2_hunan_illegal_land.md)
- GPU 节点复现手册：[`docs/handoff_gpu_server.md`](handoff_gpu_server.md)
