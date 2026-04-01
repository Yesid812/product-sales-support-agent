"""
rag/retriever.py
================
Busca y rankea las secciones de política más relevantes para una consulta.

Estrategia de ranking (TF-IDF simplificado + boost por keywords) por el momento:
    1. Tokenizar la consulta y cada sección
    2. Contar palabras las palabras que tengan en común
    3. Aplicar boost si la consulta menciona palabras clave del encabezado
    4. Retornar las N secciones con mayor score

Por qué no usar embeddings:
    - No requiere modelo externo ni llamadas a API
    - Es predecible y auditable
    - Suficientemente preciso para 3 documentos cortos
    - Responde en microsegundos (crítico para el límite de 10s TTFT)

Nota: Intentar con sentence-transformers — la interfaz pública no cambia.
"""

import re
import math
from collections import Counter
from rag.loader import get_politicas


# Stopwords en español — palabras a criterio propio que no aportan significado para el ranking
_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "en", "con", "por", "para", "que",
    "es", "son", "fue", "ser", "estar", "tiene", "tienen",
    "se", "su", "sus", "mi", "me", "te", "le", "nos",
    "y", "o", "a", "e", "pero", "si", "no", "ya", "más",
    "como", "esto", "esta", "este", "qué", "cómo", "cuándo",
    "puedo", "puede", "quiero", "necesito", "tengo", "hay",
    "mi", "mis", "tu", "tus", "mi", "producto", "pedido",
}


def _tokenize(text: str) -> list[str]:
    """
    Convierte texto a lista de tokens normalizados.
    Minúsculas, sin puntuación y sin stopwords.
    """
    text = text.lower()
    # Normalize acentos y caracteres especiales para mejorar la coincidencia
    text = (text
            .replace('á', 'a').replace('é', 'e').replace('í', 'i')
            .replace('ó', 'o').replace('ú', 'u').replace('ü', 'u')
            .replace('ñ', 'n'))
    tokens = re.findall(r'\b[a-z]{3,}\b', text)
    return [t for t in tokens if t not in _STOPWORDS]


def _score(query_tokens: list[str], seccion: dict) -> float:
    """
    Calcula la relevancia de una sección para la consulta.

    Score = overlap_normalizado + boost_encabezado

    - overlap_normalizado: fracción de tokens de la consulta que
      aparecen en el contenido de la sección
    - boost_encabezado: bonus si tokens de la consulta aparecen
      en el título de la sección (es una señal de que la sección es más fuerte de relevancia)
    """
    if not query_tokens:
        return 0.0

    content_tokens = set(_tokenize(seccion["full"]))
    heading_tokens   = set(_tokenize(seccion["heading"]))
    query_set        = set(query_tokens)

    # Overlap con el contenido completo
    overlap = len(query_set & content_tokens) / len(query_set)

    # Boost si la consulta coincide con el encabezado (x2)
    heading_boost = len(query_set & heading_tokens) / max(len(heading_tokens), 1)

    return overlap + (heading_boost * 2.0)


# Sinónimos para expandir consultas comunes vocabulario común en Colombia
# Cuando el usuario pregunta por X, también buscamos el sinonimo
_SINONIMOS = {
    "devolver":    ["devolucion", "plazo", "cambio", "elegible"],
    "devolución":  ["devolucion", "plazo", "cambio", "elegible"],
    "cambiar":     ["cambio", "devolucion", "plazo"],
    "garantia":    ["garantia", "cubre", "cobertura", "falla"],
    "garantía":    ["garantia", "cubre", "cobertura", "falla"],
    "envio":       ["envio", "entrega", "tiempo", "plazo", "zona"],
    "envío":       ["envio", "entrega", "tiempo", "plazo", "zona"],
    "reembolso":   ["reembolso", "devolucion", "plazo", "pago"],
    "cancelar":    ["cancelacion", "despacho", "pedido"],
    "tarjeta":     ["tarjeta", "credito", "debito", "reembolso"],
}


def _expand(tokens: list[str]) -> list[str]:
    """Expande tokens con sinónimos para mejorar."""
    expanded = list(tokens)
    for t in tokens:
        if t in _SINONIMOS:
            expanded.extend(_SINONIMOS[t])
    return expanded


def search(query: str, top_k: int = 2, min_score: float = 0.1) -> list[dict]:
    """
    Retorna las secciones de política más relevantes para la consulta.

    Args:
        query:  Pregunta o texto del usuario
        top_k:     Máximo de secciones a retornar (2 por defecto)
        min_score: Score mínimo para incluir una sección

    Returns:
        Lista de secciones ordenadas por relevancia descendente.
        Cada sección incluye su score bajo la clave "_score".
        Lista vacía si ninguna sección supera min_score.

    Ejemplo:
        secciones = search("cuánto tiempo tengo para devolver")
        # → [{"doc": "devoluciones", "heading": "Plazos para Devoluciones", ...}]
    """
    politicas = get_politicas()
    query_tokens = _expand(_tokenize(query))

    if not query_tokens:
        return []

    scored = []
    for sec in politicas:
        s = _score(query_tokens, sec)
        if s >= min_score:
            scored.append({**sec, "_score": round(s, 3)})

    # Ordenar por score descendente
    scored.sort(key=lambda x: x["_score"], reverse=True)

    return scored[:top_k]


def search_for_doc(query: str, doc: str, top_k: int = 2) -> list[dict]:
    """
    Busca solo dentro de un documento específico.

    Útil cuando el agente ya sabe qué tipo de política busca
    (ej. el usuario pregunta explícitamente por garantía).

    Args:
        consulta: Pregunta del usuario
        doc:      "devoluciones" | "garantia" | "envio"
        top_k:    Máximo de secciones
    """
    politicas = get_politicas()
    query_tokens = _tokenize(query)

    filtradas = [s for s in politicas if s["doc"] == doc]
    scored = []
    for sec in filtradas:
        s = _score(query_tokens, sec)
        scored.append({**sec, "_score": round(s, 3)})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    return scored[:top_k]


def format_for_prompt(sections: list[dict]) -> str:
    """
    Convierte las secciones recuperadas en texto listo para el prompt.

    El agente inyecta este texto en el contexto cuando necesita
    responder sobre políticas.

    Args:
        secciones: Lista de secciones de buscar()

    Returns:
        Texto formateado con fuente y contenido de cada sección.
    """
    if not sections:
        return "No se encontró información relevante en las políticas."

    parts = []
    for sec in sections:
        origin = f"[Política de {sec['doc']} — {sec['heading']}]"
        parts.append(f"{origin}\n{sec['content']}")

    return "\n\n---\n\n".join(parts)