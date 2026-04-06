"""
tools/auth.py
=============
Herramienta de autenticación del agente.

Es el gate obligatorio del challenge por lo que ninguna consulta
sobre pedidos, historial o montos puede responderse sin
haber llamado primero a verify_identity() en este archivo.
"""

from db.local import verify_customer
from core.session_context import add_tool_trace, set_session_customer, is_customer_verified


def verify_identity(dni: str = None, phone: str = None) -> dict:
    """
    Verifica la identidad del cliente por cédula o teléfono.

    El agente llama esta función cuando el usuario proporciona
    su cédula o número de celular. Si la verificación es exitosa,
    registra al cliente en la sesión y desbloquea las consultas
    de pedidos.

    Args:
        dni:   Número de cédula (solo dígitos, sin puntos ni guiones)
        phone: Número de celular (cualquier formato, ej: 3001234567)

    Returns:
        Dict con:
            - success (bool): si se verificó o no
            - customer_id: ID del cliente (si success)
            - nombre: nombre para saludar (si success)
            - account_status: estado de la cuenta (si success)
            - mensaje: texto explicativo del resultado
    """
    # Validación básica — necesitamos al menos uno
    if not dni and not phone:
        result = {
            "success": False,
            "mensaje": "Se requiere cédula o número de celular para verificar identidad."
        }
        add_tool_trace("verify_identity", {"dni": dni, "phone": phone}, result)
        return result

    # Buscar en la base de datos
    customer = verify_customer(dni=dni, phone=phone)

    if not customer:
        result = {
            "success": False,
            "mensaje": "No encontramos un cliente con ese documento o celular. "
                       "Verifica que el número esté correcto e intenta de nuevo."
        }
        add_tool_trace("verify_identity", {"dni": dni, "phone": phone}, result)
        return result

    # Cliente encontrado — registrar en sesión
    name_display = f"{customer['name']} {customer['last_name1']}"
    set_session_customer(customer["customer_id"], name_display)

    result = {
        "success": True,
        "customer_id": customer["customer_id"],
        "nombre": name_display,
        "account_status": customer["account_status"],
        "is_premium": customer["is_premium"],
        "mensaje": f"Identidad verificada correctamente."
    }
    add_tool_trace("verify_identity", {"dni": dni, "phone": phone}, result)
    return result


def get_auth_status() -> dict:
    """
    Retorna si hay un cliente autenticado en la sesión actual.

    El agente usa esto para decidir si necesita pedir
    identificación antes de responder una consulta sensible.

    Returns:
        Dict con authenticated (bool) y datos del cliente si aplica.
    """
    from core.session_context import get_session_customer
    customer = get_session_customer()

    if customer:
        return {
            "authenticated": True,
            "customer_id": customer["customer_id"],
            "nombre": customer["display_name"],
        }
    return {"authenticated": False}