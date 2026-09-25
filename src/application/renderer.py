import time
from domain.generation_schema import KanjiFacts, KanjiLesson, QuizAttempt, AnkiResult


def typewriter_print(text: str, delay: float = 0.01):
    """Prints text character by character with a slight delay."""
    for char in str(text):
        print(char, end='', flush=True)
        time.sleep(delay)
    print()

def render_kanji(kanji: str):
    print("\n" + "=" * 60)
    typewriter_print(f"KANJI: {kanji}")
    print("-" * 60)
    
def render_kanji_info(facts: KanjiFacts):
    typewriter_print("Kanji Information")
    print("-" * 60)
    typewriter_print(facts.to_polished_string())
    print("-" * 60)
    
def render_kanji_lesson(kanji_lesson: KanjiLesson):
    typewriter_print("Lesson")
    print("-" * 60)
    typewriter_print(kanji_lesson.to_polished_string())
    print("=" * 60)
    
def render_quiz_result(attempt: QuizAttempt):
    print("=" * 60)
    typewriter_print("Feedback:")
    typewriter_print(attempt.feedback)
    if attempt.outcome != "correct":
        print("-" * 60)
        typewriter_print(f"Correct answer: {attempt.question.expected}")

def render_anki_result(anki_result: AnkiResult):
    print("=" * 60)
    mark = "✓" if anki_result.ok else "✗"
    typewriter_print(f"ANKI [{anki_result.action}]: {mark}")
    typewriter_print(anki_result.message)
    print("=" * 60)

def render_additional_explanation(explanation:str):
    print("=" * 60)
    typewriter_print("Additional Explanation:")
    typewriter_print(explanation)
    print("=" * 60)
    
def render_interrupt(interrupt_value: dict):
    print("\n" + "=" * 60)
    
    if isinstance(interrupt_value, dict):
        message = interrupt_value.get('message')
        if message:
            typewriter_print(message)
            
        question = interrupt_value.get('question')
        if question:
            typewriter_print(question)
            
    print("=" * 60)