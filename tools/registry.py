import datetime

from loguru import logger

# 1. Define the schema to pass to the LLM
available_tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time and date. Use this when the user asks what time or day it is.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
]


# 2. Define the actual execution logic
async def execute_tool(tool_name: str, arguments: dict) -> str:
    logger.info(f"Executing tool: {tool_name} with args: {arguments}")

    if tool_name == "get_current_time":
        now = datetime.datetime.now().strftime("%I:%M %p on %A, %B %d")
        return f"The current time is {now}."

    return "Error: Tool not found."
