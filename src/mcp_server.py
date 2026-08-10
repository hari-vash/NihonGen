import os
import re
import uuid
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Japanese Kanji Batcher")

sessions = {}
CHUNK_SIZE = 15


def extract_kanji_chunks(text: str, chunk_size: int) -> list[list[str]]:
    """Extracts unique sorted Kanji and splits them into smaller chunks."""
    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    
    found_kanjis = sorted(list(set(kanji_pattern.findall(text))))
    
    return [found_kanjis[i:i + chunk_size] for i in range(0, len(found_kanjis), chunk_size)]


@mcp.tool()
async def initialize_file_stream(file_path: str) -> str:
    """
    Parses a .txt or .pdf file, extracts unique Kanji, creates a session, 
    and returns the FIRST chunk of Kanji to process.
    """
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found at {file_path}"})
        
    _, ext = os.path.splitext(file_path.lower())
    extracted_text = ""

    try:
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                extracted_text = f.read()
        elif ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            extracted_text = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
        else:
            return json.dumps({"error": "Unsupported file format. Use .txt or .pdf."})

        chunks = extract_kanji_chunks(extracted_text, CHUNK_SIZE)
        
        if not chunks:
            return json.dumps({"status": "empty", "message": "No Kanji characters found in file."})

        # Create a unique 8-character ID for this file processing session
        session_id = str(uuid.uuid4())[:8]
        first_chunk = chunks[0]
        remaining_chunks = chunks[1:]
        
        # Save remaining chunks in memory under this session ID
        if remaining_chunks:
            sessions[session_id] = remaining_chunks

        return json.dumps({
            "status": "success",
            "session_id": session_id,
            "current_chunk": first_chunk,
            "has_more": len(remaining_chunks) > 0,
            "message": f"Extracted first chunk of {len(first_chunk)} kanji." + 
                       (f" Call get_next_kanji_chunk(session_id='{session_id}') for more." if remaining_chunks else "")
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": f"Processing failed: {str(e)}"})


@mcp.tool()
async def get_next_kanji_chunk(session_id: str) -> str:
    """
    Fetches the next chunk of Kanji for an active session ID when has_more is True.
    """
    if session_id not in sessions or not sessions[session_id]:
        return json.dumps({"status": "done", "kanji": [], "has_more": False})

    # Pull the next chunk from the front of the list
    next_chunk = sessions[session_id].pop(0)
    has_more = len(sessions[session_id]) > 0

    # Clean up memory if no chunks are left in the session
    if not has_more:
        del sessions[session_id]

    return json.dumps({
        "status": "success",
        "current_chunk": next_chunk,
        "has_more": has_more
    }, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")