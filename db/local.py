"""
db/local.py
===========
Capa de datos local usando DuckDB sobre los CSVs del challenge.
 
Todas las funciones retornan dicts o listas de dicts — nunca
DataFrames ni objetos DuckDB. Así el agente no depende de pandas.
 
Interfaz pública (las mismas funciones existen en db/aws.py para cuando tenga las credenciales de AWS):
    - verify_customer(dni, phone) -> dict | None
    - get_orders_by_customer(customer_id) -> list[dict]
    - get_order_detail(order_id, customer_id) -> dict | None
    - get_order_items(order_id) -> list[dict]
    - get_shipment(order_id) -> dict | None
"""


import re as re
import duckdb
from pathlib import Path
from config import setting


# Connection to the local DuckDB database, which is in-memory and will be created on the fly
# only one connection is needed for the whole app, so we create it at the module level
# Duck DB will read the CSV files directly from the data_path defined in the settings

_conn : duckdb.DuckDBPyConnection | None = None

def _get_con() -> duckdb.DuckDBPyConnection:
    """ Get the DuckDB connection, creating it if it doesn't exist. """
    global _conn
    if _conn is None:
        # Create a new in-memory DuckDB connection
        _conn = duckdb.connect(database=':memory:')
    return _conn

def _csv (name: str) -> str:
    """ Get the full path to a CSV file in the data directory. """
    return str(setting.data_path / f"{name}.csv")

# Funciones utils para los datos

# Normalizar el formato del teléfono para que sea consistente con el formato de los datos
# El CSV guarda: "+57 300 133 8908"
# El usuario puede escribir cualquier variante.
# Normalizamos ambos a solo dígitos paara que se puede comparar más fácil


def normalize_phone(phone: str) -> str:
    ''' Clean the phone number to only digits for easier comparison. '''
    return re.sub(r"\D", "", phone)


# AUTH

def verify_customer(dni: str = None, phone: str = None) -> dict | None:
    """ Verify the customer by their DNI and/or phone number. """

    """
    Busca un cliente por cédula o teléfono.
 
    La comparación de teléfono normaliza ambos lados para
    que "+57 300 133 8908" == "3001338908" == "300 133 8908".
 
    Args:
        dni:   Número de cédula pero solo con los digitos
        phone: Teléfono en cualquier formato
 
    Returns:
        Dict con datos del cliente si se encontró, None si no.
        Incluye: customer_id, name, last_name1, account_status, is_premium
    """

    con = _get_con()
    
    if dni:
        # Get customer by clean DNI
        dni_limpio = dni.strip()
        result = con.execute(f"""
            SELECT customer_id, tipo_id, dni, name, last_name1, last_name2,
                   phone, account_status, is_premium
            FROM '{_csv("customers")}'
            WHERE dni = '{dni_limpio}'
            LIMIT 1
        """).fetchone()
 
        if result:
            cols = ["customer_id", "tipo_id", "dni", "name", "last_name1",
                    "last_name2", "phone", "account_status", "is_premium"]
            return dict(zip(cols, result))
 
    if phone:
        # Get customer by normalized phone number
        # Get all customers and compare normalized phone numbers using Python
        phone_normalizado = normalize_phone(phone)
 
        rows = con.execute(f"""
            SELECT customer_id, tipo_id, dni, name, last_name1, last_name2,
                   phone, account_status, is_premium
            FROM '{_csv("customers")}'
        """).fetchall()
 
        cols = ["customer_id", "tipo_id", "dni", "name", "last_name1",
                "last_name2", "phone", "account_status", "is_premium"]
 
        for row in rows:
            customer = dict(zip(cols, row))
            if normalize_phone(customer["phone"]) == phone_normalizado:
                return customer
 
    return None


# ORDERS

def get_orders_by_customer(customer_id: int | str) -> list[dict]:
    """
    Retorna todos los pedidos de un cliente autenticado.
 
    Args:
        customer_id: ID del cliente (ej. 1001)
 
    Returns:
        Lista de pedidos ordenados por fecha descendente.
        Cada dict incluye los campos principales del pedido.
    """
    con = _get_con()
    rows = con.execute(f"""
        SELECT order_id, order_date, status, subtotal, tax,
               shipping_cost, total_amount, delivery_method,
               payment_method, shipped_at, delivered_at, cancelled_at
        FROM '{_csv("orders")}'
        WHERE customer_id = {int(customer_id)}
        ORDER BY order_date DESC
    """).fetchall()
 
    cols = ["order_id", "order_date", "status", "subtotal", "tax",
            "shipping_cost", "total_amount", "delivery_method",
            "payment_method", "shipped_at", "delivered_at", "cancelled_at"]
 
    return [dict(zip(cols, row)) for row in rows]
 
 
def get_order_detail(order_id: int | str, customer_id: int | str) -> dict | None:
    """
    Retorna el detalle de un pedido específico.
 
    Nota: siempre recibe customer_id para verificar que
    el pedido le pertenece al cliente autenticado. Nunca
    retornar datos de un pedido de otro cliente.
 
    Args:
        order_id:    ID del pedido
        customer_id: ID del cliente autenticado en esta sesión
 
    Returns:
        Dict con todos los campos del pedido, o None si no existe
        o no es del cliente.
    """
    con = _get_con()
    row = con.execute(f"""
        SELECT order_id, customer_id, order_date, status,
               subtotal, tax, shipping_cost, total_amount,
               delivery_method, payment_method,
               shipped_at, delivered_at, cancelled_at,
               cancellation_reason, customer_notes
        FROM '{_csv("orders")}'
        WHERE order_id = {int(order_id)}
          AND customer_id = {int(customer_id)}
        LIMIT 1
    """).fetchone()
 
    if not row:
        return None
 
    cols = ["order_id", "customer_id", "order_date", "status",
            "subtotal", "tax", "shipping_cost", "total_amount",
            "delivery_method", "payment_method",
            "shipped_at", "delivered_at", "cancelled_at",
            "cancellation_reason", "customer_notes"]
 
    return dict(zip(cols, row))
 
 
def get_order_items(order_id: int | str) -> list[dict]:
    """
    Retorna los ítems de un pedido con info del producto.
 
    Hace JOIN con products para incluir nombre y categoría.
    Sirve para mostrar qué productos tiene el pedido,
    estado de garantía y si aplica devolución.
 
    Args:
        order_id: ID del pedido
 
    Returns:
        Lista de ítems. Cada dict incluye producto, precio,
        estado del ítem, fechas de garantía y devolución.
    """
    con = _get_con()
    rows = con.execute(f"""
        SELECT
            oi.item_id,
            oi.product_id,
            p.name        AS product_name,
            oi.qty,
            oi.unit_price,
            oi.item_status,
            oi.warranty_expires_at,
            oi.return_deadline
        FROM '{_csv("order_items")}' oi
        LEFT JOIN '{_csv("products")}' p
            ON oi.product_id = p.product_id
        WHERE oi.order_id = {int(order_id)}
    """).fetchall()
 
    cols = ["item_id", "product_id", "product_name", "qty",
            "unit_price", "item_status", "warranty_expires_at", "return_deadline"]
 
    return [dict(zip(cols, row)) for row in rows]
 
 
def get_shipment(order_id: int | str) -> dict | None:
    """
    Retorna la info de envío de un pedido.
 
    Args:
        order_id: ID del pedido
 
    Returns:
        Dict con transportadora, guía, URL de tracking,
        fechas y estado del envío. None si no existe el envío.
    """
    con = _get_con()
    row = con.execute(f"""
        SELECT shipment_id, order_id, carrier, tracking_number,
               tracking_url, shipped_date, estimated_delivery_date,
               actual_delivery_date, delivery_attempts,
               failed_delivery_reason, shipment_status
        FROM '{_csv("shipments")}'
        WHERE order_id = {int(order_id)}
        LIMIT 1
    """).fetchone()
 
    if not row:
        return None
 
    cols = ["shipment_id", "order_id", "carrier", "tracking_number",
            "tracking_url", "shipped_date", "estimated_delivery_date",
            "actual_delivery_date", "delivery_attempts",
            "failed_delivery_reason", "shipment_status"]
 
    return dict(zip(cols, row))
 
 
# ─────────────────────────────────────────────
# PRODUCTS (No Auth required)
# ─────────────────────────────────────────────
 
def get_product_info(product_id: int | str) -> dict | None:
    """
    Retorna info pública de un producto: precio, stock, garantía.
    No requiere autenticación esta es información pública.
    """
    con = _get_con()
    row = con.execute(f"""
        SELECT
            p.product_id, p.name, p.price, p.category_id,
            p.brand_id, p.warranty_months, p.return_days,
            p.free_shipping, p.is_active,
            s.stock_qty - s.reserved_qty AS available_stock
        FROM '{_csv("products")}' p
        LEFT JOIN '{_csv("stock")}' s ON p.product_id = s.product_id
        WHERE p.product_id = {int(product_id)}
        LIMIT 1
    """).fetchone()
 
    if not row:
        return None
 
    cols = ["product_id", "name", "price", "category_id", "brand_id",
            "warranty_months", "return_days", "free_shipping",
            "is_active", "available_stock"]
 
    return dict(zip(cols, row))