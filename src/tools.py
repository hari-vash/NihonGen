from langchain.tools import tool
from kanji_class import KanjiExample
from connect_anki import request_anki

@tool("check_kanji_exists", description="Search Anki collection(deck) to see if a note for this specific kanji already exists.")
def check_kanji_exists(kanji: str) -> bool:
    params = {
        "query": f'deck:"Test_Deck1" "{kanji}"'
    }
    note_ids = request_anki(action="findNotes", params=params)
    return len(note_ids) > 0

@tool("create_kanji_flashcard", description="Use this tool to create kanji flashcards and add them to anki deck")
def create_kanji_flashcard(
    kanji: str, 
    onyomi: str, 
    kunyomi: str, 
    kanji_meaning: str, 
    onyomi_examples: list[KanjiExample],
    kunyomi_examples: list[KanjiExample]
) -> str:

    formatted_onyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in onyomi_examples]
    formatted_kunyomi = [f"{ex.word} [{ex.kana}] ({ex.romaji}) - {ex.meaning}" for ex in kunyomi_examples]
    
    onyomi_ex_str = ", ".join(formatted_onyomi)
    kunyomi_ex_str = ", ".join(formatted_kunyomi)
    
    polished_text = (
        f"On'yomi: {onyomi}\n"
        f"Kunyomi: {kunyomi}\n"
        f"Kanji Meaning: {kanji_meaning}\n\n"
        f"Readings and Examples:\n"
        f"On'yomi: {onyomi_ex_str}\n"
        f"Kunyomi: {kunyomi_ex_str}"
    )

    html_back = polished_text.replace('\n', '<br>')
        
    params = {
            "note": {
                "deckName": "Test_Deck1",
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