"""
llm/factory.py
==============
Crea el proveedor LLM según LLM_PROVIDER en .env.

Agregar un proveedor nuevo:
    1. Crear llm/nuevo_provider.py implementando LLMProvider
    2. Agregar el caso aquí
    3. Actualizar .env — nada más cambia
"""

from config import settings
from llm.base import LLMProvider


def get_provider() -> LLMProvider:
    """
    Retorna el proveedor configurado.

    LLM_PROVIDER=groq      → GroqProvider  (gratis, desarrollo)
    LLM_PROVIDER=gemini    → GeminiProvider
    LLM_PROVIDER=anthropic → AnthropicProvider (futuro)
    LLM_PROVIDER=openai     → OpenAIProvider (GPT-4o-mini, tool calling real)
    """
    provider = settings.llm_provider.lower().strip()

    if provider == "groq":
        from llm.groq_provider import GroqProvider
        return GroqProvider()

    if provider == "gemini":
        from llm.gemini_provider import GeminiProvider
        return GeminiProvider()
    if provider == "openai":
        from llm.openai_provider import OpenAIProvider
        return OpenAIProvider()

    raise ValueError(
        f"Proveedor '{provider}' no soportado.\n"
        f"Opciones: groq, gemini\n"
        f"Revisa LLM_PROVIDER en tu .env"
    )