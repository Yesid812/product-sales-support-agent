import re
from typing import Optional

from core.llm import generate_text
from core.session_context import is_customer_verified, reset_session
from tools import auth, orders, policies
from tools.products import search_products


class Agent:
    """El agente que responde preguntas del usuario."""

    def __init__(self, streaming: bool = False):
        self._last_response = None
        self.streaming = streaming
        self._pending_order_status_id: Optional[str] = None
        self._pending_action: Optional[str] = None
        self._awaiting_verification: bool = False
        self._history: list[tuple[str, str]] = []

    @staticmethod
    def create_agent(streaming: bool = False) -> "Agent":
        """Crea una instancia del agente con opciones de streaming y reinicia la sesión."""
        reset_session()
        return Agent(streaming=streaming)

    def __call__(self, message: str) -> str:
        """Permite invocar el agente directamente como agente('texto')."""
        return self.respond(message)

    def reset_memory(self) -> None:
        """Resetea el estado del agente y de la sesión entre conversaciones."""
        reset_session()
        self._last_response = None
        self._pending_order_status_id = None
        self._pending_action = None
        self._awaiting_verification = False
        self._history = []

    def respond(self, message: str) -> str:
        """Procesa el mensaje del usuario y devuelve una respuesta."""
        text = (message or "").strip()
        if not text:
            self._last_response = self._generate_generic_response(
                "Por favor escribe tu consulta para que pueda ayudarte."
            )
            return self._last_response

        # Resistencia a prompt injection — hard gate de seguridad
        if self._is_prompt_injection(text):
            self._last_response = (
                "Solo puedo ayudarte con consultas sobre pedidos, productos "
                "y políticas de la tienda."
            )
            return self._last_response

        normalized = text.lower()
        order_id = self._extract_order_id(normalized)

        if self._is_simple_greeting(normalized) and not self._last_response:
            self._last_response = "¡Hola! Buenas. ¿En qué puedo ayudarte?"
            return self._last_response

        if self._awaiting_verification and self._looks_like_identity_input(normalized):
            self._last_response = self._handle_verification(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._pending_action == "order_status" and is_customer_verified() and order_id:
            self._last_response = self._handle_order_status(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._pending_action == "order_status" and is_customer_verified() and not order_id:
            self._last_response = self._generate_order_number_request()
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_polite_closing(normalized):
            self._last_response = self._generate_polite_response(normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_policy_request(normalized):
            self._last_response = self._handle_policy(text)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_order_status_request(normalized):
            self._last_response = self._handle_order_status(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_order_amount_request(normalized):
            self._last_response = self._handle_order_amount(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_order_history_request(normalized):
            self._last_response = self._handle_order_history(text)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_order_items_request(normalized):
            self._last_response = self._handle_order_items(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        # Rama 3: precios/stock de productos — no requiere autenticación
        # Verificar ANTES de _is_verification_request para evitar falsos positivos
        # con la palabra "celular" en consultas de producto
        if self._is_product_query(normalized):
            self._last_response = self._handle_product_query(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        if self._is_verification_request(normalized):
            self._last_response = self._handle_verification(text, normalized)
            self._append_history(text, self._last_response)
            return self._last_response

        self._last_response = self._generate_generic_response(text)
        self._append_history(text, self._last_response)
        return self._last_response

    def _handle_verification(self, text: str, normalized: str) -> str:
        dni = self._extract_dni(normalized)
        phone = self._extract_phone(normalized)
        if not dni and not phone and self._awaiting_verification:
            if re.fullmatch(r"\d{6,12}", normalized):
                dni = normalized

        self._awaiting_verification = False
        if not dni and not phone:
            return "Necesito que me indiques tu cédula o tu número de celular para verificar tu identidad."

        result = auth.verify_identity(dni=dni, phone=phone)
        if not result.get("success"):
            return self._generate_verification_response(result, success=False)

        if self._pending_action == "order_status":
            if self._pending_order_status_id:
                order_id = self._pending_order_status_id
                self._pending_order_status_id = None
                self._pending_action = None
                status_result = orders.get_order_status(order_id)
                if status_result.get("success"):
                    return self._format_order_status(status_result)
                return status_result.get("mensaje", "No pude consultar el estado del pedido.")
            return self._generate_post_verification_order_status_response(result)

        self._pending_action = None
        return self._generate_verification_response(result, success=True)

    def _handle_policy(self, text: str) -> str:
        result = policies.search_policy(text)
        if not result.get("encontrado"):
            return result.get("contexto", "No se encontró información relevante en las políticas.")

        prompt = (
            "Eres un asistente de soporte al cliente. Responde en español usando SOLO el siguiente contexto de política. "
            "No inventes nada. Mantén la respuesta breve. "
            f"Pregunta: {text}\n\nContexto:\n{result['contexto']}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return result.get("contexto", "No se encontró información relevante en las políticas.")

    def _handle_order_status(self, text: str, normalized: str) -> str:
        order_id = self._extract_order_id(normalized)
        if not is_customer_verified():
            self._awaiting_verification = True
            self._pending_action = "order_status"
            if order_id:
                self._pending_order_status_id = order_id
                return self._generate_verification_request(order_id=order_id)
            return self._generate_verification_request(order_id=None)

        if not order_id:
            self._pending_action = "order_status"
            return self._generate_generic_response(
                "Claro, dime el número de pedido para consultar su estado."
            )

        result = orders.get_order_status(order_id)
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar el estado del pedido.")

        self._pending_action = None
        self._pending_order_status_id = None

        facts = [
            f"Pedido #{result['order_id']}",
            f"estado {result['status']}",
            f"pedido el {result['order_date']}",
            f"método de entrega {result['delivery_method']}",
            f"método de pago {result['payment_method']}"
        ]
        envio = result.get("envio")
        if envio:
            facts.extend([
                f"transportadora {envio.get('transportadora')}",
                f"guía {envio.get('numero_guia')}"
            ])
            if envio.get("estado_envio"):
                facts.append(f"estado de envío {envio.get('estado_envio')}")

        prompt = (
            "Eres un asistente de soporte al cliente. Usa solo los datos del pedido para dar una respuesta clara y natural en español. "
            "No agregues información que no está presente. "
            f"Datos: {', '.join(facts)}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            envio_text = (
                f" Envío: {envio.get('transportadora')} - {envio.get('numero_guia')}"
                if envio else "No hay información de envío disponible."
            )
            return (
                f"Pedido #{result['order_id']} está en estado '{result['status']}'. "
                f"Fecha del pedido: {result['order_date']}. {envio_text}"
            )

    def _handle_order_amount(self, text: str, normalized: str) -> str:
        order_id = self._extract_order_id(normalized)
        if not order_id:
            return self._generate_generic_response(
                "Dime el número de pedido para consultar cuánto pagaste."
            )

        result = orders.get_order_amounts(order_id)
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar el monto del pedido.")

        prompt = (
            "Eres un asistente de soporte al cliente. Explica en español el monto de este pedido usando SOLO estos datos. "
            f"Pedido #{result['order_id']}, subtotal {result['subtotal']}, IVA {result['tax']}, envío {result['shipping_cost']}, total {result['total_amount']}, pago {result['payment_method']}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return (
                f"Pedido #{result['order_id']} tiene subtotal {result['subtotal']}, "
                f"IVA {result['tax']}, envío {result['shipping_cost']} y total {result['total_amount']}. "
                f"Método de pago: {result['payment_method']}."
            )

    def _handle_order_history(self, text: str) -> str:
        result = orders.get_order_history()
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar tu historial de pedidos.")

        orders_list = result.get("pedidos", [])
        if not orders_list:
            return self._generate_generic_response("No tienes pedidos registrados en tu cuenta.")

        details = "; ".join(
            f"Pedido #{pedido['order_id']}: {pedido['status']}, fecha {pedido['fecha']}, total {pedido['total']}"
            for pedido in orders_list[:5]
        )
        prompt = (
            "Eres un asistente de soporte al cliente. Resume en español esta lista de pedidos de forma clara y breve. "
            f"Datos: {details}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "\n".join(details.split("; "))

    def _handle_order_items(self, text: str, normalized: str) -> str:
        order_id = self._extract_order_id(normalized)
        if not order_id:
            return self._generate_generic_response(
                "Dime el número de pedido para ver los detalles de los ítems."
            )

        result = orders.get_order_items_detail(order_id)
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar los ítems del pedido.")

        item_lines = [
            f"{item['producto']} x{item['qty']} a ${item['precio_unitario']}, estado {item['estado_item']}, garantía vigente {item['en_garantia']}"
            for item in result.get("items", [])[:5]
        ]
        prompt = (
            "Eres un asistente de soporte al cliente. Responde en español usando SOLO la siguiente información. "
            f"Pedido #{result['order_id']}, estado {result['order_status']}. Ítems: {'; '.join(item_lines)}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "\n".join(item_lines)

    def _generate_generic_response(self, message: str) -> str:
        prompt = (
            "Eres un asistente de soporte al cliente para una tienda de comercio electrónico. "
            "Responde en español de forma natural y breve. No inventes información. "
            "Evita saludos largos y no empieces cada respuesta con un saludo si ya hubo uno en la conversación. "
            f"Usuario: {message}\nRespuesta:"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "Lo siento, no puedo procesar tu solicitud ahora. Por favor intenta nuevamente."

    def _append_history(self, user: str, assistant: str) -> None:
        """Registra el último intercambio para referencia interna del agente."""
        self._history.append((user, assistant))

    def _generate_verification_request(self, order_id: Optional[str]) -> str:
        if order_id:
            instruction = (
                f"El cliente quiere consultar el estado del pedido #{order_id}, pero antes debes verificar su identidad. "
                "Pide solo la cédula o el número de celular y no hagas otra cosa."
            )
        else:
            instruction = (
                "El cliente quiere consultar el estado de un pedido, pero antes debes verificar su identidad. "
                "Pide solo la cédula o el número de celular y no hagas otra cosa."
            )
        prompt = (
            "Eres un asistente de soporte al cliente para una tienda de comercio electrónico. "
            "Responde en español de forma cordial y natural. No inventes información. "
            f"{instruction}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            if order_id:
                return (
                    f"Para consultar el pedido #{order_id} primero necesito verificar tu identidad. "
                    "Por favor, indícame tu cédula o tu número de celular."
                )
            return (
                "Antes de consultar el estado de tu pedido necesito verificar tu identidad. "
                "Por favor dime tu cédula o tu número de celular."
            )

    def _generate_verification_response(self, result: dict, success: bool) -> str:
        if success:
            prompt = (
                "Eres un asistente de soporte al cliente. Responde en español de forma natural y breve. "
                "El cliente ha proporcionado sus datos de verificación. "
                f"Resultado: success={result.get('success')}, mensaje={result.get('mensaje')}"
            )
        else:
            prompt = (
                "Eres un asistente de soporte al cliente. Responde en español de forma natural y clara. "
                "El cliente intentó verificar su identidad. "
                f"Resultado: success={result.get('success')}, mensaje={result.get('mensaje')}"
            )
        try:
            return generate_text(prompt)
        except Exception:
            return result.get("mensaje", "No pude verificar tu identidad.")

    def _generate_post_verification_order_status_response(self, result: dict) -> str:
        prompt = (
            "Eres un asistente de soporte al cliente. Responde en español de forma natural y clara. "
            "El cliente ya verificó su identidad correctamente, pero aún no proporcionó el número de pedido. "
            "Pide solo el número de pedido para poder revisar su estado, no incluyas otros datos."
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "Tu identidad está verificada. Por favor dime el número de pedido para poder consultarlo."

    def _generate_order_number_request(self) -> str:
        prompt = (
            "Eres un asistente de soporte al cliente y la identidad del cliente ya está verificada. "
            "Responde en español de forma natural y breve. "
            "Pide de forma clara el número de pedido para continuar con la consulta."
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "Ya verifiqué tu identidad. Por favor indícame el número de pedido para consultarlo."

    def _generate_polite_response(self, text: str) -> str:
        if "gracias" in text or "muchas gracias" in text:
            return "Con gusto, estoy aquí para ayudarte cuando lo necesites."
        if any(term in text for term in ["adiós", "hasta luego", "nos vemos", "chao"]):
            return "Hasta luego. Si necesitas algo más, estaré aquí para ayudarte."
        return "Con gusto, dime si necesitas algo más."

    def _is_polite_closing(self, text: str) -> bool:
        return bool(
            any(term in text for term in [
                "gracias", "muchas gracias", "mil gracias", "te lo agradezco",
                "adiós", "adios", "hasta luego", "nos vemos", "chao"
            ])
        )

    def _is_verification_request(self, text: str) -> bool:
        return any(term in text for term in [
            "verificar", "verificacion", "verificación", "identidad", "dni", "cédula", "cedula", "celular", "teléfono", "telefono"
        ])

    def _is_policy_request(self, text: str) -> bool:
        return any(term in text for term in [
            "política", "politica", "devolución", "devolucion", "garantía", "garantia",
            "envío", "envio", "reembolso", "cancelación", "cancelacion", "plazo", "cambio"
        ])

    def _is_order_status_request(self, text: str) -> bool:
        return "pedido" in text and any(term in text for term in ["estado", "seguimiento", "tracking", "pedido"])

    def _is_order_amount_request(self, text: str) -> bool:
        return "pedido" in text and any(term in text for term in ["cuánto pagué", "cuanto pague", "total", "monto", "valor", "pagé"])

    def _is_order_history_request(self, text: str) -> bool:
        return any(term in text for term in ["mis pedidos", "historial", "qué he comprado", "que he comprado", "qué compré", "que compré", "lista de pedidos"])

    def _is_order_items_request(self, text: str) -> bool:
        return any(term in text for term in ["ítems", "items", "artículos", "articulos", "detalles del pedido", "detalle del pedido"])

    def _is_simple_greeting(self, text: str) -> bool:
        return bool(
            re.match(
                r"^(hola|buenas|buenos días|buenos dias|buenas tardes|buenas noches)([.!?]|\s.*)?$",
                text,
            )
        )

    def _looks_like_identity_input(self, text: str) -> bool:
        if self._extract_dni(text) or self._extract_phone(text):
            return True
        return bool(re.fullmatch(r"[\d\s\+\-\(\)]{6,20}", text))

    def _extract_order_id(self, text: str) -> Optional[str]:
        patterns = [
            r"pedido\s*#?\s*(\d+)",
            r"orden\s*#?\s*(\d+)",
            r"número\s*de\s*pedido\s*#?\s*(\d+)",
            r"numero\s*de\s*pedido\s*#?\s*(\d+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        digits = re.findall(r"\b\d+\b", text)
        return digits[0] if digits else None

    def _extract_dni(self, text: str) -> Optional[str]:
        match = re.search(
            r"(?:dni|cédula|cedula)\s*(?:[:\-]|\b(?:es|es:)\b)?\s*(\d{6,12})",
            text,
        )
        if match:
            return match.group(1)
        if self._awaiting_verification and re.fullmatch(r"\d{6,12}", text):
            return text
        return None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(
            r"(?:celular|tel[eé]fono|telefono)\s*(?:[:\-]|\b(?:es|es:)\b)?\s*([\d\s\+\-\(\)]+)",
            text,
        )
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            return digits if digits else None
        if self._awaiting_verification and re.fullmatch(r"[\d\s\+\-\(\)]{7,20}", text):
            digits = re.sub(r"\D", "", text)
            return digits if digits else None
        return None

    def _format_policy_response(self, result: dict, question: str) -> str:
        if not result.get("encontrado"):
            return result.get("contexto", "No se encontró información relevante en las políticas.")

        prompt = (
            "Eres un asistente de soporte al cliente. Responde en español usando SOLO la siguiente información "
            "de las políticas de la empresa. No inventes nada. Si la pregunta no puede contestarse con el contexto, di que no hay información suficiente. "
            f"Pregunta: {question}\n\nContexto:\n{result['contexto']}"
        )
        try:
            return generate_text(prompt)
        except Exception as exc:
            return (
                "Encontré información en las políticas, pero no pude generar una respuesta con Gemini. "
                f"Contexto: {result['contexto']}"
            )

    def _format_order_status(self, result: dict) -> str:
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar el estado del pedido.")

        facts = [
            f"Pedido #{result['order_id']}",
            f"estado {result['status']}",
            f"pedido el {result['order_date']}",
            f"método de entrega {result['delivery_method']}",
            f"método de pago {result['payment_method']}"
        ]
        envio = result.get("envio")
        if envio:
            facts.extend([
                f"transportadora {envio.get('transportadora')}",
                f"guía {envio.get('numero_guia')}"
            ])
            if envio.get("estado_envio"):
                facts.append(f"estado de envío {envio.get('estado_envio')}")

        prompt = (
            "Eres un asistente de soporte al cliente. Usa solo los datos del pedido para dar una respuesta clara y natural en español. "
            "No agregues información que no está presente. "
            f"Datos: {', '.join(facts)}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            envio_text = (
                f" Envío: {envio.get('transportadora')} - {envio.get('numero_guia')}"
                if envio else "No hay información de envío disponible."
            )
            return (
                f"Pedido #{result['order_id']} está en estado '{result['status']}'. "
                f"Fecha del pedido: {result['order_date']}. {envio_text}"
            )

    def _format_order_amounts(self, result: dict) -> str:
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar el monto del pedido.")

        prompt = (
            "Eres un asistente de soporte al cliente. Presenta el monto del pedido en español usando solo estos valores. "
            f"Pedido #{result['order_id']}, subtotal {result['subtotal']}, IVA {result['tax']}, envío {result['shipping_cost']}, total {result['total_amount']}, pago {result['payment_method']}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return (
                f"Pedido #{result['order_id']} tiene subtotal {result['subtotal']}, "
                f"IVA {result['tax']}, envío {result['shipping_cost']} y total {result['total_amount']}. "
                f"Método de pago: {result['payment_method']}."
            )

    def _format_order_history(self, result: dict) -> str:
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar tu historial de pedidos.")

        orders_list = result.get("pedidos", [])
        if not orders_list:
            return "No tienes pedidos registrados en la cuenta."

        lines = [f"Tengo {result['total_pedidos']} pedidos registrados en tu cuenta."]
        for pedido in orders_list[:5]:
            lines.append(
                f"Pedido #{pedido['order_id']}: {pedido['status']}, fecha {pedido['fecha']}, total {pedido['total']}"
            )
        prompt = (
            "Eres un asistente de soporte al cliente. Resume esta lista de pedidos en un texto corto y claro en español. "
            f"Información: {'; '.join(lines)}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "\n".join(lines)

    def _format_order_items(self, result: dict) -> str:
        if not result.get("success"):
            return result.get("mensaje", "No pude consultar los ítems del pedido.")

        items = result.get("items", [])
        if not items:
            return f"El pedido #{result['order_id']} no tiene ítems registrados."

        lines = [f"Pedido #{result['order_id']} - estado {result['order_status']}. Ítems:"]
        for item in items[:5]:
            lines.append(
                f"{item['producto']} x{item['qty']} a ${item['precio_unitario']}, estado {item['estado_item']}, garantia vigente: {item['en_garantia']}"
            )
        prompt = (
            "Eres un asistente de soporte al cliente. Resume esta información del pedido en una respuesta clara y natural en español. "
            f"Datos: {'; '.join(lines)}"
        )
        try:
            return generate_text(prompt)
        except Exception:
            return "\n".join(lines)
