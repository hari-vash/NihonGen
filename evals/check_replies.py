"""Reply eval: pre-pass accuracy offline, full classifier with --llm.

Scoring per row:
- exact:   pre-pass returned the expected label (no LLM needed)
- deferred: pre-pass returned "clarify" (correctly handed to the classifier)
- misroute: pre-pass returned a WRONG label (a bug; exits non-zero)

Usage (from repo root):
    uv run python evals/check_replies.py
    uv run python evals/check_replies.py --llm   # needs GOOGLE_API_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from graph.helpers import prepass_reply  # noqa: E402

FILES = {
    "quiz_readiness": "evals/reply_readiness.jsonl",
    "quiz_answer": "evals/reply_answer.jsonl",
    "anki_approval": "evals/reply_approval.jsonl",
}


def check_prepass() -> int:
    total_exact = total_deferred = 0
    failures = []
    for prompt, rel in FILES.items():
        exact = deferred = 0
        rows = _load(rel)
        for row in rows:
            got = prepass_reply(row["text"], prompt)
            if got == row["expected"]:
                exact += 1
            elif got == "clarify":
                deferred += 1
            else:
                failures.append((prompt, row["text"], row["expected"], got))
        total_exact += exact
        total_deferred += deferred
        print(f"{prompt}: {exact}/{len(rows)} exact, {deferred} deferred to classifier")
    print(f"total: {total_exact} exact, {total_deferred} deferred, {len(failures)} misrouted")
    for prompt, text, expected, got in failures:
        print(f"  MISROUTE [{prompt}] {text!r}: expected {expected}, got {got}")
    return 1 if failures else 0


def check_llm() -> int:
    from llm.model import build_models
    from graph.nodes.reply import classify_label

    models = build_models()
    bad = 0
    for prompt, rel in FILES.items():
        correct = 0
        rows = _load(rel)
        for row in rows:
            got = asyncio.run(classify_label(prompt, row["text"], models.classifier))
            ok = got == row["expected"]
            correct += ok
            if not ok:
                bad += 1
                print(f"  MISS [{prompt}] {row['text']!r}: expected {row['expected']}, got {got}")
        print(f"{prompt}: {correct}/{len(rows)} final-label accuracy")
    return 1 if bad else 0


def _load(rel: str) -> list[dict]:
    with open(REPO_ROOT / rel, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> int:
    if "--llm" in sys.argv:
        if not os.environ.get("GOOGLE_API_KEY"):
            print("GOOGLE_API_KEY not set, skipping classifier check")
            return 0
        return check_llm()
    return check_prepass()


if __name__ == "__main__":
    raise SystemExit(main())
