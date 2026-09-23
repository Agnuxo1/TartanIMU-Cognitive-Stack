import unittest

from jev_orchestrator.client import JEVResponse
from jev_orchestrator.orchestrator import JEVOrchestrator


class FakeClient:
    def __init__(self):
        self.calls = []

    def evaluate(self, state, questions):
        self.calls.append((state, questions))
        return JEVResponse("jev-test", {"ok": {"type": "noul", "noul": 1}}, {}, {})


class OrchestratorTests(unittest.TestCase):
    def test_route_batches_typed_questions_in_one_call(self):
        client = FakeClient()
        result = JEVOrchestrator(client).route("preparar revisión", {"fase": "producción"})
        self.assertEqual(result.provenance, "jev")
        self.assertEqual(len(client.calls), 1)
        questions = client.calls[0][1]
        self.assertEqual(questions["agent"]["type"], "choice")
        self.assertEqual(questions["model"]["type"], "choice")
        self.assertEqual(questions["needs_supervision"]["type"], "noul")

    def test_gatekeeper_contains_completion_and_policy_checks(self):
        client = FakeClient()
        JEVOrchestrator(client).gatekeep({"result": "draft"})
        questions = client.calls[0][1]
        self.assertEqual(set(questions), {"ready", "policy_ok"})
