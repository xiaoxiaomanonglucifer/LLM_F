# R2 → R3 交接说明（v1）

> 交接人：R2 曾平 ｜ 日期：2026-11-04 ｜ 范围：v1 全国国土资源法规 RAG
> 目的：R3 拿到本仓库后，不依赖 R2 口头解释，即可开始评测集构建、指标实现与结果复核。
> 本文只覆盖 R2 交付的工程、数据、结果与已知缺口；评测集、LLM-as-judge、
> Kappa 与统计检验由 R3/R1 负责。

## 0. 交接结论

**可以交接的部分：**

- v1 法规语料（75 部 / 4,104 条）、BGE-M3 索引、法条图谱；
- G0/G1/G2 检索-生成流水线与单题问答/实验入口；
- `dev-server-v1`（规则图谱）与 `dev-llm-graph`（当前 LLM 图谱）非正式对照结果；
- `repro-server-1` 全流程复现留档与图谱导出校验工具；
- 数据接口契约与结果字段说明。

**仍由 R3/R1 完成的部分：**

- `data/eval/v1/questions.jsonl`（≥60 题，30 常规/20 边界/10 对抗）；
- LLM-as-judge、Recall@5、引用准确率、拒答率、Kappa 与人工抽检；
- 三元组抽取质量抽检与评测报告；
- McNemar / 配对 t / Bonferroni、功效复核与最终统计结论；
- v1 正式主实验 `main-v1`（≥60 题 × G0/G1/G2 × repeats≥2）。

**当前不能声称“正式结果已交付”：** 仓库内只有 7 题 dev 集对照，
`dev-server-v1`、`dev-llm-graph` 与 `repro-server-1` 都不是正式主实验。

## 1. 交付包清单

| 内容 | 路径 | 规模 | sha256 / 说明 |
|---|---|---|---|
| v1 法条 | `data/v1/articles.jsonl` | 75 部 / 4,104 条 | `03d3e2ee…b70a` |
| v1 语料清单 | `data/v1/manifest.json`、`data/v1/corpus_stats.json` | 75 部 / 519,496 字 | 结构告警 0 |
| v1 索引清单 | `data/v1/index/index_manifest.json` | BGE-M3 / 1024 / 4,104 | `a9eef9d9…e362` |
| v1 三元组 | `data/v1/graph/triples.jsonl` | 3,694 条法条 / 4,757 实体（LLM 抽取） | `3b131ede…` |
| 规则版归档 | `data/v1/graph/triples_rule.jsonl` | 3,476 条 / 630 实体 | `539ff727…`，仅对照 |
| v1 图谱 Cypher | `data/v1/graph/neo4j_import.cypher` | 28,453 条语句 | `d6adfc0b…` |
| 图谱结构校验 | `scripts/verify_graph_export.py` | 8,451 节点 / 24,755 关系（预期） | 11 项校验 0 失败 |
| Neo4j 实际导入 | 规则版嵌入式 Neo4j 5.26 实例（历史） | 4,106 节点 / 25,648 关系 | 21 项校验 0 失败；不适用于 LLM 版 |
| dev 对照结果 | `results/dev-server-v1/`、`results/dev-llm-graph/` | 7 题 × 3 组 × 2 次 / 7 题 × 3 组 × 1 次 | **非正式**；后者为当前 LLM 图谱 |
| 全流程复现 | `results/repro-server-1/` | 5/5 步 / 211.3s | 规则图谱；当时 29 项测试，当前 14 项 |
| 接口契约 | `docs/data_contract.md` | — | 字段以该文件为准 |
| 图谱校验 | `scripts/verify_graph_export.py` | — | 对比 triples/Cypher/DB 计数 |
| 一键复现 | `scripts/reproduce.py` | — | 采集→切分→图谱→索引→测试→dev 实验 |

> `results/dev-server-v1/`、`results/dev-llm-graph/` 与 `results/repro-server-1/`
> 已随仓库提交；后续新产生的 `results/<run_id>/` 默认被 `.gitignore` 忽略。
> Chroma、BM25 缓存不入库，跨机器需重建索引。

## 2. 版本状态

| 项目 | 状态 | 规模 | 用途 |
|---|---|---|---|
| v1 语料 | 冻结（2026-10-27） | 75 部 / 4,104 条 / 519,496 字 | 法条问答主实验 |
| v1 索引 | 正式（2026-11-03 GPU） | BGE-M3 / 1024 / 4,104 | G1/G2 稠密检索 |
| v1 图谱 | 正式（2026-11-04 切换 LLM 抽取） | 3,694 条三元组 / 4,757 实体 / 28,453 条 Cypher | G2 图谱信号与 Neo4j 演示 |
| 正式题库 | **未交付** | `data/eval/v1/questions.jsonl` 待 R3 | 正式主实验 |

规则：

1. `data/v1/` 已冻结，不再就地改写；扩数据请新建版本目录并在 CHANGELOG 登记。
2. 不要复用 `dev-server-v1`、`repro-server-1` 作为正式 `run_id`；正式实验用新 `run_id`。
3. 单题问答用 `pipeline.ask`，实验用 `pipeline.run_experiment`，运行前确认使用 `config/settings.yaml`。

### 2.1 v1 语料哈希变化说明

2026-11-03 的 `reproduce.py` 给 v1 的 `documents/articles` 补齐了 `jurisdiction` 字段，
并重写了 `parsed_at/extracted_at`，因此 `articles_sha256` 从 `6a54c73f…` 变为
`03d3e2ee…`。当时条数、条文文本、三元组集合均未变化。R3 评测时应使用当前仓库的
`data/v1/index/index_manifest.json` 和 `data/v1/articles.jsonl`，不要引用旧哈希。

> 2026-11-04 图谱另行从规则版切换为 LLM 版（见 §4.4）；该切换不影响
> `articles.jsonl` 与索引哈希，但会改变 `triples.jsonl`、G2 上下文和结果排序。

### 2.2 组别与检索信号

| 组别 | 检索信号 | 说明 |
|---|---|---|
| G0 | 无 | 不检索、无证据、不引用条文 |
| G1 | BGE-M3 dense + BM25 | RRF 融合，top_k=5、candidate_k=30、rrf_k=60 |
| G2 | G1 + 法条图谱一跳子图 | 图谱来自 `data/v1/graph/triples.jsonl`（LLM 抽取），离线 `GraphIndex` |

> 开题报告把 G1 描述为“向量检索增强”；实现中 G1 已包含 BM25 混合检索，
> G2 才额外加入图谱。报告中应按本表描述，避免把 G1 写成纯向量检索。
> 当前 G2 使用 LLM 图谱；`dev-server-v1`、`repro-server-1` 的 G2 使用规则图谱，
> 不要与当前图谱结果混用。三组必须使用同一生成器、同一解码参数、同一提示词模板，
> 仅检索上下文不同；`prompt_version` 应一致，`prompt_hash` 因上下文不同而不同。

## 3. 结果文件怎么用

### 3.1 v1 法规结果

路径：`results/<run_id>/<group>_r<repeat>.jsonl`，组别 `G0/G1/G2`。

关键字段：

- `answer`：生成答案；
- `evidence[]`：`article_id/citation/law_title/text/score/ranks`；
- `graph_context`：仅 G2，拼入提示词的一跳子图谱文本；
- `prompt_hash/prompt_version/decoding_params`：归因控制；`prompt_version` 三组应一致，
  `prompt_hash` 是完整消息哈希，组间因检索上下文不同而不同，不要用它判断模板是否一致；
  同题同组跨 repeat 的 `prompt_hash` 应一致；
- `usage/latency_sec`：成本；
- `refusal_rule_flag`：规则拒答标记，仅供参考。

### 3.2 指标映射

| 指标 | 用什么字段 | gold 从哪里来 | 注意 |
|---|---|---|---|
| Recall@5 | `evidence[].article_id`、`evidence[].ranks` | 题目的 `reference_citations` | 先把 citation 映射到 `article_id`；G0 无证据，Recall@5 记 N/A |
| 引用准确率 | `answer` 中的引用串、`evidence[].citation` | 同上 | G0 无检索证据，应记 0 或 N/A |
| 答案正确率 | `answer` | 题目的 `reference_answer` 或 R3 标准答案 | LLM-as-judge 0–3，≥2 判正确；人工抽检 20% |
| 拒答率 | `answer`、`refusal_rule_flag` | 对抗题标注 | `refusal_rule_flag` 只是启发式，必须人工复核 |
| 检索命中 | `evidence[].ranks` | `reference_citations` | 可同时报告 Recall@1 / Recall@5 / MRR |

> 指标口径应在评测脚本中预注册：Recall@5 以有 `reference_citations` 的题为分母；
> 答案正确率同时报告 0–3 均分与“≥2 判正确”的二分类准确率；引用准确率按答案中的
> 引用与 gold 精确匹配计算，多引用题需说明 micro/macro；拒答率以对抗题为分母
> （边界题可单列），不能只依赖 `refusal_rule_flag`。

### 3.3 正式实验门槛

R3 在结果表里只能使用同时满足以下条件的结果：

- `run_meta.mock == false`；
- 索引 `embedding_model == BAAI/bge-m3`、`embedding_dim == 1024`、`embedding_model_debug == false`；
- 查询嵌入模型与索引 manifest 一致（运行日志无“查询嵌入模型与索引模型不一致”警告）；
- `decoding_params` 为 `temperature=0.1, top_p=0.9, seed=42, max_tokens=1024`；
- `questions_sha256` 与实际题库一致；
- 正式主实验 `repeats >= 2`，且两次运行使用固定 seed；
- 三组使用同一生成器、同一解码参数、同一提示词模板（`prompt_version` 一致），
  仅检索上下文不同；`run_meta.decoding_params` 与 `generation_service` 必须一致。

### 3.4 假设与统计方案

开题报告的 H1/H0 与边界假设必须在评测报告中逐条对应：

- H1：G1/G2 的答案正确率与引用准确率显著高于 G0；
- H0：无显著差异；接受 H0 时如实报告并分析 RAG 在法规短文本场景的失效条件；
- 边界假设：对知识库范围外与对抗诱导问题，RAG 的拒答率应显著高于 G0。

统计检验按开题报告执行：正确/错误的二分类用配对 McNemar 检验，0–3 评分用配对 t 检验，
α=0.05（双侧），报告效应量；三组两两比较采用 Bonferroni 校正。60 题规模下，
开题给出的功效参考为：不一致对占 40%（24 对）且 80% 有利于 RAG 时功效约 81%，
占 30% 时约 72%；最终以实测不一致对数量复核，R1 将功效计算脚本随实验记录归档。
`repeats=2` 的两次结果需报告一致性（逐题答案/引用/指标），不能只取其中一次。

## 4. 已知缺口与处理口径

### 4.1 正式评测集尚未交付

`data/eval/v1/questions.jsonl` 不存在，仓库内只有 `data/eval/dev/questions.jsonl`（7 题）。
`dev-server-v1`（规则图谱）与 `dev-llm-graph`（当前 LLM 图谱）都是 7 题 dev 对照，
**不能**用于 H1 正式统计。

### 4.2 语料规模与开题预估不一致

开题报告预计 2 万~5 万文本块，实际按“条”切分为 4,104 条 / 51.9 万字。
原因是检索单位固定为“条”（条内款/项不拆），且目录为 75 部现行有效法规；
未通过拆条或复制文本虚增规模。实验与评测一律以 4,104 条为准，
报告中的规模数字应按实测口径修正。

### 4.3 12 部法规缺失

FLK 精确标题检索未返回现行有效（`sxx=3`）的同名版本，未用失效/近似文本替代。
清单与原因见 `CHANGELOG.md` 和 `data/v1/manifest.json` 的 `missing[]`。
R3 出题时应避开这 12 部法规，或将其作为“知识库未覆盖”的边界题单独统计。

### 4.4 图谱抽取方式（已切换为 LLM）

当前正式 `data/v1/graph/triples.jsonl` 为 LLM 抽取（`method=llm`，
`Qwen/Qwen2.5-7B-Instruct`，AWQ int4），与开题报告一致。4,104 条中
3,696 条有效、407 条空、1 条规则兜底、0 错误；写入 3,694 条，覆盖 90.0%。
主体、行为全部通过原文逐字回验；处罚按 16 类规范化，70/801 条规范名不逐字出现
（如“吊销资质证书/营业执照”→“吊销许可证”，“给予处分”→“行政处分”）。

规则版 `data/v1/graph/triples_rule.jsonl` 仅作对照归档。`dev-server-v1` 与
`repro-server-1` 的 G2 使用规则图谱；`dev-llm-graph` 使用当前 LLM 图谱。
Neo4j 侧：当前 Cypher 已通过 11 项结构校验，预期 8,451 节点 / 24,755 关系；
本节点未重新实际导入，历史 4,106 / 25,648 计数属于规则版。

R3 的三元组抽检建议：按法规层级/领域分层抽取不少于 10% 的法条（且不少于 100 条），
逐条核对主体、行为是否在原文中有依据、处罚类型是否可对应；处罚允许规范化，
不要求逐字匹配。抽检结果与 `triples.stats.json` 的 empty/fallback 数量一并报告。

### 4.5 其他口径

| 事项 | 口径 |
|---|---|
| 生成模型 | `Qwen/Qwen2.5-7B-Instruct`，共享 GPU 上使用 AWQ int4；量化标记见 `run_meta.generation_service` |
| Neo4j | 规则版曾用嵌入式 5.26 导入校验；LLM 版当前 11 项结构校验，实际导入待部署机；在线 Docker 容器未启动；G2 实验用离线 `GraphIndex` |
| G0 | 不检索、不引用；引用准确率/Recall@5 对 G0 记 N/A 或 0，需在报告中统一 |
| 结果目录 | `dev-server-v1`、`dev-llm-graph` 与 `repro-server-1` 已入库；新 `run_id` 默认被 gitignore |
| 提示词版本 | 当前 `prompt_version=1.0`；改提示词需同步升版本并登记 CHANGELOG |

## 5. R3 起步任务（建议顺序）

1. 读 `docs/data_contract.md` 与本文，确认 v1 是当前唯一主线。
2. 用 `data/v1/articles.jsonl` 起草 ≥60 题（30 常规 / 20 边界 / 10 对抗），
   参考答案必须带条文号，落入 `data/eval/v1/questions.jsonl`；R1 复核题干与答案严谨性。
3. 为每题补 `reference_answer`、`reference_citations`，并把 citation 映射到
   `article_id`；避开 12 部缺失法规，范围外问题放入对抗题单列。
4. 按开题完成标注：4 名组员全员参与、双人交叉复核，报告 Cohen's Kappa（目标 ≥0.8）；
   另对 LLM-as-judge 人工抽检 20%，报告人工与自动评分的一致性。
5. 完成三元组质量抽检：按 §4.4 的建议抽样，核对主体/行为原文依据与处罚类型；
   结果写入评测报告。
6. 先用 `dev-llm-graph` 跑通指标脚本，再申请 GPU 跑正式 `main-v1`（`repeats=2`）；
   统计按 §3.4 执行，并报告两次运行一致性。
7. 把新题库路径、哈希、类别分布、变更原因/时间/操作人写入 CHANGELOG，
   并通知 R2 复核接口字段。R3 交付物：评测集与标注记录（含 Kappa）、
   评测流水线代码、评测报告（含三元组抽检与统计检验）。

## 6. 常用命令

### 6.1 环境与测试

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

$PY -m unittest discover -s tests          # 当前 14 项
```

> 本机无 GPU 时：把 settings 中 `embedding.device` 改为 `cpu` 可跑 BGE-M3 检索，
> 但生成仍需可用的 vLLM/OpenAI 兼容端点；不要用 `--mock` 结果做正式评测。

### 6.2 图谱导出校验

```bash
$PY scripts/verify_graph_export.py \
  --triples data/v1/graph/triples.jsonl \
  --cypher data/v1/graph/neo4j_import.cypher
```

> 不带 `--db-counts` 时执行 11 项结构校验；要复现 21 项，需要额外提供已导入
> Neo4j 的计数 JSON（`--db-counts`）或 Bolt 连接（`--neo4j-uri`）。

### 6.3 跑 v1 正式题库（需 vLLM 服务）

```bash
export PYTHONPATH=src
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/v1/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id main-v1
```

前置：vLLM 在 `http://127.0.0.1:8000/v1` 提供 `Qwen/Qwen2.5-7B-Instruct`；
索引为 BGE-M3/1024；`--embedding-model` 默认读 settings。

### 6.4 跑通 dev 链路（无正式题库时）

```bash
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl \
  --groups G0,G1,G2 --repeats 1 --run-id dev-check
```

### 6.5 另一台机器重建索引

```bash
export PYTHONPATH=src
$PY -m legal_rag.corpus.collect --min-docs 50
$PY -m legal_rag.corpus.build
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3
$PY -m legal_rag.graph.extract --method llm --workers 4
```

重建会覆盖 `index_manifest.json` 与正式 `triples.jsonl`；正式实验前确认清单仍是
BGE-M3/1024，图谱 `method=llm`。无模型服务时可用 `--method rule` 生成对照，
但不要把它当作正式图谱。

## 7. R3 交接验收清单

- [ ] 能读取 `data/v1/articles.jsonl`，字段与 `data_contract.md` 一致。
- [ ] 能运行 14 项单测，以及 `verify_graph_export.py` 的结构校验
      （默认 11 项；提供 DB 计数时 21 项）。
- [ ] 能说明 `dev-server-v1`、`dev-llm-graph`、`repro-server-1` 都不是正式结果。
- [ ] 能按 3.2 节把 gold citation 映射到 `article_id`，并处理 G0 的 N/A。
- [ ] 知道正式题库缺失，先交付 ≥60 题（30 常规 / 20 边界 / 10 对抗），
      且经 R1 复核、4 人标注、双人交叉复核、Kappa ≥0.8。
- [ ] 知道 judge 为 0–3 分、≥2 判正确，并人工抽检 20% 校准。
- [ ] 知道 12 部法规缺失与 4,104 条与开题预估的差异。
- [ ] 知道图谱是 LLM 抽取；主体/行为逐字回验，处罚为 16 类规范化；
      规则版 `triples_rule.jsonl` 仅归档。
- [ ] 知道正式图谱 Neo4j 实际导入待部署机，当前只有 11 项结构校验。
- [ ] 知道 H1/H0/边界假设与统计方案（McNemar + 配对 t、α=0.05、效应量、
      Bonferroni、功效复核）。
- [ ] 正式实验使用新 `run_id`，`repeats=2`，并报告两次运行一致性。
- [ ] 完成三元组抽检并写入评测报告。
- [ ] 新题库版本写入 CHANGELOG（原因/时间/操作人/哈希/类别分布），不覆盖 `data/v1/`。

## 8. 变更与联系

- R2 负责：语料、索引、图谱、流水线、结果格式与校验工具。
- R3 负责：题库、参考答案、标注与 Kappa、LLM-as-judge、指标脚本、
  三元组抽取质量抽检与评测报告；统计检验由 R1 执行/复核。
- 任何数据/接口变更先改 `docs/data_contract.md` 与 `CHANGELOG.md`，再通知对方；
  R3 不要直接改 `data/v1/` 的原始文件。
