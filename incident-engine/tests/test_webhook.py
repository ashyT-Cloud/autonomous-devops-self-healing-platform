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


if __name__ == "__main__":
    unittest.main()
