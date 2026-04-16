"""
llm/openai_provider.py
======================

Proveedor OpenAI (GPT-4o-mini) con tool calling real.

Modelo recomendado:
    gpt-4o-mini  ← barato + excelente para agentes
"""

import json
from openai import OpenAI
from llm.base import LLMProvider, LLMResponse, ToolCall
from config import settings


def _tools_a_openai(tools_gemini: list[dict]) -> list[dict]:
    """
    Convierte tools de formato Gemini a formato OpenAI.

    Gemini:
        [{"function_declarations": [...]}]

    OpenAI:
        [{"type": "function", "function": {...}}]
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


class OpenAIProvider(LLMProvider):

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
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
                model=settings.llm_model or "gpt-4o-mini",
                messages=mensajes,
                tools=_tools_a_openai(tools),
                tool_choice="auto",
                temperature=temperature,
            )
        except Exception as e:
            raise RuntimeError(f"Error OpenAI: {e}")

        message = response.choices[0].message

        # =========================
        # TOOL CALLS
        # =========================
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

        # =========================
        # TEXTO FINAL
        # =========================
        return LLMResponse(
            text=message.content or "",
            tool_calls=[]
        )

    # =========================
    # HELPERS DE MENSAJES
    # =========================

    def user_message(self, texto: str) -> dict:
        return {"role": "user", "content": texto}

    def assistant_message(self, texto: str) -> dict:
        return {"role": "assistant", "content": texto}

    def assistant_tool_call_message(self, tool_calls: list[ToolCall]) -> dict:
        """
        Igual que Groq:
        primero el mensaje del assistant con tool_calls
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
        """
        El tool_call_id debe coincidir.
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "name": tool_call.name,
            "content": json.dumps(result, ensure_ascii=False, default=str),
        }