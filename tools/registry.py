import datetime
from loguru import logger
from tools.notes_db import save_note_tool, search_notes_tool

# Define the JSON schema to pass to the LLM
available_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time and date.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save a thought, idea, or reminder to the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "transcript": {"type": "string", "description": "The exact text to save."},
                    "tags": {"type": "string", "description": "Comma-separated tags (e.g. 'work, idea')."}
                },
                "required": ["transcript"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notes",
            "description": "Search the database for previously saved notes using keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The keyword or phrase to search for."}
                },
                "required": ["query"]
            },
        },
    }
]

async def execute_tool(tool_name: str, arguments: dict) -> str:
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")

    if tool_name == "get_current_time":
        now = datetime.datetime.now().strftime("%I:%M %p on %A, %B %d")
        return f"System: The current time is {now}."
    
    elif tool_name == "save_note":
        return await save_note_tool(arguments)
        
    elif tool_name == "search_notes":
        return await search_notes_tool(arguments)

    return "System: Error - Tool not found."