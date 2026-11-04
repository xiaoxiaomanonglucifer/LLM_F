# 服务器（GPU 节点）交接文档（v1）

维护人：R2 曾平 ｜ 更新日期：2026-11-04 ｜ 当前主线：v1 全国国土资源法规 RAG
R3 评测交接见 `docs/r3_handoff.md`

本文是**在 GPU 节点上把 v1 跑通并产出正式实验结果的唯一入口**。
细节口径见文末「文档索引」，冲突时以本文的命令与验收清单为准。

---

## 0. 一句话项目状态

国土资源法律法规 RAG 问答系统（云南大学《大模型实战实践》第 9 组）。
v1 语料已冻结（75 部 / 4,104 条 / 519,496 字），BGE-M3 正式索引与法条图谱已完成；
2026-11-03 在 GPU 节点用 Qwen2.5-7B-Instruct（AWQ int4）完成 7 题 dev 集对照。
**正式评测集 `data/eval/v1/questions.jsonl` 尚未交付，`main-v1` 正式主实验待 R3/R1。**

| 项 | 已验证值 |
|---|---|
| v1 语料 | 75 部 / 4,104 条 / 519,496 字，结构告警 0 |
| 分级 | 法律 29、行政法规 29、地方性法规 17 |
| v1 图谱 | 3,476 条三元组（84.7% 覆盖），630 个类型化实体 |
| Neo4j Cypher | 29,128 条语句；实际导入 4,106 节点 / 25,648 关系 |
| 索引 | BGE-M3 / 1024 维 / 4,104 条，`embedding_model_debug=false` |
| dev 评测集 | `data/eval/dev/questions.jsonl`（7 题，联调用） |
| 正式评测集 | **尚未交付**，待 R3 写入 `data/eval/v1/questions.jsonl`（≥60 题） |
| 单元测试 | 14 项 |

---

## 1. 需要传什么到服务器

**只需 git 跟踪的内容，约 16 MB。** 索引缓存、结果、日志、模型权重都不传（可重建或不该入库）。

### 1.1 必传（都在版本控制内）

```
config/          settings.yaml, corpus_catalog.yaml
src/legal_rag/   全部模块（corpus / index / retrieval / graph / generation / pipeline）
tests/           test_core.py（14 项）
scripts/         reproduce.py, verify_graph_export.py
docs/            data_contract.md, r2_delivery.md, r3_handoff.md, 本文
deploy/neo4j/    docker-compose.yml, .env.example
data/v1/         raw/*.docx(75), meta/*.json, manifest.json, documents.jsonl,
                 articles.jsonl, corpus_stats.json, graph/triples.jsonl,
                 graph/neo4j_import.cypher, index/index_manifest.json
data/eval/dev/   questions.jsonl
CHANGELOG.md  README.md  requirements.txt  .gitignore
```

> **必须传 `data/v1/raw/`**：FLK 在服务器上可能抓取失败或有 WAF，
> 原始文件是复现的锚点。正常流程用 `--skip-collect`，不要重新采集。

### 1.2 明确不传

| 不传的东西 | 原因 |
|---|---|
| `data/v1/index/chroma/`、`data/v1/index/*.pkl` | `.gitignore` 已排除；到服务器重建 |
| `results/` | `.gitignore` 已排除；需要时单独拷贝或重跑 |
| `models/` | `.gitignore` 已排除，权重不入库 |
| `.env`、任何密钥 | 永远不入库、不上传。`NEO4J_PASSWORD` 只从环境变量读 |
| `.venv/`、`__pycache__/` | 服务器自建 |

### 1.3 拉取或打包

```bash
git clone https://github.com/xiaoxiaomanonglucifer/LLM_F.git
cd LLM_F
git log -1 --oneline
```

无 remote 时可用 `git archive --format=tar -o ../legal-rag.tar HEAD` 导出快照；
注意快照不含 `.git`，`run_meta.json` 的 `git_commit` 可能为 null。

---

## 2. 服务器环境准备

### 2.1 Python 与依赖

本机环境为 **Python 3.11.17**，服务器建议同版本（3.10+ 可用）。

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install "torch>=2.1" --index-url https://download.pytorch.org/whl/cu121   # 先装 CUDA 版 torch
pip install -r requirements.txt                                               # 其余依赖走 PyPI 镜像
```

> `requirements.txt` 里 torch 只写了 `>=2.1`，不指定 CUDA 构建；先单独装 cu121/cu124 版，
> 再跑 `-r requirements.txt` 就不会被 CPU 版覆盖。装完用
> `python -c "import torch;print(torch.__version__, torch.cuda.is_available())"` 确认为 `True`。

依赖要点：

- `rank_bm25` + `jieba` 是 BM25 的硬依赖（`src/legal_rag/index/bm25.py`），别漏。
- 解析 HTML 用标准库 `html.parser`，**不需要**装 bs4/lxml。
- `neo4j` 驱动只有做图谱导入演示时才需要。

### 2.2 模型权重

| 用途 | 模型 | 说明 |
|---|---|---|
| 检索嵌入 | `BAAI/bge-m3`（1024 维） | 首次运行会下载约 2.2 GB。HF 不通就 `export HF_ENDPOINT=https://hf-mirror.com`，或从 ModelScope 下到本地目录后用 `--embedding-model <绝对路径>` |
| 生成 | `Qwen2.5-7B-Instruct` | bf16 约 16 GB 显存；共享卡显存不足时用 AWQ int4 |

### 2.3 生成服务（OpenAI 兼容接口，二选一）

```bash
# A. Ollama
ollama pull qwen2.5:7b-instruct && ollama serve
# 然后把 config/settings.yaml 的 generation.base_url 改成 http://127.0.0.1:11434/v1

# B. vLLM（推荐）
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
# config/settings.yaml 已指向 http://127.0.0.1:8000/v1
```

代码只走 `openai` 客户端（`src/legal_rag/generation/llm_client.py`），`api_key` 缺省填
`not-needed`，**不要**往仓库里写任何真实 key。

---

## 3. 上服务器后要改的配置（改完必须登记 CHANGELOG.md）

打开 `config/settings.yaml`：

| 键 | 本机值 | 服务器值 |
|---|---|---|
| `embedding.device` | `cpu` | `cuda` |
| `generation.base_url` | `http://127.0.0.1:11434/v1` | 按 §2.3 选的服务改 |
| `generation.model` | `qwen2.5:7b-instruct` | 与服务实际暴露的模型名**严格一致** |
| `vector_store.path` 相关 | 中文路径自动回退到 `%LOCALAPPDATA%` | Linux 路径纯 ASCII，直接用仓库内 `data/v1/index/chroma` |

**不许改的**（一改实验归因就废了）：`generation.temperature=0.1`、`top_p=0.9`、`seed=42`、
`max_tokens=1024`、`retrieval.top_k=5`、`candidate_k=30`、`rrf_k=60`、
`bm25.k1=1.5`、`b=0.75`、`use_char_bigram=true`。

> `embedding.device` 有个坑：`build_index` 有 `--device` 命令行参数，但**实验时查询侧嵌入器
> 读的是 yaml 里的 `embedding.device`**（`run_experiment.build_runtime`）。所以一定要改 yaml，
> 只在建索引时加 `--device cuda` 是不够的。

CHANGELOG 登记格式照已有条目：日期、原因、操作人、影响范围。

---

## 4. 执行顺序（照着抄，每步都有校验点）

```bash
cd ~/legal-rag
export PYTHONPATH=src
PY=.venv/bin/python
```

### 第 1 步 冒烟：确认代码与环境没问题（不烧 GPU）

`bm25.pkl` 与 `chroma/` 不入库，服务器上是**没有索引**的，而实验会直接加载它们
（缺 `index_manifest.json` 或 `bm25.pkl` 会 `SystemExit`）。所以冒烟前先建一次调试索引。

```bash
$PY -m unittest discover -s tests -v                     # 期望：14 项 OK
$PY -m legal_rag.index.build_index --embedding-model hashing
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl --groups G0,G1,G2 \
  --mock --embedding-model hashing --run-id smoke-server
```

校验点：`results/smoke-server/run_meta.json` 里 `mock=true`、`git_commit` 非空、
`questions_count=7`。这一步不通过就不要继续往下走。

> 建完调试索引后，`data/v1/index/index_manifest.json` 会被覆盖成 hashing 版。
> 第 2 步建正式索引会再覆盖一次，最终以 BGE-M3 那份为准；**入库的清单文件别把 hashing 版带回去**。

### 第 2 步 建 v1 正式索引（BGE-M3）

```bash
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3 --device cuda
```

校验 `data/v1/index/index_manifest.json`，四项必须全中：

```
embedding_model       = BAAI/bge-m3
embedding_model_debug = false
embedding_dim         = 1024
article_count         = 4104
```

任一不符 → 这批结果只能标为流程验证，不能用。

### 第 3 步 真模型单题试跑（确认服务通了）

```bash
$PY -m legal_rag.pipeline.ask "村里盖房子占了农用地要办什么手续" --group G2 --show-evidence
```

看答案是否给出条文引用、G2 是否显示图谱上下文、证据名次是否合理。

### 第 4 步 v1 dev 对照（正式题库未到时）

```bash
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/dev/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id dev-server-v1
```

7 题 × 3 组 × 2 次 = 42 条；结果只能标为 dev，不能进正式结果表。

### 第 5 步 v1 正式主实验（R3 题库到位后）

```bash
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/v1/questions.jsonl \
  --groups G0,G1,G2 --repeats 2 --run-id main-v1
```

60 题 × 3 组 × 2 次 = 360 次调用。`--resume` 可断点续跑；
`results/<run_id>/<group>_r<repeat>.jsonl` 是逐题结果。

> **阻塞项**：`data/eval/v1/questions.jsonl` 目前不存在，正式题库由 R3 交付。

### 第 6 步 Neo4j 演示（可选，离线图谱索引已支撑实验）

```bash
$PY -m legal_rag.graph.export_neo4j          # 生成 data/v1/graph/neo4j_import.cypher

# 结构校验（不需要 Neo4j 服务）
$PY scripts/verify_graph_export.py \
  --triples data/v1/graph/triples.jsonl \
  --cypher data/v1/graph/neo4j_import.cypher \
  --db-counts logs/neo4j_import_v1.json

cd deploy/neo4j && cp .env.example .env      # 填 NEO4J_PASSWORD，确认 .env 不入库
docker compose up -d && cd ../..
$PY -m legal_rag.graph.export_neo4j --import # 需 pip install "neo4j>=5.20"
```

预期：4,106 节点 / 25,648 关系（Article 3,476 / Subject 29 / Action 35 / Penalty 566）。

### 第 7 步 全流程留档

```bash
$PY scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3 --run-id repro-server-1
```

回传后本机做三件事：① 把 `index_manifest.json` 覆盖回仓库（该文件入库）；
② 更新 `docs/r2_delivery.md` 的实测数字；③ 在 `CHANGELOG.md` 记正式索引与实验运行号。
`results/` 不入库，用网盘/群文件归档给 R1、R3。

---

## 5. 正式结果的验收清单（提交给 R1/R3 前逐条打勾）

- [ ] `run_meta.json.mock = false`，`git_commit` 非空，`index_manifest.embedding_model = BAAI/bge-m3` 且 `embedding_model_debug = false`
- [ ] `run_meta.json.decoding_params` = `temperature 0.1 / top_p 0.9 / seed 42 / max_tokens 1024`，且与 `prompt_version` 一起留痕
- [ ] 每条结果有 `answer`、`evidence[].article_id/citation/score/ranks`、`prompt_hash`、`usage`、`latency_sec`，字段与 `docs/data_contract.md` 一致
- [ ] 生成过程中**没有出现**「查询嵌入模型与索引模型不一致」警告
- [ ] G0 组：证据 0 条、`graph_context` 为空（设计如此，不是 bug）
- [ ] G1/G2 组：每题 5 条证据；G2 每题有图谱上下文
- [ ] 正式主实验 `repeats >= 2`，且 `questions_count >= 60`
- [ ] `questions_sha256` 与 `data/eval/v1/questions.jsonl` 实际哈希一致

---

## 6. 硬约束（这些是实验可信度的底线）

1. **单变量归因**：G0/G1/G2 必须同一生成器、同一解码参数、同一提示词模板，
   唯一变量是检索信号。换模型、改温度 = 实验作废。
2. **信号定义**（`config/settings.yaml`）：G0 无信号；G1 = dense + bm25；
   G2 = dense + bm25 + graph。
3. **G0 口径**：不检索、不引用；引用准确率/Recall@5 对 G0 记 N/A 或 0，报告中统一。
4. **合规**：只用公开法律法规文本；不提交权重、密钥、索引缓存。
5. **数据版本不可就地改写**：v1 已冻结。要扩充法规，新目录 + CHANGELOG 登记，
   别在 v1 上做覆盖。
6. **凭据**：`NEO4J_PASSWORD` 只从环境变量读；`.env` 已 gitignore。

---

## 7. 已知坑（本机踩过的，服务器别再踩）

| 现象 | 原因 / 处理 |
|---|---|
| Chroma 实际路径不在 `data/v1/index/chroma` | 仓库路径含中文时程序自动回退到 `%LOCALAPPDATA%\legal_rag\chroma\<hash>`。清单里 `path` 是实际路径、`configured_path` 是配置路径。Linux 下 ASCII 路径不会有这问题 |
| 检索结果异常但没报错 | 索引仍是 hashing 调试索引。跑实验前看 stderr 警告和 `index_manifest.embedding_model_debug` |
| 采集卡住 / 返回非 JSON | FLK 有 WAF。客户端已做冷却重试 + 断点续跑，但**服务器直接用 `--skip-collect`** |
| docx 校验失败 | 已校验 ZIP 魔数；非 docx 视为采集失败，不要手工绕过 |
| 换机器索引对不上 | 索引不入库，重建即可；重建前把 `articles.jsonl` 的 sha256 记下来比对（清单里有 `articles_sha256`） |
| G0 证据数为 0 被判失败 | 设计如此，逐题校验时 G0 单独归类 |
| 0.5B 小模型答案格式漂 | 方向对但不稳定输出「《法规名》第X条」。引用准确率**必须**用 Qwen2.5-7B-Instruct 测 |
| `reproduce.py` 只跑 v1 | 它串的是 采集/切分/三元组/索引/测试/dev 实验，这是当前唯一主线 |
| `scripts/reproduce.py --skip-collect` 在无网机器上仍报缺 raw | 确认 `data/v1/raw` 已传过去（75 个 docx） |

---

## 8. 还差什么（交接后的责任划分）

| 待办 | 归谁 | 说明 |
|---|---|---|
| 正式评测集 ≥60 题（30 简单 / 20 中等 / 10 困难） | R3 | 落到 `data/eval/v1/questions.jsonl`，字段 `id/category/question/reference_answer/reference_citations` |
| v1 正式主实验 `main-v1` | R2 执行 / R1 设计 | 等 R3 题库；G0/G1/G2 × repeats=2 |
| Recall@5、引用准确率、拒答率统计 | R3 | 按 `article_id` 与 citation 计算；消费 `results/<run_id>/*.jsonl` |
| 语料规模与开题报告不一致的解释口径 | R1/R4 | 实测 4,104 条 vs 报告预计 2万~5万 → 建议**改报告数字以对齐实测**，而不是拆条虚增 |
| 12 部缺失法规的补充 | R2 | 可扩充目录（部门规章、地方性法规）或改用官方最新标题重新采集 |
| 报告与 PPT 更新 | R4 | 数字以 `data/v1/corpus_stats.json` 和正式 `run_meta.json` 为准 |

---

## 9. 文档索引

- [README.md](../README.md) — 目录结构、快速开始、归因控制
- [docs/data_contract.md](data_contract.md) — 字段契约（改接口必读）
- [docs/r2_delivery.md](r2_delivery.md) — R2 交付对照与关键数字
- [docs/r3_handoff.md](r3_handoff.md) — R3 评测交接
- [docs/demo_manual.md](demo_manual.md) — 演示操作手册
- [CHANGELOG.md](../CHANGELOG.md) — 语料/索引/图谱/流水线变更登记
- 关键代码：[src/legal_rag/pipeline/run_experiment.py](../src/legal_rag/pipeline/run_experiment.py)、
  [src/legal_rag/pipeline/ask.py](../src/legal_rag/pipeline/ask.py)、
  [src/legal_rag/index/build_index.py](../src/legal_rag/index/build_index.py)、
  [src/legal_rag/config.py](../src/legal_rag/config.py)

遇到问题按这个顺序自查：`run_meta.json` → `index_manifest.json` → stderr 警告 → `docs/data_contract.md`。
