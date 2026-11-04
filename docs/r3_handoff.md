# R2 → R3 交接说明

> 交接人：R2 曾平 ｜ 日期：2026-11-03
> 目的：R3 拿到本仓库后，不依赖 R2 口头解释，即可开始评测集构建、指标实现与结果复核。
> 范围：本文只覆盖 R2 交付的工程、数据、结果与已知缺口；评测集、LLM-as-judge、
> Kappa 与统计检验由 R3/R1 负责。

## 0. 交接结论

**可以交接的部分：**

- v1 全领域法规语料、BGE-M3 索引、法条图谱、G0/G1/G2 流水线；
- v2 湖南非法占地语料、案例层、案件图谱、五步问答与五组消融；
- `case-main-v1`（5 组 × 17 题）正式运行留档与校验工具；
- 数据接口契约、复现脚本、图谱/结果校验脚本。

**仍由 R3/R1 完成的部分：**

- `data/eval/v1/questions.jsonl`（≥60 题，30 常规/20 边界/10 对抗）；
- 若走 v2 主线：把案件题扩到 ≥60，并完成 60 案 gold 切分；
- LLM-as-judge、Recall@5、引用准确率、拒答率、Kappa 与人工抽检；
- McNemar / 配对 t / Bonferroni 与最终统计结论。

**当前不能声称“全部数据已交付”：** 案例只有 11 份试点、案件题只有 17 道，
`case-main-v1` 只有 1 次重复，不足以支撑 H1 的正式统计结论。

## 1. 交付包清单

以下哈希对应 2026-11-03 工作区状态；若文件被后续版本替换，以新 manifest 为准。

| 内容 | 路径 | 规模 | sha256 / 说明 |
|---|---|---|---|
| v1 法条 | `data/v1/articles.jsonl` | 75 部 / 4,104 条 | `03d3e2ee…b70a` |
| v1 语料清单 | `data/v1/manifest.json`、`data/v1/corpus_stats.json` | 75 部 / 519,496 字 | 结构告警 0 |
| v1 索引清单 | `data/v1/index/index_manifest.json` | BGE-M3 / 1024 / 4,104 | `a9eef9d9…e362` |
| v1 图谱 | `data/v1/graph/triples.jsonl`、`neo4j_import.cypher` | 3,476 条法条有图谱 / 29,128 语句 | `logs/neo4j_import_v1.json` |
| v2 法条 | `data/v2/articles.jsonl` | 11 部 / 597 条 / 82,505 字 | `6c52e7ea…e768` |
| v2 索引清单 | `data/v2/index/index_manifest.json` | BGE-M3 / 1024 / 597 | `d052c2ea…6af3` |
| v2 图谱 | `data/v2/graph/triples.jsonl`、`neo4j_import.cypher` | 4,890 语句 | `logs/neo4j_import_v2.json` |
| 案例 | `data/cases/v1/cases.jsonl` | 11 案 | `19e7fb91…aa2c` |
| 案件图谱 | `data/cases/v1/graph/` | 30 节点 / 180 边 | `stats.json` 含逐案质检 |
| 案件题（试点） | `data/cases/v1/questions.jsonl` | 17 题 | `edecb3a7…7d3e` |
| 正式案例结果 | `results/case-main-v1/` | 5 组 × 17 题 = 85 条 | `run_meta.json` `32ec502a…f9c4` |
| v1 dev 对照 | `results/dev-server-v1/` | 7 题 × 3 组 × 2 次 = 42 条 | **非正式**，只用于链路联调 |
| 全流程复现 | `results/repro-server-1/`、`logs/reproduce_20261103-184956.{json,log}` | 5/5 步 / 211.3s | 当时 29 项测试；当前 32 项 |
| 接口契约 | `docs/data_contract.md` | — | 字段以该文件为准 |
| 结果校验 | `scripts/validate_case_results.py` | — | 当前 `case-main-v1` 774 项检查 0 失败 |
| 图谱校验 | `scripts/verify_graph_export.py` | — | v1/v2 各 21 项 0 失败 |

> `results/`、Chroma、BM25 缓存在 `.gitignore` 中。若 R3 不在同一台 GPU 服务器，
> 需要单独拷贝 `results/case-main-v1/`，或按第 6 节命令重跑；不要假设 `git clone`
> 自带结果目录。

## 2. 三条版本线，不要混用

| 版本 | 状态 | 规模 | 用途 |
|---|---|---|---|
| v1 全领域法规 | 冻结（2026-10-27） | 75 部 / 4,104 条 | 原开题主线的法条问答；正式题库由 R3 交付 |
| v2 湖南非法占地 | 当前主线（2026-10-31 试点） | 11 部 / 597 条 | 答辩后收窄的案例驱动路线 |
| `data/cases/v1` 案例 | 试点冻结 | 11 案 / 17 题 | 五步问答与案例层评测的起点 |

规则：

1. `data/v1/` 与 `data/cases/v1/` 不再就地改写；扩数据请新建 `v2` 目录并在 CHANGELOG 登记。
2. `case-main-v1` 是冻结结果，不要复用这个 `run_id`；新实验用新 `run_id`。
3. v1 与 v2 的索引、题库、结果不能混合统计；运行时用 `LEGAL_RAG_SETTINGS` 明确切换。

### 2.1 v1 语料哈希变化说明

2026-11-03 的 `reproduce.py` 给 v1 的 `documents/articles` 补齐了 `jurisdiction` 字段，
并重写了 `parsed_at/extracted_at`，因此 `articles_sha256` 从 `6a54c73f…` 变为
`03d3e2ee…`。条数、条文文本、三元组集合均未变化。R3 评测时应使用当前仓库的
`data/v1/index/index_manifest.json` 和 `data/v1/articles.jsonl`，不要引用旧哈希。

### 2.2 `case-main-v1` 的冻结说明

该运行生成于 2026-11-03 18:24–18:44，早于“图谱同分邻居稳定排序 + Cypher 换行转义”
修复。若 R3 只消费 `results/case-main-v1/` 的已有答案与引用，没有问题；
若 R3 用当前代码重跑同一题库，G2 图谱上下文可能与旧结果有细微差异。
正式重跑请用新 `run_id`（如 `case-r3-v1`），不要声称能逐字复现旧 run。

## 3. 结果文件怎么用

### 3.1 v1 法规结果

路径：`results/<run_id>/<group>_r<repeat>.jsonl`，组别 `G0/G1/G2`。

关键字段：

- `answer`：生成答案；
- `evidence[]`：`article_id/citation/law_title/text/score/ranks`；
- `prompt_hash/prompt_version/decoding_params`：归因控制；
- `usage/latency_sec`：成本；
- `refusal_rule_flag`：规则拒答标记，仅供参考。

### 3.2 v2 案件结果

路径：`results/<run_id>/<group>_r<repeat>.jsonl`，组别 `G0/G1/G2/G2-case/G2-graph`。

关键字段：

- `answer` / `deterministic_answer`：模型答案与五步规则答案；
- `steps.facts/characterization/law_application/discretion/conclusion`：五步中间结果；
- `similar_cases[]`：类案及分数、理由；
- `citations[]`：`article_id/citation/score/ranks/role/source`；
- `citation_strings[]`：引用串，供精确匹配；
- `prompt_hash/prompt_version/decoding_params`：归因控制；
- `confidence`：系统自评，不等于正确率，需 R3 复核。

### 3.3 指标映射

| 指标 | 用什么字段 | gold 从哪里来 | 注意 |
|---|---|---|---|
| Recall@5 | `evidence[].article_id`、`evidence[].ranks` | v1 题 `reference_citations`；v2 题 `expected.required_citations` | 先把 citation 映射到 `article_id`；G0 无证据，Recall@5 记 N/A |
| 引用准确率 | `citations[].citation`、`citation_strings` | 同上 | G0 为空数组，应记 0 或 N/A；裁量基准见 4.1 |
| 答案正确率 | `answer` | 题目的 `reference_answer` 或 R3 标准答案 | LLM-as-judge 0–3，≥2 判正确；人工抽检 20% |
| 拒答率 | `answer`、`refusal_rule_flag` | 对抗题标注 | `refusal_rule_flag` 只是启发式，必须人工复核 |
| 罚款区间 | `steps.discretion.predicted_fine_range`、`partial_fine_range`、`needs_land_type` | `expected.fine_range`、`partial_fine_range` | 缺地类/历史行为可能为 null，不能算系统错误 |
| 处罚类型 | `steps.discretion` / `deterministic_answer` | `expected` 或案卷 | 建议按集合 micro-F1 |
| 类案质量 | `similar_cases[]` | 案卷相似性标注 | 注意 `exclude_case_id` 防泄漏 |
| 版本提示 | `steps.discretion.version_note`、`current_standard_applied` | `expected.version_note_contains` | 历史行为不套现行幅度 |

### 3.4 正式实验门槛

R3 在结果表里只能使用同时满足以下条件的结果：

- `run_meta.mock == false`；
- 索引 `embedding_model == BAAI/bge-m3`、`embedding_dim == 1024`、`embedding_model_debug == false`；
- 查询嵌入模型与索引 manifest 一致；
- `decoding_params` 为 `temperature=0.1, top_p=0.9, seed=42, max_tokens=1024`；
- `questions_sha256` 与实际题库一致；
- 正式主实验 `repeats >= 2`（当前 `case-main-v1` 只有 1 次）。

`scripts/validate_case_results.py` 已改为从题库、案例、图谱 stats、索引 manifest 自动取数，
不再写死 17 题/11 案/597 条，可直接校验 R3 扩题后的新 run：

```bash
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

$PY scripts/validate_case_results.py --run-dir results/case-r3-v1 \
  --questions data/cases/v2/questions.jsonl \
  --cases data/cases/v2/cases.jsonl
```

## 4. 已知缺口与处理口径

### 4.1 裁量基准没有进检索库（最重要）

`湘自资规〔2022〕1号` 的罚款档位目前硬编码在
`src/legal_rag/cases/schema.py` 的 `DISCRETION_BRACKETS`，`data/v2/articles.jsonl`
没有该文件，11 份案例的 `penalty_basis_articles` 也没有引用它。

R3 计算引用准确率时请采用以下口径之一，并在评测报告中写明：

- 把裁量基准视为“外部政策依据”，单独统计其引用是否正确；
- 或先要求 R2 把裁量基准补入 v2 语料，再按 `article_id` 精确匹配；
- **不要**因为该引用不在 `data/v2/articles.jsonl` 就一律判为“编造条文”。

案件数据中的 `policy_citations` 字段保留了政策文件标题，可用于核对。

### 4.2 案例字段缺失

- 4 案缺 `land_use`：`hn-yongzhou-2025-7/9/10/12`。系统应要求补充地类，
  不臆造罚款总额；R3 不应把 `fine_range=null` 直接判为错误。
- 8 案 `project_nature=未知`。涉及公益/非公益档位时，系统按法规幅度给区间，
  R3 应把“性质未知”作为边界条件单独统计。
- 当前 17 题中 6 题是边界题；不要把 17 题当成 17 个独立案件样本。

### 4.3 样本相关性与统计功效

17 题由 11 案改写，同一案件可能对应多题。若 R3 直接把 17 题当独立样本做 McNemar，
会低估方差、夸大显著性。建议：

- v2 主线先把 gold 案例扩到 60 份，再按“一案一题”或“分层抽样”构造 60 题；
- 或在报告中明确使用案件级聚类/分层分析，不把题级独立性写死。

### 4.4 其他口径

| 事项 | 口径 |
|---|---|
| 生成模型 | `Qwen/Qwen2.5-7B-Instruct`，共享 GPU 上使用 AWQ int4；量化标记见 `run_meta.generation_service` |
| 法条图谱抽取 | 当前 `method=rule`，不是开题所写“大模型抽取”；`extract.py --method llm` 尚未用于正式产物 |
| Neo4j | Cypher 与嵌入式 Neo4j 5.26 导入校验完成；在线 Docker 容器未启动；G2 实验用离线 `GraphIndex` |
| G0 | 不检索、不引用、不计算罚款；引用准确率/Recall@5 对 G0 记 N/A 或 0，需在报告中统一 |
| 结果目录 | `results/` 被 gitignore；跨机器交接需单独拷贝或重跑 |
| 提示词版本 | 当前案例 `prompt_version=2.0`；校验脚本仍按 2.0 检查，改提示词需同步升版本 |

## 5. R3 起步任务（建议顺序）

1. 读 `docs/data_contract.md` 与本文，确认 v1/v2 哪条是期末主线。
2. 用 `data/v1/articles.jsonl` 或 `data/cases/v1/cases.jsonl` 起草 60 题；
   常规 30 / 边界 20 / 对抗 10，参考答案必须带条文号。
3. 为每题补 `reference_answer`、`reference_citations`（v1）或 `expected`
   （v2，含 `required_citations/fine_range/scope_status`）。
4. 写 LLM-as-judge 评分细则（0–3，≥2 正确），先人工双评 20% 算 Kappa。
5. 先用 `case-main-v1` / `dev-server-v1` 跑通指标脚本，再申请正式 GPU 重跑。
6. 把新题库路径、哈希、类别分布写入 CHANGELOG，并通知 R2 更新校验器默认值
   （如新增 `data/cases/v2/`）。

## 6. 常用命令

### 6.1 环境与测试

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

$PY -m unittest discover -s tests          # 当前 32 项
```

> 本机无 GPU 时：把 settings 中 `embedding.device` 改为 `cpu` 可跑 BGE-M3 检索，
> 但生成仍需可用的 vLLM/OpenAI 兼容端点；不要用 `--mock` 结果做正式评测。

### 6.2 校验已有正式结果

```bash
$PY scripts/validate_case_results.py --run-dir results/case-main-v1
$PY scripts/verify_graph_export.py \
  --triples data/v1/graph/triples.jsonl \
  --cypher data/v1/graph/neo4j_import.cypher \
  --db-counts logs/neo4j_import_v1.json
$PY scripts/verify_graph_export.py \
  --triples data/v2/graph/triples.jsonl \
  --cypher data/v2/graph/neo4j_import.cypher \
  --db-counts logs/neo4j_import_v2.json
```

### 6.3 跑 v2 新题库（需 vLLM 服务）

> `data/cases/v2/` 是 R3 扩题后的示例路径，当前仓库只有 `data/cases/v1/`。
> 建议复制一份 `config/settings_v2_r3.yaml`，只改其中的 `cases_dir/case_questions_file`，
> 不要直接改 `settings_v2.yaml`，否则 `case-main-v1` 的配置口径会和当前配置不一致。

```bash
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
export PYTHONPATH=src

$PY -m legal_rag.pipeline.run_case_experiment \
  --questions data/cases/v2/questions.jsonl \
  --groups G0,G1,G2,G2-case,G2-graph \
  --repeats 2 --run-id case-r3-v1
```

前置：vLLM 在 `http://127.0.0.1:8000/v1` 提供
`Qwen/Qwen2.5-7B-Instruct`；索引为 BGE-M3/1024；`--embedding-model` 默认读 settings。

### 6.4 跑 v1 正式题库

```bash
unset LEGAL_RAG_SETTINGS
export PYTHONPATH=src

$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/v1/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id main-v1
```

### 6.5 另一台机器重建索引

```bash
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
$PY -m legal_rag.corpus.collect --min-docs 10
$PY -m legal_rag.corpus.build
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3
$PY -m legal_rag.graph.extract
```

v1 重建则取消 `LEGAL_RAG_SETTINGS`，使用 `config/settings.yaml` 与 `config/corpus_catalog.yaml`。
重建会覆盖 `index_manifest.json`；正式实验前确认清单仍是 BGE-M3/1024。

## 7. R3 交接验收清单

- [ ] 能读取 `data/v1/articles.jsonl` 与 `data/cases/v1/cases.jsonl`，字段与 `data_contract.md` 一致。
- [ ] 能运行 32 项单测，以及 `case-main-v1` 的 774 项校验。
- [ ] 能说明 `case-main-v1` 是正式运行但只有 1 次重复，`dev-server-v1` 不是正式结果。
- [ ] 能按 3.3 节把 gold citation 映射到 `article_id`，并处理 G0 的 N/A。
- [ ] 知道裁量基准不在 v2 检索库，采用 4.1 的统计口径。
- [ ] 知道 4 案缺地类、8 案性质未知，不把 null 当系统错误。
- [ ] 知道扩题后要用新 `run_id`，且 `repeats=2` 才能进正式结果表。
- [ ] 新题库/案例集版本写入 CHANGELOG，不覆盖 `data/cases/v1/`。

## 8. 变更与联系

- R2 负责：语料、索引、图谱、案例解析、流水线、结果格式与校验工具。
- R3 负责：题库、参考答案、judge、Kappa、指标脚本。
- 任何数据/接口变更先改 `docs/data_contract.md` 与 `CHANGELOG.md`，再通知对方；
  R3 不要直接改 `data/v1/`、`data/v2/` 或 `data/cases/v1/` 的原始文件。
