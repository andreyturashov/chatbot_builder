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

    uncovered_files: list[tuple[str, int, int, str, list[int]]] = []
    covered_files: list[tuple[str, int, str]] = []

    for file_path, file_data in sorted(files.items()):
        summary = file_data.get("summary", {})
        stmts = summary.get("num_statements", 0)
        miss = summary.get("missing_lines", 0)
        pct = summary.get("percent_covered_display", "0")
        missing_lines = file_data.get("missing_lines", [])

        # Filter: files with <100% coverage
        if miss > 0 or (stmts > 0 and float(pct) < 100.0):
            uncovered_files.append((file_path, stmts, miss, pct, missing_lines))
        else:
            covered_files.append((file_path, stmts, pct))

    lines = [
        "## 📊 Code Coverage Report",
        "",
        f"> **Total Coverage: {total_pct}%** ({total_stmts - total_miss}/{total_stmts} statements covered)",
        "",
    ]

    if uncovered_files:
        lines.append(f"### ⚠️ Files with <100% Coverage ({len(uncovered_files)})")
        lines.append("")
        lines.append(
            "| Module / File | Statements | Missing | Missing Lines | Coverage |"
        )
        lines.append("| :--- | :---: | :---: | :---: | :---: |")
        for file_path, stmts, miss, pct, missing_lines in uncovered_files:
            lines_str = ", ".join(str(line_no) for line_no in missing_lines[:10])
            if len(missing_lines) > 10:
                lines_str += f" (+{len(missing_lines) - 10} more)"
            lines.append(
                f"| `{file_path}` | {stmts} | {miss} | `{lines_str}` | **{pct}%** ❌ |"
            )
        lines.append("")
    else:
        lines.append("🎉 **All files have 100% coverage! No uncovered files.**")
        lines.append("")

    if covered_files:
        lines.append("<details>")
        lines.append(
            f"<summary>📋 View 100% covered files ({len(covered_files)})</summary>"
        )
        lines.append("")
        lines.append("| Module / File | Statements | Coverage |")
        lines.append("| :--- | :---: | :---: |")
        for file_path, stmts, pct in covered_files:
            lines.append(f"| `{file_path}` | {stmts} | **{pct}%** ✅ |")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "coverage.json"
    print(generate_markdown(path))
