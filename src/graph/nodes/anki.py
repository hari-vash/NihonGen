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

    return {"last_reply": str(decision), "reply_prompt": "anki_approval"}


def update_flashcard(state: State):
    facts = state["dictionary_facts"]
    result = update_kanji_flashcard.invoke(
        {
            "kanji": state["kanji"],
            "onyomi": ", ".join(facts.onyomi),
            "kunyomi": ", ".join(facts.kunyomi),
            "kanji_meaning": "; ".join(facts.meanings),
            "deck": state["deck"],
            "onyomi_examples": [],
            "kunyomi_examples": [],
            "words": [w.model_dump() for w in state["lesson"].words],
            "lesson": state["lesson"],
        }
    )

    return {"anki_status": result}


def approve_create(state: State):
    decision = interrupt({"type": "anki_create_approval",
            "message": f"Do you want to add the Kanji {state['kanji']} to the Anki deck '{state['deck']}'?"})

    return {"last_reply": str(decision), "reply_prompt": "anki_approval"}


def create_flashcard(state: State):
    facts = state["dictionary_facts"]

    result = create_kanji_flashcards.invoke(
        {
            "kanji": state["kanji"],
            "onyomi": ", ".join(facts.onyomi),
            "kunyomi": ", ".join(facts.kunyomi),
            "kanji_meaning": "; ".join(facts.meanings),
            "deck": state["deck"],
            "onyomi_examples": [],
            "kunyomi_examples": [],
            "words": [w.model_dump() for w in state["lesson"].words],
            "lesson": state["lesson"],
        }
    )

    return {"anki_status": result}