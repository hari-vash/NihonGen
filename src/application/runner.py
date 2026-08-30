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


async def run_interactive_graph(graph,initial_state,config,context):
    """
    Run the graph and resume it whenever an interrupt occurs.
    """

    result = await graph.ainvoke(initial_state,config=config,context=context)

    while True:
        interrupts = result.get("__interrupt__")

        if not interrupts:
            return result

        interrupt_value = interrupts[0].value

        print("\n" + "=" * 60)

        if isinstance(interrupt_value, dict):
            print(interrupt_value.get("message", interrupt_value))
        else:
            print(interrupt_value)

        print("=" * 60)

        user_input = await asyncio.to_thread(input,"\n> ")

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
                    "deck": "Test_Deck1",
                },
                config=config,
                context=context,
            )

    print("\nProcessing complete.")


if __name__ == "__main__":
    asyncio.run(run_app())