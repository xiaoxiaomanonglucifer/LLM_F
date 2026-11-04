# 服务器（GPU 节点）交接文档

维护人：R2 曾平 ｜ 交接日期：2026-11-03 ｜ 代码状态：32 项单元测试通过；交付提交 `75422c4`；R3 评测交接见 `docs/r3_handoff.md`

本文是**在 GPU 节点上把项目跑通并产出正式实验结果的唯一入口**。
细节口径见文末「文档索引」，冲突时以本文的命令与验收清单为准。

---

## 0. 一句话项目状态

国土资源法律法规 RAG 问答系统（云南大学《大模型实战实践》第 9 组）。
v1 冻结（全国国土法规·法条问答），v2 是当前主线（**湖南·非法占地行政处罚·五步判断链**）。
本机为 CPU + 离线 pip；工程链路已用调试嵌入器（hashing）+ mock 生成器验证，
且 GPU 节点已于 2026-11-03 用 BGE-M3 + Qwen2.5-7B-Instruct 完成正式索引与
`case-main-v1`。**本机结果一律不得充当正式结论；正式结论以 GPU 节点
`mock=false` 且索引为 BGE-M3/1024 的结果为准。**

| 项 | 已验证值 |
|---|---|
| v1 语料 | 75 部 / 4,104 条 / 519,496 字，结构告警 0 |
| v2 语料 | 11 部 / 597 条 / 82,505 字（法律 3、行政法规 3、湖南地方性法规 5），结构告警 0 |
| v2 法条图谱 | 559 三元组 |
| 案例层 | 11 份湖南公开处罚决定书（9 未经批准占用 + 2 超过批准数量占用），7 案字段完整、4 案缺地类 |
| 案件图谱 | 30 节点 / 180 边 |
| 案件评测题 | 17 题（`data/cases/v1/questions.jsonl`） |
| v1 正式评测集 | **尚未交付**，仓库内只有 `data/eval/dev/questions.jsonl`（7 题，联调用） |
| 索引 | v1 4,104 条 / v2 597 条，均 BGE-M3 1024 维（2026-11-03 GPU 节点重建） |

> 2026-11-03 GPU 节点执行结果：v2 正式案件实验 `case-main-v1`（5 组 × 17 题，
> 旧版脚本 771 项 / 当前脚本 774 项校验 0 失败）、v1 dev 对照 `dev-server-v1`、
> 全流程复现 `repro-server-1` 均已完成。v1 正式题库仍缺，详见 `CHANGELOG.md`。

---

## 1. 需要传什么到服务器

**只需 git 跟踪的内容，约 16 MB。** 索引缓存、结果、日志、模型权重都不传（可重建或不该入库）。

### 1.1 必传（都在版本控制内）

```
config/          settings.yaml, settings_v2.yaml, corpus_catalog.yaml,
                 corpus_catalog_v2.yaml, case_catalog.yaml
src/legal_rag/   全部模块（corpus / index / retrieval / graph / cases / generation / pipeline）
tests/           test_core.py（14 项）、test_cases.py（18 项），共 32 项
scripts/         reproduce.py
docs/            data_contract.md, r2_delivery.md, route_v2_hunan_illegal_land.md, 本文
deploy/neo4j/    docker-compose.yml, .env.example
data/v1/         raw/*.docx(75), meta/*.json, manifest.json, documents.jsonl,
                 articles.jsonl, corpus_stats.json, graph/triples.jsonl,
                 index/index_manifest.json
data/v2/         同上结构（11 部）+ graph/
data/cases/v1/   cases.jsonl, raw/*.txt(11, 已脱敏), manifest.json, stats.json,
                 graph/, questions.jsonl
data/eval/dev/   questions.jsonl
CHANGELOG.md  README.md  requirements.txt  .gitignore
```

> **必须传 `data/*/raw/`**：FLK 与湖南自然资源局网站在服务器上可能抓取失败或有 WAF，
> 原始文件是复现的锚点。正常流程用 `--skip-collect`，不要重新采集。

### 1.2 明确不传

| 不传的东西 | 原因 |
|---|---|
| `data/*/index/chroma/`、`data/*/index/*.pkl` | `.gitignore` 已排除；本机是 hashing 调试索引，传过去反而误用。到服务器重建 |
| `results/`（4.6 MB，6 次 mock 运行） | `.gitignore` 已排除，本机结果仅作流程证明 |
| `logs/collect_v1.log`、`logs/download_bge_small.log` | 本机杂项日志（`logs/reproduce_*` 是例外，已入库） |
| `models/` | `.gitignore` 已排除，权重不入库 |
| `.env`、任何密钥 | 永远不入库、不上传。`NEO4J_PASSWORD` 只从环境变量读 |
| `.venv/`、`__pycache__/` | 服务器自建 |

### 1.3 打包命令（本机执行，无 git remote）

```bash
cd "E:/演绎/LLM/大作业"
git status --short          # 必须先为空
git archive --format=tar -o ../legal-rag-980da77.tar HEAD
ls -lh ../legal-rag-980da77.tar
```

服务器上解压：

```bash
mkdir -p ~/legal-rag && tar -xf legal-rag-980da77.tar -C ~/legal-rag
cd ~/legal-rag && find . -maxdepth 1
```

> 注意：`git archive` 导出的是快照，不含 `.git`。如果需要 `run_meta.json` 里记录真实
> `git_commit`，改为在服务器 `git init` 后提交一次，或把整个 `.git`（4.2 MB）一起传过去。
> **`_git_commit()` 取不到提交号时会写 null，正式实验要求该字段非空。**

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
> 再跑 `-r requirements.txt` 就不会被 CPU 版覆盖。装完用 `python -c "import torch;print(torch.__version__, torch.cuda.is_available())"` 确认为 `True`。

依赖要点：
- `rank_bm25` + `jieba` 是 BM25 的硬依赖（`src/legal_rag/index/bm25.py`），别漏。
- 解析 HTML 用标准库 `html.parser`，**不需要**装 bs4/lxml。
- `neo4j` 驱动只有做图谱导入演示时才需要，本机未装。

### 2.2 模型权重

| 用途 | 模型 | 说明 |
|---|---|---|
| 检索嵌入 | `BAAI/bge-m3`（1024 维） | 首次运行会下载约 2.2 GB。HF 不通就 `export HF_ENDPOINT=https://hf-mirror.com`，或从 ModelScope 下到本地目录后用 `--embedding-model <绝对路径>` |
| 生成 | `Qwen2.5-7B-Instruct` | bf16 约 16 GB 显存，**24 GB 卡可跑**（3090/4090/A5000/A100 都行） |

### 2.3 生成服务（OpenAI 兼容接口，二选一）

```bash
# A. Ollama（config/settings.yaml 默认指向它：http://127.0.0.1:11434/v1，model: qwen2.5:7b-instruct）
ollama pull qwen2.5:7b-instruct && ollama serve

# B. vLLM（更快，适合 530+ 次调用）
vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
# 然后把 generation.base_url 改成 http://127.0.0.1:8000/v1，model 改成 Qwen/Qwen2.5-7B-Instruct
```

代码只走 `openai` 客户端（`src/legal_rag/generation/llm_client.py`），`api_key` 缺省填 `not-needed`，
**不要**往仓库里写任何真实 key。

---

## 3. 上服务器后要改的配置（就 4 处，改完必须登记 CHANGELOG.md）

打开 `config/settings_v2.yaml`（v1 用 `config/settings.yaml`，改法一样）：

| 键 | 本机值 | 服务器值 |
|---|---|---|
| `embedding.device` | `cpu` | `cuda` |
| `generation.base_url` | `http://127.0.0.1:11434/v1` | 按 §2.3 选的服务改 |
| `generation.model` | `qwen2.5:7b-instruct` | 与服务实际暴露的模型名**严格一致** |
| `vector_store.path` 相关 | 中文路径自动回退到 `%LOCALAPPDATA%` | Linux 路径纯 ASCII，直接用仓库内 `data/v2/index/chroma` |

**不许改的**（一改实验归因就废了）：`generation.temperature=0.1`、`top_p=0.9`、`seed=42`、
`max_tokens=1024`、`retrieval.top_k=5`、`candidate_k=30`、`rrf_k=60`、`case_top_k=3`、
`bm25.k1=1.5`、`b=0.75`、`use_char_bigram=true`。

> `embedding.device` 有个坑：`build_index` 有 `--device` 命令行参数，但**实验时查询侧嵌入器
> 读的是 yaml 里的 `embedding.device`**（`run_experiment.build_runtime`）。所以一定要改 yaml，
> 只在建索引时加 `--device cuda` 是不够的。

CHANGELOG 登记格式照 `CHANGELOG.md` 已有条目：日期、原因、操作人、影响范围。

---

## 4. 执行顺序（照着抄，每步都有校验点）

全程先设环境变量；v2 与 v1 靠它隔离，忘了 export 就会串库。

```bash
cd ~/legal-rag
export PYTHONPATH=src
PY=.venv/bin/python
```

### 第 1 步 冒烟：确认代码与环境没问题（不烧 GPU）

`bm25.pkl` 与 `chroma/` 不入库，服务器上是**没有索引**的，而实验会直接加载它们
（缺 `index_manifest.json` 或 `bm25.pkl` 会 `SystemExit`）。所以冒烟前先建一次调试索引。

```bash
$PY -m unittest discover -s tests -v          # 期望：32 项 OK
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
$PY -m legal_rag.index.build_index --embedding-model hashing     # 调试索引，几分钟内完成
$PY -m legal_rag.pipeline.run_case_experiment --groups G0,G1,G2,G2-case,G2-graph \
  --mock --embedding-model hashing --run-id smoke-server
```

校验点：`results/smoke-server/run_meta.json` 里 `mock=true`、`git_commit` 非空、
`case_count=11`、`case_graph.nodes=30 / edges=180`、`questions_count=17`。
这一步不通过就不要继续往下走。

> 建完调试索引后，`data/v2/index/index_manifest.json` 会被覆盖成 hashing 版。
> 第 2 步建正式索引会再覆盖一次，最终以 BGE-M3 那份为准；**入库的清单文件别把 hashing 版带回去**。

### 第 2 步 建 v2 正式索引（BGE-M3）

```bash
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3 --device cuda
```

校验 `data/v2/index/index_manifest.json`，四项必须全中：

```
embedding_model       = BAAI/bge-m3
embedding_model_debug = false
embedding_dim         = 1024
article_count         = 597
```

任一不符 → 这批结果只能标为流程验证，不能用。

### 第 3 步 v2 真模型单题试跑（确认服务通了）

```bash
$PY -m legal_rag.pipeline.ask_case "未经批准占用永久基本农田建厂房会怎么罚" --group G2
```

`ask` 是 v1 单步问答；v2 案件问答用 `ask_case`，会输出
facts / characterization / law_application / discretion / conclusion 五步结构。
看答案是否给出条文引用、五步是否齐全。

### 第 4 步 v2 正式案件实验（主线，约 85~170 次生成调用）

```bash
$PY -m legal_rag.pipeline.run_case_experiment \
  --groups G0,G1,G2,G2-case,G2-graph --run-id case-main-v1
# 要跑 repeats=2 做稳定性对照，就加 --repeats 2（调用量翻倍，约 170 次）
```

`--resume` 可断点续跑；`results/<run_id>/<group>_r<repeat>.jsonl` 是逐题结果。

### 第 5 步 v1 正式索引（如果 R3 题库到位）

```bash
unset LEGAL_RAG_SETTINGS                       # 回到 v1
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3 --device cuda
# 校验 data/v1/index/index_manifest.json：article_count=4104, debug=false, dim=1024
```

### 第 6 步 v1 对照实验（G0/G1/G2 × repeats 2）

```bash
$PY -m legal_rag.pipeline.run_experiment \
  --questions data/eval/v1/questions.jsonl --groups G0,G1,G2 --repeats 2 --run-id main-v1
# 60 题 × 3 组 × 2 = 360 次调用
```

> **阻塞项**：`data/eval/v1/questions.jsonl` 目前不存在，正式题库由 R3 李渊栋交付。
> 题库没到就用 `--questions data/eval/dev/questions.jsonl`（7 题）跑通链路，
> 但在实验记录里标明是 dev 集，不能写进报告的正式结果表。

### 第 7 步 Neo4j 演示（可选，离线图谱索引已支撑实验，不影响结果）

现状：v1/v2 与案例层 Cypher 均已生成；v1/v2 已用 Neo4j 5.26.0 嵌入式实例实际导入并通过
计数校验（v1 4,106 节点 / 25,648 关系，v2 707 节点 / 4,327 关系），证据见
`logs/neo4j_import_v1.json`、`logs/neo4j_import_v2.json`。在线 Docker 容器尚未启动。
需要重建或复核时执行：

```bash
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
$PY -m legal_rag.graph.export_neo4j          # 生成 data/v2/graph/neo4j_import.cypher

# 结构校验（不需要 Neo4j 服务）
$PY scripts/verify_graph_export.py \
  --triples data/v2/graph/triples.jsonl \
  --cypher data/v2/graph/neo4j_import.cypher

cd deploy/neo4j && cp .env.example .env      # 填 NEO4J_PASSWORD，确认 .env 不入库
docker compose up -d && cd ../..
$PY -m legal_rag.graph.export_neo4j --import # 导入；neo4j 驱动需 pip install neo4j>=5.20
```

### 第 8 步 全流程留档 + 结果回传

```bash
$PY scripts/reproduce.py --skip-collect --embedding-model BAAI/bge-m3 --run-id repro-server-1
tar -czf results-server.tar.gz results logs data/v2/index/index_manifest.json data/v1/index/index_manifest.json
```

回传后本机做三件事：① 把 `index_manifest.json` 覆盖回仓库（这两个小文件是入库的）；
② 更新 `docs/r2_delivery.md` 的实测数字；③ 在 `CHANGELOG.md` 记正式索引与实验运行号。
`results/` 不入库，用网盘/群文件归档给 R1、R3。

---

## 5. 正式结果的验收清单（提交给 R1/R3 前逐条打勾）

题目 id 为 `hn-case-q01`…`hn-case-q17`，下面简写为 q01…q17；
17 题全部带 `expected` 字段（`scope_status` / `behavior` / `land_groups` / `area_m2` /
`fine_range` / `actual_fine` / `fine_contained`），逐题比对直接用它。

- [ ] `run_meta.json.mock = false`，`git_commit` 非空，`index_manifest.embedding_model = BAAI/bge-m3` 且 `embedding_model_debug = false`
- [ ] `run_meta.json.decoding_params` = `temperature 0.1 / top_p 0.9 / seed 42 / max_tokens 1024`，且与 `prompt_version` 一起留痕
- [ ] 每条结果有 `answer`、`steps`（五步）、`citations[].article_id/citation/score/ranks`、`similar_cases`、`prompt_hash`、`usage`、`latency_sec`，字段与 `docs/data_contract.md` 一致
- [ ] 生成过程中**没有出现**「调试嵌入器」「查询嵌入模型与索引模型不一致」这两条警告
- [ ] G0 组：引用数 0、类案数 0、罚款区间 null（这是设计如此，不是 bug）
- [ ] G1/G2 组：`expected` 类题目命中率达标；G2 的 `similar_cases` 每题 ≤ 3 且**不含查询案自身**（`exclude_case_id` 生效）
- [ ] 历史行为题（q04=2004 年、q10=2021 年）不套用现行幅度，`version_note` 里出现「第76条 / 第42条 / 湘自然资规〔2019〕5号」
- [ ] 缺地类题（q06/q08/q09）`needs_land_type=true`；q11 给 `partial_fine_range` 并说明面积缺口；q12 `scope_status=excluded`
- [ ] 罚款区间落在题目期望值内：q01 [271300,398200]、q02 [214200,321300]、q03 [1050400,2087600]、q05 [2119484,4117360]、q07 [1540359,2591861]、q13/q14 [1500000,2500000]、q15 [400000,600000]、q16 [500000,600000]、q17 [300000,500000]

> 2026-11-03 自动校验：`scripts/validate_case_results.py --run-dir results/case-main-v1`
> 共 771 项检查、0 失败（旧版脚本；当前校验器为 774 项）；复选框仍留给 R1/R3 复核。

> 上面这几组区间和逐题判定，是 `results/case-smoke-20261103` 里已经用规则引擎验证过的期望值。
> 换 BGE-M3 + 7B 之后，**规则算出的罚款区间不应变化**（区间由裁量基准决定），
> 变化的应该是检索证据和 LLM 自然语言答案。若区间也变了，先查检索证据是不是漂了。

---

## 6. 硬约束（这些是实验可信度的底线）

1. **单变量归因**：G0/G1/G2（及 G2-case、G2-graph）必须同一生成器、同一解码参数、同一提示词模板，
   唯一变量是检索信号。换模型、改温度 = 实验作废。
2. **信号定义**（`src/legal_rag/cases/case_qa.py` 的 `CASE_GROUPS`）：
   G0 无信号；G1 = dense + bm25 + 固定法条链；G2 = dense + bm25 + 法条图谱 + 类案 + 案件图谱；
   G2-case = G2 去掉案例层；G2-graph = G2 去掉法条图谱。
3. **防泄漏**：类案文本默认不含处罚结果（`case_text(include_outcome=False)`），检索时排除查询案自身。
   评测题若来源于某份决定书，题目里必须带 `exclude_case_id` 或 `case_id`。
4. **版本口径**：2021 年及以前的占地行为不套用现行裁量幅度（湖南现行 = 湘自资规〔2022〕1号）。
5. **合规**：只用公开法律文本与公开处罚决定书；个人姓名/证件号/电话必须脱敏（`raw/*.txt` 与
   `cases.jsonl` 同步脱敏，`text_sha256` 按脱敏后文本算）；单位名称保留。
   改脱敏规则会改变哈希，必须在 CHANGELOG 说明。
6. **凭据**：`NEO4J_PASSWORD` 只从环境变量读；`.env` 已 gitignore；不提交权重、密钥、索引缓存。
7. **数据版本不可就地改写**：v1 已冻结。要扩充案例/法规，新目录 + CHANGELOG 登记，别在 v1 上做覆盖。

---

## 7. 已知坑（本机踩过的，服务器别再踩）

| 现象 | 原因 / 处理 |
|---|---|
| Chroma 实际路径不在 `data/*/index/chroma` | 仓库路径含中文时程序自动回退到 `%LOCALAPPDATA%\legal_rag\chroma\<hash>`。清单里 `path` 是实际路径、`configured_path` 是配置路径，两个都留痕。Linux 下 ASCII 路径不会有这问题 |
| 检索结果异常但没报错 | 索引仍是 hashing 调试索引。跑实验前看 stderr 警告和 `index_manifest.embedding_model_debug` |
| 采集卡住 / 返回非 JSON | FLK 有 WAF。客户端已做冷却重试 + 断点续跑，但**服务器直接用 `--skip-collect`** |
| docx 校验失败 | 已校验 ZIP 魔数；非 docx 视为采集失败，不要手工绕过 |
| 换机器索引对不上 | 索引不入库，重建即可；重建前把 `articles.jsonl` 的 sha256 记下来比对（清单里有 `articles_sha256`） |
| G0 引用数为 0 被判失败 | 设计如此。逐题校验脚本里 G0 单独归类 |
| 0.5B 小模型答案格式漂 | 本机试过 0.5B，方向对但不稳定输出「《法规名》第X条」。引用准确率**必须**用 Qwen2.5-7B-Instruct 测，小模型结果不能代替 |
| `reproduce.py` 只跑 v1 | 它串的是 采集/切分/三元组/索引/测试/dev 实验，不含案件实验。v2 必须按第 4 节手动走 `run_case_experiment` |
| `scripts/reproduce.py --skip-collect` 在无网机器上仍报缺 raw | 确认 `data/v1/raw` 已传过去（75 个 docx） |

---

## 8. 还差什么（交接后的责任划分）

| 待办 | 归谁 | 说明 |
|---|---|---|
| 正式评测集 ≥60 题（30 简单 / 20 中等 / 10 困难） | R3 李渊栋 | 落到 `data/eval/v1/questions.jsonl`，字段 `id/category/question`；案件题可扩到 `data/eval/v1/case_questions.jsonl` |
| 案例从 11 份扩到 80~100 份 | R2 | 已确认 4 案缺地类是文书本身没写，属真实信息缺口，不靠猜补 |
| BGE-M3 索引 + 7B 正式实验 | R2 执行 / R1 设计 | 2026-11-03 已完成索引与 v2 `case-main-v1`；v1 正式题库缺失，仅有 dev 对照 |
| Recall@5、引用准确率、五步正确率统计 | R3 | 按 `article_id` 与 citation 计算；评测脚本消费 `results/<run_id>/*.jsonl` |
| 语料规模与开题报告不一致的解释口径 | R1/R4 | 实测 4,104 条 vs 报告预计 2万~5万。粒度换到条/项两级也只有 5,763，句级 10,842，都够不到 2 万 → 建议**改报告数字以对齐实测**，而不是拆条虚增 |
| 报告与 PPT 更新 | R4 喻方园 | 数字以 `data/*/corpus_stats.json` 和正式 `run_meta.json` 为准 |

---

## 9. 文档索引

- [README.md](../README.md) — 目录结构、快速开始、归因控制
- [docs/data_contract.md](data_contract.md) — 字段契约（改接口必读）
- [docs/r2_delivery.md](r2_delivery.md) — R2 交付对照与关键数字
- [docs/route_v2_hunan_illegal_land.md](route_v2_hunan_illegal_land.md) — 答辩反馈后的 v2 路线、决策与限制
- [CHANGELOG.md](../CHANGELOG.md) — 语料/索引/图谱/流水线变更登记
- 关键代码：[src/legal_rag/cases/case_qa.py](../src/legal_rag/cases/case_qa.py)（五步与信号定义）、
  [src/legal_rag/pipeline/run_case_experiment.py](../src/legal_rag/pipeline/run_case_experiment.py)、
  [src/legal_rag/index/build_index.py](../src/legal_rag/index/build_index.py)、
  [src/legal_rag/config.py](../src/legal_rag/config.py)（`LEGAL_RAG_SETTINGS` 加载）

遇到问题按这个顺序自查：`run_meta.json` → `index_manifest.json` → stderr 警告 → `docs/data_contract.md`。
