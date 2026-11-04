# R2（工程与数据）交付说明

对应开题报告第九组 R2 职责。本文说明**已交付什么、证据在哪、还差什么、如何在 GPU 节点收尾**，
供组长、R1（实验）与 R3（评测）核对。

> **v2 试点（2026-10-31）**：按开题答辩反馈，范围收窄为“湖南省·非法占地行政处罚”。
> 新增 `data/v2/`（11 部、597 条）与 `data/cases/v1/`（11 案、17 题），
> 五步案件问答与 `G0/G1/G2/G2-case/G2-graph` 已在本机 mock 打通。
> 详见 `docs/route_v2_hunan_illegal_land.md` 与 `CHANGELOG.md`；
> 下文第一至六节为 v1 法规 RAG 的交付说明，仍然有效。
>
> **GPU 节点正式运行（2026-11-03）**：v2 已用 BGE-M3 + Qwen2.5-7B-Instruct（AWQ int4）
> 完成 `case-main-v1`（5 组 × 17 题，旧版脚本 771 项校验 0 失败，当前脚本 774 项 0 失败）；
> v1 正式题库仍未交付，仅用 dev 集完成 `dev-server-v1` 对照。详见 `CHANGELOG.md`。
> **R3 交接（2026-11-03）**：R3 请先读 `docs/r3_handoff.md`；案例校验器已支持可变题库/案例规模。

## 一、交付物对照

| # | 开题报告 R2 交付物 | 状态 | 证据 / 入口 |
|---|---|---|---|
| 1 | 法规语料采集与版本化 | 完成 | `config/corpus_catalog.yaml`、`data/v1/manifest.json`、`data/v1/raw/`、`data/v1/meta/`、`CHANGELOG.md` |
| 2 | 按条切分语料 | 完成 | `src/legal_rag/corpus/article_parser.py`、`data/v1/articles.jsonl`（4,104 条） |
| 3 | BGE-M3 向量化 + Chroma 构建 | 完成（2026-11-03 GPU 节点） | v1 4,104 条 / v2 597 条，BGE-M3 1024 维；`data/v1/index/`、`data/v2/index/` 的 index_manifest |
| 4 | Neo4j 图谱构建 | 完成（Cypher + 嵌入式 Neo4j 实际导入校验） | v1 29,128 语句 / v2 4,890 语句；`scripts/verify_graph_export.py`；`logs/neo4j_import_v1.json`、`logs/neo4j_import_v2.json` |
| 5 | 检索-生成流水线 | 完成并联调 | `src/legal_rag/retrieval/`、`pipeline/`、`generation/`；G0/G1/G2 |
| 6 | 推理服务部署 | 完成（vLLM + AWQ int4） | OpenAI 兼容客户端，`base_url=http://127.0.0.1:8000/v1`，`Qwen/Qwen2.5-7B-Instruct` |
| 7 | 可复现运行脚本 | 完成 | `scripts/reproduce.py`；GPU 节点记录 `logs/reproduce_20261103-184956.json` |
| 8 | Git 提交记录 | 已完成 | 交付提交 `75422c4`；历史提交 `fac7de4`、`a985187`、`d3908a6`、`980da77` |
| 9 | 全流程重跑记录 | GPU 节点复现完成 | `repro-server-1`（5/5 步，211.3s）、`case-main-v1`、`dev-server-v1` |
| 10 | 语料变更登记 | 完成 | `CHANGELOG.md`（v1，含 12 部缺失清单） |

## 二、关键数字（均为实测，可直接引用）

| 指标 | 数值 |
|---|---|
| 法规目录 / 成功采集 / 缺失 / 错误 | 87 / 75 / 12 / 0 |
| 可索引法规 | 75 部（法律 29、行政法规 29、地方性法规 17） |
| 按条文本块 | 4,104 条 |
| 语料正文规模 | 519,496 字（约 51.9 万字） |
| 条均 / 最短 / 最长 | 126.6 / 16 / 1,131 字 |
| 结构告警 | 0（条号单调、无重复、首条为第 1 条、无空正文） |
| 图谱覆盖 | 3,476 条法条（84.7%）；Neo4j 类型化实体 630 个（主体 29 + 行为 35 + 处罚 566） |
| Neo4j Cypher | v1 29,128 条 / v2 4,890 条语句 |
| Neo4j 实际导入 | v1 4,106 节点 / 25,648 关系；v2 707 节点 / 4,327 关系；21 项校验 0 失败 |
| 单元测试 | v1 11 项；含 v2 案例层与图谱导出回归，全仓 32 项通过 |
| 本地一键复现 | 5 步全部成功，14.2s（hashing + mock） |
| v2 正式索引 | BGE-M3 1024 维，597 条，built_at 2026-11-03T18:03:05+08:00 |
| v1 正式索引 | BGE-M3 1024 维，4,104 条，built_at 2026-11-03T18:51:02+08:00 |
| v2 正式案件实验 | `case-main-v1`：5 组 × 17 题 = 85 条，19.5 分钟；旧版脚本 771 项、当前脚本 774 项校验 0 失败 |
| v1 dev 对照 | `dev-server-v1`：7 题 × 3 组 × 2 = 42 条（**非正式**，v1 题库未交付） |
| GPU 全流程复现 | `repro-server-1`：5/5 步成功，211.3s（BGE-M3，非 mock） |

> 与开题报告“2 万~5 万文本块”的差异已在 `CHANGELOG.md` 说明：检索单位固定为“条”，
> 目录仅 75 部现行有效法规，实际 4,104 条；未通过拆条或复制文本虚增规模。

## 三、本地已完成的验证

```bash
export PYTHONPATH=src
PY="E:/演绎/LLM/第二次作业/rag_home/.venv/Scripts/python.exe"

# 单元测试（32 项）
$PY -m unittest discover -s tests -v

# 一键复现（调试嵌入器 + 模拟生成器）
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1

# 图谱导出结构校验（无需 Neo4j 服务）
$PY scripts/verify_graph_export.py \
  --triples data/v1/graph/triples.jsonl \
  --cypher data/v1/graph/neo4j_import.cypher

# 单条问答（真实 0.5B，仅验证链路）
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2
```

已验证内容：
- 采集端可断点续跑，WAF 返回非 JSON 时自动冷却重试；docx 校验 ZIP 魔数。
- 按条解析正确跳过目录、保留条内款/项；章/节/条号元数据齐全。
- 检索：口语化问题“村里盖房子占了农用地要办什么手续”在 G1/G2 首位命中
  《中华人民共和国土地管理法》第六十二条。
- G0 无证据、G1 五条证据、G2 额外注入图谱一跳子图（7 题上下文 313~438 字符）；
  mock 与 0.5B 均能跑通完整流水线，结果字段与 `docs/data_contract.md` 一致。
- 0.5B 模型答案方向正确，但未稳定输出“《法规名》第X条”格式；
  引用准确率必须用正式 Qwen2.5-7B-Instruct 评测，不能以 0.5B 结果代替。

## 四、GPU 节点执行记录（2026-11-03）

1. **正式索引**：v2 与 v1 均用 `BAAI/bge-m3` 重建，1024 维、debug=false。
   v2 为 597 条（18:03:05），v1 为 4,104 条（18:51:02，由复现脚本重建）。

2. **生成服务**：vLLM 0.6.3.post1 加载 `Qwen/Qwen2.5-7B-Instruct` 的 AWQ int4 权重，
   OpenAI 兼容端点 `http://127.0.0.1:8000/v1`；共享 GPU 显存不足，故未用 bf16 原权重。
   启动参数与量化标记已写入 `config/settings*.yaml` 与 `run_meta.generation_service`。

3. **v2 正式案件实验**（主线）：

   ```bash
   export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
   $PY -m legal_rag.pipeline.run_case_experiment \
     --groups G0,G1,G2,G2-case,G2-graph --run-id case-main-v1
   ```

   结果：85 条（5 组 × 17 题），19.5 分钟；`scripts/validate_case_results.py`
   旧版脚本 771 项检查 0 失败（当前校验器 774 项），无调试嵌入器/模型不一致警告。逐题期望（罚款区间、历史版本、
   缺地类、部分区间、排除题）全部命中。

4. **v1 对照**：正式题库 `data/eval/v1/questions.jsonl` 未交付（R3 阻塞），
   按 handoff 改用 dev 集 7 题 × G0/G1/G2 × repeats=2，运行号 `dev-server-v1`；
   结果标注 dev，不进入正式结果表。

5. **全流程复现与归档**：

   ```bash
   $PY scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3 --run-id repro-server-1
   tar -czf results-server.tar.gz results logs data/v2/index/index_manifest.json data/v1/index/index_manifest.json
   ```

   5/5 步成功（当时 29 项单测；收尾后全仓 32 项），211.3s；日志
   `logs/reproduce_20261103-184956.{json,log}`。

6. **Neo4j 图谱与导入校验**：v1/v2 Cypher 已重新生成（29,128 / 4,890 条语句），
   并用 Neo4j 5.26.0 嵌入式实例实际导入：
   v1 4,106 节点 / 25,648 关系，v2 707 节点 / 4,327 关系；`scripts/verify_graph_export.py`
   对 triples/Cypher/DB 计数做 21 项校验，全部通过（`logs/neo4j_import_v1.json`、
   `logs/neo4j_import_v2.json`）。Docker 在线服务因当前节点无 `docker` 组权限未启动；
   演示环境仍按 `deploy/neo4j` 的 compose 启动，密码只从 `NEO4J_PASSWORD` 读取。

## 五、风险与边界

- **规模**：4,104 条低于开题预估，属于真实测量结果；若需扩大，优先补充部门规章与
  地方性法规到 `config/corpus_catalog.yaml`，切分与索引代码无需改动。
- **12 部缺失法规**：FLK 无同名现行有效版本（`sxx=3`），未用近似标题或失效文本替代；
  清单与原因见 `CHANGELOG.md` 和 `data/v1/manifest.json`。
- **索引口径**：GPU 节点 v1/v2 均为 BGE-M3 1024 维正式索引；hashing 索引只用于本机联调，
  不得与正式结果混用。
- **推理量化**：正式实验使用 AWQ int4 权重（共享 GPU 显存限制），服务名仍为
  `Qwen/Qwen2.5-7B-Instruct`；量化标记见 `run_meta.generation_service`。
- **v1 正式题库缺失**：`data/eval/v1/questions.jsonl` 未交付，`dev-server-v1` 仅为 dev 链路对照，
  不能作为 v1 正式结果。
- **Chroma 路径**：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\09e06fb173`；换机器重建即可，清单记录了实际路径。
- **Neo4j 在线服务未启动**：图谱 Cypher 已用嵌入式 Neo4j 5.26 实际导入并校验计数；
  当前 GPU 节点没有 `docker` 组权限，未启动 `deploy/neo4j` 的在线容器。G2 实验使用
  离线 GraphIndex，不依赖 Neo4j，因此不影响实验复现；演示时再启动容器即可。
- **图谱排序口径**：2026-11-03 收尾时把 `GraphIndex` 的同分邻居改为按 `article_id`
  稳定排序，并修复 Cypher 字符串换行转义。`case-main-v1` 生成于该修复之前；
  若 R1 需要逐字复现旧 G2 图谱上下文，应以 `results/case-main-v1/` 留档为准；
  正式 v1 `main-v1` 应使用修复后的代码。
- **裁量基准未进检索库**：`湘自资规〔2022〕1号` 的罚款档位目前硬编码在
  `src/legal_rag/cases/schema.py:DISCRETION_BRACKETS`，`data/v2/articles.jsonl` 未收录该文件，
  案例 `penalty_basis_articles` 也未引用它。R3 计算引用准确率时需把政策文件作为外部依据
  单独统计，不能直接判为“编造条文”；处理口径见 `docs/r3_handoff.md` 第 4.1 节。

## 六、与 R1 / R3 的接口

> R3 的完整交接包、结果字段用法、指标口径与已知缺口见 `docs/r3_handoff.md`。

- R3 提供正式题库 `data/eval/v1/questions.jsonl`（字段 `id/category/question`）；
  R1 用 `run_experiment.py` 产出 `results/<run_id>/<group>_r<repeat>.jsonl` 与 `run_meta.json`。
- 每条结果包含 `answer`、`evidence[].citation/article_id/score/ranks/graph`、
  `graph_context`、`prompt_hash`、`usage`、`latency`；评测脚本按 `article_id`/citation
  计算 Recall@5 与引用准确率。
- 正式实验前置校验：`run_meta.json.index_manifest.embedding_model` 必须为 BGE-M3 且
  `mock=false`；否则结果只能标记为流程验证。
- v2 正式结果消费入口：`results/case-main-v1/`（5 组 × 17 题）与
  `scripts/validate_case_results.py`。校验器已按题库/案例/图谱 stats/索引 manifest
  自动取数，R3 扩题后可传 `--questions`、`--cases` 校验新 run；
  v1 正式题库到位后再跑 `main-v1`。
- 图谱交付校验：`scripts/verify_graph_export.py` 可对比 `triples.jsonl`、Cypher 与
  已导入 Neo4j 的节点/关系计数；有在线 Neo4j 时传 `--neo4j-uri` 即可复核。
- 结果格式 2.1：`citations` 为对象数组，另有 `citation_strings` 供按引用串匹配。
- 字段契约详见 `docs/data_contract.md`；变更接口须同步更新该文件与 `CHANGELOG.md`。
