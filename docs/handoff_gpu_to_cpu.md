# GPU → CPU 演示交接文档（v1）

> 交接人：R2 曾平 ｜ 适用：CPU 笔记本 / 工作站，不跑模型，只做**Neo4j 图谱可视化**
> 与**结果查看**；实时问答仍在 GPU 节点执行。

---

## 0. 一句话结论

代码、v1 语料、图谱 Cypher 与 dev 结果已经在仓库里。CPU 机器拉下来后：

- **可以**安装 Neo4j 导入 v1 法条图谱，做交互式图谱演示；
- **可以**查看 `results/dev-server-v1/` 的逐题答案与检索证据；
- **不可以**直接跑实时 `ask` / `run_experiment`，因为仓库没有向量索引与模型权重；
- 实时问答在 GPU 节点执行，CPU 只负责展示 Neo4j 与已有结果。

---

## 1. 从 GitHub 拉取

### 1.1 仓库地址

```text
HTTPS: https://github.com/xiaoxiaomanonglucifer/LLM_F.git
SSH:   git@github.com:xiaoxiaomanonglucifer/LLM_F.git
```

```bash
git clone https://github.com/xiaoxiaomanonglucifer/LLM_F.git
cd LLM_F
git log -1 --oneline
git status -sb
```

### 1.2 确认关键文件存在

Linux / macOS：

```bash
test -f data/v1/graph/neo4j_import.cypher && echo OK
test -f data/v1/articles.jsonl && echo OK
test -f results/dev-server-v1/run_meta.json && echo OK
test -f docs/demo_manual.md && echo OK
```

Windows PowerShell：

```powershell
Test-Path data/v1/graph/neo4j_import.cypher
Test-Path data/v1/articles.jsonl
Test-Path results/dev-server-v1/run_meta.json
Test-Path docs/demo_manual.md
```

四项都应为 `True` / 输出 `OK`。

---

## 2. CPU 机器环境要求

### 2.1 查看结果

| 项目 | 要求 |
|---|---|
| Python | 3.9+，只用标准库 |
| 第三方依赖 | 不需要 |
| GPU / 模型权重 / 向量索引 | 不需要 |
| 网络 | 只在 clone 时需要 |

### 2.2 Neo4j 图谱

- Neo4j **5.26 Community**；
- 用 tarball / Desktop 时宿主机需要 **JDK 17**（Neo4j 5.x 不支持 JDK 11）；
- 用 Docker 镜像 `neo4j:5.26-community` 时镜像自带 Java，宿主机不需要 JDK。

### 2.3 Windows 中文输出

```bat
chcp 65001
set PYTHONUTF8=1
```

PowerShell：

```powershell
$env:PYTHONUTF8=1
chcp 65001
```

---

## 3. 仓库里有什么、没有什么

### 3.1 已包含

| 路径 | 内容 |
|---|---|
| `data/v1/` | 全国法规 v1：75 部、4,104 条、519,496 字 |
| `data/v1/graph/neo4j_import.cypher` | v1 法条图：4,106 节点 / 25,648 关系 |
| `data/v1/graph/triples.jsonl` | 3,476 条三元组 |
| `results/dev-server-v1/` | 7 题 × G0/G1/G2 × 2 次，`mock=false`（**dev 集，非正式**） |
| `results/repro-server-1/` | 全流程复现结果（**非正式**） |
| `docs/demo_manual.md` | 演示流程与讲稿 |
| `scripts/verify_graph_export.py` | 图谱导出校验 |

### 3.2 未包含

| 路径 | 原因 |
|---|---|
| `models/` | 模型权重体积大，超过 GitHub 限制 |
| `data/v1/index/chroma/`、`data/v1/index/*.pkl` | 派生索引，可由 `articles.jsonl` 重建 |
| `.env` | 密钥，禁止入库 |
| `大模型开题报告-...docx` | 含姓名/学号，未公开 |

因此 CPU 机器**不能**实时问答；如果确实需要，按 `docs/demo_manual.md` 在 GPU 节点执行。

---

## 4. 演示路线 A：Neo4j 法条图谱（推荐）

### 4.1 启动 Neo4j（Docker）

```bash
cd deploy/neo4j
cp .env.example .env
```

编辑 `.env`，把 `change-me-please` 改成自己的密码。`.env` 已被 gitignore，不要提交。

```bash
docker compose up -d
docker compose ps
```

浏览器打开 `http://localhost:7474`：

```text
Connect URL: bolt://localhost:7687
Username:    neo4j
Password:    .env 中的 NEO4J_PASSWORD
Database:    neo4j
```

### 4.2 导入 v1 图谱（Windows 中文环境重点）

先把 Cypher 文件拷到容器：

```bash
docker cp data/v1/graph/neo4j_import.cypher \
  legal-rag-neo4j:/var/lib/neo4j/import/
```

Windows 中文环境必须先进 PowerShell 设置 UTF-8，否则会导入成乱码：

```powershell
chcp 65001
$env:JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8"
docker exec legal-rag-neo4j cypher-shell `
  -u neo4j -p "你的密码" `
  -f /var/lib/neo4j/import/neo4j_import.cypher
```

Linux / macOS：

```bash
docker exec legal-rag-neo4j cypher-shell \
  -u neo4j -p '你的密码' \
  -f /var/lib/neo4j/import/neo4j_import.cypher
```

如果之前导入过旧数据，先清空再导入：

```cypher
MATCH (n) DETACH DELETE n;
```

### 4.3 校验数量

```cypher
MATCH (n) RETURN labels(n)[0] AS 标签, count(*) AS 数量 ORDER BY 数量 DESC;
MATCH ()-[r]->() RETURN type(r) AS 关系, count(*) AS 数量 ORDER BY 数量 DESC;
```

v1 预期：

```text
Article 3476
Penalty 566
Action 35
Subject 29
总节点：4106
总关系：25648
```

### 4.4 常用展示查询

整体规模（不要直接 `MATCH p=()-->() RETURN p`，会成毛线球）：

```cypher
MATCH (n) RETURN labels(n)[0] AS 标签, count(*) AS 数量 ORDER BY 数量 DESC;
```

单条法条及其一跳邻居：

```cypher
MATCH p=(a:Article {article_id:'law-land-admin#a0044'})-[r]-(n)
RETURN p;
```

土地管理法第 77 条（非法占地处罚）：

```cypher
MATCH p=(a:Article {article_id:'law-land-admin#a0077'})-[r]-(n)
RETURN p;
```

按主体找法条：

```cypher
MATCH p=(a:Article)-[:APPLIES_TO]->(s:Subject {name:'农村村民'})
RETURN p
LIMIT 50;
```

按行为找法条：

```cypher
MATCH p=(a:Article)-[:REGULATES]->(ac:Action {name:'占用'})
RETURN p
LIMIT 50;
```

在结果面板切到 **Graph** 视图；点击节点查看属性；节点标题建议设为 `citation` / `name`；
加 `LIMIT` 避免“毛线球”。

### 4.5 不用 Docker 的替代方案

- **Neo4j Desktop**：新建 5.x DBMS，启动后打开 Browser，用 Terminal 里的
  `cypher-shell -f` 导入；
- **Linux tarball / Windows zip**：安装 JDK 17，解压 Neo4j 5.26 Community，
  首次启动前执行 `neo4j-admin dbms set-initial-password`，再用 `cypher-shell -f` 导入；
- Windows 中文环境同样要先 `chcp 65001` 并设置 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`。

---

## 5. 演示路线 B：查看 dev 结果（无 GPU）

`results/dev-server-v1/` 是 7 题 dev 集对照，`mock=false`，但**不是正式结果**。
逐题查看答案与证据：

```bash
python - <<'PY'
import json
for line in open('results/dev-server-v1/G2_r1.jsonl', encoding='utf-8'):
    r = json.loads(line)
    print('=' * 60)
    print(r['question_id'], r.get('category', ''))
    print(r['answer'][:300].replace('\n', ' '))
    print('证据：', [e['citation'] for e in r.get('evidence', [])])
PY
```

Windows CMD 可用：

```bat
chcp 65001
set PYTHONUTF8=1
python -c "import json;[print(json.loads(l)['question_id'], json.loads(l)['answer'][:120].replace(chr(10),' ')) for l in open('results/dev-server-v1/G2_r1.jsonl',encoding='utf-8')]"
```

也可以直接打开 `results/dev-server-v1/run_meta.json`，核对：

- `mock=false`；
- `questions_count=7`；
- `index_manifest.embedding_model=BAAI/bge-m3`、`embedding_dim=1024`、`embedding_model_debug=false`；
- `decoding_params` 为 0.1 / 0.9 / 42 / 1024。

---

## 6. 实时问答（仅在 GPU 节点）

CPU 机器没有索引与模型，不能直接跑。需要在 GPU 节点执行：

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

# 单题
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2 --show-evidence

# dev 集实验
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl --groups G0,G1,G2 --repeats 1 --run-id demo-dev
```

详细讲稿与评委问答见 [`docs/demo_manual.md`](demo_manual.md)。

---

## 7. 常见问题

### 7.1 `python` 找不到

用 `python3`；Windows 上通常是 `python`。

### 7.2 Neo4j 中文乱码

导入前必须设置：

```powershell
chcp 65001
$env:JAVA_TOOL_OPTIONS="-Dfile.encoding=UTF-8"
```

然后清空旧图、重新导入。乱码一旦写进数据库，改编码不会自动修复。

### 7.3 Neo4j 连不上

- 确认容器在运行：`docker compose ps`
- 确认端口 7474 / 7687 没被占用
- 确认用户名 `neo4j`、密码与 `.env` 一致
- 如果改过 compose 端口映射，Browser 里的地址也要相应改

### 7.4 Neo4j 报 Java 版本错误

Docker 镜像不需要宿主机 JDK。只有 tarball / Desktop / 嵌入式方式才需要 **JDK 17**。

### 7.5 `FileNotFoundError: results/...`

`results/` 默认被 `.gitignore` 排除；确认 clone 后的仓库确实包含
`results/dev-server-v1/`，否则需要从 GPU 节点单独拷贝。

### 7.6 找不到索引 / 模型

CPU 机器本来就没有；这是预期行为。实时问答请回 GPU 节点。

---

## 8. 交接验收清单

- [ ] `git clone` 成功，`data/v1/articles.jsonl` 有 4,104 行。
- [ ] Neo4j 启动成功，`http://localhost:7474` 能登录。
- [ ] v1 Cypher 导入成功，count 为 4,106 节点 / 25,648 关系。
- [ ] 单条法条查询能显示 Article—Subject/Action/Penalty 子图。
- [ ] 中文节点属性无乱码。
- [ ] 能查看 `results/dev-server-v1/G2_r1.jsonl` 的答案与证据。
- [ ] 明确 dev 结果不是正式结论，正式题库与 `main-v1` 仍待 R3/R1。

---

## 附录：相关文档

- 演示逐幕讲稿：[`docs/demo_manual.md`](demo_manual.md)
- R3 评测交接：[`docs/r3_handoff.md`](r3_handoff.md)
- R2 交付说明：[`docs/r2_delivery.md`](r2_delivery.md)
- 接口字段契约：[`docs/data_contract.md`](data_contract.md)
- GPU 节点复现手册：[`docs/handoff_gpu_server.md`](handoff_gpu_server.md)
