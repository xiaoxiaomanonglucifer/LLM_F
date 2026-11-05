# 国土资源法律法规 RAG 智能问答系统（第 9 组）

课程项目《大模型实战实践》的工程底座，由 R2（工程与数据）维护：
法规语料采集与版本化 → 按条切分 → 向量/关键词/图谱索引 → 混合检索 →
带条文引用的生成 → G0/G1/G2 对照实验输出。

当前语料版本为 **v1**（2026-11-05 建成）：

- 178 部现行有效法规、10,069 条、1,273,548 字；法律 52、行政法规 86、地方性法规 40。
  其中全国性法规 138 部（8,241 条）、云南省地方性法规 15 部（764 条）、
  昆明市地方性法规 25 部（1,064 条）。
- 索引为 BGE-M3 1024 维、10,069 条，`embedding_model_debug=false`，
  集合 `legal_articles_v1`。
- 图谱为 `Qwen/Qwen2.5-7B-Instruct` LLM 抽取，正式文件
  `data/v1/graph/triples.jsonl`：8,943 条三元组（覆盖 88.82%），
  10,737 个实体（主体 3,198、行为 7,406、处罚 133）；Cypher 68,707 条语句，
  11 项结构校验 0 失败，规则兜底 3 条。
- 仓库内只有 `data/eval/dev/questions.jsonl`（7 题，联调用）；正式评测集
  `data/eval/v1/questions.jsonl`（≥60 题）由 R3 交付，正式主实验待跑。
- 原 75 部 / 4,104 条旧快照及其索引、图谱、结果已于 2026-11-05 删除，
  当前 `data/v1/` 即唯一交付版本。

交付对照见 `docs/r2_delivery.md`，R3 评测交接见
[`docs/r3_handoff.md`](docs/r3_handoff.md)，接口字段见
[`docs/data_contract.md`](docs/data_contract.md)，语料与索引变更见 `CHANGELOG.md`。

## 目录结构

```
config/             settings.yaml（当前配置）、corpus_catalog.yaml（178 部目录）
data/v1/            v1 语料：raw/*.docx、meta/*.json、manifest.json、
                    documents.jsonl、articles.jsonl、corpus_stats.json、
                    index/（Chroma + BM25 + manifest）、graph/triples.jsonl（LLM 抽取）
data/eval/dev/      流程联调用小题集（非正式评测集，正式集由 R3 交付 data/eval/v1/）
results/            本机 dev 冒烟：dev-v1-smoke（mock）、dev-v1-llm（真实生成，未入库）
scripts/            reproduce.py（一键复现）、verify_graph_export.py（图谱导出校验）
docs/               data_contract.md（接口契约）、r2_delivery.md（R2 交付说明）、
                    r3_handoff.md（R3 评测交接）
CHANGELOG.md        语料/索引/图谱/流水线变更登记
src/legal_rag/
  corpus/           FLK 客户端、docx 读取、按条解析、语料构建
  index/            BGE-M3 封装、Chroma、BM25、索引构建
  retrieval/        查询重写、RRF 融合、混合检索
  graph/            三元组 schema/抽取、离线图谱索引、Neo4j 导出导入
  generation/       提示词模板、LLM 客户端
  pipeline/         法规问答、G0/G1/G2 实验执行器
deploy/neo4j/       Neo4j Community docker-compose 与 .env 模板
tests/              标准库 unittest（14 项）
```

## 快速开始

```bash
# 0. 环境（本机复用已有 venv；新机器按 requirements.txt 安装）
export PYTHONPATH=src
export LEGAL_RAG_SETTINGS=config/settings.yaml
PY="<你的 Python 解释器>"
# GPU 节点示例：PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

# 1. 采集法规（支持断点续跑；已有 raw+meta 的会跳过）
$PY -m legal_rag.corpus.collect --min-docs 178

# 2. 按条切分
$PY -m legal_rag.corpus.build

# 3. 三元组抽取（正式产物为 LLM 抽取；无模型服务时用 --method rule 生成对照版）
$PY -m legal_rag.graph.extract --method llm --workers 4 \
  --out data/v1/graph/triples.jsonl

# 4. 构建索引（正式实验用 BGE-M3；本地无权重时用 --embedding-model 覆盖）
$PY -m legal_rag.index.build_index
# 本地流程验证（调试嵌入器，512 维，结果不得作为正式数据）：
$PY -m legal_rag.index.build_index --embedding-model hashing

# 5. 对照实验（先用 dev 题库 + 模拟生成器联调）
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl --groups G0,G1,G2 --mock --run-id dev-mock
# 正式跑（需 vLLM/Ollama 已启动且模型一致）：
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/v1/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id main-v1

# 6. 单题问答（G0 无检索；G1 稠密 + BM25；G2 再加图谱）
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2 --show-evidence

# 7. 测试（tests/ 无 __init__.py，需从 tests/ 目录运行）
cd tests && PYTHONPATH=../src $PY test_core.py && cd ..

# 8. 一键复现（采集可选跳过，自动跑切分/图谱/索引/测试/dev 实验）
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1
```

> `data/v1/index/chroma/`、`data/v1/index/*.pkl` 与 `*.progress.jsonl` 默认不入库；
> 新机器拉取后需按第 4 步重建索引。
> 图谱抽取默认写 `triples_llm.jsonl`，正式化时用 `--out` 指定
> `data/v1/graph/triples.jsonl`（本仓库已按此生成正式文件）。
> 无外网时，加载已缓存的 BGE-M3 需设置 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`。

## 实验归因控制（硬约束）

- G0/G1/G2 使用**同一生成器、同一解码参数、同一提示词模板**，唯一变量是检索信号：
  G0 无检索；G1 稠密 + BM25；G2 稠密 + BM25 + 图谱一跳子图。
- G0 不引用条文；无可靠依据时应明确说明“现有知识库中没有找到条文依据”。
- 解码参数固定在 `config/settings.yaml`：`temperature=0.1, top_p=0.9, seed=42,
  max_new_tokens=1024`；检索参数 `top_k=5, candidate_k=30, rrf_k=60`。
- 每条结果记录 `prompt_hash`、`decoding_params`、检索证据与名次，`run_meta.json` 记录配置快照。
- 正式实验必须使用索引清单中记录的嵌入模型；若命令行覆盖模型，程序会打印警告，
  该结果只能用于流程验证。

## 语料与合规

- 来源：国家法律法规数据库（flk.npc.gov.cn）；自然资源部政策文本未纳入。
- 范围：全国性国土资源相关法律/行政法规 + 云南省/昆明市相关地方性法规；
  选择以与土地、矿产、水、森林、草原、湿地、海洋、能源、生态环境、
  国土空间规划及资源行政执法相关的现行有效文本为准。
- 依据《著作权法》第五条，法律法规及国家机关行政性文件不适用著作权法，可自由复制、
  分发与加工。
- 语料按 `data/v1/` 版本管理，任何变更写入 `CHANGELOG.md`（原因、时间、操作人）。
- 后续扩数据应新建版本目录并登记，不在当前 `data/v1/` 就地改写。

## 运行环境说明

- 本机为 CPU、离线 pip；正式实验的 BGE-M3 与 Qwen2.5-7B-Instruct 在 GPU 节点运行。
- 本机无可用嵌入权重时，流程验证改用 `HashingEmbedder`（`--embedding-model hashing`，
  512 维确定性特征哈希），索引清单会标记 `embedding_model_debug=true`；
  **不得与 BGE-M3 的正式实验结果混用**，正式实验前必须重建索引。
- 生成服务通过 OpenAI 兼容接口接入：Ollama 默认 `http://127.0.0.1:11434/v1`，
  vLLM 改为其 `/v1` 地址即可，模型名与解码参数不变。
- Neo4j 为可选在线组件：G2 的图谱信号由 `triples.jsonl` 离线构建，保证实验可复现；
  `python -m legal_rag.graph.export_neo4j --import` 可导入 Neo4j 供演示与查询。

## 接口契约

R1（实验）、R3（评测）与本仓库的接口见 `docs/data_contract.md`。
