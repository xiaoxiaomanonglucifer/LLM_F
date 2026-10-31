# 变更日志

本文件记录 `data/v1/` 语料、索引、图谱与流水线的每次实质变更。任何新增/替换法规、
重新切分、重建索引或修改检索/提示词配置，都必须在此登记（时间、原因、影响范围）。

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
