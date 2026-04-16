"""
llm/groq_provider.py
====================
Proveedor Groq — formato OpenAI con tool_call_id explícito.

Modelos recomendados:
    llama-3.3-70b-versatile  ← mejor tool calling
    llama-3.1-70b-versatile  ← alternativa estable
"""

import json
from groq import Groq
from llm.base import LLMProvider, LLMResponse, ToolCall
from config import settings


def _tools_a_openai(tools_gemini: list[dict]) -> list[dict]:
    """
    Convierte tools de formato Gemini a formato OpenAI/Groq.

    Gemini:  [{"function_declarations": [{"name":..., "parameters":...}]}]
    OpenAI:  [{"type": "function", "function": {"name":..., "parameters":...}}]
    """
    resultado = []
    for grupo in tools_gemini:
        for fn in grupo.get("function_declarations", []):
            resultado.append({
                "type": "function",
                "function": {
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {
                        "type": "object",
                        "properties": {}
                    }),
                }
            })
    return resultado


class GroqProvider(LLMProvider):

    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.system_prompt = ""

    def chat(
        self,
        historial: list[dict],
        tools: list[dict],
        temperature: float = 0,
    ) -> LLMResponse:
        mensajes = [
            {"role": "system", "content": self.system_prompt}
        ] + historial

        try:
            response = self.client.chat.completions.create(
                model=settings.llm_model,
                messages=mensajes,
                tools=_tools_a_openai(tools),
                tool_choice="auto",
                temperature=temperature,
            )
        except Exception as e:
            raise RuntimeError(f"Error Groq: {e}")

        message = response.choices[0].message

        if message.tool_calls:
            return LLMResponse(
                text=None,
                tool_calls=[
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments)
                    )
                    for tc in message.tool_calls
                ]
            )

        return LLMResponse(text=message.content or "", tool_calls=[])

    def user_message(self, texto: str) -> dict:
        return {"role": "user", "content": texto}

    def assistant_message(self, texto: str) -> dict:
        return {"role": "assistant", "content": texto}

    def assistant_tool_call_message(self, tool_calls: list[ToolCall]) -> dict:
        """
        Groq requiere el mensaje del asistente con tool_calls ANTES
        de los mensajes de resultado. Los IDs deben coincidir.
        """
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.args, ensure_ascii=False),
                    }
                }
                for tc in tool_calls
            ]
        }

    def tool_result_message(self, tool_call: ToolCall, result: dict) -> dict:
        """El tool_call_id debe coincidir con el del mensaje del asistente."""
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.name,
            "content": json.dumps(result, ensure_ascii=False, default=str),
        }