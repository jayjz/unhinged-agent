import pytest
from services.llm_service import LLMService


@pytest.mark.asyncio
async def test_llm_service_initialization():
    llm = LLMService()

    # Verify the unhinged system prompt is loaded natively
    assert len(llm.messages) == 1
    assert llm.messages[0]["role"] == "system"
    assert "unhinged" in llm.messages[0]["content"].lower()

    await llm.close()


@pytest.mark.asyncio
async def test_llm_memory_isolation():
    # Verify that creating two distinct connections doesn't share memory
    llm_1 = LLMService()
    llm_2 = LLMService()

    llm_1.messages.append({"role": "user", "content": "Hello LLM 1"})

    assert len(llm_1.messages) == 2
    assert len(llm_2.messages) == 1  # LLM 2 should be unaffected

    await llm_1.close()
    await llm_2.close()
