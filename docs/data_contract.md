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

## 2. 评测集（R3 交付，R2 只读）

### data/eval/v1/questions.jsonl

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 是 | 题目唯一编号，如 `reg-001` |
| category | 是 | 常规 / 边界 / 对抗 |
| question | 是 | 提问原文 |
| reference_answer | 建议 | 参考答案 |
| reference_citations | 建议 | 条文引用数组，用于引用准确率与 Recall@N |

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
index_manifest（嵌入模型、维数、索引条数、articles.jsonl 哈希）、Python 版本。

## 4. 复现约定

- 同一 `run_id` 下每组每次重复一个文件，不覆盖历史目录。
- `--resume` 依据 `question_id` 断点续跑；正式实验前清空或换新 `run_id`。
- 正式数据必须满足：`index_manifest.embedding_model == 运行日志中的查询模型`，
  且 `run_meta.mock == false`。

## 5. v2 案例层（2026-10-31 新增，`data/v2` + `data/cases/v1`）

v2 与 v1 完全隔离：v1 的 75 部法规、4,104 条与索引冻结不动；
v2 使用 `LEGAL_RAG_SETTINGS=config/settings_v2.yaml`，只含国家核心法 + 湖南地方立法。

### 5.1 法规语料 `data/v2/articles.jsonl`

字段与 v1 相同，新增：

| 字段 | 类型 | 说明 |
|---|---|---|
| jurisdiction | str | `national` 或 `hunan`，用于检索过滤与统计 |

规模（2026-10-31）：11 部、597 条、约 8.3 万字；结构告警 0。
目录见 `config/corpus_catalog_v2.yaml`。

### 5.2 案例 `data/cases/v1/cases.jsonl`

一行一案。关键字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| case_id | str | 主键，如 `hn-yongzhou-2025-6` |
| source | object | `url/portal/collected_at` |
| decision_no / decision_date / agency | str | 文书号、日期、机关 |
| party | object | `type/name/name_masked`；个人姓名脱敏 |
| facts | str | 违法事实（已脱敏） |
| behavior | str[] | `未经批准占用土地` / `超过批准数量占用土地` / `临时用地` / `设施农用地` / `未按批准用途使用土地` |
| scope_status | str | `included` / `excluded`；excluded 不进入类案检索 |
| exclusion_reason | str\|null | 排除原因 |
| land_use | object[] | `type/group/area_m2`；group ∈ 永久基本农田 / 其他耕地 / 其他土地 |
| area_m2 | float | 总面积 |
| project_nature | str | 公益 / 非公益 / 未知 |
| violated_articles | object[] | 违反条款；含 `law/article_num/cited_article_num/version_year/article_id/citation/resolved/mapped_from_old_version` |
| penalty_basis_articles | object[] | 处罚依据条款，字段同上 |
| policy_citations | str[] | 裁量基准等政策文件标题（无条号） |
| penalty_types | str[] | 责令退还 / 限期拆除 / 没收 / 罚款 / 处分 |
| fine_amount | float | 罚款总额 |
| fine_rate | object[] | `land/group/yuan_per_m2/area_m2`，用于核对面积×单价 |
| factors | str[] | 从轻/从重等情节 |
| raw_path / text_sha256 | str | 脱敏后原文路径与哈希（`raw/*.txt` 与入库文本一致） |
| consistency_warnings | str[] | 面积和、罚款乘积、缺失字段等质检告警 |

版本映射：旧法条号自动映射到现行条号，并保留 `cited_article_num` 与
`mapped_from_old_version`。当前规则：土地管理法 2004 版第 76 条 → 现行第 77 条；
实施条例 2014 版第 42 条 → 现行第 57 条。

> `policy_citations` 记录裁量基准等政策文件标题，但 `湘自资规〔2022〕1号` 当前未进入
> `data/v2/articles.jsonl`，其罚款档位由 `cases/schema.py` 维护。R3 计算引用准确率时
> 应把政策文件作为外部依据单独统计，不能仅因不在法条库中就判为编造；
> 详见 `docs/r3_handoff.md` 第 4.1 节。

### 5.3 案件图谱 `data/cases/v1/graph/`

| 文件 | 说明 |
|---|---|
| nodes.jsonl | Case / Behavior / Article / PenaltyType / LandType / Factor |
| edges.jsonl | `ALLEGED_BEHAVIOR`、`VIOLATES`、`CITES_BASIS`、`PRESCRIBES`、`SANCTIONED_WITH`、`HAS_LAND_TYPE`、`HAS_FACTOR` |
| case_triples.jsonl | 供离线检索/检查的扁平三元组 |
| neo4j.cypher | 可直接导入 Neo4j 的 MERGE 语句 |
| stats.json | 节点/边/行为/地类统计与逐案质检结果 |

案件图谱只写入材料能支撑的事实，不写推测值；G2 默认用离线实例，Neo4j 仅用于演示。

### 5.4 案件评测题 `data/cases/v1/questions.jsonl`

| 字段 | 必填 | 说明 |
|---|---|---|
| id | 是 | 题目编号 |
| question | 是 | 仅给案件事实，不含文号、机关、处罚结果 |
| category | 是 | 题型/考查点 |
| case_id / exclude_case_id | 否 | 由真实案件改写时标注；检索时排除该案，防泄漏 |
| expected | 是 | 结构化核对项：`scope_status/behavior/land_groups/area_m2/fine_range/partial_fine_range/needs_land_type/current_standard_applied/version_note_contains/required_citations/required_text/actual_fine` |

当前 17 题：11 题由试点案例改写，6 题为边界题（排除情形、临时用地、设施农用地、
不符合规划、公益项目、性质未知）。R3 扩题时保持同一字段契约，新题库建议放入
`data/cases/v2/questions.jsonl` 等新版本目录，不覆盖试点 17 题。

### 5.5 案例实验结果 `results/<run_id>/<group>_r<repeat>.jsonl`

组别：`G0`、`G1`、`G2`、`G2-case`、`G2-graph`。

| 字段 | 说明 |
|---|---|
| question_id / question / group / repeat | 题目与组别 |
| answer | 大模型答案；mock/无 LLM 时为确定性答案 |
| deterministic_answer | 五步规则生成的确定性答案，便于复核 |
| confidence | high / medium / low |
| steps | `facts/characterization/law_application/discretion/conclusion` 五步中间结果 |
| similar_cases | 相似案例（含 `case_id/decision_no/score/reasons/fine_amount/fine_rate`） |
| citations | 引用对象数组：`article_id/citation/score/ranks/role/source`；`score` 与 `ranks` 来自检索命中，法条链引用为 null/空；G0 为空数组（2.1 起） |
| citation_strings | 引用条文串数组，供按 citation 精确匹配的评测脚本使用 |
| prompt_hash / prompt_version / decoding_params | 提示词与解码快照 |
| usage / latency_sec / wall_sec | 用量与耗时 |

`run_meta.json` 额外记录 `mode=case`、案例数、案件图谱统计、组别配置与题库哈希。

### 5.6 防泄漏与合规

- `case_text(include_outcome=False)` 默认不拼接罚款金额与处罚种类，类案检索只看事实；
- 查询案件自身通过 `exclude_case_id` 排除；
- G0 不启用条文检索、类案、图谱，也不计算罚款；G1 不启用类案；
- 个人姓名、手机号、身份证号在入库前脱敏，`raw/*.txt` 与 `cases.jsonl` 同步处理；
  法定代表人、联系人及证据清单中的第三人姓名一并掩码；单位名称保留；
- 只采集公开决定书/台账，不采集非公开案卷；`text_sha256` 按脱敏后文本计算，
  `manifest.json` 保留来源 URL 与原始页面 `source_sha256` 供回溯。
