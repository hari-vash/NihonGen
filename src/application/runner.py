import asyncio
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from graph.builder import build_graph
from graph.context import RuntimeContext
from graph.helpers import hint_for_interrupt
from llm.model import build_models
from infrastructure.dictionary import DictionaryService
from application import renderer
from application.config import Config

async def run_interactive_graph(graph, initial_state, config, context):
    """
    Run the graph and resume it whenever an interrupt occurs.
    """

    result = await graph.ainvoke(
        initial_state,
        config=config,
        context=context,
    )

    last_rendered_kanji = None
    evaluation_rendered = True
    last_rendered_explanation = None
    last_rendered_anki_status = None
    skip_noticed_for = None

    while True:
        current_kanji = result.get("kanji")

        if current_kanji and current_kanji != last_rendered_kanji:
            evaluation_rendered = False
            last_rendered_explanation = None
            last_rendered_anki_status = None

            renderer.render_kanji(result["kanji"])

            if result.get("dictionary_facts"):
                renderer.render_kanji_info(result["dictionary_facts"])

            if result.get("lesson"):
                renderer.render_kanji_lesson(result["lesson"])

            last_rendered_kanji = current_kanji

        if result.get("quiz_evaluation") and not evaluation_rendered:
            renderer.render_quiz_result(result["quiz_evaluation"])
            evaluation_rendered = True

        if result.get("anki_status") and result["anki_status"] != last_rendered_anki_status:
            renderer.render_anki_result(result["anki_status"])
            last_rendered_anki_status = result["anki_status"]

        if result.get("reply_intent") == "skip_kanji" and current_kanji != skip_noticed_for:
            print(f"\nSkipped {current_kanji} — moving on.")
            skip_noticed_for = current_kanji

        interrupts = result.get("__interrupt__")

        if not interrupts:
            if result.get("reply_intent") == "stop":
                chunk = result.get("current_chunk") or []
                index = result.get("current_index") or 0
                print(f"\nStopped after {min(index, len(chunk))} of {len(chunk)} in this chunk.")
            return result

        interrupt_value = interrupts[0].value

        if result.get("pending_explanation") and result["pending_explanation"] != last_rendered_explanation:
            renderer.render_additional_explanation(result["pending_explanation"])
            last_rendered_explanation = result["pending_explanation"]

        renderer.render_interrupt(interrupt_value)

        if isinstance(interrupt_value, dict):
            hint = hint_for_interrupt(interrupt_value.get("type", ""))
            if hint:
                print(hint)

        user_input = await asyncio.to_thread(input,"\n> ")

        result = await graph.ainvoke(
            Command(resume=user_input.strip()),
            config=config,
            context=context,
        )

async def run_app():
    load_dotenv()
    app_config = Config()

    src_dir = Path(__file__).resolve().parents[1]
    server_script_path = src_dir / "mcp_server.py"
    dict_path = Path(app_config.dict_path)
    if not dict_path.is_absolute():
        dict_path = src_dir.parent / dict_path

    server_params = StdioServerParameters(command=sys.executable,args=[str(server_script_path)])

    graph = build_graph()
    models = build_models()
    dictionary = DictionaryService(dict_path)

    thread_id = f"kanji_convo_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}

    file_path = await asyncio.to_thread(input,"Enter the path to your Japanese text/PDF file: ")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            context = RuntimeContext(mcp_session=session,models=models,dictionary=dictionary)

            final_state = await run_interactive_graph(
                graph=graph,
                initial_state={
                    "file_path": file_path.strip(),
                    "deck": app_config.anki_deck
                },
                config=config,
                context=context
            )

    print("\nProcessing complete.")


if __name__ == "__main__":
    asyncio.run(run_app())