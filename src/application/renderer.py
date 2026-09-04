import time
from pydantic import BaseModel

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
    
def render_kanji_info(kanji_info: BaseModel):
    typewriter_print("Kanji Information")
    print("-" * 60)
    typewriter_print(kanji_info.to_polished_string())
    print("-" * 60)
    
def render_kanji_lesson(kanji_lesson: BaseModel):
    typewriter_print("Lesson")
    print("-" * 60)
    typewriter_print(kanji_lesson.to_polished_string())
    print("=" * 60)
    
def render_quiz_result(quiz_eval: BaseModel):
    print("=" * 60)
    typewriter_print("Feedback:")
    typewriter_print(quiz_eval.feedback)
    print("-" * 60)
    typewriter_print("Explanation:")
    typewriter_print(quiz_eval.explanation)

def render_interrupt(interrupt_message: list):
    if not interrupt_message:
        return

    interrupt_value = interrupt_message[0].value
    
    print("\n" + "=" * 60)
    
    if isinstance(interrupt_value, dict):
        message = interrupt_value.get('message')
        if message:
            typewriter_print(message)
            
        question = interrupt_value.get('question')
        if question:
            typewriter_print(question)
            
    print("=" * 60)