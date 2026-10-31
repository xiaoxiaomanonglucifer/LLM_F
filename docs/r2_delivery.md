# R2（工程与数据）交付说明

对应开题报告第九组 R2 职责。本文说明**已交付什么、证据在哪、还差什么、如何在 GPU 节点收尾**，
供组长、R1（实验）与 R3（评测）核对。

> **v2 试点（2026-10-31）**：按开题答辩反馈，范围收窄为“湖南省·非法占地行政处罚”。
> 新增 `data/v2/`（11 部、597 条）与 `data/cases/v1/`（11 案、17 题），
> 五步案件问答与 `G0/G1/G2/G2-case/G2-graph` 已在本机 mock 打通。
> 详见 `docs/route_v2_hunan_illegal_land.md` 与 `CHANGELOG.md`；
> 下文第一至六节为 v1 法规 RAG 的交付说明，仍然有效。

## 一、交付物对照

| # | 开题报告 R2 交付物 | 状态 | 证据 / 入口 |
|---|---|---|---|
| 1 | 法规语料采集与版本化 | 完成 | `config/corpus_catalog.yaml`、`data/v1/manifest.json`、`data/v1/raw/`、`data/v1/meta/`、`CHANGELOG.md` |
| 2 | 按条切分语料 | 完成 | `src/legal_rag/corpus/article_parser.py`、`data/v1/articles.jsonl`（4,104 条） |
| 3 | BGE-M3 向量化 + Chroma 构建 | 脚手架完成，正式向量待 GPU | `src/legal_rag/index/`、`data/v1/index/index_manifest.json`；本机为 hashing 调试索引 |
| 4 | Neo4j 图谱构建 | 图谱与 Cypher 完成；本机未实际导入 | `data/v1/graph/triples.jsonl`、`neo4j_import.cypher`（29,059 条语句） |
| 5 | 检索-生成流水线 | 完成并联调 | `src/legal_rag/retrieval/`、`pipeline/`、`generation/`；G0/G1/G2 |
| 6 | 推理服务部署 | 接口完成；正式 7B 待 GPU | OpenAI 兼容客户端（Ollama / vLLM），`src/legal_rag/generation/llm_client.py` |
| 7 | 可复现运行脚本 | 完成 | `scripts/reproduce.py`；记录 `logs/reproduce_20261027-184739.json` |
| 8 | Git 提交记录 | 本次初始化并提交 | 初始提交 `fac7de4`；仓库根 `git log --oneline` |
| 9 | 全流程重跑记录 | 本地调试链路完成 | 上述 reproduce 记录 + `results/repro-local-1/`、`results/dev-mock/`、`results/dev-llm-0.5b/` |
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
| 图谱覆盖 | 3,476 条法条（84.7%），实体 630 个 |
| Neo4j Cypher | 29,059 条语句（未在本机导入） |
| 单元测试 | v1 11 项；含 v2 案例层全仓 29 项通过 |
| 本地一键复现 | 5 步全部成功，14.2s（hashing + mock） |

> 与开题报告“2 万~5 万文本块”的差异已在 `CHANGELOG.md` 说明：检索单位固定为“条”，
> 目录仅 75 部现行有效法规，实际 4,104 条；未通过拆条或复制文本虚增规模。

## 三、本地已完成的验证

```bash
export PYTHONPATH=src
PY="E:/演绎/LLM/第二次作业/rag_home/.venv/Scripts/python.exe"

# 单元测试（11 项）
$PY -m unittest discover -s tests -v

# 一键复现（调试嵌入器 + 模拟生成器）
$PY scripts/reproduce.py --skip-collect --embedding-model hashing --mock --run-id repro-local-1

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

## 四、待 GPU 节点收尾（按顺序）

1. **构建正式索引**（BGE-M3，1024 维）：

   ```bash
   $PY -m legal_rag.index.build_index --embedding-model <BGE-M3 本地路径或模型名>
   ```

   检查 `data/v1/index/index_manifest.json`：`embedding_model` 为 BGE-M3、
   `embedding_model_debug` 为 false、`article_count=4104`。

2. **启动生成服务**（Ollama 或 vLLM，OpenAI 兼容）：

   ```bash
   # 以 vLLM 为例
   vllm serve Qwen/Qwen2.5-7B-Instruct --port 8000
   # config/settings.yaml 中 generation.base_url 指向 http://127.0.0.1:8000/v1
   ```

3. **正式对照实验**（同一生成器/解码参数/提示词，仅检索信号不同）：

   ```bash
   $PY -m legal_rag.pipeline.run_experiment \
     --questions data/eval/v1/questions.jsonl --groups G0,G1,G2 --repeats 2 --run-id main-v1
   ```

4. **Neo4j 演示环境**（可选，不影响离线实验）：

   ```bash
   cd deploy/neo4j
   cp .env.example .env          # 填入 NEO4J_PASSWORD，切勿提交 .env
   docker compose up -d
   cd ../..
   $PY -m legal_rag.graph.export_neo4j --import
   ```

   密码只从环境变量 `NEO4J_PASSWORD` 读取；仓库内不保存任何凭据。

5. **全流程重跑留档**：执行 `scripts/reproduce.py`（不加 `--mock`、指定 BGE-M3），
   将生成的 `logs/reproduce_*.json|log` 与 `results/main-v1/` 一并归档。

## 五、风险与边界

- **规模**：4,104 条低于开题预估，属于真实测量结果；若需扩大，优先补充部门规章与
  地方性法规到 `config/corpus_catalog.yaml`，切分与索引代码无需改动。
- **12 部缺失法规**：FLK 无同名现行有效版本（`sxx=3`），未用近似标题或失效文本替代；
  清单与原因见 `CHANGELOG.md` 和 `data/v1/manifest.json`。
- **本机索引为调试索引**：hashing 512 维，仅用于联调；正式结果必须重建 BGE-M3 索引。
- **Chroma 路径**：仓库路径含中文时自动回退到
  `%LOCALAPPDATA%\legal_rag\chroma\09e06fb173`；换机器重建即可，清单记录了实际路径。
- **Neo4j 未导入**：本机无 Docker 与 neo4j 驱动；G2 实验使用离线 GraphIndex，
  不依赖 Neo4j，因此不影响实验复现。

## 六、与 R1 / R3 的接口

- R3 提供正式题库 `data/eval/v1/questions.jsonl`（字段 `id/category/question`）；
  R1 用 `run_experiment.py` 产出 `results/<run_id>/<group>_r<repeat>.jsonl` 与 `run_meta.json`。
- 每条结果包含 `answer`、`evidence[].citation/article_id/score/ranks/graph`、
  `graph_context`、`prompt_hash`、`usage`、`latency`；评测脚本按 `article_id`/citation
  计算 Recall@5 与引用准确率。
- 正式实验前置校验：`run_meta.json.index_manifest.embedding_model` 必须为 BGE-M3 且
  `mock=false`；否则结果只能标记为流程验证。
- 字段契约详见 `docs/data_contract.md`；变更接口须同步更新该文件与 `CHANGELOG.md`。
