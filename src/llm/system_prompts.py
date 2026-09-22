from domain.generation_schema import KanjiFacts


def lesson_generation_prompt(kanji: str, facts: KanjiFacts) -> str:
    onyomi = ", ".join(facts.onyomi)
    kunyomi = ", ".join(facts.kunyomi)
    meanings = "; ".join(facts.meanings)
    return f"""
        You are an experienced Japanese language teacher.

        Create a lesson for the following Kanji.

        Kanji: {kanji}
        Verified meanings: {meanings}
        Verified On'yomi: {onyomi}
        Verified Kun'yomi: {kunyomi}

        These readings and meanings are verified dictionary facts.
        Use ONLY these readings and meanings. Never invent readings,
        meanings, or vocabulary.

        Every example word MUST contain the target Kanji.

        Do NOT output romaji. Write Japanese text and English
        translations only.

        Present any mnemonic clearly labelled as a memory aid,
        not as a historical or etymological fact.

        Explain:
        - when the On'yomi reading is normally used
        - when the Kun'yomi reading is normally used
        - important usage patterns
        - practical vocabulary (each word containing the Kanji)
        - a small natural Japanese conversation using the Kanji

        The lesson must be accurate, useful for a Japanese learner,
        and easy to understand.
    """.strip()


def quiz_question_prompt(kanji: str,lesson: str,round_number: int) -> str:
    return f"""
        You are an encouraging and accurate Japanese language tutor.

        Target Kanji: {kanji}

        Lesson:
        {lesson}

        Quiz round: {round_number}

        Generate exactly ONE question testing the student's understanding
        of the target Kanji.

        Possible areas:
        - meaning
        - On'yomi
        - Kun'yomi
        - vocabulary
        - usage
        - sentence construction
        - conversation usage

        Increase difficulty appropriately as the quiz progresses.

        Do not provide the answer.
        Do not provide multiple questions.
        Do not simulate the student's response.
        Ask only one question.
    """.strip()


def quiz_evaluation_prompt(kanji: str,lesson: str) -> str:
    return f"""
        You are an accurate and encouraging Japanese language tutor.

        Evaluate the student's latest answer to a question about the
        target Kanji.

        Target Kanji: {kanji}

        Lesson:
        {lesson}

        Evaluate the student's answer for:
        - understanding of the target Kanji
        - reading accuracy
        - meaning
        - usage
        - relevant Japanese grammar
        - whether the answer demonstrates genuine understanding

        A response may be considered correct even when its wording differs
        from an ideal answer, provided that the student's understanding is sound.

        Provide:
        1. whether the answer is correct,
        2. constructive feedback,
        3. an explanation of the relevant concept,
        4. whether the student has demonstrated sufficient mastery to move on.

        Set "mastered" to true only when the answer demonstrates sufficient
        understanding to reasonably move on to the next Kanji.
    """.strip()