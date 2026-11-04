# R2（工程与数据）交付说明（v1）

对应开题报告第九组 R2 职责。本文说明**已交付什么、证据在哪、还差什么、如何在 GPU 节点收尾**，
供组长、R1（实验）与 R3（评测）核对。

> **当前主线**：v1 全国国土资源法规 RAG（75 部 / 4,104 条）。
> 2026-11-03 已在 GPU 节点用 BGE-M3 重建正式索引，并完成 7 题 dev 集对照；
> 2026-11-04 正式图谱切换为 `Qwen/Qwen2.5-7B-Instruct` 抽取（覆盖 90.0%），
> 规则版归档为 `triples_rule.jsonl`。
> v1 正式题库 `data/eval/v1/questions.jsonl`（≥60 题）仍未交付，正式主实验待 R3/R1。
> R3 请先读 `docs/r3_handoff.md`。

## 一、交付物对照

| # | 开题报告 R2 交付物 | 状态 | 证据 / 入口 |
|---|---|---|---|
| 1 | 法规语料采集与版本化 | 完成 | `config/corpus_catalog.yaml`、`data/v1/manifest.json`、`data/v1/raw/`、`data/v1/meta/`、`CHANGELOG.md` |
| 2 | 按条切分语料 | 完成 | `src/legal_rag/corpus/article_parser.py`、`data/v1/articles.jsonl`（4,104 条） |
| 3 | BGE-M3 向量化 + Chroma 构建 | 完成（2026-11-03 GPU 节点） | 4,104 条，BGE-M3 1024 维；`data/v1/index/index_manifest.json` |
| 4 | Neo4j 图谱构建 | 完成（LLM 抽取 + Cypher + 结构校验；实际导入待部署机） | 3,694 条三元组；28,453 条语句；11 项结构校验 0 失败；规则版归档 |
| 5 | 检索-生成流水线 | 完成并联调 | `src/legal_rag/retrieval/`、`pipeline/`、`generation/`；G0/G1/G2 |
| 6 | 推理服务部署 | 完成（vLLM + AWQ int4） | OpenAI 兼容客户端，`base_url=http://127.0.0.1:8000/v1`，`Qwen/Qwen2.5-7B-Instruct` |
| 7 | 可复现运行脚本 | 完成 | `scripts/reproduce.py`；GPU 节点结果 `results/repro-server-1/` |
| 8 | Git 提交记录 | 完成 | 具体提交号见 `git log` |
| 9 | 全流程重跑记录 | 完成（全流程为规则图谱；当前 LLM 图谱有 dev 冒烟） | `repro-server-1`（5/5 步，211.3s）、`dev-llm-graph` |
| 10 | 语料变更登记 | 完成 | `CHANGELOG.md`（含 12 部缺失清单与哈希变化说明） |

## 二、关键数字（均为实测，可直接引用）

| 指标 | 数值 |
|---|---|
| 法规目录 / 成功采集 / 缺失 / 错误 | 87 / 75 / 12 / 0 |
| 可索引法规 | 75 部（法律 29、行政法规 29、地方性法规 17） |
| 按条文本块 | 4,104 条 |
| 语料正文规模 | 519,496 字（约 51.9 万字） |
| 条均 / 最短 / 最长 | 126.6 / 16 / 1,131 字 |
| 结构告警 | 0（条号单调、无重复、首条为第 1 条、无空正文） |
| 图谱覆盖 | 3,694 条法条（90.0%，LLM 抽取）；类型化实体 4,757 个（主体 1,409 + 行为 3,281 + 处罚 67） |
| Neo4j Cypher | 28,453 条语句（4 约束 + 28,449 数据） |
| Neo4j 预期规模 | 8,451 节点 / 24,755 关系；11 项结构校验 0 失败；实际导入待部署机 |
| 规则版归档 | 3,476 条（84.7%）/ 630 实体；`triples_rule.jsonl`，仅作历史对照 |
| 单元测试 | 14 项通过 |
| 本地一键复现 | 5 步全部成功，14.2s（hashing + mock） |
| v1 正式索引 | BGE-M3 1024 维，4,104 条，built_at 2026-11-03T18:51:02+08:00 |
| v1 dev 对照 | `dev-server-v1`：7 题 × 3 组 × 2 次 = 42 条（规则图谱，**非正式**） |
| 当前图谱 dev 冒烟 | `dev-llm-graph`：7 题 × 3 组 × 1 次；G2 7/7 注入图谱上下文（**非正式**） |
| GPU 全流程复现 | `repro-server-1`：5/5 步成功，211.3s（BGE-M3，规则图谱，非 mock） |

> 与开题报告“2 万~5 万文本块”的差异已在 `CHANGELOG.md` 说明：检索单位固定为“条”，
> 目录仅 75 部现行有效法规，实际 4,104 条；未通过拆条或复制文本虚增规模。

## 三、本地已完成的验证

```bash
export PYTHONPATH=src
PY="<你的 Python 解释器>"

# 单元测试（14 项）
$PY -m unittest discover -s tests -v

# 一键复现（调试嵌入器 + 模拟生成器；--mock 时图谱默认用规则版）
# 会重建 data/v1/graph/triples.jsonl 与索引，建议在仓库副本执行
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1

# 正式图谱：LLM 抽取（需 vLLM/OpenAI 兼容端点）
$PY -m legal_rag.graph.extract --method llm --workers 4

# 无模型环境的规则对照（只写归档文件，不覆盖正式 triples.jsonl）
$PY -m legal_rag.graph.extract --method rule --out data/v1/graph/triples_rule.jsonl

# 图谱导出结构校验（无需 Neo4j 服务）
$PY scripts/verify_graph_export.py \
  --triples data/v1/graph/triples.jsonl \
  --cypher data/v1/graph/neo4j_import.cypher

# 单条问答（需模型服务；无服务时加 --mock 只验证链路）
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2
```

已验证内容：

- 采集端可断点续跑，WAF 返回非 JSON 时自动冷却重试；docx 校验 ZIP 魔数。
- 按条解析正确跳过目录、保留条内款/项；章/节/条号元数据齐全。
- 检索：口语化问题“村里盖房子占了农用地要办什么手续”的 G1 前五包含
  《中华人民共和国土地管理法》第六十二条；G2 在当前 LLM 图谱下首位为
  《云南省土地管理条例》第五十五条，图谱信号会改变排序。单题名次不作为结论，
  G2 增益由 R3 在 v1 题库上评估。
- G0 无证据、G1 五条证据、G2 额外注入图谱一跳子图；`dev-llm-graph` 的
  7 题 G2 上下文为 314~539 字符，7/7 均有图谱上下文；结果字段与
  `docs/data_contract.md` 一致。
- 0.5B 模型答案方向正确，但未稳定输出“《法规名》第X条”格式；
  引用准确率必须用正式 Qwen2.5-7B-Instruct 评测，不能以 0.5B 结果代替。

## 四、GPU 节点执行记录（2026-11-03）

1. **正式索引**：v1 用 `BAAI/bge-m3` 重建，1024 维、debug=false、4,104 条
   （18:51:02，由复现脚本重建）。清单 `articles_sha256=03d3e2ee…`。

2. **生成服务**：vLLM 0.6.3.post1 加载 `Qwen/Qwen2.5-7B-Instruct` 的 AWQ int4 权重，
   OpenAI 兼容端点 `http://127.0.0.1:8000/v1`；共享 GPU 显存不足，故未用 bf16 原权重。
   启动参数与量化标记已写入 `config/settings.yaml` 与 `run_meta.generation_service`。

3. **v1 dev 对照（规则图谱）**：正式题库 `data/eval/v1/questions.jsonl` 未交付（R3 阻塞），
   按 handoff 改用 dev 集 7 题 × G0/G1/G2 × repeats=2，运行号 `dev-server-v1`；
   结果标注 dev，不进入正式结果表。G0 证据 0 条，G1/G2 各 5 条；答案含规范引用 6/7。
   该运行的 G2 使用规则图谱，不能与当前 LLM 图谱结果直接比较。

4. **全流程复现与归档（规则图谱）**：

   ```bash
   $PY scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3 --run-id repro-server-1
   ```

   5/5 步成功（当时 29 项单测；当前 14 项），211.3s；结果保留在
   `results/repro-server-1/`，运行日志不随仓库分发。该记录对应 2026-11-03
   的规则图谱，保留为历史全流程证据。

5. **LLM 图谱切换（2026-11-04）**：

   正式 `triples.jsonl` 改为 `Qwen/Qwen2.5-7B-Instruct` 抽取：
   4,104 条中 3,696 条有效、407 条空、1 条规则兜底、0 错误，正式记录 3,694 条
   （覆盖 90.0%）。主体/行为全部通过原文逐字回验；处罚按 16 类规范化。
   Cypher 28,453 条语句，`verify_graph_export.py` 11 项结构校验 0 失败。
   预期 8,451 节点 / 24,755 关系。规则版归档为 `triples_rule.jsonl`。

6. **当前图谱 dev 冒烟（`dev-llm-graph`）**：

   ```bash
   $PY -m legal_rag.pipeline.run_experiment \
     --questions data/eval/dev/questions.jsonl \
     --groups G0,G1,G2 --repeats 1 --run-id dev-llm-graph
   ```

   7 题 × 3 组 × 1 次；G2 7/7 注入图谱上下文，答案含规范引用 7/7；
   仅用于确认 LLM 图谱链路，不作为正式结果。

7. **规则图谱 Neo4j 导入校验（历史）**：2026-11-03 的规则版 Cypher
   （29,128 条语句）曾用 Neo4j 5.26.0 嵌入式实例实际导入：
   4,106 节点 / 25,648 关系；21 项校验全部通过。该计数仅属于规则版，
   不适用于当前 LLM 图谱；部署机重新导入 `neo4j_import.cypher` 后，
   可用 `--neo4j-uri` 或 `--db-counts` 复跑 21 项校验。
   Docker 在线服务因当前节点无 `docker` 组权限未启动；演示环境仍按
   `deploy/neo4j` 的 compose 启动，密码只从 `NEO4J_PASSWORD` 读取。

## 五、风险与边界

- **规模**：4,104 条低于开题预估，属于真实测量结果；若需扩大，优先补充部门规章与
  地方性法规到 `config/corpus_catalog.yaml`，切分与索引代码无需改动。
- **12 部缺失法规**：FLK 无同名现行有效版本（`sxx=3`），未用近似标题或失效文本替代；
  清单与原因见 `CHANGELOG.md` 和 `data/v1/manifest.json`。
- **索引口径**：GPU 节点 v1 为 BGE-M3 1024 维正式索引；hashing 索引只用于本机联调，
  不得与正式结果混用。
- **推理量化**：正式实验使用 AWQ int4 权重（共享 GPU 显存限制），服务名仍为
  `Qwen/Qwen2.5-7B-Instruct`；量化标记见 `run_meta.generation_service`。
- **v1 正式题库缺失**：`data/eval/v1/questions.jsonl` 未交付，`dev-server-v1` 仅为 dev 链路对照，
  不能作为 v1 正式结果。
- **Chroma 路径**：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\09e06fb173`；换机器重建即可，清单记录了实际路径。
- **Neo4j 在线服务未启动**：图谱 Cypher 已用嵌入式 Neo4j 5.26 实际导入并校验计数；
  当前 GPU 节点没有 `docker` 组权限，未启动 `deploy/neo4j` 的在线容器。G2 实验使用
  离线 GraphIndex，不依赖 Neo4j，因此不影响实验复现；演示时再启动容器即可。
- **图谱排序口径**：2026-11-03 收尾时把 `GraphIndex` 的同分邻居改为按 `article_id`
  稳定排序，并修复 Cypher 字符串换行转义；正式 v1 `main-v1` 应使用修复后的代码。
- **图谱抽取方式**：正式图谱为 LLM 抽取（`method=llm`，Qwen2.5-7B-Instruct），
  与开题报告一致；规则版仍保留为 `triples_rule.jsonl` 对照。
  LLM 抽取的主体/行为逐字回验通过；处罚字段按 16 类规范化，因此部分处罚名
  （如“吊销许可证”“行政处分”）不要求原文逐字出现。407 条法条被判定为空
  （多为立法目的、定义、原则性条款），1 条规则兜底，详见 `triples.stats.json`。
- **旧结果与图谱版本**：`dev-server-v1`、`repro-server-1` 的 G2 基于规则图谱；
  当前图谱的链路证据是 `dev-llm-graph`。正式 `main-v1` 必须使用当前
  `triples.jsonl` 重新运行，不能直接复用旧 G2 结果。
- **语料来源**：v1 仅使用国家法律法规数据库（FLK）；开题报告提到的
  自然资源部政策文本未纳入，报告中应按实际语料说明。
- **一键复现的覆盖行为**：`scripts/reproduce.py` 会重建 `data/v1/graph/triples.jsonl`
  与索引；`--mock` 默认用规则图谱，正式复现默认用 LLM 图谱。建议在仓库副本或
  临时分支执行，避免覆盖交付快照。

## 六、与 R1 / R3 的接口

> R3 的完整交接包、结果字段用法、指标口径与已知缺口见 `docs/r3_handoff.md`。

- R3 提供正式题库 `data/eval/v1/questions.jsonl`（字段 `id/category/question`）；
  R1 用 `run_experiment.py` 产出 `results/<run_id>/<group>_r<repeat>.jsonl` 与 `run_meta.json`。
- 每条结果包含 `answer`、`evidence[].citation/article_id/score/ranks/graph`、
  `graph_context`、`prompt_hash`、`usage`、`latency`；评测脚本按 `article_id`/citation
  计算 Recall@5 与引用准确率。
- 正式实验前置校验：`run_meta.json.index_manifest.embedding_model` 必须为 BGE-M3 且
  `mock=false`；否则结果只能标记为流程验证。
- 图谱交付校验：`scripts/verify_graph_export.py` 可对比 `triples.jsonl` 与 Cypher；
  当前 LLM 图谱已完成 11 项结构校验。部署机导入新 Cypher 后，传 `--neo4j-uri`
  或 `--db-counts` 可复跑 21 项计数校验。
- 字段契约详见 `docs/data_contract.md`；变更接口须同步更新该文件与 `CHANGELOG.md`。
