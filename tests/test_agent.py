import unittest
from unittest.mock import patch

from core.agent import Agent
from core.session_context import is_customer_verified, reset_session


class TestAgent(unittest.TestCase):
    def setUp(self):
        reset_session()

    def tearDown(self):
        reset_session()

    def test_agent_asks_for_identity_before_order_status(self):
        agent = Agent.create_agent()

        def fake_generate_text(prompt: str) -> str:
            return "Para continuar necesito verificar tu identidad."

        with patch("core.agent.generate_text", side_effect=fake_generate_text):
            response = agent.respond("Quiero consultar el estado del pedido #303")

        self.assertTrue("verificar tu identidad" in response.lower() or "necesito verificar" in response.lower())
        self.assertEqual(agent._pending_action, "order_status")
        self.assertEqual(agent._pending_order_status_id, "303")
        self.assertTrue(agent._awaiting_verification)

        response_after_verification = agent.respond("Mi cédula es 1181165722")

        self.assertTrue(is_customer_verified())
        self.assertTrue("pedido #303" in response_after_verification.lower() or "estado" in response_after_verification.lower())
        self.assertIsNone(agent._pending_action)
        self.assertFalse(agent._awaiting_verification)

    def test_agent_handles_polite_closing_gracias(self):
        agent = Agent.create_agent()
        response = agent.respond("muchas gracias")

        self.assertIn("con gusto", response.lower())
