import json
import aiohttp
from loguru import logger

from config.settings import settings
from tools.registry import available_tools, execute_tool

class LLMService:
    def __init__(self):
        # FIXED: Mapped to the new lowercase Pydantic V2 fields
        self.url = f"{settings.ollama_url}/api/chat"
        self.system_prompt = (
            "You are an unhinged, highly sarcastic, brilliantly capable AI assistant. "
            "You despise corporate politeness. You give brutally honest, concise answers. "
            "Do not use markdown formatting, asterisks, or emojis in your speech because it will be read by a TTS engine. "
            "Talk like a real, slightly deranged engineer."
        )
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.session = aiohttp.ClientSession()

    async def close(self):
        await self.session.close()

    async def query(self, user_text: str) -> str:
        if user_text.strip():
            self.messages.append({"role": "user", "content": user_text})

        payload = {
            "model": settings.ollama_model, # FIXED
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

                if message.get("tool_calls"):
                    self.messages.append(message)
                    for tool in message["tool_calls"]:
                        tool_name = tool["function"]["name"]
                        raw_args = tool["function"]["arguments"]
                        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        
                        tool_result = await execute_tool(tool_name, tool_args)
                        self.messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "name": tool_name,
                        })
                    return await self.query("")

                ai_text = message.get("content", "I have no words.").strip()
                self.messages.append({"role": "assistant", "content": ai_text})

                # Strict Memory Truncation: System prompt + last 16 messages
                if len(self.messages) > 17:
                    self.messages = [self.messages[0]] + self.messages[-16:]

                return ai_text

        except Exception as e:
            logger.error(f"LLM Query Failed: {e}")
            return "I encountered a critical error processing your request."