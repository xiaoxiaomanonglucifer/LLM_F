# R2（工程与数据）交付说明（v1）

对应开题报告第九组 R2 职责。本文说明**已交付什么、证据在哪、还差什么、如何在 GPU 节点收尾**，
供组长、R1（实验）与 R3（评测）核对。

> **当前唯一主线**：v1 全国性 + 云南/昆明国土资源法规 RAG（178 部 / 10,069 条）。
> 2026-11-05 已在 GPU 节点完成 v1 语料、BGE-M3 正式索引与
> `Qwen/Qwen2.5-7B-Instruct` 图谱抽取；原 75 部 / 4,104 条旧快照已删除。
> 正式题库 `data/eval/v1/questions.jsonl`（≥60 题）仍未交付，正式主实验待 R3/R1。
> R3 请先读 `docs/r3_handoff.md`。

## 一、交付物对照

| # | 开题报告 R2 交付物 | 状态 | 证据 / 入口 |
|---|---|---|---|
| 1 | 法规语料采集与版本化 | 完成 | `config/corpus_catalog.yaml`、`data/v1/manifest.json`、`data/v1/raw/`、`data/v1/meta/`、`CHANGELOG.md` |
| 2 | 按条切分语料 | 完成 | `src/legal_rag/corpus/article_parser.py`、`data/v1/articles.jsonl`（10,069 条） |
| 3 | BGE-M3 向量化 + Chroma 构建 | 完成（2026-11-05 GPU 节点） | 10,069 条，BGE-M3 1024 维；`data/v1/index/index_manifest.json` |
| 4 | Neo4j 图谱构建 | 完成（LLM 抽取 + Cypher + 结构校验；实际导入待部署机） | 8,943 条三元组；68,707 条语句；11 项结构校验 0 失败；`data/v1/graph/triples.jsonl`、`neo4j_import.cypher` |
| 5 | 检索-生成流水线 | 完成并联调 | `src/legal_rag/retrieval/`、`pipeline/`、`generation/`；G0/G1/G2 |
| 6 | 推理服务部署 | 完成（vLLM + AWQ int4） | OpenAI 兼容客户端，`base_url=http://127.0.0.1:8000/v1`，`Qwen/Qwen2.5-7B-Instruct` |
| 7 | 可复现运行脚本 | 完成 | `scripts/reproduce.py`；v1 单题、mock 与真实 LLM dev 冒烟均已通过 |
| 8 | Git 提交记录 | 基线已提交；本次 v1 提升改动待提交 | 具体提交号见 `git log`；当前 `data/v1/`、`config/`、文档改动在工作区 |
| 9 | 全流程重跑记录 | 完成（v1 索引重建、图谱校验、dev 冒烟） | 索引 112.0s（10,069 条 BGE-M3）；Cypher 11 项校验；`dev-v1-smoke`（mock）与 `dev-v1-llm`（真实生成）各 7 题 × 3 组 × 1 次 |
| 10 | 语料变更登记 | 完成 | `CHANGELOG.md`（v1 范围、规模、索引与图谱变更） |

## 二、关键数字（均为实测，可直接引用）

| 指标 | 数值 |
|---|---|
| 法规目录 / 成功采集 / 缺失 / 错误 | 178 / 178 / 0 / 0 |
| 可索引法规 | 178 部（法律 52、行政法规 86、地方性法规 40） |
| 适用范围（法条数） | 全国 8,241、云南 764、昆明 1,064 |
| 按条文本块 | 10,069 条 |
| 语料正文规模 | 1,273,548 字（约 127.4 万字） |
| 条均 / 最短 / 最长 | 126.5 / 16 / 2,656 字 |
| 结构告警 | 0（条号单调、无重复、首条为第 1 条、无空正文） |
| 单元测试 | 14 项通过 |
| v1 正式索引 | BGE-M3 1024 维，10,069 条，built_at 2026-11-05T10:47:43+08:00，耗时 112.0s |
| 图谱覆盖 | 8,943 条法条（88.82%，LLM 抽取；规则兜底 3 条）；实体 10,737 个（主体 3,198 + 行为 7,406 + 处罚 133） |
| Neo4j Cypher | 68,707 条语句（4 约束 + 68,703 数据）；预期 19,680 节点 / 59,760 关系 |
| Neo4j 结构校验 | 11 项 0 失败；实际导入待部署机 |
| mock dev 冒烟 | `dev-v1-smoke`：7 题 × 3 组 × 1 次；G2 7/7 注入图谱上下文（**非正式**） |
| LLM dev 冒烟 | `dev-v1-llm`：7 题 × 3 组 × 1 次，mock=false；G2 7/7 注入图谱上下文（**非正式**） |
| LLM 冒烟耗时 | 2026-11-05 11:03:48 → 11:05:02；单次生成平均 2.31~3.70s（G0~G2） |

> 与开题报告“2 万~5 万文本块”的差异已在 `CHANGELOG.md` 说明：v1 限定为
> 全国性相关法规 + 云南省/昆明市地方性法规，实际 10,069 条；未通过拆条或复制文本虚增规模。
> 若继续扩大，应增加其他省市地方性法规或部门规章，而不是改变切分粒度。

## 三、本地已完成的验证

```bash
cd /data_disk/tjh/zp/LLM_FIN
export PYTHONPATH=src
export LEGAL_RAG_SETTINGS=config/settings.yaml
PY="<你的 Python 解释器>"
# GPU 节点示例：PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

# 单元测试（14 项；tests/ 无 __init__.py，从 tests/ 目录运行）
cd tests && PYTHONPATH=../src $PY test_core.py && cd ..

# 一键复现（调试嵌入器 + 模拟生成器；--mock 时图谱默认用规则版）
# 会重建当前 settings 指向的 triples.jsonl 与索引，建议在仓库副本执行
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1

# 正式图谱：LLM 抽取（需 vLLM/OpenAI 兼容端点）
$PY -m legal_rag.graph.extract --method llm --workers 4 \
  --out data/v1/graph/triples.jsonl

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
- 按条解析正确跳过目录、保留条内款/项；章/节/条号元数据齐全；
  178 部法规条文数均与 `documents.jsonl` 一致，无空正文。
- 检索：口语化问题“村里盖房子占了农用地要办什么手续”的 G1 首位命中
  《中华人民共和国城乡规划法》第四十一条，前五包含
  《中华人民共和国土地管理法实施条例》第三十四条（占用农用地应办理农用地转用审批）
  与《云南省土地管理条例》第二十九条；昆明类问题
  “滇池保护范围内新建排污口需要满足什么要求” G1 首位命中
  《云南省滇池保护条例》第二十九条，第七十九条列第 3。单题名次不作为结论，
  G2 增益由 R3 在正式题库上评估。
- dev 冒烟 `dev-v1-smoke`：G0 证据 0 条，其中 6/7 明确声明无条文依据；
  对抗题 dev-005 的模拟回答复述了题干中的引用，说明拒答必须用正式模型与人工复核。
  G1/G2 各 5 条证据，G2 7/7 注入图谱上下文（264~535 字符）；
  G1/G2 答案含规范引用 7/7。结果字段与 `docs/data_contract.md` 一致。
  该冒烟使用模拟生成器，仅验证链路，不能用于评测结论。
- 真实 LLM 冒烟 `dev-v1-llm`（2026-11-05 11:03:48 → 11:05:02，mock=false）：
  G0 证据 0 条，G1/G2 各 5 条；G2 7/7 注入图谱上下文（264~535 字符）；
  G1/G2 各 6/7 输出“《法规名》第X条”格式引用，dev-007 为范围外对抗题并拒答。
  G0 仍有 4/7 答案引用条文（模型参数知识），说明“G0 不引用”不能只靠提示词保证；
  正式评测须按 R3 预设口径将 G0 引用准确率记 N/A 或 0，并在报告中披露。
  该结果仍为 dev 链路，不能用于正式结论；引用准确率由 R3 用正式题库计算。

## 四、GPU 节点执行记录（2026-11-05）

1. **v1 语料**：178 部全部成功，按条切分 10,069 条、1,273,548 字，结构告警 0。
   全部 178 部带 `jurisdiction`（全国 / 云南 / 昆明）。旧 75 部 / 4,104 条快照
   已删除，当前 `data/v1/` 为唯一交付版本。

2. **v1 正式索引**：`BAAI/bge-m3` 重建，1024 维、debug=false、10,069 条，
   collection `legal_articles_v1`，built_at `2026-11-05T10:47:43+08:00`，
   articles_sha256 `64cfe766…7bd338`，耗时 112.0s。
   节点无外网，加载缓存权重时设置 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`；
   与在线加载使用同一份权重与参数，效果一致。

3. **生成服务**：vLLM 0.6.3.post1 加载 `Qwen/Qwen2.5-7B-Instruct` 的 AWQ int4 权重，
   OpenAI 兼容端点 `http://127.0.0.1:8000/v1`；共享 GPU 显存不足，故未用 bf16 原权重。
   启动参数与量化标记已写入 `config/settings.yaml` 与
   `run_meta.generation_service`。

4. **v1 LLM 图谱**：`python -m legal_rag.graph.extract --method llm --workers 4`
   对 10,069 条全量抽取，正式文件 `data/v1/graph/triples.jsonl`。
   10,069 条中 `llm_ok` 8,940、`llm_empty` 1,126、`rule_fallback` 3、`error` 0，
   写入 8,943 条（覆盖 88.82%）；实体 10,737 个（主体 3,198、行为 7,406、处罚 133），
   关系 59,760 条。主体/行为原文回验通过（1 处行为因条文跨行，去除换行后可匹配）。
   Cypher 68,707 条语句（4 约束 + 68,703 数据），预期 19,680 节点 / 59,760 关系；
   `verify_graph_export.py` 结构校验 11 项 0 失败，摘要见
   `data/v1/graph/verify_summary.json`。

5. **mock dev 冒烟**：`results/dev-v1-smoke`，7 题 × G0/G1/G2 × 1 次（模拟生成器）；
   G0 证据 0 条、G1/G2 各 5 条，G2 7/7 注入图谱上下文（264~535 字符），
   答案含规范引用 7/7；仅用于确认 v1 链路，不作为正式结果，且该目录未入库。

6. **真实 LLM dev 冒烟**：`results/dev-v1-llm`，7 题 × G0/G1/G2 × 1 次，
   mock=false，vLLM `Qwen/Qwen2.5-7B-Instruct`（AWQ int4）；
   运行时间 11:03:48 → 11:05:02。G0 证据 0 条，G1/G2 各 5 条；
   G2 7/7 注入图谱上下文（264~535 字符）；G1/G2 各 6/7 输出规范引用，
   dev-007 为范围外对抗题并拒答。G0 有 4/7 引用条文（参数知识），
   正式评测需按预设口径处理并在报告中披露。该目录未入库，不作为正式结果。

## 五、风险与边界

- **规模**：v1 为 10,069 条，仍低于开题预估 2 万~5 万条，属于真实测量结果；
  本次范围限定为全国性相关法规 + 云南省/昆明市地方性法规，未纳入全国其他省市的
  地方性法规。若需继续扩大，应扩充目录后重建，切分与索引代码无需改动。
- **范围相关性**：目录以土地、矿产、水、森林、草原、湿地、海洋、能源、生态环境、
  国土空间规划及资源行政执法相关文本为准；行政程序类法规用于处罚/许可依据。
  开题报告提到的自然资源部政策文本未纳入。
- **目录筛选**：旧目录中 12 部无现行有效精确匹配的法规未纳入；已被新法替代的
  旧文本以现行法为准（如耕地占用税暂行条例→耕地占用税法，矿产资源登记类旧办法→
  矿产资源法及实施条例）。R3 出题应以 `data/v1/manifest.json` 的 178 部目录为准。
- **索引口径**：v1 为 BGE-M3 1024 维正式索引；hashing 索引只用于本机联调，
  不得与正式结果混用。索引缓存不入库，换机器需重建。
- **推理量化**：正式实验使用 AWQ int4 权重（共享 GPU 显存限制），服务名仍为
  `Qwen/Qwen2.5-7B-Instruct`；量化标记见 `run_meta.generation_service`。
- **正式题库缺失**：`data/eval/v1/questions.jsonl` 未交付，dev 冒烟不能作为
  正式结果；正式主实验需 R3 题库到位后重新运行。
- **G0 引用泄漏**：真实 LLM 冒烟中 G0 仍有 4/7 答案给出条文引用（模型参数知识），
  说明“G0 不引用”不能只靠提示词保证；正式评测按预设口径将 G0 引用准确率记
  N/A 或 0，并在报告中披露该现象。
- **Chroma 路径**：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\...`；换机器重建即可，清单记录了实际路径。
- **Neo4j 在线服务未启动**：Cypher 已通过 11 项结构校验，实际导入待部署机；
  G2 实验使用离线 GraphIndex，不依赖 Neo4j，因此不影响实验复现。
- **图谱抽取方式**：正式图谱为 LLM 抽取（`method=llm`，Qwen2.5-7B-Instruct），
  与开题报告一致；10,069 条中 1,126 条空结果、3 条规则兜底、0 错误，
  主体/行为原文回验通过（1 处跨行），详见 `triples.stats.json`。
- **旧结果已删除**：原 75 部快照对应的 `results/dev-server-v1/`、
  `results/dev-llm-graph/`、`results/repro-server-1/` 已不在仓库；
  当前仅保留当前 v1 的 `dev-v1-smoke` 与 `dev-v1-llm` 冒烟。
  正式实验必须使用当前 v1 索引与 `data/v1/graph/triples.jsonl` 重新运行。
- **一键复现的覆盖行为**：`scripts/reproduce.py` 会按当前 settings 重建
  `triples.jsonl` 与索引；`--mock` 默认用规则图谱，正式复现默认用 LLM 图谱。
  建议在仓库副本或临时分支执行，避免覆盖交付快照。

## 六、与 R1 / R3 的接口

> R3 的完整交接包、结果字段用法、指标口径与已知缺口见 `docs/r3_handoff.md`。

- R3 提供正式题库 `data/eval/v1/questions.jsonl`（字段 `id/category/question`）；
  R1 用 `run_experiment.py` 产出 `results/<run_id>/<group>_r<repeat>.jsonl` 与 `run_meta.json`。
- 每条结果包含 `answer`、`evidence[].citation/article_id/score/ranks/graph`、
  `graph_context`、`prompt_hash`、`usage`、`latency`；评测脚本按 `article_id`/citation
  计算 Recall@5 与引用准确率。
- 正式实验前置校验：`run_meta.json.index_manifest.embedding_model` 必须为 BGE-M3、
  `article_count=10069`、`vector_store.collection=legal_articles_v1` 且 `mock=false`；
  否则结果只能标记为流程验证。
- 图谱交付校验：`scripts/verify_graph_export.py` 可对比 `triples.jsonl` 与 Cypher；
  当前 LLM 图谱已完成 11 项结构校验。部署机导入 Cypher 后，传 `--neo4j-uri`
  或 `--db-counts` 可复跑 21 项计数校验。
- 字段契约详见 `docs/data_contract.md`；变更接口须同步更新该文件与 `CHANGELOG.md`。
