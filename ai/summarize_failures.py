"""Summarise failed tests from a JUnit XML report into a short root-cause note.

Usage:  python -m ai.summarize_failures reports/junit.xml
Output: reports/failure_summary.md (also appended to $GITHUB_STEP_SUMMARY in CI)
"""
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ai.llm import ask

SYSTEM = ("You are a QA lead. Given failed automated test details, group failures by "
          "likely root cause, say whether each looks like a product bug, a test/locator "
          "issue, or an environment problem, and suggest the next debugging step. "
          "Be concise: max 10 lines.")


def collect_failures(xml_path):
    failures = []
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        for tag in ("failure", "error"):
            node = case.find(tag)
            if node is not None:
                msg = (node.get("message") or "").strip().splitlines()[:3]
                failures.append((f"{case.get('classname')}::{case.get('name')}", " ".join(msg)))
    return failures


def offline_summary(failures):
    return "\n".join(f"- `{name}`: {msg[:200]}" for name, msg in failures) + \
        "\n\n_Set ANTHROPIC_API_KEY to get an AI root-cause analysis instead of this raw list._"


def main(xml_path):
    if not Path(xml_path).exists():
        sys.exit(f"{xml_path} not found")
    failures = collect_failures(xml_path)
    if not failures:
        text = "All tests passed. Nothing to summarise."
    else:
        prompt = "\n".join(f"{n}\n  {m}" for n, m in failures)
        text = ask(prompt, SYSTEM) or offline_summary(failures)
    out = f"## Test failure summary\n\n{text}\n"
    Path("reports").mkdir(exist_ok=True)
    Path("reports/failure_summary.md").write_text(out)
    print(out)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "reports/junit.xml")
