import unittest

from core.session_context import reset_session
from tools import auth, orders


class TestOrders(unittest.TestCase):
    def setUp(self):
        reset_session()

    def tearDown(self):
        reset_session()

    def test_order_status_rejects_without_identity(self):
        result = orders.get_order_status("303")

        self.assertFalse(result["success"])
        self.assertIn("verificación de identidad", result["mensaje"])

    def test_order_status_returns_order_details_after_verification(self):
        auth.verify_identity(dni="1181165722")
        result = orders.get_order_status("303")

        self.assertTrue(result["success"])
        self.assertEqual(result["order_id"], 303)
        self.assertEqual(result["status"], "delivered")
        self.assertEqual(result["envio"]["numero_guia"], "DEP-34055-46369")

    def test_order_amounts_returns_totals_for_verified_customer(self):
        auth.verify_identity(phone="+57 300 133 8908")
        result = orders.get_order_amounts("303")

        self.assertTrue(result["success"])
        self.assertEqual(result["subtotal"], 13314268.0)
        self.assertEqual(result["total_amount"], 15855978.92)
        self.assertEqual(result["payment_method"], "contraentrega")

    def test_order_history_returns_recent_orders(self):
        auth.verify_identity(dni="1181165722")
        result = orders.get_order_history()

        self.assertTrue(result["success"])
        self.assertEqual(result["total_pedidos"], 3)
        self.assertEqual(len(result["pedidos"]), 3)
        self.assertEqual(result["pedidos"][0]["order_id"], 303)

    def test_order_items_detail_returns_enriched_items(self):
        auth.verify_identity(dni="1181165722")
        result = orders.get_order_items_detail("303")

        self.assertTrue(result["success"])
        self.assertEqual(result["order_id"], "303")
        self.assertTrue(any(item["producto"] == "Licuadora Oster Pro Pro" for item in result["items"]))
        self.assertIn("en_garantia", result["items"][0])
