# NihonGen

VERSION 1
────────────────────────
Basic Anki automation

```mermaid
flowchart TD
    Start([START]) --> Analyze[ANALYZE KANJI]
    Analyze --> Lesson[GENERATE LESSON]
    Analyze --> Print[PRINT]
    Lesson --> Print
    Lesson --> Check[CHECK KANJI EXISTS]
    Check -->|EXISTS| Finish([FINISH])
    Check -->|MISSING| Create[CREATE FLASHCARD and ADD TO ANKI DECK]
    Create --> Finish
```

✅ COMPLETE


VERSION 2
────────────────────────
Document → MCP → Kanji processing → Anki

✅ COMPLETE


VERSION 3
────────────────────────
Interactive Kanji Tutor

• Better lesson schema
• Separate system prompts
• Multi-turn conversation
• Conversation memory
• HITL
• Quiz/evaluation
• Pass/fail loop
• Only advance after passing
• User approval before Anki mutation


VERSION 4
────────────────────────
Learning Pipeline / Staging

• Holdout database
• Study batches
• e.g. 10 kanji/session
• Flashcard lifecycle
• Staged → approved → Anki
• Resume unfinished sessions


VERSION 5
────────────────────────
Adaptive Learning

• Read Anki study/progress data
• Track learner progress
• Determine active vs established kanji
• Reuse learned kanji in:
    - examples
    - conversations
    - quizzes
• Personalized lesson difficulty


VERSION 6
────────────────────────
Production Hardening

• Modular architecture
• Logging
• Testing
• Persistence
• Retry policies
• Idempotency
• Observability
• Error recovery
• Deployment