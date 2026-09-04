import time
from domain.generation_schema import KanjiFormat, KanjiLesson, QuizEvaluation


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
    
def render_kanji_info(kanji_info: KanjiFormat):
    typewriter_print("Kanji Information")
    print("-" * 60)
    typewriter_print(kanji_info.to_polished_string())
    print("-" * 60)
    
def render_kanji_lesson(kanji_lesson: KanjiLesson):
    typewriter_print("Lesson")
    print("-" * 60)
    typewriter_print(kanji_lesson.to_polished_string())
    print("=" * 60)
    
def render_quiz_result(quiz_eval: QuizEvaluation):
    print("=" * 60)
    typewriter_print("Feedback:")
    typewriter_print(quiz_eval.feedback)
    print("-" * 60)
    typewriter_print("Explanation:")
    typewriter_print(quiz_eval.explanation)

def render_anki_result(anki_result:str):
    print("=" * 60)
    typewriter_print("ANKI:")
    typewriter_print(anki_result)
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