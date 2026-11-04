# 演示操作手册（v2 湖南非法占地五步问答）

> 维护人：R2 曾平 ｜ 适用：第 9 组课程项目答辩 / 课堂演示
> 演示主线：**v2 湖南·非法占地行政处罚**。v1 全国法规是冻结旧线，不作为本次演示主线。
> 推荐方式：**无 GPU 离线回放**；实时问答只作为有 GPU 时的加分项。
> 本文 q01/q06/q12 等数字均来自冻结结果 `results/case-main-v1/`；
> 用 `--run-dir` 指向新 run 时，以实际输出为准，脚本不会写死任何案例或金额。

## 0. 先记住四句话

1. **没有 GPU、没有模型、没有网络也能演示**：`scripts/demo_replay.py` 读取冻结结果
   `results/case-main-v1/`，不加载模型和索引。
2. **实时问答才需要 GPU**：vLLM + BGE-M3 索引；现场网络或显存不稳时不要赌实时。
3. **`case-main-v1` 是正式运行但不是正式统计结论**：`mock=false`、BGE-M3/1024，
   但只有 17 题、11 案、1 次重复，不能声称显著性。
4. **本项目没有前端**：R4 负责 Streamlit；R2 的演示入口是 CLI + 离线回放，
   不要把它说成“完整产品”。

---

## 1. 演示机准备（5 分钟）

### 1.1 最低配置

| 项目 | 要求 |
|---|---|
| Python | 3.8+ 即可；离线回放只用标准库 |
| GPU | 不需要 |
| 网络 | 不需要 |
| 必须有的目录 | 仓库根目录、`results/case-main-v1/`、`data/cases/v1/questions.jsonl` |
| 终端 | 字号 16–18，UTF-8；建议深色背景 |

`results/` 默认被 `.gitignore` 排除，`git clone` 不会带结果。把结果目录单独拷贝到演示机：

```bash
# 在 GPU 节点打包（只有约 1.3 MB）
tar -czf case-main-v1.tar.gz results/case-main-v1

# 在演示机仓库根目录解压
tar -xzf case-main-v1.tar.gz
```

仓库根已有 `results-server.tar.gz` 时，也可以只取正式结果：

```bash
tar -xzf results-server.tar.gz results/case-main-v1
```

### 1.2 三条自检命令

在仓库根目录执行：

```bash
# Linux / macOS
python3 scripts/demo_replay.py --list
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare
python3 scripts/validate_case_results.py --run-dir results/case-main-v1
```

Windows 把 `python3` 换成 `python` 或 `py -3.11`：

```bat
chcp 65001
python scripts\demo_replay.py --list
```

预期：

- `--list` 输出 **17 题**；
- `--compare` 输出 **G0/G1/G2/G2-case/G2-graph 五行**；
- 校验器输出 **774 项检查，失败 0 项**。

中文乱码时先设 `export PYTHONUTF8=1`（Windows 用 `set PYTHONUTF8=1`）。

---

## 2. 推荐演示流程（10 分钟，离线）

### 2.1 时间分配

| 时间 | 场景 | 目的 |
|---|---|---|
| 0:00–1:00 | 项目与数据规模 | 说明范围已收窄到湖南非法占地 |
| 1:00–5:00 | q01 单题完整链路 | 展示事实→定性→法条→裁量→结论 |
| 5:00–7:00 | 五组消融对比 | 说明 G0/G1/G2 与两项消融的差异 |
| 7:00–9:00 | q06 + q12 边界题 | 展示“不臆造金额”和“排除情形” |
| 9:00–10:00 | 校验与边界 | 展示可复核性，主动说明限制 |

### 2.2 第 1 幕：项目与数据（1 分钟）

不用敲命令，直接说：

> 这是第 9 组的法规 RAG 系统。开题时是全国国土法规问答，答辩后把范围收窄为
> **湖南省·未经批准非法占用土地**的行政处罚。当前 v2 依据库有 11 部法规、597 条、
> 约 8.3 万字；案例层有 11 份公开处罚决定书、案件图谱 30 个节点/180 条边、
> 17 道案件题。v1 的 75 部、4,104 条全国法规仍然保留，但已经冻结，不再混用。

如果评委追问“为什么只有 11 个案例”，直接承认：这是试点规模，扩到 60–100 份是
R2/R3 的后续工作，当前不拿 11 个案例做统计显著性结论。

### 2.3 第 2 幕：单题完整链路（4 分钟）

```bash
python3 scripts/demo_replay.py --question-id hn-case-q01
```

这是“2023 年某公益项目未经批准占用耕地 722㎡、园地 315㎡、林地 163㎡、
其他土地 69㎡”的题。按屏幕顺序讲：

1. **模型答案**：先看结论，不要逐字念全文。
2. **五步中间结果**：
   - 事实：总面积 1,269㎡，地类拆分清楚；
   - 定性：未经批准占用土地，属于非法占用；
   - 法条适用：土地管理法第 44 条（定性）、第 77 条（处罚）、实施条例第 57 条、
     湖南省实施办法第 55 条；
   - 裁量：其他耕地 722㎡ × 300–400 元/㎡ = 216,600–288,800 元；
     其他土地 547㎡ × 100–200 元/㎡ = 54,700–109,400 元；
     合计 **271,300–398,200 元**；
   - 结论：责令退还、没收或限期拆除、并处罚款。
3. **引用**：6 条，能对应到具体法条和来源（法条链/检索/类案）。
4. **类案**：3 份相似决定书，带案号、相似度分数、实际罚款，可核对。
5. **运行信息**：prompt 版本 2.0、哈希、耗时，说明结果可追溯。

一句话总结：

> 它不是只给一段答案，而是把“事实、定性、条文、裁量、结论”分开，
> 罚款区间可以用面积乘单价手算复现。

### 2.4 第 3 幕：五组消融（2 分钟）

```bash
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare
```

预期表格：

| 组别 | 引用数 | 类案数 | 罚款区间 | 说明 |
|---|---:|---:|---|---|
| G0 | 0 | 0 | — | 不检索，明确说“无法依据现行法给出幅度” |
| G1 | 6 | 0 | 271,300–398,200 元 | 法条检索 + 固定法条链 |
| G2 | 6 | 3 | 271,300–398,200 元 | 完整组：法条 + 类案 + 图谱 |
| G2-case | 5 | 0 | 271,300–398,200 元 | 去掉类案 |
| G2-graph | 7 | 3 | 271,300–398,200 元 | 去掉法条图谱 |

讲法：

> 五组用同一个模型、同一套提示词、同一组解码参数，只改检索信号。
> G0 没有检索，所以它不引用、不算罚款，也不会假装知道；
> G1 只给法条；G2 再加类案和案件图谱；G2-case、G2-graph 分别去掉类案和法条图谱，
> 用来做消融。这里不是“引用越多越好”，而是看每组能否给出可核对、可解释的依据。

如果时间紧，只讲 G0/G1/G2 三行；消融两行留作备用。

### 2.5 第 4 幕：两个边界题（2 分钟）

**边界 A：地类缺失，不臆造金额**

```bash
python3 scripts/demo_replay.py --question-id hn-case-q06
```

指着“4) 裁量”说：

> 这题只给了总面积 13,070.5㎡，没给地类。系统没有编一个单价乘总面积，
> 而是明确要求补充调查，罚款总额为空。这是故意的：地类不同，单价不同，
> 缺地类时给总额反而是错误。

**边界 B：排除情形，不硬套非法占地**

```bash
python3 scripts/demo_replay.py --question-id hn-case-q12
```

> 这题是“经批准占用后未按批准用途使用”，不是“未经批准占用”。系统把它标成
> `excluded`，说明不属于土地管理法第 77 条的非法占地，不能按这道题硬套罚款。
> 这对应开题时说的“边界/对抗题”，也是 17 题里 6 道边界题的代表。

### 2.6 第 5 幕：可复核性与限制（1 分钟）

```bash
python3 scripts/validate_case_results.py --run-dir results/case-main-v1
```

预期最后一行：`共 774 项检查，失败 0 项`。

如果演示机装了项目依赖，再补一句：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
# 预期 Ran 32 tests ... OK
```

主动说明：

> `case-main-v1` 是 `mock=false`、BGE-M3/1024 的正式运行，5 组 × 17 题 = 85 条；
> 但只有 1 次重复、17 题由 11 案改写，不能支撑 McNemar / 配对 t / Bonferroni
> 的正式统计结论。正式题库、60 案 gold、Kappa 和 2 次重复由 R3/R1 继续。

---

## 3. 命令速查

所有命令都在仓库根目录执行；`--run-dir` 默认 `results/case-main-v1`。

```bash
# 题目列表
python3 scripts/demo_replay.py --list

# 单题：默认 G2、默认第一题
python3 scripts/demo_replay.py --question-id hn-case-q01

# 指定组别
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G0
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G1
python3 scripts/demo_replay.py --question-id hn-case-q01 --group G2-graph

# 五组对比
python3 scripts/demo_replay.py --question-id hn-case-q01 --compare

# 原始 JSON（调试/二次处理）
python3 scripts/demo_replay.py --question-id hn-case-q01 --json

# 换结果目录或重复次数
python3 scripts/demo_replay.py --run-dir results/case-main-v1 --repeat 1
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--run-dir` | `results/case-main-v1` | 结果目录 |
| `--group` | `G2` | `G0/G1/G2/G2-case/G2-graph` |
| `--question-id` | 题库第一题 | 如 `hn-case-q01` |
| `--compare` | 关 | 对比五组 |
| `--list` | 关 | 列出 17 题 |
| `--json` | 关 | 输出完整记录 |
| `--repeat` | `1` | 结果文件后缀 `_r1` |

---

## 4. 可选：实时问答

> **默认不建议现场实时演示。** 需要 GPU、模型服务、索引，任何一项没起来都会冷场。
> 只有评委明确要求“现场提问”时再用。

### 4.1 方案 A：本机 CPU（不推荐，仅备用）

需要项目依赖、BGE-M3 权重和可用的 Chroma 索引。当前索引清单记录的是 GPU 节点
绝对路径，换机器后通常要重建索引：

```bash
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
export PYTHONPATH=src
PY=<你的项目 Python>

# 可选：把查询嵌入改到 CPU（修改 config/settings_v2.yaml 的 embedding.device: cpu）
$PY -m legal_rag.index.build_index --embedding-model BAAI/bge-m3 --device cpu

# 只验证检索/五步链路，不调用大模型
$PY -m legal_rag.pipeline.ask_case "2023年，某公益项目未经批准占用耕地722平方米、园地315平方米、林地163平方米、其他土地69平方米，应如何处罚？" --group G2 --mock
```

`--mock` 是确定性生成器，**只能证明链路通，不能作为正式结果**。要真实回答，
必须配置 OpenAI 兼容的生成服务并去掉 `--mock`。

### 4.2 方案 B：GPU 节点 + vLLM（现场加分项）

先看显卡占用，挑空闲卡，不要影响别人：

```bash
nvidia-smi
```

启动 vLLM（本机 AWQ int4 权重，命令与 2026-11-03 正式运行一致）：

```bash
cd /data_disk/tjh/zp/LLM_FIN
export CUDA_VISIBLE_DEVICES=1          # 按 nvidia-smi 结果换成空闲卡
nohup /data_disk/tjh/conda_envs/LLM_vLLM/bin/vllm serve models/qwen2.5-7b-instruct-awq \
  --served-model-name Qwen/Qwen2.5-7B-Instruct \
  --quantization awq --dtype float16 \
  --gpu-memory-utilization 0.24 --max-model-len 8192 --max-num-seqs 4 \
  --guided-decoding-backend lm-format-enforcer \
  --host 127.0.0.1 --port 8000 > logs/vllm_demo.log 2>&1 &
echo $! > /tmp/vllm_demo.pid
```

等模型加载（首次约 1–3 分钟），确认服务：

```bash
curl -s http://127.0.0.1:8000/v1/models
```

返回的 `id` 必须是 `Qwen/Qwen2.5-7B-Instruct`。看不到就查日志：

```bash
tail -f logs/vllm_demo.log
```

服务就绪后，另开终端跑单题：

```bash
cd /data_disk/tjh/zp/LLM_FIN
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python
$PY -m legal_rag.pipeline.ask_case "2023年，某公益项目未经批准占用耕地722平方米、园地315平方米、林地163平方米、其他土地69平方米，应如何处罚？" --group G2
```

加 `--json` 可输出完整五步结构。演示结束只关闭自己启动的进程：

```bash
kill "$(cat /tmp/vllm_demo.pid)"
```

不要 `pkill -f vllm`，共享节点上可能有别人的服务。

### 4.3 方案 C：重跑一次实验（评委问“结果怎么来的”）

约 85 次生成调用、20 分钟左右；必须确认 vLLM、BGE-M3 索引和 `mock=false`：

```bash
cd /data_disk/tjh/zp/LLM_FIN
export LEGAL_RAG_SETTINGS=config/settings_v2.yaml
export PYTHONPATH=src
PY=/data_disk/tjh/conda_envs/LLM_F/bin/python

$PY -m legal_rag.pipeline.run_case_experiment \
  --groups G0,G1,G2,G2-case,G2-graph \
  --run-id demo-$(date +%Y%m%d-%H%M)
```

跑完用新目录校验：

```bash
$PY scripts/validate_case_results.py --run-dir results/<新 run_id>
```

注意：默认 `repeats=1`，只能证明链路和逐题结果，仍不是正式统计。

---

## 5. 评委可能问什么

| 问题 | 建议回答 |
|---|---|
| 为什么只有 11 个案例、17 道题？ | 这是答辩后收窄范围的试点，先打通“案例→法条→裁量”链路；扩到 60–100 案、60 题是下一步，不把试点当正式统计。 |
| 17 题能证明系统有效吗？ | 不能单独证明。17 题由 11 案改写，存在相关性；当前证明的是工程链路、分组隔离和逐题期望，不是显著性。 |
| 为什么 G0 有时也能说出法律？ | G0 不提供检索证据，模型可能凭自身知识回答；但 G0 的 `citations` 是 0，实验比较的是“是否提供可核对依据”，不是模型记忆。 |
| 为什么罚款是区间不是具体金额？ | 裁量基准给的是幅度；实际处罚还取决于规划符合性、公益/非公益、从轻从重等情节。系统给区间并附类案，不冒充最终处罚决定。 |
| 为什么 q06 没有罚款？ | 只给了总面积、没给地类，无法按地类单价计算；系统要求补充调查，不臆造金额。 |
| 为什么 q12 不按第 77 条罚？ | 它是“未按批准用途使用土地”，不是“未经批准占用土地”，属于排除情形；系统标成 `excluded`，避免硬套。 |
| 裁量基准进检索库了吗？ | 没有。`湘自资规〔2022〕1号` 目前硬编码在 `cases/schema.py`，作为外部政策依据；统计引用准确率时要单列，不能因为它不在 `data/v2/articles.jsonl` 就判为编造。 |
| 结果能直接写进论文吗？ | `case-main-v1` 可作为工程结果和逐题案例，不能作为 H1 的正式统计结论；正式实验需要 R3 题库 + `repeats=2`。 |
| 为什么用 AWQ int4？ | 共享 A100 显存受限，正式运行用 AWQ int4；解码参数、提示词、评测口径未变，已在 `run_meta.generation_service` 留痕。 |
| 和开题的 2 万–5 万文本块不一致？ | 检索单位固定为“条”，v1 实际 4,104 条；没有拆条或复制文本虚增规模。v2 进一步收窄到 597 条，这是范围调整，不是数据造假。 |
| 有网页/前端吗？ | 当前没有；R4 负责 Streamlit。R2 提供 CLI、离线回放和可消费的结果字段。 |

---

## 6. 故障处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `ModuleNotFoundError: legal_rag` | 用了系统 Python 跑项目模块 | 设 `PYTHONPATH=src`，并用项目环境的 Python |
| `FileNotFoundError: ...G2_r1.jsonl` | 不在仓库根目录，或没拷 `results/` | `cd` 到仓库根；按 §1.1 解压结果 |
| 中文乱码 | 终端编码不是 UTF-8 | `export PYTHONUTF8=1`；Windows `chcp 65001` |
| `Connection refused` | vLLM 没启动或端口不对 | `curl http://127.0.0.1:8000/v1/models`；看 `logs/vllm_demo.log` |
| 返回的模型名不对 | `--served-model-name` 与 settings 不一致 | 启动时用 `Qwen/Qwen2.5-7B-Instruct`，或同步改 `generation.model` |
| CUDA OOM | 共享卡被别人占用 | `nvidia-smi` 换空闲卡；降低 `--gpu-memory-utilization`；不要杀别人的进程 |
| BGE-M3 下载很慢 | 无外网/HF 不通 | 设 `HF_ENDPOINT=https://hf-mirror.com`，或改用本地权重路径 |
| Chroma 路径不存在 | 索引清单记录的是另一台机器的绝对路径 | 在原机器演示，或在本机重建索引 |
| `Address already in use` | 8000 端口被占 | 换 8001 并改 `generation.base_url`；不要杀未知进程 |
| 校验器报 `mock=true` | 用了 `--mock` 结果 | 换 `case-main-v1` 或重跑非 mock；mock 只能做流程验证 |
| 输出太长刷屏 | 单题答案本身较长 | 用 `--compare` 看对比；或重定向到文件后再讲 |

---

## 7. 演示前检查清单

- [ ] `python3 scripts/demo_replay.py --list` 能列出 17 题。
- [ ] q01 的 G2 输出包含 6 条引用、3 个类案、罚款区间 271,300–398,200 元。
- [ ] `--compare` 能显示五组，G0 引用/类案均为 0。
- [ ] q06 显示“地类未查全，不给出罚款总额”。
- [ ] q12 显示 `excluded`，不按第 77 条罚款。
- [ ] `validate_case_results.py` 输出 774 项、0 失败。
- [ ] 终端字号、UTF-8、投影分辨率已检查。
- [ ] 已准备离线备份：关键页面截图或 `--json` 输出文件。
- [ ] 记住三条限制：11 案/17 题、1 次重复、无正式统计结论。
- [ ] 不把 `dev-server-v1` 或任何 `mock=true` 结果说成正式结果。

---

## 8. 一页速查

**数据规模**

- v2 法规：11 部 / 597 条 / 82,505 字
- 案例：11 份（9 未经批准 + 2 超过批准数量）；4 案缺地类；8 案项目性质未知
- 案件图谱：30 节点 / 180 边
- 案件题：17 道（11 道案例改写 + 6 道边界题）
- 正式结果：`case-main-v1`，5 组 × 17 题 = 85 条，`mock=false`，BGE-M3/1024
- 校验：774 项 0 失败；单测 32 项

**五组**

| 组别 | 条文检索 | 类案 | 法条图谱 | 用途 |
|---|---|---|---|---|
| G0 | 否 | 否 | 否 | 无检索基线 |
| G1 | 是 | 否 | 否 | 法条检索 |
| G2 | 是 | 是 | 是 | 完整组 |
| G2-case | 是 | 否 | 是 | 去掉类案 |
| G2-graph | 是 | 是 | 否 | 去掉法条图谱 |

**推荐题目**

| 题号 | 看点 |
|---|---|
| `hn-case-q01` | 完整链路、罚款区间、类案、五组对比 |
| `hn-case-q02` | 超过批准数量占用 |
| `hn-case-q05` | 永久基本农田，单价更高 |
| `hn-case-q06` | 缺地类，不臆造金额 |
| `hn-case-q12` | 排除情形，不硬套第 77 条 |
| `hn-case-q16` | 公益 + 永久基本农田 + 超批准 |
| `hn-case-q17` | 最简单的现行标准题 |

**最重要的三条限制**

1. 11 案、17 题、1 次重复，不能支撑正式统计结论。
2. 裁量基准 `湘自资规〔2022〕1号` 未进入 v2 检索库，引用统计需单列。
3. 当前没有前端；Streamlit 属于 R4，R2 演示 CLI 与离线回放。

---

## 附录：17 题清单

| 题号 | 题型 | 一句话 |
|---|---|---|
| `hn-case-q01` | 现行标准/公益/多农用地 | 完整链路与罚款区间 |
| `hn-case-q02` | 现行标准/超批准/非公益 | 超过批准数量 |
| `hn-case-q03` | 现行标准/地类混合/性质未知 | 多宗地类合并 |
| `hn-case-q04` | 旧法映射/2004 行为 | 旧法条号映射与版本提示 |
| `hn-case-q05` | 现行标准/永久基本农田 | 永久基本农田高单价 |
| `hn-case-q06` | 地类缺失/需补充调查 | 不臆造罚款总额 |
| `hn-case-q07` | 现行标准/超批准 | 超批准数量 |
| `hn-case-q08` | 地类缺失/需补充调查 | 地类不明 |
| `hn-case-q09` | 地类缺失/需补充调查 | 未查明地类 |
| `hn-case-q10` | 旧裁量标准/2021 行为 | 历史行为不套现行幅度 |
| `hn-case-q11` | 部分地类缺失/不能给总额 | 只给已查明部分 |
| `hn-case-q12` | 排除情形/未按批准用途 | 不属于非法占地 |
| `hn-case-q13` | 子类型/临时用地 | 临时用地定性 |
| `hn-case-q14` | 子类型/设施农用地 | 设施农用地定性 |
| `hn-case-q15` | 现行标准/不符合规划/非公益 | 规划符合性影响处罚种类 |
| `hn-case-q16` | 现行标准/公益/永久基本农田/超批准 | 多重情节叠加 |
| `hn-case-q17` | 现行标准/性质未知 | 最简题，适合开场 |
