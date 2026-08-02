#!/usr/bin/env python3
"""
Spec Review Generator

Analyzes all feature specification directories under specs/ and produces a structured,
high-density Markdown quality audit report with executive metrics, a feature matrix,
and collapsible detailed breakdowns.
"""

import argparse
import re
from pathlib import Path


def make_progress_bar(completed: int, total: int, length: int = 10) -> str:
    """Generate a visual ASCII progress bar."""
    if total == 0:
        return "`[░░░░░░░░░░]` 0%"
    pct = int((completed / total) * 100)
    filled = int((completed / total) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"`[{bar}]` {pct}%"


def format_fr_summary(fr_list: list[str]) -> str:
    """Format requirement IDs into a compact summary string."""
    if not fr_list:
        return "None"

    def fr_key(fr_str: str) -> int:
        match = re.search(r"\d+", fr_str)
        return int(match.group()) if match else 0

    fr_sorted = sorted(set(fr_list), key=fr_key)
    count = len(fr_sorted)
    if count == 1:
        return f"{count} ({fr_sorted[0]})"
    elif count <= 3:
        joining = ", ".join(fr_sorted)
        return f"{count} ({joining})"
    else:
        return f"{count} ({fr_sorted[0]}..{fr_sorted[-1]})"


def _process_single_spec_dir(p: Path) -> dict | None:
    """Process a single directory and return feature metrics if valid."""
    dir_name = p.name
    spec_file = p / "spec.md"
    plan_file = p / "plan.md"
    tasks_file = p / "tasks.md"

    spec_exists = spec_file.is_file()
    plan_exists = plan_file.is_file()
    tasks_exists = tasks_file.is_file()

    allowed_non_spec_dirs = {"personas"}
    if dir_name in allowed_non_spec_dirs or not (
        spec_exists or plan_exists or tasks_exists or re.match(r"^\d{3}-", dir_name)
    ):
        return None

    fr_matches: list[str] = []
    if spec_exists:
        content = spec_file.read_text(encoding="utf-8")
        fr_matches = re.findall(r"FR-\d+", content)

    total_tasks = 0
    completed_tasks = 0
    if tasks_exists:
        t_content = tasks_file.read_text(encoding="utf-8")
        total_tasks = len(re.findall(r"- \[(?: |x)\]", t_content))
        completed_tasks = len(re.findall(r"- \[x\]", t_content))

    if not (spec_exists and plan_exists and tasks_exists):
        status_badge = "⚠️ Incomplete"
    elif total_tasks > 0 and completed_tasks == total_tasks:
        status_badge = "🎉 Complete"
    elif completed_tasks > 0:
        status_badge = "🚧 In Progress"
    else:
        status_badge = "🆕 Not Started"

    return {
        "name": dir_name,
        "spec": spec_exists,
        "plan": plan_exists,
        "tasks": tasks_exists,
        "fr": fr_matches,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "status": status_badge,
    }


def analyze_specs(specs_dir: Path) -> tuple[list[dict], list[str], dict]:
    """Scan specs_dir and collect feature audit statistics."""
    if not specs_dir.exists():
        return [], [], {}

    features: list[dict] = []
    non_spec_dirs: list[str] = []

    total_tasks_all = 0
    completed_tasks_all = 0
    total_reqs_all: set[str] = set()

    done_features = 0
    in_progress_features = 0
    not_started_features = 0
    incomplete_features = 0

    for p in sorted(specs_dir.iterdir()):
        if not p.is_dir():
            continue

        feat_data = _process_single_spec_dir(p)
        if feat_data is None:
            non_spec_dirs.append(p.name)
            continue

        features.append(feat_data)
        total_reqs_all.update(feat_data["fr"])
        total_tasks_all += feat_data["total_tasks"]
        completed_tasks_all += feat_data["completed_tasks"]

        status = feat_data["status"]
        if status == "🎉 Complete":
            done_features += 1
        elif status == "🚧 In Progress":
            in_progress_features += 1
        elif status == "🆕 Not Started":
            not_started_features += 1
        else:
            incomplete_features += 1

    metrics = {
        "total_features": len(features),
        "done_features": done_features,
        "in_progress_features": in_progress_features,
        "not_started_features": not_started_features,
        "incomplete_features": incomplete_features,
        "total_tasks_all": total_tasks_all,
        "completed_tasks_all": completed_tasks_all,
        "total_reqs_count": len(total_reqs_all),
    }

    return features, non_spec_dirs, metrics


def _build_executive_summary(metrics: dict) -> list[str]:
    """Build Executive Summary Dashboard markdown block."""
    total_features = metrics["total_features"]
    done_features = metrics["done_features"]
    in_progress_features = metrics["in_progress_features"]
    not_started_features = metrics["not_started_features"]
    incomplete_features = metrics["incomplete_features"]
    completed_tasks_all = metrics["completed_tasks_all"]
    total_tasks_all = metrics["total_tasks_all"]
    total_reqs_count = metrics["total_reqs_count"]

    pct_complete = int((done_features / total_features) * 100) if total_features > 0 else 0
    overall_progress_bar = make_progress_bar(completed_tasks_all, total_tasks_all, length=12)

    summary = [
        "#### 📊 Executive Summary Dashboard",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| 📁 **Total Active Features** | **{total_features}** feature specs |",
        f"| 🎉 **Completed Features** | **{done_features}** complete ({pct_complete}%) |",
        f"| 🚧 **In-Progress Features** | **{in_progress_features}** active |",
        f"| 🆕 **Not Started Features** | **{not_started_features}** pending |",
    ]

    if incomplete_features > 0:
        summary.append(
            f"| ⚠️ **Incomplete Artifacts** | **{incomplete_features}** missing spec files |"
        )

    summary.extend(
        [
            f"| 📋 **Traced Requirements** | **{total_reqs_count}** unique `FR-XXX` IDs |",
            (
                f"| 🎯 **Overall Task Execution** | "
                f"**{completed_tasks_all} / {total_tasks_all}** tasks completed |"
            ),
            f"| 📈 **Overall Progress** | {overall_progress_bar} |",
            "",
        ]
    )
    return summary


def generate_report(features: list[dict], non_spec_dirs: list[str], metrics: dict) -> str:
    """Generate Markdown audit report from feature statistics."""
    report: list[str] = [
        "### 📐 SpecKit Specification Quality Audit",
        "",
    ]

    if not features:
        report.append("ℹ️ No feature specification directories found under `specs/`.")  # noqa: RUF001
        return "\n".join(report)

    report.extend(_build_executive_summary(metrics))

    # 2. Specification Audit Matrix (Table)
    report.extend(
        [
            "#### 📋 Specification Audit Matrix",
            "",
            "| Feature | Artifacts | Requirements | Tasks | Progress Bar | Status |",
            "| :--- | :---: | :---: | :---: | :--- | :---: |",
        ]
    )

    for f in features:
        artifacts_str = (
            f"spec:{'✅' if f['spec'] else '❌'} "
            f"plan:{'✅' if f['plan'] else '❌'} "
            f"tasks:{'✅' if f['tasks'] else '❌'}"
        )
        req_str = format_fr_summary(f["fr"])
        task_str = f"{f['completed_tasks']}/{f['total_tasks']}"
        prog_bar = make_progress_bar(f["completed_tasks"], f["total_tasks"], length=8)
        status = f["status"]
        name = f["name"]
        line = f"| `{name}` | {artifacts_str} | {req_str} | {task_str} | {prog_bar} | {status} |"
        report.append(line)

    report.extend(
        [
            "",
            "<details>",
            "<summary><b>🔍 View Detailed Feature Breakdown</b></summary>",
            "",
        ]
    )

    def fr_key(fr_str: str) -> int:
        match = re.search(r"\d+", fr_str)
        return int(match.group()) if match else 0

    for f in features:
        report.append(f"#### Feature: `{f['name']}`")
        report.append(
            f"- **Files**: `spec.md`: {'✅' if f['spec'] else '❌'} | "
            f"`plan.md`: {'✅' if f['plan'] else '❌'} | "
            f"`tasks.md`: {'✅' if f['tasks'] else '❌'}"
        )

        fr_sorted = sorted(set(f["fr"]), key=fr_key)
        req_detail = (
            f"{len(fr_sorted)} unique requirement IDs ({', '.join(fr_sorted)})"
            if fr_sorted
            else "None found"
        )
        report.append(f"- **Requirements Traced**: {req_detail}")

        progress_pct = (
            int((f["completed_tasks"] / f["total_tasks"]) * 100) if f["total_tasks"] > 0 else 0
        )
        t_comp = f["completed_tasks"]
        t_tot = f["total_tasks"]
        prog_msg = (
            f"- **Task Execution Progress**: {t_comp}/{t_tot} tasks completed ({progress_pct}%)"
        )
        report.append(prog_msg)
        report.append("")

    report.extend(["</details>", ""])

    if non_spec_dirs:
        skipped_str = ", ".join(f"`{d}`" for d in non_spec_dirs)
        report.extend([f"*Note: Excluded non-feature directory: {skipped_str}*", ""])

    report.append("*Automated report generated by Spec Review Bot.*")
    return "\n".join(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Spec Review Generator")
    parser.add_argument(
        "--specs-dir",
        type=Path,
        default=Path("specs"),
        help="Path to specs directory (default: specs)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("spec_review_report.md"),
        help="Path to output markdown file (default: spec_review_report.md)",
    )
    args = parser.parse_args()

    features, non_spec_dirs, metrics = analyze_specs(args.specs_dir)
    report_md = generate_report(features, non_spec_dirs, metrics)

    args.output.write_text(report_md, encoding="utf-8")
    print(f"Spec review report successfully written to {args.output}")


if __name__ == "__main__":
    main()
