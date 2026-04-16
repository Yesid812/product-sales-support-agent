"""
rag/loader.py
=============
Carga los archivos Markdown de política y los segmenta por sección.

Estrategia de segmentación:
    Cada bloque ## encabezado + su contenido es una "sección".
    El agente nunca inyecta el archivo completo en el prompt —
    solo recupera las secciones más importantes para la consulta.

Estructura de una sección:
    {
        "doc":     "devoluciones",
        "heading": "Plazos de Reembolso",
        "content": "El tiempo en que...",
        "full":    "## Plazos...\n..."
    }
"""

import re
from pathlib import Path
from config import settings


_DOC_NAMES = {
    "devoluciones": ["devolucion", "cambio"],
    "garantia":     ["garantia", "garant"],
    "envio":        ["envio", "env"],
}


def _segment(text: str, doc_name: str) -> list[dict]:
    """
    Divide el Markdown en secciones por encabezados ##.
    """
    sections = []
    parts = re.split(r'\n(?=## )', text)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        lines = part.split('\n')
        first = lines[0].strip()

        if not first.startswith('## '):
            continue

        heading = first.lstrip('#').strip()
        heading = re.sub(r'\*\*(.+?)\*\*', r'\1', heading)  # quitar la **negrita**
        content = '\n'.join(lines[1:]).strip()
        content = content.replace('\\*', '*').replace('\\-', '-')

        sections.append({
            "doc":     doc_name,
            "heading": heading,
            "content": content,
            "full":    f"## {heading}\n\n{content}",
        })

    return sections


def _find_md(keywords: list[str]) -> Path | None:
    """Busca un .md en policies/ cuyo nombre contenga alguna de las keywords."""
    for md in settings.policies_path.glob("*.md"):
        name = md.name.lower()
        if any(k in name for k in keywords):
            return md
    return None


def load_policies() -> list[dict]:
    """
    Carga y segmenta todos los documentos de política.

    Returns:
        Lista plana de secciones de los 3 documentos.
    """
    all = []

    for doc_key, keywords in _DOC_NAMES.items():
        route = _find_md(keywords)
        if not route:
            print(f"[RAG] Advertencia: no se encontró documento '{doc_key}'")
            continue

        text = route.read_text(encoding="utf-8")
        sections = _segment(text, doc_key)
        all.extend(sections)

    return all


_cache: list[dict] | None = None


def get_politicies() -> list[dict]:
    """Retorna secciones cacheadas para ahorrar. Carga una sola vez por proceso."""
    global _cache
    if _cache is None:
        _cache = load_policies()
    return _cache