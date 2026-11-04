# 变更日志

本文件记录 `data/v1/` 语料、索引、图谱与流水线的每次实质变更。任何新增/替换法规、
重新切分、重建索引或修改检索/提示词配置，都必须在此登记（时间、原因、影响范围）。

## R3 交接准备 — 2026-11-03

状态：工程与数据可交接；正式评测集仍由 R3 产出。未改动语料、索引与已有结果。

### 1. 交接材料

- 新增 `docs/r3_handoff.md`：交付包清单、冻结版本、结果字段与指标映射、
  正式实验门槛、已知缺口、R3 起步任务与常用命令。
- 更新 `README.md`、`docs/r2_delivery.md`、`docs/handoff_gpu_server.md`、
  `docs/route_v2_hunan_illegal_land.md` 中的测试数（29 → 32）、GPU 运行状态与
  R3 交接入口，避免过期口径。

### 2. 校验工具

- `scripts/validate_case_results.py` 不再写死 17 题 / 11 案 / 597 条 / 30 节点 180 边，
  改为从题库、案例、`data/cases/*/graph/stats.json` 与索引 manifest 自动取数；
  新增 `--questions/--cases/--graph-stats/--index-manifest` 与
  `--expect-questions/--expect-cases/--expect-index-articles` 覆盖项。
- `case-main-v1` 用当前校验器为 **774 项检查 0 失败**（旧版脚本为 771 项）。

### 3. 已知缺口（交接时必须说明）

- `湘自资规〔2022〕1号` 裁量档位仍在 `cases/schema.py` 硬编码，未进入
  `data/v2/articles.jsonl`；R3 计算引用准确率时需按外部政策依据单独统计。
- `case-main-v1` 生成于图谱稳定排序修复之前，作为冻结结果使用；新实验用新 `run_id`。
- v1 正式题库未交付；案例仍为 11 份、17 题、1 次重复，不能直接支撑 H1 统计结论。
- 交接提交为 `75422c4`（含校验器、交接文档与文档刷新）；`results-server.tar.gz`
  与开题报告 docx 为本地未跟踪文件，不入库。

## GPU 节点正式运行 — 2026-11-03

状态：v2 主线完成 BGE-M3 正式索引与五组案件实验；v1 正式题库未交付，仅完成 dev 集对照。
操作人：R2（GPU 节点执行）。环境：2×A100-40GB 共享节点，conda `LLM_F`
（Python 3.11.18、torch 2.5.1+cu121），生成服务 vLLM 0.6.3.post1。

### 1. 生成服务

- `Qwen/Qwen2.5-7B-Instruct` 以 AWQ int4 权重（`models/qwen2.5-7b-instruct-awq`）由 vLLM
  提供 OpenAI 兼容接口 `http://127.0.0.1:8000/v1`。
- vLLM 参数：`--served-model-name Qwen/Qwen2.5-7B-Instruct --gpu-memory-utilization 0.24
  --max-model-len 8192 --max-num-seqs 4 --quantization awq --dtype float16`。
- 共享节点显存不足，未使用 bf16 原权重；`config/settings*.yaml` 记录
  `quantization: awq-int4`，`run_meta.generation_service` 同步留痕。该偏差只影响推理
  精度/速度，不改变解码参数与提示词。
- vLLM 0.6.3 的 outlines 引导解码依赖损坏（环境中 `pyairports` 仅有 dist-info、无实际
  模块），服务以 `--guided-decoding-backend lm-format-enforcer` 启动；本项目不使用
  受约束解码，输出口径不受影响。

### 2. 正式索引与图谱

- v2：`BAAI/bge-m3`，1024 维，597 条，`embedding_model_debug=false`，device=cuda，
  built_at `2026-11-03T18:03:05+08:00`，articles_sha256 `6c52e7ea…`。
- v1：`BAAI/bge-m3`，1024 维，4,104 条，debug=false，built_at
  `2026-11-03T18:51:02+08:00`，articles_sha256 `03d3e2ee…`（由 `reproduce.py` 重建）。
- 新增 `data/v2/graph/neo4j_import.cypher`：4,875 条语句（未导入 Neo4j）。
- 注：`reproduce.py` 重建 v1 时给 `documents/articles` 补齐了 `jurisdiction` 字段
  （与 v2 契约一致），并按当前代码重写 `parsed_at/extracted_at`；条数、条文文本、
  三元组集合均未变化（1,181 条三元组的 subjects/actions 仅列表顺序不同），因此
  `articles_sha256` 更新为 `03d3e2ee…`。

### 3. v2 正式案件实验（case-main-v1）

- `2026-11-03T18:24:47+08:00` → `18:44:18+08:00`；G0/G1/G2/G2-case/G2-graph × 17 题
  = 85 条；mock=false；prompt_version=2.0；解码 temp=0.1 / top_p=0.9 / seed=42 /
  max_tokens=1024。
- run_meta：git_commit `980da77…`，case_count=11，案件图谱 30 节点 / 180 边，
  索引 BGE-M3 / 1024 / 597。
- `scripts/validate_case_results.py --run-dir results/case-main-v1`：**771 项检查，
  0 失败**；生成日志无「调试嵌入器」「查询嵌入模型与索引模型不一致」警告。
- 分组观测（17 题均值）：G0 引用 0.00 / 类案 0；G1 引用 5.71 / 类案 0；
  G2 引用 6.53 / 类案 3.00；G2-case 引用 6.00 / 类案 0；G2-graph 引用 6.24 / 类案 3.00。
  罚款区间非空 10/17（其余为历史行为、缺地类、面积缺口或排除题）。
- LLM 答案含规范条文引用（`《法规》第X条`）比例：检索四组 17/17，G0 9/17。
- handoff §5 逐题期望（罚款区间 q01/q02/q03/q05/q07/q13/q14/q15/q16/q17、
  历史版本提示 q04/q10、缺地类 q06/q08/q09、部分区间 q11、排除 q12）全部命中。

### 4. v1 对照（dev-server-v1，仅 dev 集）

- `data/eval/v1/questions.jsonl` 仍未交付（R3 阻塞项），按 handoff §4 第 6 步改用
  `data/eval/dev/questions.jsonl`（7 题）× G0/G1/G2 × repeats=2 = 42 条。
- `2026-11-03T18:46:28` → `18:49:03`；索引 BGE-M3 / 1024 / 4,104；G0 证据 0 条，
  G1/G2 各 5 条；答案含规范引用 6/7。
- **该结果标记为 dev，不得写入正式结果表。**

### 5. 一键复现留档（repro-server-1）

- `python scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3
  --run-id repro-server-1`：5/5 步成功，211.3s；29 项单测 OK；日志
  `logs/reproduce_20261103-184956.{json,log}`。
- 归档：`results-server.tar.gz`（results/ + logs/ + 两份 index_manifest.json）。

### 6. 接口与工具

- 结果格式升级为 `2.1`（`settings_v2.yaml:evaluation.output_format_version`）：
  `citations` 改为对象数组（article_id/citation/score/ranks/role/source），新增
  `citation_strings`；`docs/data_contract.md` §5.5 同步。
- `run_meta` 新增 `generation_service`（base_url/model/backend/quantization），
  v1/v2 流水线一致。
- 新增 `legal_rag.pipeline.ask_case`（v2 单题五步 CLI）与
  `scripts/validate_case_results.py`（handoff §5 自动校验）。

### 7. 已知限制

- 案例仍为 11 份（目标 80–100）；4 案文书本身缺地类。
- v1 正式评测集未到，v1 对照仅 dev；引用准确率 / Recall@5 统计仍由 R3 按
  `article_id` 计算。
- 共享 GPU 上 BGE-M3 查询嵌入放在 GPU0（vLLM 占 GPU1），与索引同为 BGE-M3 / 1024 维。

## R2 收尾：Neo4j 导出修复与导入校验 — 2026-11-03

状态：v1/v2 图谱 Cypher 已修复并用 Neo4j 5.26.0 嵌入式实例实际导入；在线 Docker 服务未启动。
操作人：R2。

### 1. 修复

- `src/legal_rag/graph/export_neo4j.py:_q()` 原先只转义反斜杠与单引号，未转义换行/制表符。
  v2 的处罚文本“责令退回款项，并对单位负责人和直\n接责任人给予行政处分”会把 Cypher
  字符串截成两行，`cypher-shell` 或驱动导入会直接语法失败。已补 `\n/\r/\t` 转义。
- `GraphIndex` 的同分邻居改为按 `(-shared_count, article_id)` 稳定排序，`search()`
  内对集合遍历也排序，消除 Python 哈希随机化导致的 `RELATED_TO` 边与 G2 图谱上下文漂移。
  用 `PYTHONHASHSEED=1/2` 分别导出 v1/v2，sha256 完全一致。
- 新增回归测试 3 项（换行转义、同分排序、导出确定性）；全仓 32 项 unittest 通过。

### 2. 重新生成 Cypher

- v1：29,128 条语句（4 约束 + 29,124 数据），sha256 `6df843e2…`。
- v2：4,890 条语句（4 约束 + 4,886 数据），sha256 `778c8659…`。
- 原 v1 29,059 条 / v2 4,875 条为修复前导出，已由新文件替换。

### 3. 实际导入校验（嵌入式 Neo4j 5.26.0 / JDK 17）

- 当前节点无 `docker` 组权限、系统无 Java，且 `dist.neo4j.org` 对本节点返回 403；
  改用 Temurin JDK 17 + Maven + `org.neo4j:neo4j:5.26.0` 嵌入式实例完成真实导入。
- v1：4,106 节点（Article 3,476 / Subject 29 / Action 35 / Penalty 566），
  25,648 关系（APPLIES_TO 2,064 / REGULATES 6,282 / PENALTY 1,025 / RELATED_TO 16,277），
  导入 166.9s。
- v2：707 节点（559 / 20 / 33 / 95），4,327 关系（341 / 1,296 / 177 / 2,513），导入 53.2s。
- 新增 `scripts/verify_graph_export.py`：对 triples/Cypher/DB 计数做 21 项校验，
  v1/v2 均 0 失败；结果 `logs/neo4j_import_v1.json`、`logs/neo4j_import_v2.json`。

### 4. 边界

- 未启动 `deploy/neo4j` 的在线容器；演示环境仍按该 compose 启动，密码只从
  `NEO4J_PASSWORD` 读取。G2 实验继续使用离线 `GraphIndex`，不依赖 Neo4j。
- `case-main-v1` 生成于本次排序修复之前；若 R1 逐字复现旧 G2 上下文，以该结果留档为准；
  正式 v1 `main-v1` 应使用修复后的代码。

## v2 案例层实施 — 2026-10-31

状态：v2 试点可运行；`data/v1/` 未改动。新增 `data/v2/` 与 `data/cases/v1/`，两者与 v1 隔离。

### 1. v2 语料与索引（`settings_v2.yaml`）

- 目录 `config/corpus_catalog_v2.yaml`：国家核心法 6 部 + 湖南地方立法 5 部，共 11 部。
- 产出：`data/v2/articles.jsonl` 597 条、约 8.3 万字，结构告警 0；
  每条新增 `jurisdiction`（national/hunan）。
- 索引：`data/v2/index/`（hashing 512 维调试嵌入器 + BM25），
  Chroma 597 条；`data/v2/graph/triples.jsonl` 559 条三元组、147 个实体。
- **正式实验仍需 GPU 节点用 BGE-M3 重建**；本机调试索引不得作为正式数据。

### 2. 案例层（`data/cases/v1/`）

- 来源 5 个：永州 2025 台账（7 案）、邵阳 2023-13、江永 2025-5、祁阳 2025-4、湘乡 2025-30；
  URL 与采集时间见 `manifest.json` 与 `config/case_catalog.yaml`。
- 入库 11 案：9 案未经批准占用 + 2 案超过批准数量；`scope_status=included`。
- 质检：7 案地类/金额完整；4 案台账只抽到总面积、地类缺失
  （`hn-yongzhou-2025-7/9/10/12`），系统会要求补充地类而非臆造金额。
- 旧条号映射：土地管理法 2004 第 76→77；实施条例 2014 第 42→57；
  保留 `cited_article_num` 与 `mapped_from_old_version`。
- 脱敏：个人姓名、手机号、身份证号掩码；单位名称保留。`raw/*.txt` 同步脱敏
  （含法定代表人、联系人及证据清单中的第三人姓名），`text_sha256` 按脱敏后文本重算。
- 案件图谱：`data/cases/v1/graph/` 30 节点、180 边，含 Neo4j Cypher 与逐案质检统计。

### 3. 代码与实验

- 新增 `src/legal_rag/cases/`：`extract.py`（解析/脱敏/条号映射）、`schema.py`（契约/校验）、
  `build_case_graph.py`（案件图谱）、`retriever.py`（类案检索）、`case_qa.py`（五步问答）。
- 新增 `src/legal_rag/pipeline/run_case_experiment.py`：
  `G0/G1/G2/G2-case/G2-graph` 五组；输出确定性答案、五步中间结果、类案与引用。
- G0 修复：不再引用条文、不检索类案、不计算罚款；G1 仅法条检索 + 固定法条链。
- 类案防泄漏：`case_text` 默认不含罚款结果；`exclude_case_id` 排除查询案件自身；
  类案总数按 `case_top_k` 封顶，图谱关联案排在直接命中之后。
- 裁量：区分现行标准（2022 年起）与历史行为（2004/2021 等）；
  历史行为不套用现行幅度，只给旧法条号与版本提示；地类未查全时不给罚款总额。
- 评测题：`data/cases/v1/questions.jsonl` 17 题（11 案改写 + 6 边界题），
  含 `exclude_case_id` 与结构化 expected。
- 测试：新增 `tests/test_cases.py`，全仓 29 项 unittest 通过。
- 本机 mock：`results/case-smoke-20261031-v2/` 五组 × 17 题，仅流程联调，未调用正式模型。
  校验结果：G0 引用/类案/罚款均为 0；四组检索型实验 17/17 符合 expected。

### 4. 已知限制

- 案例 11 份，未达到 80–100 份目标；统计检验暂不做结论。
- 本机 Chroma 为 hashing 调试嵌入器；Qwen2.5-7B-Instruct 未在本机正式运行。
- 4 案缺地类；历史裁量金额需按行为时标准另行核定。

## v2 路线修订 — 2026-10-28（规划，未实施）

依据 2026-10-27 开题答辩反馈修订研究边界，**不涉及 `data/v1/` 任何变更**：

- 范围由“国土资源全领域”收窄为“湖南省·未经批准非法占用土地（含超过批准数量占用）行政处罚”。
- 新增案例层：采集 80–100 份湖南公开行政处罚决定书/台账，60 份 gold 评测集 + 20 份开发集，
  版本化为 `data/cases/v1/`；字段含违法行为、违反条款、处罚依据、地类面积、罚款金额与单价。
- 图谱由“法条图谱”扩展为“案件—法条—裁量图谱”：Case→Behavior→Article→Penalty，复用现有 `article_id`。
- 流水线由“法条问答”升级为“案件事实 → 定性 → 法条适用 → 裁量计算 → 结构化结论”五步判断链；
  G0/G1/G2 归因控制保持不变，另加 G2−case、G2−graph 两项消融。
- 规划全文：`docs/route_v2_hunan_illegal_land.md`。现有 75 部法规、4,104 条、索引与流水线全部保留。

## v1 — 2026-10-27

状态：R2 本地可完成部分已交付；正式 BGE-M3 + Qwen2.5-7B-Instruct 实验待 GPU 节点执行。

### 1. 法规语料（collector 1.0）

- 来源：国家法律法规数据库（flk.npc.gov.cn），目录见 `config/corpus_catalog.yaml`。
- 采集结果：目录 87 部，成功 75 部，缺失 12 部，错误 0。
  - 明细与 sha256 见 `data/v1/manifest.json`；原始文件 `data/v1/raw/*.docx`，
    元数据 `data/v1/meta/*.json`。
  - 缺失判定：FLK 精确标题检索未返回**现行有效**（`sxx=3`）的同名版本，
    记为 `no_effective_exact_match`。为避免把失效/近似文本混入正式语料，未做标题替换。
- 缺失清单（12 部）：

  | doc_id | 法规名 | 备注 |
  |---|---|---|
  | law-environment | 中华人民共和国环境保护法 | 精确同名无现行有效版本 |
  | law-soil-pollution | 中华人民共和国土壤污染防治法 | 同上 |
  | reg-farmland-occupation-tax | 中华人民共和国耕地占用税暂行条例 | 已被《耕地占用税法》替代，未纳入旧条例 |
  | reg-mining-registration | 矿产资源开采登记管理办法 | 精确同名无现行有效版本 |
  | reg-mining-exploration | 矿产资源勘查区块登记管理办法 | 同上 |
  | reg-mining-transfer | 探矿权采矿权转让管理办法 | 同上 |
  | reg-mineral-compensation | 矿产资源补偿费征收管理规定 | 同上 |
  | reg-survey-marks | 测量标志保护条例 | 同上 |
  | reg-soil-conservation-implementation | 中华人民共和国水土保持法实施条例 | 同上 |
  | yn-land-admin-implementation | 云南省实施《中华人民共和国土地管理法》办法 | 同上 |
  | yn-historic-towns | 云南省历史文化名城名镇名村保护条例 | 同上 |
  | yn-geohazard | 云南省地质灾害防治条例 | 同上 |

  上述条目可在后续版本通过补充目录（部门规章、地方性法规）或改用官方最新标题重新采集。

### 2. 按条切分（parser 1.0）

- 以“条”为最小检索/引用单位，条内款、项、但书不拆分；目录段整体跳过。
- 产出：`data/v1/documents.jsonl`（75 部）、`data/v1/articles.jsonl`（4,104 条）。
- 规模：正文合计 519,496 字；条均 126.6 字（最短 16、最长 1,131）；
  部均 54.7 条；结构告警 0（条号单调、无重复、首条为第 1 条、无空正文）。
- 分级：法律 29、行政法规 29、地方性法规 17。
- **与开题报告预估的差异（如实说明）**：开题报告预计 2 万~5 万个文本块，
  实际按条切分为 4,104 条 / 51.9 万字。原因是检索单位固定为“条”且目录仅 75 部
  现行有效法规，未通过拆条或复制文本虚增规模。后续扩大规模应扩充法规目录，
  而不是改变切分粒度；实验与评测一律以实际 4,104 条为准。

### 3. 索引（index 1.0）

- 本机构建：`embedding_model = hashing`（调试用 512 维特征哈希嵌入器），
  Chroma 4,104 条 + BM25（jieba 词 + 中文字符二元组，k1=1.5，b=0.75）。
- 索引清单：`data/v1/index/index_manifest.json`（articles sha256
  `6a54c73f…bcc2`，article_count=4104，`embedding_model_debug=true`）。
- Chroma 路径：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\09e06fb173`，清单同时记录 configured_path；
  可用 `LEGAL_RAG_CHROMA_DIR` 覆盖。
- **正式实验必须重建**：使用 BGE-M3（1024 维）执行
  `python -m legal_rag.index.build_index --embedding-model <BGE-M3 路径>`；
  debug 索引仅用于流程联调，不得与正式结果混用（运行时会打印警告）。

### 4. 图谱（graph 1.0，规则抽取）

- 抽取结果：`data/v1/graph/triples.jsonl`，覆盖 3,476/4,104 条（84.7%）；
  实体 630 个（主体 29、行为 35、处罚 566）；含主体法条 1,627 条、含处罚法条 512 条。
- 图谱结构：Article—APPLIES_TO→Subject、REGULATES→Action、PENALTY→Penalty；
  G2 检索使用实体命中 + 一跳子图（共享实体 ≥2 才加邻接分）。
- Neo4j 导入脚本：`data/v1/graph/neo4j_import.cypher`（29,059 条语句）。
  本机无 Docker/neo4j 驱动，**尚未实际导入**；导入命令见 `docs/r2_delivery.md`。

### 5. 检索-生成流水线（pipeline 1.0，prompt 1.0）

- 分组：G0 无检索；G1 稠密 + BM25；G2 稠密 + BM25 + 图谱。
- 融合：查询变体内 RRF、跨信号 RRF（k=60）；top_k=5，candidate_k=30。
- 生成参数固定：temperature=0.1、top_p=0.9、seed=42、max_new_tokens=1024；
  统一 SYSTEM/USER 模板，强制引用或声明“现有知识库中没有找到条文依据”。
- 单条问答入口：`python -m legal_rag.pipeline.ask`；
  实验入口：`python -m legal_rag.pipeline.run_experiment`。

### 6. 验证记录

- 单元测试：`python -m unittest discover -s tests` → 11 项通过。
- 一键复现：`scripts/reproduce.py --skip-collect --embedding-model hashing --mock
  --run-id repro-local-1` → 5 步全部 ok，总耗时 14.2s；
  记录 `logs/reproduce_20261027-184739.json` / `.log`。
- 联调实验：
  - `results/dev-mock/`：7 题 × G0/G1/G2，模拟生成器，验证证据注入与分组隔离。
  - `results/dev-llm-0.5b/`：2 题真实生成（Ollama qwen2.5:0.5b），答案方向正确，
    但 0.5B 模型未稳定输出条文号——说明引用能力需正式 7B 模型验证。
- 以上均为流程验证，**不构成正式实验数据**；正式指标待 GPU 节点按同一脚本重跑。

### 7. 复现方式

```bash
export PYTHONPATH=src
PY="<venv>/Scripts/python.exe"

# 仅数据与索引（不重新联网采集）
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1

# 完整链路（含 FLK 采集，约 10 分钟）
$PY scripts/reproduce.py --embedding-model <BGE-M3 路径> --run-id full-v1
```

产物写入 `logs/reproduce_<时间戳>.json|log`；任一步失败脚本以退出码 1 结束。
