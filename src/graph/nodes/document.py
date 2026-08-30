from langgraph.runtime import Runtime
from graph.context import RuntimeContext
from graph.helpers import parse_mcp_json
from graph.state import State

async def initialize_document(state: State,runtime: Runtime[RuntimeContext]):
    result = await runtime.context.mcp_session.call_tool("initialize_file_stream",{"file_path": state["file_path"]})
    data = parse_mcp_json(result)

    if data.get("status") != "success":
        raise RuntimeError(data.get("error",data.get("message","MCP initialization failed.")))

    return {
        "session_id": data["session_id"],
        "current_chunk": data["current_chunk"],
        "current_index": 0,
        "has_more": data["has_more"],
    }


async def get_next_chunk(state: State,runtime: Runtime[RuntimeContext]):
    result = await runtime.context.mcp_session.call_tool("get_next_kanji_chunk",{"session_id": state["session_id"]})
    data = parse_mcp_json(result)

    if data.get("status") != "success":
        raise RuntimeError(data.get("error",data.get("message","Failed to retrieve the next Kanji chunk.")))

    return {
        "current_chunk": data["current_chunk"],
        "current_index": 0,
        "has_more": data["has_more"],
    }