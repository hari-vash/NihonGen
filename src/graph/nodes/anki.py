from langgraph.types import interrupt
from graph.state import State
from tools import check_kanji_exists,create_kanji_flashcards,update_kanji_flashcard

def check_anki(state: State):
    exists = check_kanji_exists.invoke({"kanji": state["kanji"],"deck": state["deck"]})

    return {"exists": exists}


def approve_update(state: State):
    decision = interrupt({
            "type": "anki_update_approval",
            "message": (
                f"The Kanji {state['kanji']} already exists in the Anki deck '{state['deck']}'.\n\n"
                "Do you want to update the existing flashcard with the newly generated content?"
            )
        })

    return {"user_decision": str(decision)}


def update_flashcard(state: State):
    kanji_info = state["kanji_info"]
    result = update_kanji_flashcard.invoke(
        {
            "kanji": state["kanji"],
            "onyomi": kanji_info.onyomi,
            "kunyomi": kanji_info.kunyomi,
            "kanji_meaning": kanji_info.kanji_meaning,
            "deck": state["deck"],
            "onyomi_examples": kanji_info.onyomi_examples,
            "kunyomi_examples": kanji_info.kunyomi_examples,
            "lesson": state["lesson"],
        }
    )

    print("\nAnki:")
    print(result)

    return {"anki_status": result}


def approve_create(state: State):
    decision = interrupt({"type": "anki_create_approval",
            "message": f"Do you want to add the Kanji {state['kanji']} to the Anki deck '{state['deck']}'?"})

    return {"user_decision": str(decision)}


def create_flashcard(state: State):
    kanji_info = state["kanji_info"]

    result = create_kanji_flashcards.invoke(
        {
            "kanji": state["kanji"],
            "onyomi": kanji_info.onyomi,
            "kunyomi": kanji_info.kunyomi,
            "kanji_meaning": kanji_info.kanji_meaning,
            "deck": state["deck"],
            "onyomi_examples": kanji_info.onyomi_examples,
            "kunyomi_examples": kanji_info.kunyomi_examples,
            "lesson": state["lesson"],
        }
    )

    print("\nAnki:")
    print(result)

    return {"anki_status": result}