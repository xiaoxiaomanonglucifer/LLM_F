# 变更日志

本文件记录 `data/v1/` 语料、索引、图谱与流水线的每次实质变更。任何新增/替换法规、
重新切分、重建索引或修改检索/提示词配置，都必须在此登记（时间、原因、影响范围）。

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
