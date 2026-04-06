from __future__ import annotations

from config import settings

try:
    import google.genai as genai
    _LLM_PACKAGE = "google-genai"
except ImportError:  # pragma: no cover
    try:
        import google.generativeai as genai
        _LLM_PACKAGE = "google-generativeai"
    except ImportError:
        genai = None
        _LLM_PACKAGE = None


def _validate_provider() -> None:
    if settings.llm_provider.lower() != "gemini":
        raise RuntimeError(
            f"LLM provider '{settings.llm_provider}' no está soportado. "
            "Configura LLM_PROVIDER=gemini en tu .env."
        )

    if genai is None:
        raise RuntimeError(
            "No se encontró ningún cliente Gemini. "
            "Instala google-genai con: pip install google-genai"
        )


def _create_client() -> object:
    if _LLM_PACKAGE == "google-genai":
        return genai.Client(api_key=settings.API_KEY)
    return genai


def _resolved_model_name() -> str:
    model_name = settings.MODEL_NAME
    if _LLM_PACKAGE == "google-genai":
        if model_name in {"gemini-1.5-flash", "gemini-1.5"}:
            return "gemini-2.5-flash"
        if model_name.startswith("gemini-1.5"):
            return "gemini-2.5-flash"
    return model_name


def _extract_text(response: object) -> str:
    if response is None:
        return ""

    if hasattr(response, "output_text"):
        return response.output_text.strip() or ""

    if hasattr(response, "output"):
        output = response.output
        if isinstance(output, str):
            return output.strip()
        if isinstance(output, list):
            text_parts = []
            for item in output:
                if isinstance(item, dict):
                    content = item.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(str(block.get("text", "")))
                else:
                    text_parts.append(str(item))
            return "".join(text_parts).strip()

    if hasattr(response, "candidates"):
        candidates = getattr(response, "candidates") or []
        for candidate in candidates:
            if not candidate:
                continue
            content = getattr(candidate, "content", None)
            if content is None:
                continue
            parts = getattr(content, "parts", None)
            if parts:
                text_parts = [getattr(part, "text", "") for part in parts if getattr(part, "text", None)]
                if text_parts:
                    return "".join(text_parts).strip()
            if hasattr(content, "text") and getattr(content, "text"):
                return getattr(content, "text").strip()

    if hasattr(response, "parsed") and response.parsed is not None:
        return str(response.parsed).strip()

    return str(response).strip()


def generate_text(prompt: str, max_output_tokens: int = 512) -> str:
    """Genera texto usando el modelo Gemini configurado."""
    _validate_provider()
    client = _create_client()

    if _LLM_PACKAGE == "google-genai":
        response = client.models.generate_content(
            model=_resolved_model_name(),
            contents=[prompt],
            config={
                "temperature": settings.llm_temperature,
                "maxOutputTokens": max_output_tokens,
            },
        )
    else:
        genai.configure(api_key=settings.API_KEY)
        response = genai.responses.create(
            model=settings.MODEL_NAME,
            input=prompt,
            temperature=settings.llm_temperature,
            max_output_tokens=max_output_tokens,
        )

    result_text = _extract_text(response)
    if not result_text:
        raise RuntimeError("Gemini no devolvió texto en la respuesta.")
    return result_text
