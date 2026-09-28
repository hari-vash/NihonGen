# NihonGen V3 eval (Day 8)

- Date:
- Model: gemini-3.5-flash-lite
- Kanji attempted:
- Logs: `evals/verification_failures.jsonl`, `evals/reply_log.jsonl` (this run only)

## 1. Invalid example-word rate

| Proposed words dropped | Dialogue lines flagged | Invalid words shown |
|---|---|---|
| | | |

Pre-verifier baseline: unmeasured (no logging existed before the verifier).
Claim: 0 invalid words shown across N kanji with D drops.

## 2. Classifier accuracy (`evals/check_replies.py --llm`, 62 rows)

| Prompt | Correct | Total |
|---|---|---|
| quiz_readiness | | 20 |
| quiz_answer | | 22 |
| anki_approval | | 20 |

## 3. Quiz pass/fail sanity

- Observed pass (5Q → approval):
- Observed park (3 misses → review ×2 → parked, no Anki calls):
- Suite: `uv run pytest` (all green at commit)

## Verdict

- Invalid-word rate:
- Classifier accuracy:
- Pass/fail sanity:
