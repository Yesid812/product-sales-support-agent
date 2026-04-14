"""
llm/gemini_provider.py
======================
Proveedor Gemini — usa google-generativeai con manejo de bloqueos.
"""

import uuid
import google.generativeai as genai
from llm.base import LLMProvider, LLMResponse, ToolCall
from config import settings


class GeminiProvider(LLMProvider):

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.system_prompt = ""
        self._model = None

    def _get_model(self, tools: list[dict]):
        """Crea el modelo si no existe — reutiliza entre llamadas."""
        if self._model is None:
            self._model = genai.GenerativeModel(
                model_name=settings.llm_model,
                system_instruction=self.system_prompt,
                tools=tools,
                tool_config={"function_calling_config": {"mode": "AUTO"}},
            )
        return self._model

    def chat(
        self,
        historial: list[dict],
        tools: list[dict],
        temperature: float = 0,
    ) -> LLMResponse:
        model = self._get_model(tools)

        response = model.generate_content(
            historial,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature
            ),
        )

        # Respuesta bloqueada por seguridad
        if not response.candidates:
            return LLMResponse(
                text="Lo siento, no puedo ayudarte con esa solicitud. "
                     "¿En qué más puedo ayudarte?",
                tool_calls=[]
            )

        candidate = response.candidates[0]
        finish_reason = str(getattr(candidate, "finish_reason", ""))
        if "SAFETY" in finish_reason or "RECITATION" in finish_reason:
            return LLMResponse(
                text="Lo siento, no puedo ayudarte con esa solicitud.",
                tool_calls=[]
            )

        parts = candidate.content.parts

        tool_calls = []
        for p in parts:
            if hasattr(p, "function_call") and p.function_call.name:
                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4())[:8],  # Gemini no da IDs, generamos uno
                    name=p.function_call.name,
                    args=dict(p.function_call.args),
                ))

        if tool_calls:
            # Guardar el content original para el historial
            self._last_candidate_content = candidate.content
            return LLMResponse(text=None, tool_calls=tool_calls)

        texto = "".join(
            p.text for p in parts if hasattr(p, "text") and p.text
        )
        self._last_candidate_content = candidate.content
        return LLMResponse(text=texto or "", tool_calls=[])

    def user_message(self, texto: str) -> dict:
        return {"role": "user", "parts": [texto]}

    def assistant_message(self, texto: str) -> dict:
        return {"role": "model", "parts": [texto]}

    def assistant_tool_call_message(self, tool_calls: list[ToolCall]) -> dict:
        """Gemini usa el content object original del candidate."""
        # Retornamos el content guardado del último chat()
        return getattr(self, "_last_candidate_content", {
            "role": "model", "parts": []
        })

    def tool_result_message(self, tool_call: ToolCall, result: dict) -> dict:
        """Gemini usa function_response en parts."""
        return {
            "role": "user",
            "parts": [{
                "function_response": {
                    "name": tool_call.name,
                    "response": result,
                }
            }]
        }