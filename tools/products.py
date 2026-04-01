"""
tools/products.py
=================
Herramienta de consulta de productos: precio, stock y garantía.

Esta herramienta NO requiere autenticación — es información pública
del catálogo (Fase 3, rama 3 del árbol de decisión del agente).
"""

from db.local import search_products_by_name, get_product_info
from core.session_context import add_tool_trace


def search_products(query: str) -> dict:
    """
    Busca productos por nombre o término y retorna precio, stock y garantía.

    No requiere identificación — información pública del catálogo.

    Args:
        query: Texto de búsqueda (ej. "Samsung Galaxy", "laptop", "Licuadora")

    Returns:
        Dict con:
            - found (bool): True si se encontraron productos
            - products: lista de hasta 5 productos con precio, stock y garantía
            - total: cantidad de resultados encontrados
            - mensaje: descripción si no hay resultados
    """
    products = search_products_by_name(query)

    if not products:
        result = {
            "found": False,
            "products": [],
            "total": 0,
            "mensaje": "No encontramos productos que coincidan con tu búsqueda.",
        }
        add_tool_trace("search_products", {"query": query}, result)
        return result

    result = {
        "found": True,
        "products": products[:5],
        "total": len(products),
    }
    add_tool_trace("search_products", {"query": query}, result)
    return result


def get_product_detail(product_id: str) -> dict:
    """
    Retorna el detalle completo de un producto por su ID.

    No requiere autenticación — información pública.

    Args:
        product_id: ID del producto (ej. "5001")

    Returns:
        Dict con precio, stock, garantía, o error si no existe.
    """
    try:
        product = get_product_info(int(product_id))
    except (ValueError, TypeError):
        result = {"found": False, "mensaje": "ID de producto inválido."}
        add_tool_trace("get_product_detail", {"product_id": product_id}, result)
        return result

    if not product:
        result = {
            "found": False,
            "mensaje": f"No encontramos el producto #{product_id}.",
        }
        add_tool_trace("get_product_detail", {"product_id": product_id}, result)
        return result

    result = {"found": True, **product}
    add_tool_trace("get_product_detail", {"product_id": product_id}, result)
    return result
