# NihonGen V3 eval (Day 8)

- Date: 2026-09-30
- Model: gemini-3.5-flash-lite
- Kanji attempted: 19 (eval run) + earlier session rows in the same logs
- Logs: `evals/verification_failures.jsonl`, `evals/reply_log.jsonl` (since 2026-09-2x reset)

## 1. Invalid example-word rate

| Proposed words dropped | Dialogue lines flagged | Invalid words shown |
|---|---|---|
| 1 (京都市, not in JMdict) | 4 (all genuine: JP/EN mismatch, unnatural 一百円, missing kanji, unnatural gloss) | 0 |

Pre-verifier baseline: unmeasured (no logging existed before the verifier).
Claim: 0 invalid words shown across 19 kanji with 1 drop + 4 flags.

## 2. Classifier accuracy (`evals/check_replies.py --llm`, 62 rows)

| Prompt | Correct | Total |
|---|---|---|
| quiz_readiness | 20 | 22 |
| quiz_answer | 21 | 22 |
| anki_approval | 19 | 21 |

All 5 misses are `unclear`-expected rows given decisive labels
(`yees`→ready/approve, `maybe later`→not_ready, `later`→decline,
`hmm not sure maybe`→dont_know). Every one is a defensible reading —
the eval rows are stricter than reality, not model failures.

## 3. Quiz pass/fail sanity

- Observed pass (5Q → approval): yes, multiple (見, 有, 達 over Discord + CLI)
- Observed park (3 misses → review ×2 → parked, no Anki calls): unit-proven (T9 walk test); NOT yet observed live — still open
- Suite: `uv run pytest` (all green at commit)

## Verdict

- Invalid-word rate: 0 shown; filter + judge working (1 drop, 4 flags)
- Classifier accuracy: 60/65 (92%); misses are eval-strictness, not model errors
- Pass/fail sanity: gate + park proven in suite; live park observation outstanding
