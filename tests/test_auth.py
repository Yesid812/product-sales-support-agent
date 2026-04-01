import unittest

from core.session_context import get_tool_trace, get_tool_trace_length, reset_session
from tools import auth


class TestAuth(unittest.TestCase):
    def setUp(self):
        reset_session()

    def tearDown(self):
        reset_session()

    def test_verify_identity_by_dni_sets_session_and_records_tool_trace(self):
        result = auth.verify_identity(dni="1181165722")

        self.assertTrue(result["success"])
        self.assertEqual(result["customer_id"], 1001)
        self.assertIn("Identidad verificada", result["mensaje"])

        self.assertEqual(get_tool_trace_length(), 1)
        trace = get_tool_trace()[0]
        self.assertEqual(trace["tool"], "verify_identity")
        self.assertEqual(trace["input"]["dni"], "1181165722")

    def test_verify_identity_by_phone_sets_session(self):
        result = auth.verify_identity(phone="+57 300 133 8908")

        self.assertTrue(result["success"])
        self.assertEqual(result["customer_id"], 1001)
        self.assertTrue(result["nombre"].startswith("Luis"))

    def test_verify_identity_requires_dni_or_phone(self):
        result = auth.verify_identity()

        self.assertFalse(result["success"])
        self.assertIn("Se requiere cédula o número de celular", result["mensaje"])

    def test_verify_identity_unknown_customer_returns_failure(self):
        result = auth.verify_identity(dni="0000000000")

        self.assertFalse(result["success"])
        self.assertIn("No encontramos un cliente", result["mensaje"])
