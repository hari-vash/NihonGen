from langchain.tools import tool
from domain.generation_schema import KanjiExample,KanjiLesson,VerifiedWord
from connect_anki import request_anki


def format_verified_words(words: list[VerifiedWord]) -> str:
    """Pure render of verified words for card backs. Offline-testable."""
    return "\n".join(f"- {w}" for w in words)

@tool("check_kanji_exists", description="Search Anki collection(deck) to see if a note for this specific kanji already exists.")
def check_kanji_exists(kanji: str, deck:str) -> bool:
    params = {
        "query": f'deck:"{deck}" Front:"{kanji}"'
    }
    note_ids = request_anki(action="findNotes", params=params)
    return len(note_ids) > 0

@tool("create_kanji_flashcard", description="Use this tool to create kanji flashcards and add them to anki deck")
def create_kanji_flashcards(
    kanji: str, 
    onyomi: str, 
    kunyomi: str, 
    kanji_meaning: str,
    deck:str,
    onyomi_examples: list[KanjiExample],
    kunyomi_examples: list[KanjiExample],
    words: list[VerifiedWord] | None = None,
) -> str:

    formatted_onyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in onyomi_examples]
    formatted_kunyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in kunyomi_examples]
    
    onyomi_ex_str = ", ".join(formatted_onyomi)
    kunyomi_ex_str = ", ".join(formatted_kunyomi)

    verified_str = format_verified_words(words or [])
    
    polished_text = (
        f"On'yomi: {onyomi}\n"
        f"Kunyomi: {kunyomi}\n"
        f"Kanji Meaning: {kanji_meaning}\n\n"
        f"Readings and Examples:\n"
        f"On'yomi: {onyomi_ex_str}\n"
        f"Kunyomi: {kunyomi_ex_str}\n\n"
        f"Example Words (verified):\n{verified_str or '-'}"
    )

    html_back = polished_text.replace('\n', '<br>')
        
    params = {
            "note": {
                "deckName": deck,
                "modelName": "Basic",
                "fields": {
                    "Front": kanji,
                    "Back": html_back
                },
            }
        }

    try:
        response = request_anki(action="addNote", params=params)
        if response:
            return "Successfully created the flashcard."
        return "Failed to create the card. Try again."
    except Exception as e:
        return f"Could not create card. Anki returned this error: {str(e)}"

@tool("update_kanji_flashcard",description="Update an existing Japanese kanji flashcard in the specified Anki deck with the latest kanji readings, meanings, examples, and lesson content.")
def update_kanji_flashcard(
    kanji: str,
    onyomi: str,
    kunyomi: str,
    kanji_meaning: str,
    deck: str,
    onyomi_examples: list[KanjiExample],
    kunyomi_examples: list[KanjiExample],
    lesson: KanjiLesson,
    words: list[VerifiedWord] | None = None,
) -> str:

    formatted_onyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in onyomi_examples]

    formatted_kunyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in kunyomi_examples]

    onyomi_ex_str = ", ".join(formatted_onyomi)
    kunyomi_ex_str = ", ".join(formatted_kunyomi)

    lesson_text = lesson.to_polished_string()
    verified_str = format_verified_words(words or [])

    polished_text = (
        f"On'yomi: {onyomi}\n"
        f"Kun'yomi: {kunyomi}\n"
        f"Meaning: {kanji_meaning}\n\n"
        f"Readings and Examples:\n"
        f"On'yomi: {onyomi_ex_str}\n"
        f"Kun'yomi: {kunyomi_ex_str}\n\n"
        f"Example Words (verified):\n{verified_str or '-'}\n\n"
        f"────────────────────\n\n"
        f"{lesson_text}"
    )

    html_back = polished_text.replace("\n", "<br>")

    search_params = {"query": f'deck:"{deck}" Front:"{kanji}"'}

    try:
        note_ids = request_anki(
            action="findNotes",
            params=search_params,
        )

        if not note_ids:
            return (f"Could not update '{kanji}': no existing flashcard was found in deck '{deck}'.")

        if len(note_ids) > 1:
            return (f"Could not update '{kanji}': found {len(note_ids)} matching notes in deck '{deck}'. Refusing to update automatically.")

        note_id = note_ids[0]

        update_params = {
            "note": {
                "id": note_id,
                "fields": {
                    "Front": kanji,
                    "Back": html_back,
                },
            }
        }

        request_anki(action="updateNoteFields",params=update_params)

        return (f"Successfully updated the flashcard for '{kanji}' in deck '{deck}'.")

    except Exception as e:
        return (f"Failed to update the flashcard for '{kanji}': {str(e)}")