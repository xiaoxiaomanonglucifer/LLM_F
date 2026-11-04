# 变更日志

本文件记录 `data/v1/` 语料、索引、图谱与流水线的每次实质变更。任何新增/替换法规、
重新切分、重建索引或修改检索/提示词配置，都必须在此登记（时间、原因、影响范围）。

## 项目收敛为 v1 主线 — 2026-11-04

状态：仓库只保留 v1 全国国土资源法规 RAG；v1 语料、索引、图谱与结果未改动。

- 移除 v1 之外的数据线、案例层及其代码、脚本、测试、结果和文档，避免依赖已不存在的路径。
- `README.md`、`docs/r2_delivery.md`、`docs/r3_handoff.md`、`docs/data_contract.md` 同步收敛为 v1 口径。
- 删除 `logs/` 与 `docs/demo_manual.md`、`docs/handoff_gpu_server.md`、`docs/handoff_gpu_to_cpu.md`：
  R3 交接只需要接口契约、交付说明与评测交接，运行日志和演示/部署手册不随仓库分发。
- 当前单元测试 14 项通过；v1 索引清单仍为 BGE-M3 / 1024 维 / 4,104 条。

## GPU 节点正式运行 — 2026-11-03

状态：v1 完成 BGE-M3 正式索引与 dev 集对照；正式评测集未交付。
操作人：R2（GPU 节点执行）。环境：2×A100-40GB 共享节点，conda `LLM_F`
（Python 3.11.18、torch 2.5.1+cu121），生成服务 vLLM 0.6.3.post1。

### 1. 生成服务

- `Qwen/Qwen2.5-7B-Instruct` 以 AWQ int4 权重（`models/qwen2.5-7b-instruct-awq`）由 vLLM
  提供 OpenAI 兼容接口 `http://127.0.0.1:8000/v1`。
- vLLM 参数：`--served-model-name Qwen/Qwen2.5-7B-Instruct --gpu-memory-utilization 0.24
  --max-model-len 8192 --max-num-seqs 4 --quantization awq --dtype float16`。
- 共享节点显存不足，未使用 bf16 原权重；`config/settings.yaml` 记录
  `quantization: awq-int4`，`run_meta.generation_service` 同步留痕。该偏差只影响推理
  精度/速度，不改变解码参数与提示词。

### 2. v1 正式索引

- `BAAI/bge-m3`，1024 维，4,104 条，`embedding_model_debug=false`，device=cuda，
  built_at `2026-11-03T18:51:02+08:00`，articles_sha256 `03d3e2ee…b70a`。
- `reproduce.py` 重建 v1 时给 `documents/articles` 补齐了 `jurisdiction` 字段，
  并按当前代码重写 `parsed_at/extracted_at`；条数、条文文本、三元组集合均未变化
  （部分三元组的 subjects/actions 仅列表顺序不同），因此 `articles_sha256`
  更新为 `03d3e2ee…`。

### 3. v1 dev 对照（dev-server-v1，仅 dev 集）

- `data/eval/v1/questions.jsonl` 未交付（R3 阻塞项），改用
  `data/eval/dev/questions.jsonl`（7 题）× G0/G1/G2 × repeats=2 = 42 条。
- 运行时间 `2026-11-03T18:46:28` → `18:49:03`；索引 BGE-M3 / 1024 / 4,104；
  G0 证据 0 条，G1/G2 各 5 条；答案含规范引用 6/7。
- **该结果标记为 dev，不得写入正式结果表。**

### 4. 一键复现留档（repro-server-1）

- `python scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3
  --run-id repro-server-1`：5/5 步成功，211.3s；当时 29 项单测 OK。
- 结果保留在 `results/repro-server-1/`；运行日志不随仓库分发。

### 5. 已知限制

- v1 正式评测集未到，v1 对照仅 dev；引用准确率 / Recall@5 统计由 R3 按
  `article_id` 计算。
- 共享 GPU 上 BGE-M3 查询嵌入放在 GPU0（vLLM 占 GPU1），与索引同为 BGE-M3 / 1024 维。

## R2 收尾：Neo4j 导出修复与导入校验 — 2026-11-03

状态：v1 图谱 Cypher 已修复并用 Neo4j 5.26.0 嵌入式实例实际导入；在线 Docker 服务未启动。
操作人：R2。

### 1. 修复

- `src/legal_rag/graph/export_neo4j.py:_q()` 原先只转义反斜杠与单引号，未转义换行/制表符。
  含换行的处罚文本会把 Cypher 字符串截成两行，`cypher-shell` 或驱动导入会直接语法失败。
  已补 `\n/\r/\t` 转义。
- `GraphIndex` 的同分邻居改为按 `(-shared_count, article_id)` 稳定排序，`search()`
  内对集合遍历也排序，消除 Python 哈希随机化导致的 `RELATED_TO` 边与 G2 图谱上下文漂移。
  用 `PYTHONHASHSEED=1/2` 分别导出，sha256 完全一致。
- 新增回归测试 3 项（换行转义、同分排序、导出确定性）；当前 v1 单测 14 项通过。

### 2. 重新生成 Cypher

- v1：29,128 条语句（4 约束 + 29,124 数据），sha256 `6df843e2…`。
- 原 29,059 条为修复前导出，已由新文件替换。

### 3. 实际导入校验（嵌入式 Neo4j 5.26.0 / JDK 17）

- 当前节点无 `docker` 组权限、系统无 Java，且 `dist.neo4j.org` 对本节点返回 403；
  改用 Temurin JDK 17 + Maven + `org.neo4j:neo4j:5.26.0` 嵌入式实例完成真实导入。
- v1：4,106 节点（Article 3,476 / Subject 29 / Action 35 / Penalty 566），
  25,648 关系（APPLIES_TO 2,064 / REGULATES 6,282 / PENALTY 1,025 / RELATED_TO 16,277），
  导入 166.9s。
- `scripts/verify_graph_export.py` 对 triples/Cypher/DB 计数做 21 项校验，0 失败；
  导入日志不随仓库分发。

### 4. 边界

- 未启动 `deploy/neo4j` 的在线容器；演示环境仍按该 compose 启动，密码只从
  `NEO4J_PASSWORD` 读取。G2 实验继续使用离线 `GraphIndex`，不依赖 Neo4j。
- 正式 v1 `main-v1` 应使用本次修复后的代码。

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
- 索引清单：`data/v1/index/index_manifest.json`（article_count=4104）。
- Chroma 路径：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\09e06fb173`，清单同时记录 configured_path；
  可用 `LEGAL_RAG_CHROMA_DIR` 覆盖。
- **正式实验必须重建**：2026-11-03 已在 GPU 节点用 BGE-M3（1024 维）重建；
  debug 索引仅用于流程联调，不得与正式结果混用（运行时会打印警告）。

### 4. 图谱（graph 1.0，规则抽取）

- 抽取结果：`data/v1/graph/triples.jsonl`，覆盖 3,476/4,104 条（84.7%）；
  实体 630 个（主体 29、行为 35、处罚 566）；含主体法条 1,627 条、含处罚法条 512 条。
- 图谱结构：Article—APPLIES_TO→Subject、REGULATES→Action、PENALTY→Penalty；
  G2 检索使用实体命中 + 一跳子图（共享实体 ≥2 才加邻接分）。
- Neo4j 导入脚本：`data/v1/graph/neo4j_import.cypher`（当前 29,128 条语句，含
  2026-11-03 的转义与稳定排序修复）。导入命令见 `docs/r2_delivery.md`。

### 5. 检索-生成流水线（pipeline 1.0，prompt 1.0）

- 分组：G0 无检索；G1 稠密 + BM25；G2 稠密 + BM25 + 图谱。
- 融合：查询变体内 RRF、跨信号 RRF（k=60）；top_k=5，candidate_k=30。
- 生成参数固定：temperature=0.1、top_p=0.9、seed=42、max_new_tokens=1024；
  统一 SYSTEM/USER 模板，强制引用或声明“现有知识库中没有找到条文依据”。
- 单条问答入口：`python -m legal_rag.pipeline.ask`；
  实验入口：`python -m legal_rag.pipeline.run_experiment`。

### 6. 验证记录

- 单元测试：`python -m unittest discover -s tests` → 14 项通过。
- 一键复现：`scripts/reproduce.py --skip-collect --embedding-model hashing --mock
  --run-id repro-local-1` → 5 步全部 ok，总耗时 14.2s（运行日志默认忽略，不入库）。
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

本地日志默认写入 `logs/`（已 gitignore，不随仓库分发）；任一步失败脚本以退出码 1 结束。
