import unittest
from unittest.mock import Mock

from prometheus_client import generate_latest

from incident_engine_controller import IncidentController


class IncidentMetricsTests(unittest.TestCase):

    def make_controller(self, health_responses, recovery_response):
        health = Mock(side_effect=health_responses)
        recovery = Mock(return_value=recovery_response)

        controller = IncidentController(
            health_request=health,
            recovery_request=recovery,
            cooldown_seconds=30,
            verify_delay=0,
            sleep_fn=lambda _: None,
        )

        return controller, health, recovery

    def test_successful_remediation_updates_metrics(self):
        controller, _, recovery = self.make_controller(
            [
                (503, {"status": "unhealthy"}),
                (200, {"status": "healthy"}),
            ],
            (200, {"status": "healthy"}),
        )

        self.assertTrue(controller.run_check())
        recovery.assert_called_once()

        metrics = generate_latest(controller.registry).decode()

        self.assertIn(
            'incidents_detected_total{incident_type="application_unhealthy"} 1.0',
            metrics,
        )
        self.assertIn(
            'remediation_attempts_total{result="success"} 1.0',
            metrics,
        )
        self.assertIn(
            "remediation_duration_seconds_count 1.0",
            metrics,
        )

    def test_failed_recovery_updates_metrics(self):
        controller, _, _ = self.make_controller(
            [(503, {"status": "unhealthy"})],
            (500, {"error": "recovery failed"}),
        )

        self.assertFalse(controller.run_check())

        metrics = generate_latest(controller.registry).decode()

        self.assertIn(
            'remediation_attempts_total{result="failure"} 1.0',
            metrics,
        )
        self.assertIn(
            "remediation_duration_seconds_count 1.0",
            metrics,
        )

    def test_unreachable_service_does_not_count_remediation(self):
        controller, _, recovery = self.make_controller(
            [(None, {"error": "connection refused"})],
            (200, {"status": "healthy"}),
        )

        self.assertFalse(controller.run_check())
        recovery.assert_not_called()

        metrics = generate_latest(controller.registry).decode()

        self.assertIn(
            'incidents_detected_total{incident_type="service_unreachable"} 1.0',
            metrics,
        )
        self.assertNotIn("remediation_attempts_total{", metrics)

    def test_cooldown_skip_does_not_increment_attempts(self):
        controller, _, recovery = self.make_controller(
            [
                (503, {"status": "unhealthy"}),
                (200, {"status": "healthy"}),
                (503, {"status": "unhealthy"}),
            ],
            (200, {"status": "healthy"}),
        )

        self.assertTrue(controller.run_check())
        self.assertFalse(controller.run_check())
        recovery.assert_called_once()

        metrics = generate_latest(controller.registry).decode()

        self.assertIn(
            'remediation_attempts_total{result="success"} 1.0',
            metrics,
        )
        self.assertNotIn(
            'remediation_attempts_total{result="failure"} 1.0',
            metrics,
        )


if __name__ == "__main__":
    unittest.main()
