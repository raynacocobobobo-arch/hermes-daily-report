#!/usr/bin/env python3
"""Save ChatGPT-generated Hermes Daily Research markdown reports."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "chatgpt"
DATE_FORMAT = "%Y-%m-%d"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save ChatGPT Hermes Daily Research to reports/chatgpt/YYYY-MM-DD/report.md"
    )
    parser.add_argument(
        "--date",
        default=datetime.now(ZoneInfo("Asia/Shanghai")).strftime(DATE_FORMAT),
        help="Report date in YYYY-MM-DD. Defaults to today in Asia/Shanghai.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Markdown file to save. If omitted, content is read from stdin.",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Commit report changes after saving.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push after committing. Implies --commit.",
    )
    return parser.parse_args()


def validate_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise SystemExit(f"Invalid --date {value!r}; expected YYYY-MM-DD.") from exc
    return parsed.strftime(DATE_FORMAT)


def read_report(input_path: Path | None) -> str:
    if input_path:
        text = input_path.read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    text = text.strip()
    if not text:
        raise SystemExit("Refusing to save an empty ChatGPT report.")
    return text + "\n"


def save_report(report_date: str, text: str) -> Path:
    report_dir = REPORT_ROOT / report_date
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"
    report_path.write_text(text, encoding="utf-8")
    return report_path


def run_git(args: list[str]) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def commit_report(report_path: Path, report_date: str, push: bool) -> None:
    relative = report_path.relative_to(ROOT).as_posix()
    run_git(["add", relative])

    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", relative],
        cwd=ROOT,
        check=False,
    )
    if diff.returncode == 0:
        print(f"No report changes to commit: {relative}")
        return

    run_git(["commit", "-m", f"chore: save ChatGPT daily research {report_date}"])
    if push:
        run_git(["push"])


def main() -> None:
    args = parse_args()
    report_date = validate_date(args.date)
    report = read_report(args.input)
    report_path = save_report(report_date, report)
    print(f"Saved: {report_path.relative_to(ROOT).as_posix()}")

    if args.commit or args.push:
        commit_report(report_path, report_date, push=args.push)


if __name__ == "__main__":
    main()
