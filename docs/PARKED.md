# Parked for V4/V5 (post-v0.3)

Collected during the V3 build. Deliberately not in the MVP.

- **Quiz-variety hardening.** Word-exclusion + retry reduced repeats, but a
  stubborn examiner can still circle one word (observed: 何時 4/5). Options:
  hard reject-and-regenerate, or one-question-per-word dealt like cards.
- **Romaji spacing.** Pykakasi segment joins leave `space before punctuation`
  (`ima , nanji desuka .`). Post-process segments in `infrastructure/romaji.py`.
- **Gloss selection.** Truncation keeps the first 3 JMdict glosses, but the
  first gloss isn't always the primary sense (e.g. 人 → `-ian …`). Prefer the
  gloss matching the kanji meaning, or curate per grade.
- **Unclear-loop cap.** Repeated `unclear` at any gate re-asks forever.
  Decide: Nth unclear → decline/park with a notice.
- **SqliteSaver.** `MemorySaver` drops open sessions on restart (accepted for
  V3 per SPEC). Swap checkpointer for durable sessions.
- **Tutor upgrade.** Raise the 3-call budget, add example-sentence lookup,
  let it compose drills on request. Read-only bounds stay.
- **Answer-with-`?` at quiz.** `mizu, am I right?` routes to tutor, not the
  grader. Needs grammar-aware pre-pass or classifier few-shots; logged via
  `reply_log.jsonl` for evidence.
