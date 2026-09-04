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
from llm.model import build_models
from application import renderer
from graph.helpers import message_to_text

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
    previous_message_count = len(result.get("messages", []))

    while True:
        current_kanji = result.get("kanji")

        if current_kanji and current_kanji != last_rendered_kanji:
            evaluation_rendered = False

            renderer.render_kanji(result["kanji"])

            if result.get("kanji_info"):
                renderer.render_kanji_info(result["kanji_info"])

            if result.get("lesson"):
                renderer.render_kanji_lesson(result["lesson"])

            last_rendered_kanji = current_kanji

        if result.get("quiz_evaluation") and not evaluation_rendered:
            renderer.render_quiz_result(result["quiz_evaluation"])
            evaluation_rendered = True

        if result.get("anki_status"):
            renderer.render_anki_result(result["anki_status"])

        interrupts = result.get("__interrupt__")

        if not interrupts:
            return result

        interrupt_value = interrupts[0].value

        if result.get("user_decision")and interrupt_value.get("type") == "quiz_answer":
            messages = result.get("messages", [])

            new_messages = messages[previous_message_count:]

            if new_messages:
                explanation_message = new_messages[0]
                explanation_content = message_to_text(explanation_message)
                renderer.render_additional_explanation(explanation_content)

        renderer.render_interrupt(interrupt_value)

        user_input = await asyncio.to_thread(input,"\n> ")

        previous_message_count = len(result.get("messages", []))
        result = await graph.ainvoke(
            Command(resume=user_input.strip()),
            config=config,
            context=context,
        )

async def run_app():
    load_dotenv()

    src_dir = Path(__file__).resolve().parents[1]
    server_script_path = src_dir / "mcp_server.py"

    server_params = StdioServerParameters(command=sys.executable,args=[str(server_script_path)])

    graph = build_graph()
    models = build_models()

    thread_id = f"kanji_convo_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}

    file_path = await asyncio.to_thread(input,"Enter the path to your Japanese text/PDF file: ")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            context = RuntimeContext(mcp_session=session,models=models)

            final_state = await run_interactive_graph(
                graph=graph,
                initial_state={
                    "file_path": file_path.strip(),
                    "deck": "Test_Deck1"
                },
                config=config,
                context=context
            )

    print("\nProcessing complete.")


if __name__ == "__main__":
    asyncio.run(run_app())