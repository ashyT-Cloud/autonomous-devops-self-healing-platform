import unittest

from incident_engine_controller import IncidentController


class AlertmanagerWebhookTests(unittest.TestCase):
    def setUp(self):
        self.recovery_calls = []
        self.health_calls = []

        def health_request():
            self.health_calls.append(True)
            if len(self.health_calls) == 1:
                return 503, {"status": "unhealthy"}
            return 200, {"status": "healthy"}

        def recovery_request():
            self.recovery_calls.append(True)
            return 200, {"status": "healthy"}

        self.controller = IncidentController(
            health_request=health_request,
            recovery_request=recovery_request,
            cooldown_seconds=30,
            verify_delay=0,
            sleep_fn=lambda _: None,
        )

    def test_firing_application_alert_triggers_recovery(self):
        result = self.controller.process_alertmanager_payload({
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "incident-1",
                "labels": {
                    "alertname": "ApplicationUnhealthy",
                    "severity": "critical",
                },
            }],
        })

        self.assertEqual(result["processed"], 1)
        self.assertEqual(len(self.recovery_calls), 1)

    def test_duplicate_firing_notification_is_ignored(self):
        payload = {
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "incident-duplicate",
                "labels": {"alertname": "ApplicationUnhealthy"},
            }],
        }

        self.controller.process_alertmanager_payload(payload)
        self.controller.process_alertmanager_payload(payload)

        self.assertEqual(len(self.recovery_calls), 1)

    def test_unrelated_alert_does_not_trigger_recovery(self):
        result = self.controller.process_alertmanager_payload({
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "target-down",
                "labels": {"alertname": "ApplicationMetricsTargetDown"},
            }],
        })

        self.assertEqual(result["processed"], 0)
        self.assertEqual(len(self.recovery_calls), 0)

    def test_resolved_alert_does_not_trigger_recovery(self):
        result = self.controller.process_alertmanager_payload({
            "status": "resolved",
            "alerts": [{
                "status": "resolved",
                "fingerprint": "incident-resolved",
                "labels": {"alertname": "ApplicationUnhealthy"},
            }],
        })

        self.assertEqual(result["processed"], 0)
        self.assertEqual(len(self.recovery_calls), 0)

    def test_invalid_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            self.controller.process_alertmanager_payload({"alerts": "invalid"})

    def test_webhook_remediation_updates_prometheus_metrics(self):
        from prometheus_client import generate_latest

        result = self.controller.process_alertmanager_payload({
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "metrics-incident-1",
                "labels": {
                    "alertname": "ApplicationUnhealthy",
                    "severity": "critical",
                },
            }],
        })

        self.assertEqual(result["processed"], 1)

        metrics = generate_latest(
            self.controller.registry
        ).decode()

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

    def test_duplicate_webhook_does_not_double_count_incident(self):
        from prometheus_client import generate_latest

        payload = {
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "metrics-duplicate-1",
                "labels": {
                    "alertname": "ApplicationUnhealthy",
                },
            }],
        }

        self.controller.process_alertmanager_payload(payload)
        self.controller.process_alertmanager_payload(payload)

        metrics = generate_latest(
            self.controller.registry
        ).decode()

        self.assertIn(
            'incidents_detected_total{incident_type="application_unhealthy"} 1.0',
            metrics,
        )
        self.assertEqual(len(self.recovery_calls), 1)

    def test_webhook_failed_recovery_updates_failure_metric(self):
        from prometheus_client import generate_latest

        self.controller.recovery_request = lambda: (
            500,
            {"error": "simulated recovery failure"},
        )

        result = self.controller.process_alertmanager_payload({
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "metrics-failure-1",
                "labels": {
                    "alertname": "ApplicationUnhealthy",
                },
            }],
        })

        self.assertEqual(result["processed"], 1)

        metrics = generate_latest(
            self.controller.registry
        ).decode()

        self.assertIn(
            'remediation_attempts_total{result="failure"} 1.0',
            metrics,
        )
        self.assertIn(
            "remediation_duration_seconds_count 1.0",
            metrics,
        )

    def test_unrelated_alert_does_not_increment_incident_metrics(self):
        from prometheus_client import generate_latest

        self.controller.process_alertmanager_payload({
            "status": "firing",
            "alerts": [{
                "status": "firing",
                "fingerprint": "metrics-target-down-1",
                "labels": {
                    "alertname": "ApplicationMetricsTargetDown",
                },
            }],
        })

        metrics = generate_latest(
            self.controller.registry
        ).decode()

        self.assertNotIn("incidents_detected_total{", metrics)
        self.assertNotIn("remediation_attempts_total{", metrics)

if __name__ == "__main__":
    unittest.main()
