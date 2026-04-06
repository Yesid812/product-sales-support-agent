"""
tools/orders.py
===============
Herramientas para consultar pedidos, envíos e ítems.

REGLA DE SEGURIDAD: todas las funciones aquí reciben customer_id
desde session_context no desde el mensaje del usuario.
Esto evita que un usuario consulte pedidos de otro cliente.
"""

from db.local import (
    get_orders_by_customer,
    get_order_detail,
    get_order_items,
    get_shipment,
)
from core.session_context import add_tool_trace, get_session_customer
from datetime import date


def _get_customer_id_from_session() -> str | None:
    """Obtiene el customer_id de la sesión activa. None si no hay."""
    customer = get_session_customer()
    return str(customer["customer_id"]) if customer else None


def get_order_status(order_id: str) -> dict:
    """
    Retorna el estado actual de un pedido específico.

    Incluye estado, fechas del ciclo de vida y datos del envío
    si el pedido ya fue despachado.

    Args:
        order_id: ID del pedido que el usuario quiere consultar

    Returns:
        Dict con estado del pedido y envío, o error si no aplica.
    """
    customer_id = _get_customer_id_from_session()

    if not customer_id:
        result = {
            "success": False,
            "mensaje": "Se requiere verificación de identidad antes de consultar pedidos."
        }
        add_tool_trace("get_order_status", {"order_id": order_id}, result)
        return result

    order = get_order_detail(order_id, customer_id)

    if not order:
        result = {
            "success": False,
            "mensaje": f"No encontramos el pedido #{order_id} asociado a tu cuenta."
        }
        add_tool_trace("get_order_status", {"order_id": order_id}, result)
        return result

    # Obtener info de envío si es que hay
    shipment = get_shipment(order_id)

    result = {
        "success": True,
        "order_id": order["order_id"],
        "status": order["status"],
        "order_date": order["order_date"],
        "delivery_method": order["delivery_method"],
        "payment_method": order["payment_method"],
        "shipped_at": order["shipped_at"],
        "delivered_at": order["delivered_at"],
        "cancelled_at": order["cancelled_at"],
        "cancellation_reason": order["cancellation_reason"],
        "envio": {
            "transportadora": shipment["carrier"] if shipment else None,
            "numero_guia": shipment["tracking_number"] if shipment else None,
            "url_tracking": shipment["tracking_url"] if shipment else None,
            "fecha_estimada": shipment["estimated_delivery_date"] if shipment else None,
            "estado_envio": shipment["shipment_status"] if shipment else None,
        } if shipment else None
    }

    add_tool_trace("get_order_status", {"order_id": order_id, "customer_id": customer_id}, result)
    return result


def get_order_amounts(order_id: str) -> dict:
    """
    Retorna los montos de un pedido: subtotal, IVA, envío y total.

    Requiere autenticación. Esta función es la que se llama cuando
    el usuario pregunta "¿cuánto pagué?" o "¿cuál es el total?".

    Args:
        order_id: ID del pedido

    Returns:
        Dict con subtotal, tax, shipping_cost, total_amount en COP.
    """
    customer_id = _get_customer_id_from_session()

    if not customer_id:
        result = {
            "success": False,
            "mensaje": "Se requiere verificación de identidad para consultar montos."
        }
        add_tool_trace("get_order_amounts", {"order_id": order_id}, result)
        return result

    order = get_order_detail(order_id, customer_id)

    if not order:
        result = {
            "success": False,
            "mensaje": f"No encontramos el pedido #{order_id} en tu cuenta."
        }
        add_tool_trace("get_order_amounts", {"order_id": order_id}, result)
        return result

    result = {
        "success": True,
        "order_id": order["order_id"],
        "subtotal": order["subtotal"],
        "tax": order["tax"],
        "shipping_cost": order["shipping_cost"],
        "total_amount": order["total_amount"],
        "payment_method": order["payment_method"],
        "status": order["status"],
    }

    add_tool_trace("get_order_amounts", {"order_id": order_id, "customer_id": customer_id}, result)
    return result


def get_order_history() -> dict:
    """
    Retorna el historial completo de pedidos del cliente autenticado.

    Útil cuando el usuario pregunta "¿cuáles son mis pedidos?"
    o "¿qué he comprado?".

    Returns:
        Dict con lista de pedidos y resumen.
    """
    customer_id = _get_customer_id_from_session()

    if not customer_id:
        result = {
            "success": False,
            "mensaje": "Se requiere verificación de identidad para ver el historial."
        }
        add_tool_trace("get_order_history", {}, result)
        return result

    orders = get_orders_by_customer(customer_id)

    result = {
        "success": True,
        "total_pedidos": len(orders),
        "pedidos": [
            {
                "order_id": o["order_id"],
                "fecha": o["order_date"],
                "status": o["status"],
                "total": o["total_amount"],
                "metodo_pago": o["payment_method"],
            }
            for o in orders
        ]
    }

    add_tool_trace("get_order_history", {"customer_id": customer_id}, result)
    return result


def get_order_items_detail(order_id: str) -> dict:
    """
    Retorna los ítems de un pedido con estado de garantía y devolución.

    Evalúa automáticamente si cada ítem está en garantía o
    dentro del plazo de devolución comparando con la fecha actual.

    Args:
        order_id: ID del pedido

    Returns:
        Dict con lista de ítems enriquecidos con estado de garantía.
    """
    customer_id = _get_customer_id_from_session()

    if not customer_id:
        result = {
            "success": False,
            "mensaje": "Se requiere verificación de identidad."
        }
        add_tool_trace("get_order_items_detail", {"order_id": order_id}, result)
        return result

    # Verificar que el pedido si pertenece al cliente o se lo quiere robar
    order = get_order_detail(order_id, customer_id)
    if not order:
        result = {
            "success": False,
            "mensaje": f"No encontramos el pedido #{order_id} en tu cuenta."
        }
        add_tool_trace("get_order_items_detail", {"order_id": order_id}, result)
        return result

    items = get_order_items(order_id)
    hoy = date.today()

    items_enriquecidos = []
    for item in items:
        # Evaluar la garantía
        en_garantia = False
        if item["warranty_expires_at"]:
            try:
                expira = date.fromisoformat(str(item["warranty_expires_at"])[:10])
                en_garantia = hoy <= expira
            except ValueError:
                pass

        # Evaluar si se puede hacer devolución
        puede_devolver = False
        if item["return_deadline"]:
            try:
                limite = date.fromisoformat(str(item["return_deadline"])[:10])
                puede_devolver = hoy <= limite
            except ValueError:
                pass

        items_enriquecidos.append({
            "item_id": item["item_id"],
            "producto": item["product_name"],
            "qty": item["qty"],
            "precio_unitario": item["unit_price"],
            "estado_item": item["item_status"],
            "garantia_vence": item["warranty_expires_at"],
            "en_garantia": en_garantia,
            "devolucion_limite": item["return_deadline"] or "Sin devolución",
            "puede_devolver": puede_devolver,
        })

    result = {
        "success": True,
        "order_id": order_id,
        "order_status": order["status"],
        "items": items_enriquecidos,
    }

    add_tool_trace("get_order_items_detail", {"order_id": order_id, "customer_id": customer_id}, result)
    return result