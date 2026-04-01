"""
tools/policies.py
=================
Herramienta de consulta de políticas.

El agente NUNCA responde preguntas de política desde su
conocimiento interno — siempre llama search_policy() y
responde solo con lo que esta función retorne.
"""

from rag.retriever import search, format_for_prompt
from core.session_context import add_tool_trace


def search_policy(query: str) -> dict:
    """
    Busca información en los documentos de política de la empresa.

    Cubre: devoluciones, garantías, envíos, cancelaciones,
    plazos de reembolso, cobertura geográfica, etc.

    Args:
        consulta: Pregunta del usuario sobre políticas

    Returns:
        Dict con:
            - encontrado (bool): si se halló información relevante
            - contexto: texto con las secciones más relevantes
            - fuentes: lista de documentos y secciones consultadas
    """
    results = search(query, top_k=2)

    if not results:
        result = {
            "encontrado": False,
            "contexto": "No se encontró información específica sobre ese tema en las políticas.",
            "fuentes": []
        }
        add_tool_trace("search_policy", {"consulta": query}, result)
        return result

    result = {
        "encontrado": True,
        "contexto": format_for_prompt(results),
        "fuentes": [
            {"doc": r["doc"], "seccion": r["titulo"], "relevancia": r["score"]}
            for r in results
        ]
    }

    add_tool_trace("search_policy", {"consulta": query}, result)
    return result