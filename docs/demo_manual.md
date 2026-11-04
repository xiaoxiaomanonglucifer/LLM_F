# 演示操作手册（v1 法规 RAG）

> 维护人：R2 曾平 ｜ 适用：第 9 组课程项目答辩 / 课堂演示
> 演示主线：**v1 全国国土资源法规问答（75 部 / 4,104 条）**。
> 实时问答在 GPU 节点；CPU 机器只负责 Neo4j 图谱可视化与结果查看。

## 0. 先记住四句话

1. **实时问答需要 GPU**：vLLM + BGE-M3 索引；推荐在 GPU 节点现场执行。
2. **CPU 也能演示图谱**：Neo4j 导入 `data/v1/graph/neo4j_import.cypher`，
   4,106 节点 / 25,648 关系，不需要 GPU。
3. **G0/G1/G2 是同一模型、同一解码参数，只改检索信号**，这是实验可信度的核心。
4. **仓库内只有 dev 结果**：`dev-server-v1` 是 7 题联调，不是正式结论；
   正式评测集（≥60 题）由 R3 交付。

---

## 1. 演示前准备（5 分钟）

### 1.1 GPU 节点

| 项目 | 要求 |
|---|---|
| Python | 3.11，`/data_disk/tjh/conda_envs/LLM_F/bin/python` |
| 索引 | `data/v1/index/`，BGE-M3 / 1024 / 4,104 |
| 生成服务 | vLLM，`http://127.0.0.1:8000/v1`，模型 `Qwen/Qwen2.5-7B-Instruct` |
| 终端 | 字号 16–18，UTF-8 |

检查服务：

```bash
curl -s http://127.0.0.1:8000/v1/models
```

返回的 `id` 必须是 `Qwen/Qwen2.5-7B-Instruct`。

### 1.2 CPU 机器（Neo4j）

| 项目 | 要求 |
|---|---|
| Neo4j | 5.26 Community |
| JDK | tarball / Desktop 需要 JDK 17；Docker 镜像自带 |
| 文件 | `data/v1/graph/neo4j_import.cypher` |
| 浏览器 | `http://localhost:7474` |

导入步骤见 [`docs/handoff_gpu_to_cpu.md`](handoff_gpu_to_cpu.md) 第 4 节。

---

## 2. 推荐演示流程（10 分钟）

| 时间 | 场景 | 目的 |
|---|---|---|
| 0:00–1:00 | 项目与数据规模 | 75 部 / 4,104 条 / 51.9 万字 |
| 1:00–4:00 | G2 单题完整链路 | 答案 + 5 条证据 + 图谱上下文 |
| 4:00–6:00 | G0/G1/G2 对比 | 展示检索信号的作用 |
| 6:00–8:00 | Neo4j 图谱 | Article—Subject/Action/Penalty 一跳子图 |
| 8:00–10:00 | 结果与限制 | dev 结果、正式题库缺口、规模差异 |

### 2.1 第 1 幕：项目与数据（1 分钟）

> 这是第 9 组的法规 RAG 系统，覆盖全国国土资源领域 75 部现行有效法规、4,104 条、
> 约 51.9 万字；其中法律 29、行政法规 29、地方性法规 17。
> 图谱覆盖 3,476 条法条，Neo4j 导入后是 4,106 个节点、25,648 条关系。
> 索引使用 BGE-M3 1024 维，检索是稠密 + BM25 + 图谱，生成用 Qwen2.5-7B-Instruct。

如果评委问“为什么只有 4,104 条”，直接说明：检索单位是“条”，不是任意切块；
开题预估 2 万–5 万是文本块估计，实测按条只有 4,104 条，没有拆条或复制文本虚增。

### 2.2 第 2 幕：G2 单题完整链路（3 分钟）

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

$PY -m legal_rag.pipeline.ask \
  "村里盖房子占了农用地要办什么手续" \
  --group G2 --show-evidence
```

按屏幕顺序讲：

1. **答案**：先看结论，不要逐字念全文。
2. **检索证据**：5 条法条，带 `rrf` 分数和各信号名次；例如此题首位应命中
   《中华人民共和国土地管理法》第六十二条。
3. **图谱上下文**：G2 额外注入的一跳子图，列出主体、行为、处罚与关联法条。
4. **拒答标记与提示词哈希**：说明结果可追溯；这只是规则标记，不等于正确率。

一句话总结：

> 它不是只给一段答案，而是把“用了哪 5 条法条、每条排第几、图谱补了什么”都摊开，
> 可以逐条核对。

### 2.3 第 3 幕：G0/G1/G2 对比（2 分钟）

同一问题跑三组：

```bash
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G0
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G1 --show-evidence
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2 --show-evidence
```

预期差异：

| 组别 | 检索信号 | 证据 | 图谱上下文 |
|---|---|---|---|
| G0 | 无 | 0 条 | 无 |
| G1 | 稠密 + BM25 | 5 条 | 无 |
| G2 | 稠密 + BM25 + 图谱 | 5 条 | 有 |

讲法：

> 三组用同一个模型、同一套提示词、同一组解码参数，唯一变量是检索信号。
> G0 没有证据，只能凭模型自身知识回答；G1 给法条；G2 再加图谱。
> 比较的是“是否提供可核对依据”，不是模型记忆。

### 2.4 第 4 幕：Neo4j 图谱（2 分钟）

在 CPU 机器 Browser 中执行：

```cypher
MATCH (n) RETURN labels(n)[0] AS 标签, count(*) AS 数量 ORDER BY 数量 DESC;
```

预期 `Article 3476 / Penalty 566 / Action 35 / Subject 29`。

单条法条子图：

```cypher
MATCH p=(a:Article {article_id:'law-land-admin#a0044'})-[r]-(n)
RETURN p;
```

讲法：

> 每个法条节点连到它适用的主体、规制的行为和规定的处罚；G2 的图谱信号就是
> 从命中的法条出发做一跳扩展，把共享实体 ≥2 的邻居补进上下文。
> Neo4j 只是可视化副本，实验时用的是离线 `GraphIndex`，不依赖 Neo4j 在线服务。

### 2.5 第 5 幕：结果与限制（2 分钟）

查看 dev 结果元数据：

```bash
cat results/dev-server-v1/run_meta.json
```

指出：

- `mock=false`，BGE-M3 / 1024 / 4,104；
- 7 题 × 3 组 × 2 次 = 42 条；
- 这是 **dev 集**，不是正式主实验；
- 正式题库 `data/eval/v1/questions.jsonl`（≥60 题）由 R3 交付，`main-v1` 待跑。

主动说明：

> 当前能证明的是工程链路、分组隔离、结果字段与可复现性；
> 不能拿 7 题 dev 结果做 H1 统计结论。正式结论需要 R3 题库 + repeats=2。

---

## 3. 命令速查

所有命令都在仓库根目录执行。

```bash
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

# 单题（默认 G2）
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续"

# 指定组别 + 显示证据正文
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G1 --show-evidence

# 无模型时只验证链路（确定性 mock，不得作为结果）
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2 --mock

# dev 集实验
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl \
  --groups G0,G1,G2 --repeats 1 --run-id demo-dev

# 测试
$PY -m unittest discover -s tests -v
```

---

## 4. 可选：重新跑 dev 实验（评委问“结果怎么来的”）

约 42 次生成调用（7 题 × 3 组 × 2 次），几分钟；必须确认 vLLM 与 BGE-M3 索引就绪：

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id demo-dev-$(date +%Y%m%d-%H%M)
```

注意：仍是 dev 集，只能证明链路和逐题结果，不是正式统计。

---

## 5. 评委可能问什么

| 问题 | 建议回答 |
|---|---|
| 为什么只有 4,104 条？ | 检索单位固定为“条”，75 部现行有效法规按条切分就是 4,104 条；没有拆条或复制文本虚增。开题 2 万–5 万是文本块估计，实测口径应按条报告。 |
| 为什么 G0 有时也能说出法律？ | G0 不提供检索证据，模型可能凭自身知识回答；实验比较的是“是否提供可核对依据”，不是模型记忆。 |
| G2 比 G1 多什么？ | 多图谱一跳子图：从命中法条扩展到共享实体的主体/行为/处罚/关联法条。实验里 G1/G2 的证据都是 5 条，差异在图谱上下文。 |
| 图谱是 LLM 抽取的吗？ | 当前正式产物是规则抽取（`method=rule`），不是 LLM 抽取；`--method llm` 已实现但未用于正式产物。 |
| 结果能直接写进论文吗？ | `dev-server-v1` 只能作为工程链路与 dev 对照，不能作为 H1 正式统计；正式实验需要 R3 题库 + repeats=2。 |
| 有网页/前端吗？ | 当前没有；R2 提供 CLI 与结果字段，前端由 R4 负责。 |
| Neo4j 是实验必需的吗？ | 不是。G2 用离线 `GraphIndex`，Neo4j 只用于演示与查询。 |
| 为什么用 AWQ int4？ | 共享 A100 显存受限；解码参数、提示词、评测口径未变，量化标记已在 `run_meta.generation_service` 留痕。 |

---

## 6. 故障处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: legal_rag` | 没设 `PYTHONPATH` | `export PYTHONPATH=src` |
| `Connection refused` | vLLM 没启动 | `curl http://127.0.0.1:8000/v1/models`；检查服务 |
| 返回模型名不对 | `--served-model-name` 与 settings 不一致 | 启动时用 `Qwen/Qwen2.5-7B-Instruct` |
| 索引缺失 / `SystemExit` | 新机器没有 Chroma/BM25 | 按 `docs/handoff_gpu_server.md` 重建索引 |
| CUDA OOM | 共享卡被占用 | `nvidia-smi` 换卡；不要杀别人的进程 |
| 中文乱码 | 终端不是 UTF-8 | `export PYTHONUTF8=1`；Windows `chcp 65001` |
| Neo4j 中文乱码 | JDK 按 GBK 读了 UTF-8 Cypher | 清空图，`chcp 65001` + `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8` 后重导 |
| Neo4j 毛线球 | 直接 `MATCH p=()-->() RETURN p` | 从 `Article` 出发、加 `LIMIT`，或先看聚合计数 |

---

## 7. 演示前检查清单

- [ ] vLLM `/v1/models` 返回 `Qwen/Qwen2.5-7B-Instruct`。
- [ ] `data/v1/index/index_manifest.json` 为 BGE-M3 / 1024 / 4,104 / debug=false。
- [ ] G2 单题能输出答案、5 条证据、图谱上下文。
- [ ] G0 无证据、G1 有 5 条证据、G2 有图谱上下文。
- [ ] Neo4j 已导入 v1 图谱，count 为 4,106 节点 / 25,648 关系。
- [ ] 中文节点属性无乱码。
- [ ] 已准备离线备份：关键命令输出截图或 `--json` 输出。
- [ ] 记住三条限制：dev 7 题、正式题库未交付、4,104 条 vs 开题预估。
- [ ] 不把 `--mock` 或 dev 结果说成正式结果。
