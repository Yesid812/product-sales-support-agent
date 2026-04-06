"""
core/session_context.py
=======================
Módulo de observabilidad del agente.

REGLA CRÍTICA DE DISEÑO:
    El evaluador llama get_tool_trace() desde un proceso/hilo diferente
    al que ejecuta el agente. Si usas threading.local() o contextvars,
    el trace aparece VACÍO al evaluarse → penalización por "alucinación".

    Solución: variables globales simples a nivel de módulo.
    Feas. Pero son exactamente lo que el contrato técnico exige.

FUNCIONES REQUERIDAS POR EL CONTRATO:
    - add_tool_trace(tool_name, input_data, output_data)
    - set_session_customer(customer_id, display_name)
    - reset_session()
    - get_tool_trace()
    - get_tool_trace_length()
    - get_tool_trace_since(index)
"""

import time
from typing import Any

# ─────────────────────────────────────────────
# ESTADO GLOBAL 
# ─────────────────────────────────────────────

_tool_trace: list[dict] = []          # historial de herramientas usadas
_session_customer: dict | None = None  # identidad verificada del cliente actual


# ─────────────────────────────────────────────
# 
# ─────────────────────────────────────────────

def add_tool_trace(tool_name: str, input_data: Any, output_data: Any) -> None:
    """
    Registra que el agente consultó una herramienta externa.

    CUÁNDO llamar esto: dentro de cada @tool, justo ANTES de retornar.
    Sin este registro, el evaluador no puede verificar que el agente
    consultó la fuente correcta → hard fail por anti-alucinación.

    Args:
        tool_name:   Nombre de la herramienta (ej. "verify_identity")
        input_data:  Parámetros que recibió la herramienta
        output_data: Resultado que retornó la herramienta
    """
    entry = {
        "tool": tool_name,
        "input": input_data,
        "output": output_data,
        "timestamp": time.time(),       # útil para auditoría y debugging
    }
    _tool_trace.append(entry)


def set_session_customer(customer_id: int | str, display_name: str) -> None:
    """
    Registra la identidad del cliente después de verificación exitosa.

    CUÁNDO llamar esto: en la herramienta verify_identity(), SOLO si
    la cédula o teléfono coincide con la base de datos.

    Args:
        customer_id:  ID del cliente (ej. 1001)
        display_name: Nombre para mostrar en respuestas (puede ser
                      aproximado, los datos tienen ruido intencional)
    """
    global _session_customer
    _session_customer = {
        "customer_id": customer_id,
        "display_name": display_name,
        "verified_at": time.time(),
    }


def reset_session() -> None:
    """
    Limpia el estado de la sesión entre conversaciones.

    El evaluador llama esto entre cada escenario de prueba para
    asegurar que una sesión no "contamina" la siguiente.

    IMPORTANTE: también debes implementar reset_memory() en el agente
    o garantizar que create_agent() devuelva instancias sin estado
    compartido entre llamadas.
    """
    global _tool_trace, _session_customer
    _tool_trace = []
    _session_customer = None


# ─────────────────────────────────────────────
# 
# ─────────────────────────────────────────────

def get_tool_trace() -> list[dict]:
    """
    Retorna el historial completo de herramientas usadas en esta sesión.

    El evaluador llama esto después de cada turno para verificar
    que el agente consultó la herramienta correcta antes de responder.

    Returns:
        Lista de entradas, cada una con: tool, input, output, timestamp
        Lista vacía → agente respondió sin consultar herramientas → penalización
    """
    return list(_tool_trace)  # copia defensiva para evitar modificaciones externas


def get_tool_trace_length() -> int:
    """
    Retorna cuántas herramientas han sido llamadas en esta sesión.

    Útil para el evaluador para saber si aumentó el número de
    tool calls entre turnos sin tener que comparar listas completas.
    """
    return len(_tool_trace)


def get_tool_trace_since(index: int) -> list[dict]:
    """
    Retorna solo los registros desde una posición específica.

    El evaluador usa esto para obtener las tool calls del turno
    ACTUAL sin re-procesar todo el historial anterior.

    Args:
        index: Posición desde la cual retornar (ej. longitud antes del turno)

    Returns:
        Sublista de _tool_trace desde index hasta el final

    Ejemplo:
        before = get_tool_trace_length()      # antes del turno
        agente("¿cuál es mi pedido?")         # ejecuta el turno
        new_calls = get_tool_trace_since(before)  # solo las de este turno
    """
    return list(_tool_trace[index:])


# ─────────────────────────────────────────────

# ─────────────────────────────────────────────

def get_session_customer() -> dict | None:
    """
    Retorna la identidad del cliente verificado, o None si no hay.

    Úsalo en tus tools para saber si el usuario ya se autenticó
    sin tener que pasar el estado como parámetro.

    Returns:
        Dict con customer_id, display_name, verified_at
        None si el cliente no se ha autenticado aún
    """
    return _session_customer


def is_customer_verified() -> bool:
    """Atajo: ¿hay un cliente autenticado en esta sesión?"""
    return _session_customer is not None