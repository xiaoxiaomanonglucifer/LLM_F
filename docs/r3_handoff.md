# R2 → R3 交接说明（v1）

> 交接人：R2 曾平 ｜ 日期：2026-11-04 ｜ 范围：v1 全国国土资源法规 RAG
> 目的：R3 拿到本仓库后，不依赖 R2 口头解释，即可开始评测集构建、指标实现与结果复核。
> 本文只覆盖 R2 交付的工程、数据、结果与已知缺口；评测集、LLM-as-judge、
> Kappa 与统计检验由 R3/R1 负责。

## 0. 交接结论

**可以交接的部分：**

- v1 法规语料（75 部 / 4,104 条）、BGE-M3 索引、法条图谱；
- G0/G1/G2 检索-生成流水线与单题问答/实验入口；
- `dev-server-v1`（7 题 × 3 组 × 2 次）非正式对照结果；
- `repro-server-1` 全流程复现留档与图谱导出校验工具；
- 数据接口契约与结果字段说明。

**仍由 R3/R1 完成的部分：**

- `data/eval/v1/questions.jsonl`（≥60 题，30 常规/20 边界/10 对抗）；
- LLM-as-judge、Recall@5、引用准确率、拒答率、Kappa 与人工抽检；
- McNemar / 配对 t / Bonferroni 与最终统计结论；
- v1 正式主实验 `main-v1`（≥60 题 × G0/G1/G2 × repeats≥2）。

**当前不能声称“正式结果已交付”：** 仓库内只有 7 题 dev 集对照，
`dev-server-v1` 与 `repro-server-1` 都不是正式主实验。

## 1. 交付包清单

| 内容 | 路径 | 规模 | sha256 / 说明 |
|---|---|---|---|
| v1 法条 | `data/v1/articles.jsonl` | 75 部 / 4,104 条 | `03d3e2ee…b70a` |
| v1 语料清单 | `data/v1/manifest.json`、`data/v1/corpus_stats.json` | 75 部 / 519,496 字 | 结构告警 0 |
| v1 索引清单 | `data/v1/index/index_manifest.json` | BGE-M3 / 1024 / 4,104 | `a9eef9d9…e362` |
| v1 三元组 | `data/v1/graph/triples.jsonl` | 3,476 条法条 / 630 实体 | `539ff727…` |
| v1 图谱 Cypher | `data/v1/graph/neo4j_import.cypher` | 29,128 条语句 | `6df843e2…` |
| Neo4j 导入校验 | `logs/neo4j_import_v1.json` | 4,106 节点 / 25,648 关系 | 21 项校验 0 失败 |
| dev 对照结果 | `results/dev-server-v1/` | 7 题 × 3 组 × 2 次 = 42 条 | **非正式**，只用于链路联调 |
| 全流程复现 | `results/repro-server-1/`、`logs/reproduce_20261103-184956.{json,log}` | 5/5 步 / 211.3s | 当时 29 项测试；当前 14 项 |
| 接口契约 | `docs/data_contract.md` | — | 字段以该文件为准 |
| 图谱校验 | `scripts/verify_graph_export.py` | — | 对比 triples/Cypher/DB 计数 |
| 一键复现 | `scripts/reproduce.py` | — | 采集→切分→图谱→索引→测试→dev 实验 |

> `results/`、Chroma、BM25 缓存在 `.gitignore` 中。若 R3 不在同一台 GPU 服务器，
> 需要单独拷贝 `results/dev-server-v1/`，或按第 6 节命令重跑；不要假设 `git clone`
> 自带结果目录与索引。

## 2. 版本状态

| 项目 | 状态 | 规模 | 用途 |
|---|---|---|---|
| v1 语料 | 冻结（2026-10-27） | 75 部 / 4,104 条 / 519,496 字 | 法条问答主实验 |
| v1 索引 | 正式（2026-11-03 GPU） | BGE-M3 / 1024 / 4,104 | G1/G2 稠密检索 |
| v1 图谱 | 正式（2026-11-03 修复后） | 3,476 条三元组 / 29,128 条 Cypher | G2 图谱信号与 Neo4j 演示 |
| 正式题库 | **未交付** | `data/eval/v1/questions.jsonl` 待 R3 | 正式主实验 |

规则：

1. `data/v1/` 已冻结，不再就地改写；扩数据请新建版本目录并在 CHANGELOG 登记。
2. 不要复用 `dev-server-v1`、`repro-server-1` 作为正式 `run_id`；正式实验用新 `run_id`。
3. 单题问答用 `pipeline.ask`，实验用 `pipeline.run_experiment`，运行前确认使用 `config/settings.yaml`。

### 2.1 v1 语料哈希变化说明

2026-11-03 的 `reproduce.py` 给 v1 的 `documents/articles` 补齐了 `jurisdiction` 字段，
并重写了 `parsed_at/extracted_at`，因此 `articles_sha256` 从 `6a54c73f…` 变为
`03d3e2ee…`。条数、条文文本、三元组集合均未变化。R3 评测时应使用当前仓库的
`data/v1/index/index_manifest.json` 和 `data/v1/articles.jsonl`，不要引用旧哈希。

## 3. 结果文件怎么用

### 3.1 v1 法规结果

路径：`results/<run_id>/<group>_r<repeat>.jsonl`，组别 `G0/G1/G2`。

关键字段：

- `answer`：生成答案；
- `evidence[]`：`article_id/citation/law_title/text/score/ranks`；
- `graph_context`：仅 G2，拼入提示词的一跳子图谱文本；
- `prompt_hash/prompt_version/decoding_params`：归因控制；
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

### 3.3 正式实验门槛

R3 在结果表里只能使用同时满足以下条件的结果：

- `run_meta.mock == false`；
- 索引 `embedding_model == BAAI/bge-m3`、`embedding_dim == 1024`、`embedding_model_debug == false`；
- 查询嵌入模型与索引 manifest 一致（运行日志无“查询嵌入模型与索引模型不一致”警告）；
- `decoding_params` 为 `temperature=0.1, top_p=0.9, seed=42, max_tokens=1024`；
- `questions_sha256` 与实际题库一致；
- 正式主实验 `repeats >= 2`。

## 4. 已知缺口与处理口径

### 4.1 正式评测集尚未交付

`data/eval/v1/questions.jsonl` 不存在，仓库内只有 `data/eval/dev/questions.jsonl`（7 题）。
`dev-server-v1` 是 7 题 dev 集对照，**不能**用于 H1 正式统计。

### 4.2 语料规模与开题预估不一致

开题报告预计 2 万~5 万文本块，实际按“条”切分为 4,104 条 / 51.9 万字。
原因是检索单位固定为“条”（条内款/项不拆），且目录为 75 部现行有效法规；
未通过拆条或复制文本虚增规模。实验与评测一律以 4,104 条为准，
报告中的规模数字应按实测口径修正。

### 4.3 12 部法规缺失

FLK 精确标题检索未返回现行有效（`sxx=3`）的同名版本，未用失效/近似文本替代。
清单与原因见 `CHANGELOG.md` 和 `data/v1/manifest.json` 的 `missing[]`。
R3 出题时应避开这 12 部法规，或将其作为“知识库未覆盖”的边界题单独统计。

### 4.4 图谱抽取方式

当前 `data/v1/graph/triples.jsonl` 的 `method=rule`，是规则抽取，不是开题所写“大模型抽取”。
`graph.extract --method llm` 已实现但未用于正式产物。R3 在报告中应如实描述，
不要把规则图谱写成 LLM 抽取结果。

### 4.5 其他口径

| 事项 | 口径 |
|---|---|
| 生成模型 | `Qwen/Qwen2.5-7B-Instruct`，共享 GPU 上使用 AWQ int4；量化标记见 `run_meta.generation_service` |
| Neo4j | Cypher 与嵌入式 Neo4j 5.26 导入校验完成；在线 Docker 容器未启动；G2 实验用离线 `GraphIndex` |
| G0 | 不检索、不引用；引用准确率/Recall@5 对 G0 记 N/A 或 0，需在报告中统一 |
| 结果目录 | `results/` 被 gitignore；跨机器交接需单独拷贝或重跑 |
| 提示词版本 | 当前 `prompt_version=1.0`；改提示词需同步升版本并登记 CHANGELOG |

## 5. R3 起步任务（建议顺序）

1. 读 `docs/data_contract.md` 与本文，确认 v1 是当前唯一主线。
2. 用 `data/v1/articles.jsonl` 起草 ≥60 题（30 常规 / 20 边界 / 10 对抗），
   参考答案必须带条文号，落入 `data/eval/v1/questions.jsonl`。
3. 为每题补 `reference_answer`、`reference_citations`。
4. 写 LLM-as-judge 评分细则（0–3，≥2 正确），先人工双评 20% 算 Kappa。
5. 先用 `dev-server-v1` 跑通指标脚本，再申请 GPU 重跑正式 `main-v1`。
6. 把新题库路径、哈希、类别分布写入 CHANGELOG，并通知 R2 复核接口字段。

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
  --cypher data/v1/graph/neo4j_import.cypher \
  --db-counts logs/neo4j_import_v1.json
```

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
$PY -m legal_rag.graph.extract
```

重建会覆盖 `index_manifest.json`；正式实验前确认清单仍是 BGE-M3/1024。

## 7. R3 交接验收清单

- [ ] 能读取 `data/v1/articles.jsonl`，字段与 `data_contract.md` 一致。
- [ ] 能运行 14 项单测，以及 `verify_graph_export.py` 的 21 项校验。
- [ ] 能说明 `dev-server-v1` 与 `repro-server-1` 不是正式结果。
- [ ] 能按 3.2 节把 gold citation 映射到 `article_id`，并处理 G0 的 N/A。
- [ ] 知道正式题库缺失，先交付 `data/eval/v1/questions.jsonl`。
- [ ] 知道 12 部法规缺失与 4,104 条与开题预估的差异。
- [ ] 知道图谱是规则抽取，不是 LLM 抽取。
- [ ] 正式实验使用新 `run_id`，且 `repeats=2` 才能进正式结果表。
- [ ] 新题库版本写入 CHANGELOG，不覆盖 `data/v1/`。

## 8. 变更与联系

- R2 负责：语料、索引、图谱、流水线、结果格式与校验工具。
- R3 负责：题库、参考答案、judge、Kappa、指标脚本。
- 任何数据/接口变更先改 `docs/data_contract.md` 与 `CHANGELOG.md`，再通知对方；
  R3 不要直接改 `data/v1/` 的原始文件。
