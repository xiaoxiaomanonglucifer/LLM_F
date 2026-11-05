# 变更日志

本文件记录 `data/v1/` 语料、索引、图谱与流水线的每次实质变更。
任何新增/替换法规、重新切分、重建索引或修改检索/提示词配置，都必须在此登记
（时间、原因、影响范围）。

## v1 扩充版合并与旧快照删除 — 2026-11-05

状态：当前 `data/v1/` 为原 v2 扩充版（178 部 / 10,069 条），旧 75 部 / 4,104 条
快照已从仓库删除。操作人：R2（GPU 节点执行）。

### 1. 版本合并

- 原 `data/v2/` 整体提升为 `data/v1/`：`data/v2/{raw,meta,*.jsonl,index,graph}`
  → `data/v1/`，`config/settings_v2.yaml` → `config/settings.yaml`，
  `config/corpus_catalog_v2.yaml` → `config/corpus_catalog.yaml`。
- 旧 v1 快照（75 部 / 4,104 条）的 raw/meta、索引、图谱、配置及
  `results/dev-server-v1/`、`results/dev-llm-graph/`、`results/repro-server-1/`
  已删除；仓库内不再保留旧版数据与结果。
- 当前 v1 保留旧 v1 的 4,104 个 `article_id` 与条文文本，但版本号统一为 v1，
  不再区分 v1/v2。

### 2. 语料

- 目录：178 部现行有效法规（全国 138 部、云南 15 部、昆明 25 部）。
- 采集：178 部成功、0 缺失、0 错误；原始文件 `data/v1/raw/*.docx`，
  元数据 `data/v1/meta/*.json`，清单 `data/v1/manifest.json`。
- 按条切分：10,069 条、1,273,548 字；条均 126.5 字（最短 16、最长 2,656），
  部均 56.6 条；结构告警 0。
- 分级：法律 52、行政法规 86、地方性法规 40。
- 适用范围：全国 8,241 条、云南 764 条、昆明 1,064 条；全部补齐 `jurisdiction`。
- 最大单部：`中华人民共和国生态环境法典`（1,242 条，2026-08-15 施行）。
- 旧目录 12 部无现行有效精确匹配的法规未纳入；已被新法替代的旧文本以现行法为准
  （如耕地占用税暂行条例→耕地占用税法，矿产资源登记类旧办法→矿产资源法及实施条例）。
- **规模仍低于开题预估 2 万~5 万条**：本次限定为全国性相关法规 + 云南省/昆明市
  地方性法规，未纳入全国其他省市地方性法规，也未拆条或复制文本虚增规模；
  实测以 10,069 条为准。

### 3. 索引

- `data/v1/index/index_manifest.json`：BGE-M3 / 1024 维 / 10,069 条，
  `embedding_model_debug=false`，device=cuda，集合 `legal_articles_v1`；
  built_at `2026-11-05T10:47:43+08:00`，articles_sha256 `64cfe766…7bd338`，
  重建耗时 112.0s。
- Chroma 中旧 `legal_articles_v2` 集合已删除，当前仅保留 `legal_articles_v1`。
- BM25 参数不变（jieba 词 + 字符二元组，k1=1.5，b=0.75）。
- 索引缓存 `data/v1/index/chroma/`、`*.pkl` 不入库；`.gitignore` 改为 v1 专用路径。

### 4. 图谱

- 正式文件 `data/v1/graph/triples.jsonl`：`Qwen/Qwen2.5-7B-Instruct` 全量抽取，
  10,069 条中 `llm_ok` 8,940、`llm_empty` 1,126、`rule_fallback` 3、`error` 0；
  写入 8,943 条，覆盖 88.82%（全国 7,295/8,241、昆明 939/1,064、云南 709/764）。
  sha256 `37d58468…0bb75d`。
- 实体 10,737 个（主体 3,198、行为 7,406、处罚 133）；
  关系 59,760 条（APPLIES_TO 10,944、REGULATES 14,401、PENALTY 2,076、
  RELATED_TO 32,339）。
- 原文回验：主体 10,944 处、行为 14,401 处均可逐字匹配（1 条行为因条文跨行，
  去除换行后可匹配）；处罚按规范化类型输出，不要求逐字。
- `data/v1/graph/neo4j_import.cypher` 已按新路径重新导出：68,707 条语句
  （4 约束 + 68,703 数据），预期 19,680 节点 / 59,760 关系；
  sha256 `26216333…0bfe5c`。
- `scripts/verify_graph_export.py` 结构校验 11 项 0 失败，摘要已重新生成到
  `data/v1/graph/verify_summary.json`；Neo4j 实际导入待部署机。
- 旧规则版归档 `triples_rule.jsonl` / `triples_rule.stats.json` 已随旧快照删除；
  当前正式文件为 LLM 版。

### 5. 配置、结果与文档

- `config/settings.yaml` 与 `config/corpus_catalog.yaml` 合并为唯一配置；
  检索/生成参数不变（top_k=5、candidate_k=30、rrf_k=60、
  temperature=0.1、top_p=0.9、seed=42、max_tokens=1024）。
- 正式评测集路径统一为 `data/eval/v1/questions.jsonl`，尚未由 R3 交付。
- dev 冒烟在 v1 配置下重跑为 `results/dev-v1-smoke`：7 题 × G0/G1/G2 × 1 次（mock），
  G0 证据 0 条、G1/G2 各 5 条、G2 7/7 注入图谱上下文（264~535 字符）；
  仅链路验证，非正式结果，且该目录未入库。
- 真实 LLM dev 冒烟 `results/dev-v1-llm`：7 题 × G0/G1/G2 × 1 次，mock=false，
  vLLM `Qwen/Qwen2.5-7B-Instruct`（AWQ int4），运行时间 11:03:48 → 11:05:02；
  G0 证据 0 条，G1/G2 各 5 条，G2 7/7 注入图谱上下文；G1/G2 各 6/7 输出规范引用，
  dev-007 为范围外对抗题并拒答。G0 有 4/7 引用条文（参数知识），正式评测需披露。
  该目录未入库，不能用于正式结论。
- `README.md`、`docs/r2_delivery.md`、`docs/r3_handoff.md`、
  `docs/data_contract.md` 全部改为当前 v1 口径。
- 本次迁移改动尚未提交；提交前以工作区内容为准。

## 历史沿革（旧快照，已删除）

以下版本仅用于说明当前 v1 的来源，对应数据与结果已不在仓库，不得引用为当前结果。

- **2026-10-27 旧 v1 初版**：75 部 / 4,104 条 / 519,496 字，法律 29、行政法规 29、
  地方性法规 17；目录 87 部中 12 部无现行有效精确匹配而未采集；本机 hashing 索引。
- **2026-11-03 旧 v1 GPU 运行**：BGE-M3 / 1024 / 4,104 正式索引；
  dev 集 G0/G1/G2 对照；`repro-server-1` 一键复现 5/5 步、211.3s。
- **2026-11-04 旧 v1 图谱切换**：规则图谱替换为 Qwen2.5-7B-Instruct 抽取，
  3,694 条三元组 / 4,757 实体 / 28,453 条 Cypher；`dev-llm-graph` 冒烟。
- **2026-11-05 扩充版（原 v2）**：新增 80 部全国性法规与 23 部昆明市地方性法规，
  形成 178 部 / 10,069 条；完成 BGE-M3 索引与 LLM 图谱；随后提升为当前 v1，
  旧 75 部快照删除。
