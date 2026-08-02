import json

import aiohttp
from loguru import logger

from config.settings import settings
from tools.registry import available_tools, execute_tool


class LLMService:
    def __init__(self):
        self.url = f"{settings.OLLAMA_URL}/api/chat"
        self.system_prompt = (
            "You are an unhinged, highly sarcastic, brilliantly capable AI assistant. "
            "You despise corporate politeness. You give brutally honest, concise answers. "
            "Do not use markdown formatting, asterisks, or emojis in your speech because it will be read by a TTS engine. "
            "Talk like a real, slightly deranged engineer."
        )
        # Memory is scoped to THIS instance (created per WebSocket connection)
        self.messages = [{"role": "system", "content": self.system_prompt}]

        # Reusable aiohttp session
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def query(self, user_text: str) -> str:
        # Only append if there's actual user text (prevents empty user turns after tool calls)
        if user_text.strip():
            self.messages.append({"role": "user", "content": user_text})

        payload = {
            "model": settings.LLM_MODEL,
            "messages": self.messages,
            "tools": available_tools,
            "stream": False,
        }

        try:
            async with self.session.post(self.url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Ollama API Error: {response.status}")
                    return "My brain just crashed. Give me a second."

                data = await response.json()
                message = data.get("message", {})

                # TOOL CALLING ROUTER
                if message.get("tool_calls"):
                    self.messages.append(
                        message
                    )  # Add assistant's tool call to history

                    for tool in message["tool_calls"]:
                        tool_name = tool["function"]["name"]

                        # Parse JSON string arguments from Ollama
                        raw_args = tool["function"]["arguments"]
                        tool_args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )

                        tool_result = await execute_tool(tool_name, tool_args)

                        self.messages.append(
                            {
                                "role": "tool",
                                "content": tool_result,
                                "name": tool_name,  # Ollama expects the tool name in the tool response
                            }
                        )

                    logger.info("Tool executed. Requesting final response from LLM...")

                    # CRITICAL FIX: Pass empty string to avoid polluting chat history with meta-prompts.
                    # The model will naturally respond to the 'tool' role message we just appended.
                    return await self.query("")

                # STANDARD RESPONSE
                ai_text = message.get("content", "I have no words.").strip()
                self.messages.append({"role": "assistant", "content": ai_text})

                # Memory Truncation: Keep system prompt + last 8 turns (16 messages)
                if len(self.messages) > 17:
                    self.messages = [self.messages[0]] + self.messages[-16:]

                return ai_text

        except Exception as e:
            logger.error(f"LLM Query Failed: {e}")
            return "I encountered a critical error processing your request."
