# NihonGen V3: Day-by-Day Plan

Companion to [`SPEC.md`](SPEC.md). Dates: Sun 20 Sep to Sun 27 Sep 2026, with Mon 28 Sep as buffer.
Assumes about 5 focused hours on the project.

**Daily rules**
- Before each commit, be able to explain every new node in two sentences.
- End each day with a commit and a one-line "what's next" note.
- Add or extend a test for anything that has a pure function (routing, mastery gate, classifier pre-pass, verifier).

## Priority order (and cut list)

Must keep: dictionary verification, mastery gate, Anki approval gate, the A1 fix, README with demo.

If you fall behind, cut in this order:
1. Tutor tool use (keep the classifier and a plain Q&A answer).
2. The judge pass on dialogue (keep the dictionary checks).
3. Discord (ship the CLI with a demo video instead).

## Day 1, Sun 20 Sep: stabilize and fix the baseline

- [ ] Fix **A1** in `graph/routing.py`: `route_document` must route on non-empty `current_chunk`, not `has_more`. Add `tests/test_routing.py` covering `route_chunk` and `route_document` (16-kanji and 31-kanji cases).
- [ ] Fix **A2**: add `pending_explanation` to `graph/state.py`, set it in `explain_again`, render it in `runner.py`, and remove the `new_messages[0]` heuristic.
- [ ] Move the hard-coded `"Test_Deck1"` (`application/runner.py`) into a `Config(BaseSettings)` using `pydantic-settings`.
- [ ] Pick one dependency source (`pyproject.toml` + `uv.lock`), delete `requirements.txt`, and drop unused deps.
- [ ] Update `README.md`: mark V3 in progress, add setup steps (AnkiConnect, `.env`, `uv sync`, run command).
- [ ] Copy `SPEC.md` and `PLAN.md` into `docs/`. Create an `evals/` folder.
- [ ] Regression run: 1 kanji, 3 kanji, and a 20-kanji document.
- Jobs: resume v1 with NihonGen listed as in progress, LinkedIn headline, a list of about 40 target roles.
- **Done when:** a 20-kanji document processes all 20, and `main` is pushed.

## Day 2, Mon 21 Sep: dictionary layer

- [ ] Download KANJIDIC2 and JMdict, build a local index (SQLite or JSON) under `data/`.
- [ ] Create `infrastructure/dictionary.py` with `DictionaryService.get_kanji()` and `lookup_word()`.
- [ ] Add `KanjiFacts` to `domain/generation_schema.py`, the `JsonPlusSerializer` allowlist, and `RuntimeContext`.
- [ ] Replace `analyze_kanji` with a `dictionary_lookup` node (no LLM call).
- [ ] Render facts from the dictionary in `renderer.py`.
- [ ] Unit tests on 10 known kanji (for example 友, 火, 日).
- [ ] Add EDRDG attribution to the README.
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** the kanji info panel is 100% dictionary-sourced.

## Day 3, Tue 22 Sep: verification

- [ ] Rework `lesson_generation_prompt` to build on `KanjiFacts` (readings become input, not output).
- [ ] Update `KanjiLesson`: verified `words`, a labelled `mnemonic`, and a `dialogue` with no LLM romaji.
- [ ] Generate romaji in code (`pykakasi` or similar) for words and dialogue.
- [ ] Write the `verify_lesson` node: word exists in JMdict, contains the kanji, reading matches. Retry loop (max 2), then drop and log.
- [ ] Add the judge pass for dialogue (JP/EN consistency, naturalness). Drop flagged lines.
- [ ] Log every verification failure to a file for the eval.
- [ ] Unit tests for the verifier using known-good and known-bad words.
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** 10 kanji run with zero invalid example words shown.

## Day 4, Wed 23 Sep: reply routing and tutor

- [ ] Extend `normalize_yes_no` with skip/stop phrases and per-prompt label sets.
- [ ] Add a `classify_reply` node with a small LLM classifier (structured output) for anything the pre-pass returns as `"clarify"`.
- [ ] Wire it after `quiz_readiness`, `wait_for_answer`, `approve_create`, `approve_update`. Handle `unclear` by re-asking.
- [ ] Build the `tutor` node (read-only tools `lookup_kanji`, `lookup_word`, max 3 tool calls) that returns to the same interrupt.
- [ ] Build a 20-reply eval set per prompt state in `evals/`.
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** T6, T7 and T8 pass.

## Day 5, Thu 24 Sep: quiz and mastery

- [ ] Add `QuizQuestion` and `QuizAttempt`. Make `generate_quiz_question` and `evaluate_quiz_answer` return structured output.
- [ ] Remove `mastered` from `QuizEvaluation` and drop `quiz_round`/`quiz_evaluation` in favour of `quiz_attempts`.
- [ ] Write the `mastery_gate` (pure function): 5 questions, at most 2 misses, early fail on the 3rd, coverage rule.
- [ ] Add `review_cycles`, cap at 2, and add the `park_kanji` path.
- [ ] Trim or reset `messages` per kanji.
- [ ] Unit tests for the gate (all pass/fail/early-fail/coverage cases).
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** T9 passes and no path reaches Anki without a pass.

## Day 6, Fri 25 Sep: Anki and input modes

- [ ] Move `tools.py` and `connect_anki.py` into `infrastructure/anki.py` as `AnkiClient` (non-blocking, config-driven, `ping()`).
- [ ] One `format_card_back()` for create and update. Add the update diff (fetch current `Back`) and the duplicate guard. Return `AnkiResult`.
- [ ] Add `route_input` at START, `prepare_typed_input`, and typed multi-kanji extraction.
- [ ] Add the early existence check (FR-4) and the end-of-session summary (`results`).
- [ ] Full multi-kanji document regression, including a 20-kanji run.
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** T1 to T5, T10 and T11 pass.

## Day 7, Sat 26 Sep: Discord adapter

- [ ] Introduce a small channel interface (`send`, `ask`) that both the CLI and Discord implement.
- [ ] Write `application/discord_bot.py`: threads, owner allowlist, per-thread lock, chunking, attachments, error messages.
- [ ] Give the bot process ownership of the MCP `ClientSession`.
- [ ] Make `renderer.py` return strings (Discord-safe) instead of printing.
- Jobs: about 10 applications and 5 outreach messages.
- **Done when:** a 3-kanji run works end to end in Discord, including T12 and T13.

## Day 8, Sun 27 Sep: evals, README, demo

- [ ] Run the eval over 15 to 20 kanji. Record: invalid example-word rate before and after, classifier accuracy per prompt, quiz pass/fail sanity.
- [ ] README: pitch, architecture diagram (the mermaid graph from the spec), setup steps, demo GIF or video, EDRDG attribution.
- [ ] Tag `v0.3` and freeze.
- [ ] Update the resume with the real numbers and send a larger batch of applications.

## Mon 28 Sep: buffer

Use it for slippage only. No new features. Ideas go in a parked list for V4 and V5.