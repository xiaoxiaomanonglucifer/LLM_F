# R2 → R1/R3 接口契约（v1）

所有接口文件均为 UTF-8 JSONL，一行一条记录；字段新增向后兼容，删除/改名需升版本并写入 CHANGELOG。

> R3 的完整交接包、结果字段用法、指标口径与已知缺口见 `docs/r3_handoff.md`。

## 1. 语料（R2 交付）

### data/v1/articles.jsonl（按条切分）

| 字段 | 类型 | 说明 |
|---|---|---|
| article_id | str | 主键，`<doc_id>#a0001`，重复条号加后缀 `-2` |
| doc_id | str | 法规标识（catalog 中的 id） |
| law_title | str | 法规全称 |
| level | str | 法律 / 行政法规 / 地方性法规 |
| domain | str | 土地管理 / 国土空间规划 / ... |
| jurisdiction | str | 预留字段；v1 当前为空字符串 |
| article_no | str | 如 `第四十四条` |
| article_num | int | 条序号（用于排序与统计） |
| chapter / section | str\|null | 章 / 节标题 |
| text | str | 条文全文（含款、项，不含条文号前缀以外的加工） |
| body | str | 去掉“第X条”后的正文 |
| citation | str | 引用串，`《法规名》第X条`，评测按此精确匹配 |
| effective_date / promulgation_date | str\|null | ISO 日期 |
| source_url | str | 原始页面 |
| sha256 | str | 原始 docx 哈希 |

### data/v1/manifest.json

采集清单：`documents[]`，每部法规的 `doc_id/title/level/domain/bbbs/dates/sha256/raw_file/meta_file`，
以及 `missing[]`（无现行有效版本）与 `errors[]`。

### data/v1/graph/triples.jsonl

| 字段 | 类型 | 说明 |
|---|---|---|
| article_id | str | 关联法条主键 |
| citation | str | 引用串 |
| law_title | str | 法规名 |
| subjects | str[] | 主体 |
| actions | str[] | 行为 |
| penalties | str[] | 处罚 |
| method | str | `rule` 或 `llm` |
| model | str | LLM 抽取时的模型名（规则为空） |

图谱导出与导入校验：

- `data/v1/graph/neo4j_import.cypher`：可导入 Neo4j 的 MERGE 语句；
- `scripts/verify_graph_export.py --triples ... --cypher ...`：校验 triples 与 Cypher 一致；
- `logs/neo4j_import_v1.json`：嵌入式 Neo4j 5.26 的实际导入计数与校验结果。

## 2. 评测集（R3 交付，R2 只读）

### data/eval/v1/questions.jsonl

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 是 | 题目唯一编号，如 `reg-001` |
| category | 是 | 常规 / 边界 / 对抗 |
| question | 是 | 提问原文 |
| reference_answer | 建议 | 参考答案 |
| reference_citations | 建议 | 条文引用数组，用于引用准确率与 Recall@N |

当前仓库只有 `data/eval/dev/questions.jsonl`（7 题，联调用），正式集由 R3 交付。

## 3. 实验结果（R2 产出，R3 消费）

### results/<run_id>/<group>_r<repeat>.jsonl

| 字段 | 说明 |
|---|---|
| question_id | 对应评测题 id |
| category | 题型 |
| group | G0 / G1 / G2 |
| repeat | 第几次重复运行（1 起） |
| answer | 模型回答原文 |
| refusal_rule_flag | 规则拒答标记，仅供参考；正式拒答指标由 R3 复核 |
| evidence | 检索证据数组：article_id、citation、法律名、text、rrf 分数、各信号名次、graph 要素 |
| graph_context | 仅 G2：拼入提示词的一跳子图谱文本 |
| prompt_hash | 提示词 SHA256 前 16 位，用于核对三组模板一致 |
| prompt_version | 模板版本 |
| decoding_params | 模型名、temperature、top_p、seed、max_tokens |
| usage / latency_sec / wall_sec | 用量与耗时 |
| answered_at | ISO 时间 |

### results/<run_id>/run_meta.json

run_id、时间、git commit、groups、repeats、mock、题库路径与哈希、题目数、
prompt_version、decoding_params、检索参数（top_k/candidate_k/rrf_k/signals）、
index_manifest（嵌入模型、维数、索引条数、articles.jsonl 哈希）、Python 版本、
generation_service（base_url/model/backend/quantization）。

## 4. 复现约定

- 同一 `run_id` 下每组每次重复一个文件，不覆盖历史目录。
- `--resume` 依据 `question_id` 断点续跑；正式实验前清空或换新 `run_id`。
- 正式数据必须满足：`index_manifest.embedding_model == 运行日志中的查询模型`，
  且 `run_meta.mock == false`。
- `results/` 默认被 `.gitignore` 排除；跨机器交接需单独拷贝或按命令重跑。
