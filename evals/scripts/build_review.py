"""
Build a human-readable Q&A review file from E2E eval results.

Merges the customer inputs (from the dataset files under evals/data/e2e/) with the
agent outputs recorded in the report JSONs (evals/results/*_report.json), so you can
review, per turn: what the customer said, what tools fired, and what the agent replied.

Usage:
    python evals/scripts/build_review.py
Writes:
    evals/results/e2e_review.md
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "evals", "data", "e2e")
RESULTS = os.path.join(ROOT, "evals", "results")


def load_inputs(*data_files):
    """scenario_id -> {turn_number: user_content}"""
    inputs = {}
    for fname in data_files:
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            continue
        data = json.load(open(path, encoding="utf-8"))
        for sc in data.get("scenarios", []):
            inputs[sc["id"]] = {t["turn"]: t.get("content", "") for t in sc.get("turns", [])}
    return inputs


def fmt_tools(tool_calls):
    parts = []
    for tc in tool_calls or []:
        if isinstance(tc, str):
            parts.append(f"`{tc}()`")
            continue
        name = tc.get("name", "?")
        args = tc.get("args", {})
        items = args.get("items")
        if items is not None:
            it = ", ".join(f"{i.get('name')}×{i.get('quantity')}" for i in items) or "(rỗng)"
            parts.append(f"`{name}(items=[{it}])`")
        else:
            parts.append(f"`{name}({args})`")
    return "; ".join(parts) if parts else "—"


def render(report_path, inputs, title):
    report = json.load(open(report_path, encoding="utf-8"))
    s = report["summary"]
    out = [
        f"# {title}",
        "",
        f"- Thời điểm: {s.get('timestamp')}",
        f"- Pass rate: **{s.get('pass_rate', 0) * 100:.2f}%** "
        f"({s.get('passed_count')}/{s.get('total_scenarios')})",
        "",
    ]
    for sc in report["results"]:
        sid = sc["id"]
        status = "✅ PASS" if sc.get("success") else "❌ FAIL"
        out.append(f"## {status} — {sid}: {sc.get('name', '')}")
        out.append("")
        sc_inputs = inputs.get(sid, {})
        for t in sc.get("turns", []):
            n = t.get("turn")
            user = sc_inputs.get(n, "(không có trong dataset)")
            out.append(f"**Lượt {n}**")
            out.append("")
            out.append(f"- 🧑 **Khách:** {user}")
            tools = fmt_tools(t.get("tool_calls"))
            if tools != "—":
                out.append(f"- 🔧 **Tool:** {tools}")
            tos = t.get("tool_outputs")
            if tos:
                for to in tos:
                    out.append(f"  - ↳ `{to.get('name')}` → {to.get('content')}")
            out.append(f"- 🤖 **AI:** {t.get('response', '').strip()}")
            assertions = t.get("assertions")
            if assertions:
                marks = []
                for a in assertions:
                    ok = "✅" if a.get("passed") else "❌"
                    line = f"{ok} {a.get('check')}"
                    if not a.get("passed") and "actual" in a:
                        line += f" (actual: {a['actual']})"
                    marks.append(line)
                out.append(f"- 🔎 **Assert:** {' · '.join(marks)}")
            out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def main():
    e2e_inputs = load_inputs("e2e_conversations_part1.json", "e2e_conversations_part2.json")
    oom_inputs = load_inputs("e2e_out_of_menu_test.json")

    sections = []
    e2e_report = os.path.join(RESULTS, "e2e_report.json")
    if os.path.exists(e2e_report):
        sections.append(render(e2e_report, e2e_inputs, "E2E Review — Happy-path conversations"))

    oom_report = os.path.join(RESULTS, "e2e_out_of_menu_report.json")
    if os.path.exists(oom_report):
        sections.append(render(oom_report, oom_inputs, "E2E Review — Out-of-menu / ambiguity"))

    dest = os.path.join(RESULTS, "e2e_review.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n\n".join(sections))
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
