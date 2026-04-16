"""
llm/base.py
===========
Interfaz común para todos los proveedores LLM.

El agente solo conoce esta interfaz — nunca importa un SDK directamente.
Cambiar de proveedor = cambiar LLM_PROVIDER en .env, nada más.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Herramienta que el modelo quiere ejecutar."""
    id: str        # ID único del tool call (necesario para Groq/OpenAI)
    name: str      # nombre de la función
    args: dict     # argumentos parseados


@dataclass
class LLMResponse:
    """Respuesta normalizada, independiente del proveedor."""
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def tiene_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """
    Interfaz que implementan Groq, Gemini, Anthropic, etc.

    Cada proveedor maneja su formato de historial internamente.
    El agente siempre recibe y envía tipos normalizados.
    """

    system_prompt: str = ""

    @abstractmethod
    def chat(
        self,
        historial: list[dict],
        tools: list[dict],
        temperature: float = 0,
    ) -> LLMResponse:
        """
        Envía el historial al modelo y retorna respuesta normalizada.

        Args:
            historial:   mensajes en formato del proveedor
            tools:       herramientas en formato Gemini (la factory convierte)
            temperature: temperatura del modelo

        Returns:
            LLMResponse con texto final o tool_calls a ejecutar
        """
        pass

    @abstractmethod
    def user_message(self, texto: str) -> dict:
        """Construye un mensaje de usuario en el formato del proveedor."""
        pass

    @abstractmethod
    def assistant_message(self, texto: str) -> dict:
        """Construye un mensaje de asistente de texto en el formato del proveedor."""
        pass

    @abstractmethod
    def assistant_tool_call_message(self, tool_calls: list[ToolCall]) -> dict:
        """
        Construye el mensaje del asistente cuando hace tool calls.
        Debe incluir los IDs para que los resultados se asocien correctamente.
        """
        pass

    @abstractmethod
    def tool_result_message(self, tool_call: ToolCall, result: dict) -> dict:
        """
        Construye el mensaje de resultado de una herramienta.
        El ID debe coincidir con el del tool_call correspondiente.
        """
        pass