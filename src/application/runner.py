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


async def run_interactive_graph(graph,initial_state,config,context):
    """
    Run the graph and resume it whenever an interrupt occurs.
    """

    result = await graph.ainvoke(initial_state,config=config,context=context)

    last_rendered_kanji = None
    eval_result = True
    while True:
        current_kanji = result.get('kanji')
        
        if current_kanji and current_kanji != last_rendered_kanji:
            eval_result = False
            if result.get('kanji'):
                renderer.render_kanji(result['kanji'])
            if result.get('kanji_info'):
                renderer.render_kanji_info(result['kanji_info'])
            if result.get('lesson'):
                renderer.render_kanji_lesson(result['lesson'])

            last_rendered_kanji = current_kanji
        
        if result.get("quiz_evaluation") and not eval_result:
            renderer.render_quiz_result(result['quiz_evaluation'])
            eval_result = True
            
        interrupts = result.get("__interrupt__")
        if interrupts:
            renderer.render_interrupt(interrupts)
            
            user_input = await asyncio.to_thread(input,"\n> ")

            result = await graph.ainvoke(
                Command(resume=user_input.strip()),
                config=config,
                context=context,
            )
        
        else:
            return result

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