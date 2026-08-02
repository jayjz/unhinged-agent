import pytest

from tools.registry import available_tools, execute_tool


@pytest.mark.asyncio
async def test_get_current_time_tool():
    result = await execute_tool("get_current_time", {})
    assert "The current time is" in result


@pytest.mark.asyncio
async def test_unknown_tool_handling():
    result = await execute_tool("non_existent_tool", {})
    assert "Error" in result or "Unknown tool" in result or "not found" in result


def test_tool_schema_structure():
    assert len(available_tools) > 0
    first_tool = available_tools[0]
    assert first_tool["type"] == "function"
    assert "name" in first_tool["function"]
    assert "description" in first_tool["function"]
