import json
import sys
from pathlib import Path


def generate_markdown(json_path: str) -> str:
    data = json.loads(Path(json_path).read_text())
    files = data.get("files", {})
    totals = data.get("totals", {})

    total_pct = totals.get("percent_covered_display", "100")
    total_stmts = totals.get("num_statements", 0)
    total_miss = totals.get("missing_lines", 0)

    lines = [
        "## 📊 Code Coverage Report",
        "",
        f"> **Total Coverage: {total_pct}%** ({total_stmts - total_miss}/{total_stmts} statements covered)",
        "",
        "| Module / File | Statements | Missing | Coverage |",
        "| :--- | :---: | :---: | :---: |",
    ]

    for file_path, file_data in sorted(files.items()):
        summary = file_data.get("summary", {})
        stmts = summary.get("num_statements", 0)
        miss = summary.get("missing_lines", 0)
        pct = summary.get("percent_covered_display", "0")
        icon = "✅" if float(pct) >= 90 else ("⚠️" if float(pct) >= 75 else "❌")
        lines.append(f"| `{file_path}` | {stmts} | {miss} | **{pct}%** {icon} |")

    lines.append(
        f"| **TOTAL** | **{total_stmts}** | **{total_miss}** | **{total_pct}%** 🎯 |"
    )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "coverage.json"
    print(generate_markdown(path))
