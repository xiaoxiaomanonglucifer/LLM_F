"""离线回放 case-main-v1 结果，用于无 GPU 的答辩演示。

只读取 results/<run_id>/<group>_r<repeat>.jsonl，不加载模型、索引或网络。

用法：
  python scripts/demo_replay.py --list
  python scripts/demo_replay.py --question-id hn-case-q01 --group G2
  python scripts/demo_replay.py --question-id hn-case-q01 --compare
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

GROUPS = ("G0", "G1", "G2", "G2-case", "G2-graph")


def _load_group(run_dir: Path, group: str, repeat: int) -> dict[str, dict]:
    path = run_dir / f"{group}_r{repeat}.jsonl"
    if not path.exists():
        raise SystemExit(f"找不到结果文件：{path}")
    records = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            item = json.loads(line)
            records[item["question_id"]] = item
    return records


def _load_all(run_dir: Path, repeat: int) -> dict[str, dict[str, dict]]:
    return {group: _load_group(run_dir, group, repeat) for group in GROUPS}


def _width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int, align: str = "left") -> str:
    padding = " " * max(0, width - _width(text))
    return padding + text if align == "right" else text + padding


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _range(value) -> str:
    if not value:
        return "—"
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{_money(value[0])}–{_money(value[1])} 元"
    return str(value)


def _land_use(facts: dict) -> str:
    parts = []
    for item in facts.get("land_use") or []:
        parts.append(f"{item.get('type')} {_money(item.get('area_m2'))}㎡（{item.get('group')}）")
    return "；".join(parts) or "未查清/未提供"


def _print_list(groups: dict[str, dict[str, dict]]) -> None:
    records = groups["G2"]
    print(f"共 {len(records)} 题；结果目录按题号回放。\n")
    for qid, record in records.items():
        question = record.get("question") or ""
        print(f"{qid}  [{record.get('category')}]")
        print(f"  {question}")


def _print_record(record: dict) -> None:
    steps = record.get("steps") or {}
    facts = steps.get("facts") or {}
    characterization = steps.get("characterization") or {}
    discretion = steps.get("discretion") or {}
    conclusion = steps.get("conclusion") or {}
    evidence = (steps.get("law_application") or {}).get("evidence") or []

    print("=" * 78)
    print(f"题号：{record.get('question_id')}    组别：{record.get('group')}    "
          f"题型：{record.get('category')}")
    print(f"问题：{record.get('question')}")
    print(f"置信度：{record.get('confidence')}")
    print("=" * 78)
    print("\n【模型答案】")
    print((record.get("answer") or "（无答案）").strip())

    print("\n【五步中间结果】")
    print("1) 事实")
    print(f"   面积：{_money(facts.get('area_m2'))}㎡；行为：{'、'.join(facts.get('behavior') or []) or '—'}")
    print(f"   地类：{_land_use(facts)}")
    print(f"   项目性质：{facts.get('project_nature') or '未知'}；规划符合性：{facts.get('plan_conformity') or '未知'}")
    print("2) 定性")
    print(f"   违法行为：{characterization.get('illegal_occupation') or '—'}；"
          f"范围：{characterization.get('scope_status') or '—'}")
    print("3) 法条适用")
    if evidence:
        for item in evidence:
            print(f"   - {item.get('citation')}（{item.get('role')}，来源={item.get('source')}）")
    else:
        print("   - 本组未启用条文检索")
    print("4) 裁量")
    if discretion.get("needs_land_type"):
        print("   - 地类未查全，系统要求补充调查，不给出罚款总额")
    else:
        print(f"   - 罚款区间：{_range(discretion.get('predicted_fine_range'))}")
        if discretion.get("partial_fine_range"):
            print(f"   - 已查明部分区间：{_range(discretion.get('partial_fine_range'))}")
    if discretion.get("version_note"):
        print(f"   - 版本提示：{discretion.get('version_note')}")
    print("5) 结论")
    print(f"   {conclusion.get('text') or '—'}")

    print("\n【引用】")
    citations = record.get("citations") or []
    if citations:
        for item in citations:
            print(f"- {item.get('citation')}（{item.get('role')}，来源={item.get('source')}）")
    else:
        print("- 无（G0 不启用检索）")

    print("\n【类案】")
    similar = record.get("similar_cases") or []
    if similar:
        for hit in similar:
            reasons = "；".join(hit.get("reasons") or [])
            print(f"- {hit.get('case_id')} {hit.get('decision_no')} "
                  f"score={hit.get('score')} 罚款={_money(hit.get('fine_amount'))} 元")
            if reasons:
                print(f"  理由：{reasons}")
    else:
        print("- 无（G1 及以下不启用类案）")

    usage = record.get("usage") or {}
    print("\n【运行信息】")
    print(f"提示词版本：{record.get('prompt_version')}；哈希：{record.get('prompt_hash')}；"
          f"耗时：{record.get('latency_sec')}s；tokens：{usage.get('total_tokens') or usage}")


def _print_compare(groups: dict[str, dict[str, dict]], qid: str) -> None:
    if qid not in groups["G2"]:
        raise SystemExit(f"题号不存在：{qid}")
    print(f"题号：{qid}")
    print(groups["G2"][qid].get("question"))
    print()
    columns = [("组别", 10, "left"), ("答案字数", 10, "right"), ("引用数", 8, "right"),
               ("类案数", 8, "right"), ("罚款区间", 26, "left"), ("置信度", 8, "left")]
    header = " ".join(_pad(name, width, align) for name, width, align in columns)
    print(header)
    print("-" * _width(header))
    for group in GROUPS:
        record = groups[group].get(qid)
        if record is None:
            continue
        citation_count = len(record.get("citations") or [])
        similar_count = len(record.get("similar_cases") or [])
        fine = _range((record.get("steps") or {}).get("discretion", {}).get("predicted_fine_range"))
        answer_len = len((record.get("answer") or "").strip())
        values = [group, str(answer_len), str(citation_count), str(similar_count), fine,
                  record.get("confidence") or "—"]
        print(" ".join(_pad(value, width, align)
                       for value, (_, width, align) in zip(values, columns)))
    print("\n说明：G0 无检索；G1 仅法条检索；G2 为完整组；")
    print("      G2-case 去掉类案，G2-graph 去掉法条图谱，用于消融对比。")


def main() -> None:
    parser = argparse.ArgumentParser(description="离线回放案件实验结果（无需 GPU）")
    parser.add_argument("--run-dir", default="results/case-main-v1")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--group", default="G2", choices=GROUPS)
    parser.add_argument("--question-id", default=None, help="默认取题库第一题")
    parser.add_argument("--list", action="store_true", help="列出全部题目")
    parser.add_argument("--compare", action="store_true", help="对比五组结果")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    groups = _load_all(run_dir, args.repeat)
    if args.list:
        _print_list(groups)
        return

    qid = args.question_id or next(iter(groups["G2"]))
    if args.compare:
        _print_compare(groups, qid)
        return

    record = groups[args.group].get(qid)
    if record is None:
        raise SystemExit(f"题号不存在：{qid}")
    if args.json:
        print(json.dumps(record, ensure_ascii=False, indent=1))
        return
    _print_record(record)


if __name__ == "__main__":
    main()
