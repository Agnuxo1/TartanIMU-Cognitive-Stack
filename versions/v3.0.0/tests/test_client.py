import json
import os
import unittest
from unittest.mock import patch

from jev_orchestrator.client import JEVNotConfigured, TypesafeJevClient
from jev_orchestrator.config import Settings


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class ClientTests(unittest.TestCase):
    def test_missing_key_is_explicit_and_does_not_call_network(self):
        with patch.dict(os.environ, {}, clear=True):
            client = TypesafeJevClient(opener=lambda *a, **k: self.fail("network call"))
            self.assertFalse(client.configured)
            with self.assertRaises(JEVNotConfigured):
                client.evaluate("estado", {"ok": {"type": "noul", "instructions": "¿sí?"}})

    def test_posts_utf8_typed_questions_and_parses_usage(self):
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(
                {
                    "model": "jev-1.13.0",
                    "answers": {"ruta": {"type": "choice", "choice": "editorial", "confidence": 0.9}},
                    "usage": {"input_tokens": 12, "output_tokens": 4},
                }
            )

        settings = Settings(endpoint="https://example.invalid", timeout_seconds=7, max_retries=0)
        client = TypesafeJevClient(api_key="test-only", settings=settings, opener=opener)
        response = client.evaluate(
            {"tarea": "revisión editorial con ñ"},
            {
                "ruta": {
                    "type": "choice",
                    "instructions": "¿Qué ruta?",
                    "criteria": {"editorial": "Edición", "engineering": "Código"},
                }
            },
        )
        self.assertEqual(response.answers["ruta"]["choice"], "editorial")
        self.assertEqual(response.usage["input_tokens"], 12)
        self.assertEqual(calls[0][0].headers["Content-type"], "application/json; charset=utf-8")
        body = json.loads(calls[0][0].data.decode("utf-8"))
        self.assertEqual(body["state"]["tarea"], "revisión editorial con ñ")
        self.assertEqual(calls[0][1], 7)
