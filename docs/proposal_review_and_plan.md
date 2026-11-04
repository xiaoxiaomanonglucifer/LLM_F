# 开题报告对照与后续计划（R2 曾平）

> 依据：《大模型开题报告-法规RAG智能问答系统-第九组.docx》；
> 答辩后范围修订见 `docs/route_v2_hunan_illegal_land.md`。
> 统计截止：2026-11-03。v1（全领域法规）已冻结，v2（湖南非法占地）为答辩后的主线。
> 本文只回答 R2（工程与数据）应做什么、已经做了什么、还差什么；R1/R3/R4 的事项仅列依赖关系。

## 0. 一句话结论

R2 的工程底座已经完整跑通：v1 75 部法规/4,104 条、v2 11 部法规/597 条、11 份案例/17 题，
BGE-M3 索引、BM25+向量+图谱混合检索、G0/G1/G2 及两项消融、vLLM 推理、Neo4j 导入校验、
一键复现均已落地。**但距离“可支撑 H1 正式结论”还差三个闭环：正式评测集（≥60 题）、
正式主实验（2 次重复 + 统计检验）、演示界面。** 这三项分别主要由 R3、R1、R4 负责，
R2 当前最紧急的是提交工作区、用修复后的代码重跑复现、并刷新文档中的过期数字。

## 1. 开题报告要求拆解

### 1.1 主假设与实验设计

| 项目 | 开题报告要求 | 当前状态 | 判定 |
|---|---|---|---|
| 主假设 H1 | RAG（向量 + 图谱）的答案正确率、引用准确率显著高于同模型无检索基线 | 流水线与五组对照已实现，尚无正式统计结论 | 未完成（等 R1/R3） |
| 对照组 | G0 无检索；G1 向量 RAG；G2 向量 + 图谱 | 三组均已实现；v2 另加 G2-case、G2-graph 消融 | 已完成（代码/运行） |
| 归因控制 | 同一生成器、同一解码参数、同一提示词模板 | `temperature=0.1, top_p=0.9, seed=42, max_tokens=1024` 已固定 | 已完成 |
| 重复次数 | 每组独立运行 2 次 | `case-main-v1` 为 `repeats=1`；`dev-server-v1` 为 2 次但属 dev | 部分完成 |
| 显著性检验 | McNemar + 配对 t，α=0.05，Bonferroni | 尚未执行 | 未完成（R1） |

### 1.2 技术架构

| 层次 | 开题要求 | 当前实现 | 判定 |
|---|---|---|---|
| 数据层 | 法规原文版本化 → 按条切分 → BGE-M3 → Chroma；大模型抽取三元组 → Neo4j | v1/v2 语料、切分、BGE-M3 1024 维 Chroma 已完成；三元组当前为规则抽取；Neo4j Cypher + 嵌入式导入校验已完成 | 部分完成 |
| 检索层 | 查询重写 → 稠密 + BM25 + 图谱子图 → Top-K | 查询变体 + RRF(k=60)、top_k=5、candidate_k=30、一跳图子图均已实现 | 已完成 |
| 生成层 | 带引用格式要求的提示词 → Qwen2.5-7B-Instruct | 提示词模板与 OpenAI 兼容客户端已完成；GPU 节点用 AWQ int4 权重运行 | 已完成（有量化偏差） |
| 评测层 | Recall@5、答案正确率、引用准确率、拒答率、LLM-as-judge、人工抽检 | 结果文件已带 `citations/evidence/ranks`，评测脚本与 judge 未实现 | 未完成（R3） |
| 展示层 | Streamlit 交互界面 | 目前只有 CLI（`ask`、`ask_case`） | 未完成（R4） |

### 1.3 数据与评测目标

| 指标 | 开题报告目标 | 当前实测 | 判定 |
|---|---|---|---|
| 法规数量 | ≥50 部 | v1 75 部；v2 11 部 | 达标 |
| 文本块规模 | 2 万 ~ 5 万条 | v1 4,104 条；v2 597 条 | 未达标（约 8%~21%） |
| 评测集 | ≥60 题（常规 30 / 边界 20 / 对抗 10） | 仅 `data/eval/dev/` 7 题；v2 17 题；`data/eval/v1/` 未交付 | 未达标 |
| 标注一致性 | Cohen's Kappa ≥ 0.8 | 未报告 | 未完成（R3） |
| 人工抽检 | 20% | 未执行 | 未完成（R3） |
| 版本管理 | `data/v1/`、`data/eval/v1/`、CHANGELOG | 语料有 v1/v2 与 CHANGELOG；评测集目录缺失 | 部分完成 |

### 1.4 分工与 R2 交付物

开题报告对 R2 的职责是：法规语料采集与版本化；切分、向量化与 Chroma 构建；
Neo4j 图谱构建；检索-生成流水线实现与推理服务部署。
交付证据是：`data/v1/` 与 `CHANGELOG.md`、Git 提交记录、可复现运行脚本、全流程重跑记录。

## 2. R2 应做 vs 已做

| # | 开题要求 | 当前状态 | 证据 | 仍缺什么 |
|---|---|---|---|---|
| 1 | 法规语料采集与版本化 | 已完成 | `config/corpus_catalog.yaml`、`data/v1/raw/`、`data/v1/meta/`、`data/v1/manifest.json`；87 部目录、75 部成功、12 部缺失、0 错误 | 12 部缺失法规需在报告中说明；扩充需新建版本 |
| 2 | 按条切分 | 已完成 | `src/legal_rag/corpus/article_parser.py`、`data/v1/articles.jsonl`（4,104 条/519,496 字）、`data/v2/articles.jsonl`（597 条） | 无 |
| 3 | BGE-M3 向量化 + Chroma | 已完成 | `data/v1/index/index_manifest.json`（BGE-M3/1024/4,104）、`data/v2/index/index_manifest.json`（BGE-M3/1024/597） | 无 |
| 4 | BM25 + 混合检索 + RRF | 已完成 | `src/legal_rag/index/bm25.py`、`retrieval/hybrid.py`；k1=1.5、b=0.75、字符二元组、RRF k=60 | 无 |
| 5 | 图谱 schema 与三元组 | 部分完成 | `src/legal_rag/graph/`；v1 覆盖 3,476/4,104 条（84.7%）、630 个实体；v2 559 条法条有图谱 | 当前 `method=rule`，开题写的是“大模型抽取”；需 R1 决定是否改 LLM 抽取并抽检 |
| 6 | Neo4j 图谱构建 | 部分完成 | `data/v1/graph/neo4j_import.cypher`（29,128 语句）、`data/v2/graph/neo4j_import.cypher`（4,890 语句）；嵌入式 Neo4j 5.26 实际导入 v1 4,106 节点/25,648 关系、v2 707 节点/4,327 关系；`scripts/verify_graph_export.py` 21 项校验 0 失败 | 在线 Docker 容器未启动；演示前需在具备 Docker 的机器启动 `deploy/neo4j` |
| 7 | 检索-生成流水线 | 已完成 | `pipeline/run_experiment.py`（G0/G1/G2）、`pipeline/run_case_experiment.py`（G0/G1/G2/G2-case/G2-graph）、`cases/case_qa.py` 五步问答 | v1 正式主实验尚未运行 |
| 8 | 推理服务部署 | 已完成 | vLLM 0.6.3.post1 + Qwen2.5-7B-Instruct AWQ int4，OpenAI 兼容端点；`run_meta.generation_service` 留痕 | 共享 GPU 显存限制导致 int4 量化，需在报告中如实说明 |
| 9 | 可复现运行脚本 | 已完成 | `scripts/reproduce.py`（采集→切分→三元组→索引→单测→dev 实验）；`scripts/validate_case_results.py`；`scripts/verify_graph_export.py` | 脚本已更新，需重跑一次留下与当前代码一致的记录 |
| 10 | 全流程重跑记录 | 部分完成 | `logs/reproduce_20261103-184956.{json,log}`：5/5 步成功、211.3s、BGE-M3 非 mock；`repro-server-1` | 该次记录仍写 29 项单测，当前为 32 项；且在图谱排序/转义修复之后未再重跑 |
| 11 | Git 提交记录 | 已完成 | 初始提交 `fac7de4`、v2 路线 `a985187`、交付文档 `d3908a6`、v2 案例层 `980da77`、R3 交接 `75422c4` | `results-server.tar.gz` 与开题报告 docx 为本地未跟踪文件，按约定不入库 |
| 12 | 变更登记与接口契约 | 已完成 | `CHANGELOG.md`、`docs/data_contract.md`、`docs/r2_delivery.md`、`docs/r3_handoff.md` | 无（测试数、GPU 状态已统一刷新） |

## 3. 已完成的关键节点

| 时间 | 节点 | 结果 |
|---|---|---|
| 2026-10-27 | v1 语料、索引、图谱、G0/G1/G2 流水线 | 75 部/4,104 条/51.9 万字；结构告警 0；本机 mock 与 0.5B 联调通过 |
| 2026-10-28 | 答辩后 v2 路线修订 | 范围收窄为湖南非法占地；保留 v1 工程 |
| 2026-10-31 | v2 试点 | 11 部/597 条；11 案/17 题；案件图谱 30 节点/180 边；五步问答与五组实验打通 |
| 2026-11-03 | GPU 正式运行 | v1/v2 BGE-M3 索引；`case-main-v1` 5×17=85 条、旧版脚本 771 项/当前 774 项校验 0 失败；`dev-server-v1` 7×3×2=42 条（dev）；`repro-server-1` 5/5 步 211.3s |
| 2026-11-03 | Neo4j 导入校验 | v1/v2 Cypher 重新生成并以嵌入式 Neo4j 实际导入；21 项校验 0 失败 |
| 2026-11-03 | 工程收尾 | 图谱导出换行转义、同分邻居稳定排序；新增回归测试，全仓 32 项测试通过 |

## 4. 与开题的偏差和未完成项

以下内容不能在期末报告或答辩中当作“已完成”，需要逐条说明。

### 4.1 数据规模

- 开题预计 2 万~5 万文本块，实际按“条”切分为 v1 4,104 条。原因是检索与引用单位固定为“条”，
  且目录中只有 75 部现行有效法规；没有通过拆条或复制文本虚增规模。
- v2 只有 11 部法规、597 条，属于聚焦后的依据库，不是全领域语料。
- 若必须扩大规模，应扩充法规目录并新建版本（如 v3），不得就地改写已冻结的 v1。

### 4.2 评测与正式实验

- `data/eval/v1/questions.jsonl` 尚未交付，当前只有 7 题 dev 集；v2 有 17 题。
  两者都达不到开题“≥60 题（30/20/10）”的要求。
- `case-main-v1` 是 17 题 × 5 组、`repeats=1`，只能证明工程链路与逐题期望，
  不能支撑 McNemar / 配对 t / Bonferroni 的正式结论。
- LLM-as-judge、引用准确率、Recall@5、拒答率、Kappa、20% 人工抽检均未形成正式报告。
- 这些主要是 R3/R1 的交付物；R2 负责提供可消费的结果字段与运行环境。

### 4.3 技术实现口径

- 三元组当前是规则抽取（`method=rule`），不是开题所写的“大模型抽取”。
  `src/legal_rag/graph/extract.py` 虽支持 `--method llm`，但正式产物尚未使用。
- 正式生成使用 AWQ int4 权重，而开题只写 Qwen2.5-7B-Instruct。量化会引入精度差异，
  但解码参数、提示词、评测口径未变，需在报告中作为环境约束记录。
- Neo4j 只完成了 Cypher 生成与嵌入式导入校验，在线 Community 容器尚未启动；
  G2 实验使用离线 `GraphIndex`，不依赖在线 Neo4j。
- `case-main-v1` 生成于“图谱同分邻居稳定排序”修复之前。若 R1 需要逐字复现旧 G2 上下文，
  应以该结果留档为准；正式重跑应使用修复后的代码。

### 4.4 交付形式与版本

- 没有 Streamlit 界面，只有 CLI；展示层属于 R4。
- v1 在本轮 `reproduce.py` 中被重写，补齐了 `jurisdiction` 字段并更新了时间戳。
  条数、条文文本、三元组集合未变，但 `articles_sha256` 已变化（`03d3e2ee…`）。
  这是既成事实，需在 CHANGELOG 和报告中说明；后续不得再就地改 v1。
- 已形成交付提交 `75422c4`；此后仅剩 `results-server.tar.gz` 与开题报告 docx 两个
  本地未跟踪文件，Git 提交记录本身是 R2 的交付物之一。

### 4.5 文档时效

- 本轮（2026-11-03 R3 交接准备）已刷新 README、`handoff_gpu_server.md`、
  `r2_delivery.md` 与 `route_v2_hunan_illegal_land.md` 中的 GPU 状态与测试数；
  `handoff_gpu_server.md` 已改为 32 项，`r2_delivery.md` 已区分 29 项（当时）与 32 项（收尾后）。
- 已形成交付提交 `75422c4`；后续文档若再改动，追加小提交而非改写该基线。

## 5. 后续怎么做

### 5.1 P0：本周必须闭环（R2 主责）

| 序号 | 任务 | 具体动作 | 验收标准 |
|---|---|---|---|
| P0-1 | 提交当前工作区 | 逐项审查 `git status`，提交源码、测试、脚本、文档、CHANGELOG、正式日志；`results-server.tar.gz` 与权重/索引不入库 | 已完成，交接提交 `75422c4` |
| P0-2 | 重跑一键复现 | 在 GPU 节点执行 `python scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3 --run-id repro-server-2` | 5/5 步成功；单测为 32 项；新日志写入 `logs/` |
| P0-3 | 刷新文档 | 统一 README、`r2_delivery.md`、`handoff_gpu_server.md`、CHANGELOG 中的测试数、GPU 状态、复现记录 | 已完成，见 `75422c4` 及后续文档提交 |
| P0-4 | 确认评测主线 | 与 R1/R3 明确：期末以 v1 全领域为主，还是以 v2 湖南案例为主；两者评测集口径不同，不能混算 | 形成一句结论并写入 CHANGELOG/周会记录 |
| P0-5 | 准备正式重跑环境 | 确认 vLLM 服务、BGE-M3、索引 manifest、固定解码参数；确认 `mock=false` | `run_meta` 可复现，无调试嵌入器警告 |

### 5.2 P0：团队依赖（R2 配合，不替代）

| 任务 | 主责 | 前置 | R2 配合内容 |
|---|---|---|---|
| 交付 `data/eval/v1/questions.jsonl`（≥60 题，30/20/10） | R3 | 法规原文与引用格式 | 保证 `article_id`/`citation` 可精确匹配；提供检索调试入口 |
| 若走 v2 主线：把案件题扩到 ≥60，并完成 60 案 gold 切分 | R3 + R1 | 案例扩到 80~100 份 | 继续采集、解析、脱敏、版本化；提供防泄漏字段 |
| 正式主实验（2 次重复） | R1 | 评测集就绪、GPU 服务可用 | 执行 `run_experiment.py`/`run_case_experiment.py`，输出 `run_meta` 与日志 |
| LLM-as-judge、Recall@5、引用准确率、Kappa | R3 | 结果文件与参考答案 | 保证 `citations`、`evidence[].ranks`、`reference_citations` 字段齐全 |
| Streamlit 演示 | R4 | 稳定 CLI 与结果样例 | 提供 `ask`/`ask_case` 调用方式与离线回放样例 |

### 5.3 P1：R2 工程增强（正式实验前完成）

1. **案例扩容**：从 11 份扩到 80~100 份，按 `data/cases/v1/` 契约追加；
   保持来源 URL、采集时间、sha256、脱敏规则；同一案件不跨开发/评测集。
2. **补齐数据质量**：当前 4 案缺地类、8 案项目性质未知；能补则补，不能补则在系统中明确追问，
   不臆造罚款金额。
3. **三元组抽取升级**：由 R1 确认是否启用 `--method llm`；R2 负责批量运行、接入图谱索引，
   并由 R3 抽检 20%。若时间不够，则在报告中把“规则抽取”作为明确偏差说明。
4. **在线 Neo4j 演示**：在具备 Docker 的机器执行 `deploy/neo4j` 的 compose，导入 v2 Cypher，
   用 `verify_graph_export.py --neo4j-uri` 复核；密码只从 `NEO4J_PASSWORD` 读取。
5. **产物清理**：修正 `data/v2/graph/triples.stats.json` 中残留的 Windows 绝对路径；
   确认 `raw/` 与 `cases.jsonl` 的脱敏一致。

### 5.4 P2：收尾与可选扩展

1. **语料扩容（可选）**：如坚持开题的 2 万~5 万块目标，新增 v3 目录（部门规章、地方性法规），
   重新切分/索引/图谱，不修改 v1；同时在报告中对比 v1/v2/v3 的口径。
2. **v1 正式实验（可选）**：若团队决定保留全领域主线，等 R3 交付题库后运行
   `python -m legal_rag.pipeline.run_experiment --questions data/eval/v1/questions.jsonl --groups G0,G1,G2 --repeats 2 --run-id main-v1`。
3. **最终归档**：重跑 `reproduce.py`、案例校验、图谱校验；打包 `results/`、`logs/`、
   两份 `index_manifest.json`；更新 `docs/r2_delivery.md` 的最终状态。
4. **答辩支撑**：准备“已完成/未完成/偏差”一页纸；演示优先用离线回放，
   避免现场依赖 GPU 与网络。

## 6. R2 验收清单

- [x] 工作区已提交（`75422c4`），仅剩 `results-server.tar.gz` 与开题报告 docx 两个约定不入库文件；无权重、索引缓存、密钥、`.env` 入库。
- [ ] `python -m unittest discover -s tests` 通过（当前 32 项）。
- [ ] `reproduce.py` 以 BGE-M3 非 mock 重跑成功，日志与当前代码一致。
- [ ] v1/v2 图谱 `verify_graph_export.py` 各 21 项校验 0 失败。
- [ ] `case-main-v1`（或重跑后的新 run）通过 `validate_case_results.py`。
- [ ] `README`、`r2_delivery.md`、`handoff_gpu_server.md`、`CHANGELOG.md` 数字一致。
- [ ] 正式实验 `run_meta` 满足：`mock=false`、BGE-M3/1024、固定解码参数、索引 manifest 匹配。
- [ ] v1 语料未被再次就地改写；如需扩容，新建版本。
- [ ] 在线 Neo4j 若用于演示，已用 `NEO4J_PASSWORD` 启动并完成计数复核。

## 7. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 评测集继续延期 | 无法支撑 H1，正式实验无法启动 | R2 先把工程与复现做扎实；R1/R3 并行出题；必要时先用 v2 17 题做工程验收，不写统计结论 |
| 案例扩不到 80~100 | v2 统计功效不足 | 如实说明试点规模；优先保证 60 题评测集与 2 次重复；不虚构样本 |
| 共享 GPU 不可用 | 无法重跑正式实验 | 保留 `case-main-v1` 留档；提前预约 GPU；本机只做 CPU 检索与 mock 联调 |
| 在线 Neo4j 无法启动 | 演示缺图谱可视化 | 用离线 `GraphIndex` 与 Cypher 文件演示；Docker 环境另找机器 |
| 文档数字再次漂移 | 验收对不上 | 所有数字以 manifest/run_meta/日志为准；提交前跑一遍校验清单 |
| v1 被误改 | 破坏冻结版本 | 任何 v1 变更先写 CHANGELOG；扩容走新版本目录 |

## 8. 演示可行性（无 GPU 本机）

| 方案 | 可行性 | 前提 |
|---|---|---|
| 离线回放已有结果 | 可行 | 直接展示 `results/case-main-v1/`、`results/repro-server-1/` 与校验脚本 |
| CPU 检索 + 远程 vLLM | 可行 | 本机把 `embedding.device` 改为 `cpu`；通过 SSH 隧道连 GPU 节点的 vLLM；需网络 |
| 本机完整 7B 生成 | 不可行 | 无 GPU；不建议用 0.5B 结果冒充正式结果 |

## 9. 证据索引

- 开题报告：`大模型开题报告-法规RAG智能问答系统-第九组.docx`
- v2 路线与限制：`docs/route_v2_hunan_illegal_land.md`
- R2 交付说明：`docs/r2_delivery.md`
- GPU 运行手册：`docs/handoff_gpu_server.md`
- 接口契约：`docs/data_contract.md`
- 变更日志：`CHANGELOG.md`
- R3 交接说明：`docs/r3_handoff.md`
- 正式案例结果：`results/case-main-v1/`（5 组 × 17 题，旧版 771 项/当前 774 项校验）
- v1 dev 对照：`results/dev-server-v1/`（非正式）
- 全流程复现：`results/repro-server-1/`、`logs/reproduce_20261103-184956.{json,log}`
- 图谱导入校验：`logs/neo4j_import_v1.json`、`logs/neo4j_import_v2.json`
- 索引清单：`data/v1/index/index_manifest.json`、`data/v2/index/index_manifest.json`
- 案例与题目：`data/cases/v1/cases.jsonl`、`data/cases/v1/questions.jsonl`
- 校验脚本：`scripts/validate_case_results.py`、`scripts/verify_graph_export.py`
