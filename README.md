# 国土资源法律法规 RAG 智能问答系统（第 9 组）

课程项目《大模型实战实践》的工程底座，由 R2（工程与数据）维护：
法规语料采集与版本化 → 按条切分 → 向量/关键词/图谱索引 → 混合检索 →
带条文引用的生成 → G0/G1/G2 对照实验输出。

当前快照：
- **v1（2026-10-27，冻结）**：75 部现行有效法规、4,104 条、51.9 万字；图谱覆盖 84.7% 法条。
- **v2（2026-10-31，试点）**：范围收窄为**湖南省·非法占地行政处罚**；
  `data/v2/` 11 部国家核心法 + 湖南地方立法、597 条；`data/cases/v1/` 11 份公开处罚决定书；
  案件图谱 30 节点/180 边；17 道案件评测题；G0/G1/G2/G2-case/G2-graph 五组流水线打通。
  2026-11-03 已在 GPU 节点用 BGE-M3 + Qwen2.5-7B-Instruct（AWQ int4）完成
  `case-main-v1`（5 组 × 17 题，当前校验器 774 项检查 0 失败）。正式评测集（≥60 题）
  与 2 次重复仍待 R3/R1 交付，当前结果不能直接支撑 H1 统计结论。

交付对照与待办见 `docs/r2_delivery.md`，R3 交接见
[`docs/r3_handoff.md`](docs/r3_handoff.md)，演示操作见
[`docs/demo_manual.md`](docs/demo_manual.md)，语料与索引变更见 `CHANGELOG.md`。
v2 路线、已确认边界与当前限制见
[`docs/route_v2_hunan_illegal_land.md`](docs/route_v2_hunan_illegal_land.md)。

## 目录结构

```
config/             settings.yaml（v1）、settings_v2.yaml（v2）、
                    corpus_catalog.yaml、corpus_catalog_v2.yaml、case_catalog.yaml
data/v1/            v1 冻结语料：raw/*.docx、meta/*.json、manifest.json、
                    documents.jsonl、articles.jsonl、corpus_stats.json、
                    index/（Chroma + BM25 + index_manifest.json）、graph/triples.jsonl
data/v2/            v2 语料：11 部国家核心法 + 湖南地方立法、597 条、
                    index/、graph/（与 v1 完全隔离）
data/cases/v1/      案例层：cases.jsonl、raw/*.txt、manifest.json、stats.json、
                    graph/（节点/边/三元组/Cypher）、questions.jsonl
data/eval/dev/      流程联调用小题集（非正式评测集，正式集由 R3 交付 data/eval/v1/）
scripts/            reproduce.py（一键复现）、demo_replay.py（无 GPU 离线回放）
docs/               data_contract.md（接口契约）、r2_delivery.md（R2 交付说明）、
                    r3_handoff.md（R3 评测交接）、demo_manual.md（演示操作手册）、
                    route_v2_hunan_illegal_land.md（答辩后 v2 路线、决策与实施状态）
CHANGELOG.md        语料/索引/图谱/流水线变更登记
src/legal_rag/
  corpus/           FLK 客户端、docx 读取、按条解析、语料构建
  index/            BGE-M3 封装、Chroma、BM25、索引构建
  retrieval/        查询重写、RRF 融合、混合检索
  graph/            三元组 schema/抽取、离线图谱索引、Neo4j 导出导入
  cases/            处罚决定书解析/脱敏、案例 schema、案件图谱、类案检索、五步问答
  generation/       提示词模板、LLM 客户端
  pipeline/         法规问答、案件五步问答、G0/G1/G2 与消融实验执行器
deploy/neo4j/       Neo4j Community docker-compose 与 .env 模板
tests/              标准库 unittest（含 v2 案例层测试）
```

## 快速开始

```bash
# 0. 环境（本机复用已有 venv；新机器按 requirements.txt 安装）
export PYTHONPATH=src
PY="<你的 Python 解释器>"
# GPU 节点示例：PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

# 1. 采集法规（支持断点续跑；已有 raw+meta 的会跳过）
$PY -m legal_rag.corpus.collect --min-docs 50

# 2. 按条切分
$PY -m legal_rag.corpus.build

# 3. 三元组抽取（默认规则抽取；GPU 节点可用 --method llm）
$PY -m legal_rag.graph.extract

# 4. 构建索引（正式实验用 BGE-M3；本地无权重时用 --embedding-model 覆盖）
$PY -m legal_rag.index.build_index
# 本地流程验证（调试嵌入器，512 维，结果不得作为正式数据）：
$PY -m legal_rag.index.build_index --embedding-model hashing

# 5. 对照实验（先用 dev 题库+模拟生成器联调）
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl --groups G0,G1,G2 --mock --run-id dev-mock
# 正式跑（需 Ollama/vLLM 已启动且模型一致）：
$PY -m legal_rag.pipeline.run_experiment --groups G0,G1,G2 --repeats 2 --run-id main-v1

# 5b. v2 案件五步问答（严格湖南；与 v1 索引隔离）
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
# 已有 data/v2 与 data/cases/v1 时可跳过前三步
$PY -m legal_rag.corpus.collect --min-docs 10  # 11 部国家核心法 + 湖南地方立法
$PY -m legal_rag.corpus.build
$PY -m legal_rag.index.build_index --embedding-model hashing  # 调试嵌入器
$PY -m legal_rag.cases.build                  # 采集/解析处罚决定书，重建 cases.jsonl
$PY -m legal_rag.cases.build_case_graph       # 重建案件图谱与 Cypher
$PY -m legal_rag.pipeline.run_case_experiment \
  --groups G0,G1,G2,G2-case,G2-graph --mock --run-id case-smoke
# 正式跑：去掉 --mock，确认索引清单为 BGE-M3 且模型服务已启动

# 5c. v2 单题五步问答（输出 facts/characterization/law_application/discretion/conclusion）
$PY -m legal_rag.pipeline.ask_case "未经批准占用永久基本农田建厂房会怎么罚" --group G2

# 6. 测试
$PY -m unittest discover -s tests -v

# 7. 一键复现（采集可选跳过，自动跑切分/图谱/索引/测试/实验）
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1
```

## 实验归因控制（硬约束）

- G0/G1/G2 使用**同一生成器、同一解码参数、同一提示词模板**，唯一变量是检索信号：
  G0 无检索；G1 稠密 + BM25；G2 稠密 + BM25 + 图谱一跳子图。
- v2 案件实验沿用同一归因原则：G0 无条文/类案/图谱；G1 法条检索 + 固定法条链；
  G2 再加相似案例与案件图谱；G2-case 去掉案例层；G2-graph 去掉法条图谱。
- G0 不引用条文、不检索类案、不计算罚款；历史行为（2021 年及以前）不套用现行裁量幅度。
- 解码参数固定在 `config/settings.yaml`：`temperature=0.1, top_p=0.9, seed=42, max_new_tokens=1024`。
- 每条结果记录 `prompt_hash`、`decoding_params`、检索证据与名次，`run_meta.json` 记录配置快照。
- 正式实验必须使用索引清单中记录的嵌入模型；若命令行覆盖模型，程序会打印警告，
  该结果只能用于流程验证。

## 语料与合规

- 来源：国家法律法规数据库（flk.npc.gov.cn）、自然资源部公开政策文本、
  湖南省自然资源厅及市州县公开行政处罚决定书/台账。
- 依据《著作权法》第五条，法律法规及国家机关行政性文件不适用著作权法，可自由复制、
  分发与加工。
- 案例只采集公开文书；入库前对个人姓名、证件号、电话脱敏，`raw/*.txt` 与
  `cases.jsonl` 保持一致；来源 URL 与原始页面哈希见 `data/cases/v1/manifest.json`。
- 语料按 `data/v1/`、`data/v2/`、`data/cases/v1/` 版本管理，任何变更写入
  `CHANGELOG.md`（原因、时间、操作人）。

## 运行环境说明

- 本机为 CPU、离线 pip；正式实验的 BGE-M3 与 Qwen2.5-7B-Instruct 在 GPU 节点运行。
- 本机无可用嵌入权重，流程验证改用 `HashingEmbedder`（`--embedding-model hashing`，
  512 维确定性特征哈希），索引清单会标记 `embedding_model_debug=true`；
  **不得与 BGE-M3 的正式实验结果混用**，正式实验前必须重建索引。
- 生成服务通过 OpenAI 兼容接口接入：Ollama 默认 `http://127.0.0.1:11434/v1`，
  vLLM 改为其 `/v1` 地址即可，模型名与解码参数不变。
- Neo4j 为可选在线组件：G2 的图谱信号由 `triples.jsonl` 离线构建，保证实验可复现；
  `python -m legal_rag.graph.export_neo4j --import` 可导入 Neo4j 供演示与查询。

## 接口契约

R1（实验）、R3（评测）与本仓库的接口见 `docs/data_contract.md`。
