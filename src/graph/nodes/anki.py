from langgraph.runtime import Runtime
from langgraph.types import interrupt
from domain.generation_schema import AnkiResult
from graph.context import RuntimeContext
from graph.state import State
from infrastructure.anki import AnkiError, DuplicateNoteError, format_card_back

DIFF_PREVIEW_CHARS = 500


def _display(back_html: str) -> str:
    text = back_html.replace("<br>", "\n")
    if len(text) > DIFF_PREVIEW_CHARS:
        return text[:DIFF_PREVIEW_CHARS] + "…"
    return text


async def check_anki(state: State, runtime: Runtime[RuntimeContext]):
    note_ids = await runtime.context.anki.find_notes(state["kanji"])
    if not note_ids:
        return {"exists": False, "current_back": None}
    current_back = await runtime.context.anki.get_back(note_ids[0])
    return {"exists": True, "current_back": current_back}


def approval_message(state: State) -> str:
    """Pure approval text with before/after diff. Offline-testable."""
    diff = ""
    if state.get("current_back"):
        new_back = format_card_back(state["dictionary_facts"], state["lesson"])
        diff = (
            "\n\nCurrent card:\n"
            f"{_display(state['current_back'])}\n\n"
            "Proposed card:\n"
            f"{_display(new_back)}\n"
        )
    return (
        f"The Kanji {state['kanji']} already exists in the Anki deck '{state['deck']}'.\n\n"
        "Do you want to update the existing flashcard with the newly generated content?"
        f"{diff}"
    )


def approve_update(state: State):
    decision = interrupt({
            "type": "anki_update_approval",
            "message": approval_message(state),
        })

    return {"last_reply": str(decision), "reply_prompt": "anki_approval"}


async def update_flashcard(state: State, runtime: Runtime[RuntimeContext]):
    back = format_card_back(state["dictionary_facts"], state["lesson"])
    try:
        note_ids = await runtime.context.anki.find_notes(state["kanji"])
        if not note_ids:
            return {"anki_status": AnkiResult(
                ok=False, action="failed",
                message=f"Could not update '{state['kanji']}': no existing flashcard was found.",
            )}
        if len(note_ids) > 1:
            return {"anki_status": AnkiResult(
                ok=False, action="failed",
                message=f"Could not update '{state['kanji']}': found {len(note_ids)} matching notes. Refusing to update automatically.",
            )}
        await runtime.context.anki.update_note(note_ids[0], state["kanji"], back)
        return {"anki_status": AnkiResult(
            ok=True, action="updated",
            message=f"Successfully updated the flashcard for '{state['kanji']}'.",
        )}
    except AnkiError as exc:
        return {"anki_status": AnkiResult(
            ok=False, action="failed",
            message=f"Failed to update the flashcard for '{state['kanji']}': {exc}",
        )}


def approve_create(state: State):
    decision = interrupt({"type": "anki_create_approval",
            "message": f"Do you want to add the Kanji {state['kanji']} to the Anki deck '{state['deck']}'?"})

    return {"last_reply": str(decision), "reply_prompt": "anki_approval"}


async def create_flashcard(state: State, runtime: Runtime[RuntimeContext]):
    back = format_card_back(state["dictionary_facts"], state["lesson"])
    try:
        note_ids = await runtime.context.anki.find_notes(state["kanji"])
        if note_ids:
            return {"anki_status": AnkiResult(
                ok=False, action="exists",
                message=f"'{state['kanji']}' is already in the deck. No duplicate created.",
            )}
        await runtime.context.anki.add_note(state["kanji"], back)
        return {"anki_status": AnkiResult(
            ok=True, action="created",
            message="Successfully created the flashcard.",
        )}
    except DuplicateNoteError:
        return {"anki_status": AnkiResult(
            ok=False, action="exists",
            message=f"'{state['kanji']}' is already in the deck. No duplicate created.",
        )}
    except AnkiError as exc:
        return {"anki_status": AnkiResult(
            ok=False, action="failed",
            message=f"Could not create card. Anki returned this error: {exc}",
        )}
