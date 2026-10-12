import contextlib
import io
import json
import unittest
from unittest.mock import Mock

from incident_engine_controller import IncidentController


def healthy_response():
    return 200, {"status": "healthy"}


def unhealthy_response():
    return 503, {"status": "unhealthy"}


class IncidentControllerTests(unittest.TestCase):
    def setUp(self):
        self.health = Mock(return_value=healthy_response())
        self.recovery = Mock(return_value=(
            200, {"status": "healthy", "message": "recovered"}
        ))
        self.controller = IncidentController(
            health_request=self.health,
            recovery_request=self.recovery,
            cooldown_seconds=30,
            verify_delay=0,
            sleep_fn=lambda _: None,
        )
        self.output = io.StringIO()
        self.capture = contextlib.redirect_stdout(self.output)
        self.capture.__enter__()

    def tearDown(self):
        self.capture.__exit__(None, None, None)

    def events(self):
        return [
            json.loads(line)
            for line in self.output.getvalue().splitlines()
        ]

    def test_healthy_application_needs_no_remediation(self):
        self.assertTrue(self.controller.run_check())
        self.recovery.assert_not_called()
        self.assertEqual(self.events()[-1]["event"], "health_check")

    def test_unhealthy_application_is_recovered(self):
        self.health.side_effect = [
            unhealthy_response(),
            healthy_response(),
        ]

        self.assertTrue(self.controller.run_check())
        self.recovery.assert_called_once()
        results = [
            event for event in self.events()
            if event["event"] == "remediation_result"
        ]
        self.assertEqual(results[-1]["result"], "recovered")

    def test_unreachable_service_does_not_trigger_recovery(self):
        self.health.return_value = (None, {"error": "connection refused"})

        self.assertFalse(self.controller.run_check())
        self.recovery.assert_not_called()
        self.assertEqual(self.events()[-1]["event"], "service_unreachable")

    def test_disabled_remediation_does_not_call_recovery(self):
        controller = IncidentController(
            health_request=Mock(return_value=unhealthy_response()),
            recovery_request=self.recovery,
            auto_remediate=False,
            verify_delay=0,
        )

        self.assertFalse(controller.run_check())
        self.recovery.assert_not_called()
        self.assertEqual(
            self.events()[-1]["reason"],
            "AUTO_REMEDIATE is disabled",
        )

    def test_cooldown_prevents_repeated_remediation(self):
        self.health.side_effect = [
            unhealthy_response(),  # First check detects the incident
            healthy_response(),    # Recovery verification succeeds
            unhealthy_response(),  # Next check hits the cooldown
        ]

        self.assertTrue(self.controller.run_check())
        self.assertFalse(self.controller.run_check())

        self.recovery.assert_called_once()
        self.assertEqual(
            self.events()[-1]["reason"],
            "cooldown_active",
        )

    def test_failed_recovery_is_reported(self):
        self.health.return_value = unhealthy_response()
        self.recovery.return_value = (500, {"error": "recovery failed"})

        self.assertFalse(self.controller.run_check())
        self.health.assert_called_once()
        self.assertEqual(
            self.events()[-1]["result"],
            "recovery_failed",
        )


if __name__ == "__main__":
    unittest.main()
