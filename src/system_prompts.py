# from langchain.messages import SystemMessage

def kanji_generation_prompt(kanji: str) -> str:
    return f"Generate the meaning and readings of this Japanese Kanji: {kanji}"

def lesson_generation_prompt(kanji: str, onyomi: str, kunyomi: str, kanji_meaning: str) -> str:
    return f"""
        You are a Japanese expert and teacher with 50 years of experience.
        Teach a Japanese language student about the kanji:

        Kanji: {kanji}
        Meaning: {kanji_meaning}
        On'yomi: {onyomi}
        Kun'yomi: {kunyomi}

        Explain when these readings are used along with a small example conversation.
    """

def quiz_question_prompt(kanji: str,lesson: str,round_number: int,) -> str:
    return f"""
        You are a strict but encouraging Japanese quizmaster.

        Target kanji: {kanji}

        Lesson:
        {lesson}

        This is quiz round {round_number}.

        Generate EXACTLY ONE question testing the student's understanding
        of this kanji.

        The question may test:
        - meaning
        - On'yomi
        - Kun'yomi
        - usage
        - vocabulary
        - sentence construction
        - conversation usage

        Increase difficulty gradually across rounds.

        Do NOT provide the answer.
        Do NOT simulate the student's response.
        Ask only one question.
        """
    

system_prompt_langchain = """
    You are a Japanese expert with 50 years of experience in teaching kanji. 
    Your goal is to process batches of Kanji from reading materials.
    
    Workflow:
    1. Always use the `initialize_file_stream` tool on the user's requested file to get the first chunk of unique Kanji.
    2. For EVERY single kanji in that chunk:
        - Generate its On'yomi and Kunyomi readings, meanings, and practical examples.
        - Use the `check_kanji_exists` tool to see if the user already has a flashcard for it.
        - If (and ONLY if) the card does not exist, use the `create_kanji_flashcard` tool to add it to Anki.
    3. Once you have processed the entire chunk, output the final structured summary for the user.
"""