#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8080").rstrip("/")
CHECK_INTERVAL = max(1, int(os.getenv("CHECK_INTERVAL", "10")))
COOLDOWN_SECONDS = max(0, int(os.getenv("COOLDOWN_SECONDS", "30")))
AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "true").lower() == "true"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "127.0.0.1")
WEBHOOK_PORT = max(1, int(os.getenv("WEBHOOK_PORT", "8081")))
MAX_WEBHOOK_BYTES = 1_048_576


def log_event(event, **details):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **details,
    }
    print(json.dumps(record), flush=True)


def request_health():
    request = urllib.request.Request(
        f"{APP_URL}/health",
        headers={"User-Agent": "project8-incident-controller"},
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            body = {"error": str(exc)}
        return exc.code, body
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, {"error": str(exc)}
    except (ValueError, UnicodeDecodeError) as exc:
        return None, {"error": f"Invalid health response: {exc}"}


def trigger_recovery():
    request = urllib.request.Request(
        f"{APP_URL}/simulate-recovery",
        data=b"",
        headers={"User-Agent": "project8-incident-controller"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (ValueError, OSError):
            body = {"error": str(exc)}
        return exc.code, body
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return None, {"error": str(exc)}


class IncidentController:
    def __init__(
        self,
        health_request=request_health,
        recovery_request=trigger_recovery,
        auto_remediate=AUTO_REMEDIATE,
        cooldown_seconds=COOLDOWN_SECONDS,
        verify_delay=1,
        sleep_fn=time.sleep,
    ):
        self.health_request = health_request
        self.recovery_request = recovery_request
        self.auto_remediate = auto_remediate
        self.cooldown_seconds = cooldown_seconds
        self.verify_delay = verify_delay
        self.sleep_fn = sleep_fn
        self.last_remediation_at = None
        self.active_alerts = set()

    def run_check(self):
        status, body = self.health_request()

        if status == 200 and body.get("status") == "healthy":
            log_event("health_check", result="healthy", http_status=status)
            return True

        if status is None:
            log_event(
                "service_unreachable",
                result="unknown",
                details=body,
                remediation="not_attempted",
            )
            return False

        log_event(
            "incident_detected",
            result="unhealthy",
            incident_type="application_unhealthy",
            http_status=status,
            details=body,
        )

        if not self.auto_remediate:
            log_event(
                "remediation_skipped",
                reason="AUTO_REMEDIATE is disabled",
            )
            return False

        now = time.monotonic()
        if (
            self.last_remediation_at is not None
            and now - self.last_remediation_at < self.cooldown_seconds
        ):
            remaining = self.cooldown_seconds - (
                now - self.last_remediation_at
            )
            log_event(
                "remediation_skipped",
                reason="cooldown_active",
                retry_after_seconds=round(remaining, 1),
            )
            return False

        self.last_remediation_at = now

        recovery_status, recovery_body = self.recovery_request()
        log_event(
            "remediation_attempt",
            http_status=recovery_status,
            details=recovery_body,
        )

        if recovery_status is None or not 200 <= recovery_status < 300:
            log_event(
                "remediation_result",
                result="recovery_failed",
                http_status=recovery_status,
                details=recovery_body,
            )
            return False

        self.sleep_fn(self.verify_delay)
        verify_status, verify_body = self.health_request()

        recovered = (
            verify_status == 200
            and verify_body.get("status") == "healthy"
        )

        log_event(
            "remediation_result",
            result="recovered" if recovered else "recovery_failed",
            http_status=verify_status,
            details=verify_body,
        )

        return recovered

    def process_alertmanager_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")

        alerts = payload.get("alerts")
        if not isinstance(alerts, list):
            raise ValueError("Payload must contain an alerts array")

        processed = 0

        for alert in alerts:
            if not isinstance(alert, dict):
                log_event("alert_ignored", reason="invalid_alert_entry")
                continue

            labels = alert.get("labels", {})
            if not isinstance(labels, dict):
                log_event("alert_ignored", reason="invalid_labels")
                continue

            alert_name = labels.get("alertname")
            status = alert.get("status", payload.get("status", ""))

            if status == "resolved":
                fingerprint = alert.get("fingerprint")
                if fingerprint:
                    self.active_alerts.discard(fingerprint)

                log_event(
                    "alert_resolved",
                    alertname=alert_name,
                    fingerprint=fingerprint,
                )
                continue

            if status != "firing":
                log_event(
                    "alert_ignored",
                    alertname=alert_name,
                    reason="unsupported_alert_status",
                )
                continue

            # Only this alert is authorized to request application recovery.
            # A metrics-target outage does not prove the application itself
            # can be reached or recovered.
            if alert_name != "ApplicationUnhealthy":
                log_event(
                    "alert_ignored",
                    alertname=alert_name,
                    reason="alert_not_remediation_eligible",
                )
                continue

            fingerprint = alert.get("fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint:
                fingerprint = json.dumps(
                    labels, sort_keys=True, separators=(",", ":")
                )

            if fingerprint in self.active_alerts:
                log_event(
                    "alert_ignored",
                    alertname=alert_name,
                    reason="duplicate_active_alert",
                    fingerprint=fingerprint,
                )
                continue

            self.active_alerts.add(fingerprint)

            log_event(
                "alert_received",
                alertname=alert_name,
                severity=labels.get("severity", "unspecified"),
                fingerprint=fingerprint,
            )

            self.run_check()
            processed += 1

        return {"accepted": True, "processed": processed}


def make_webhook_handler(controller):
    class AlertmanagerWebhookHandler(BaseHTTPRequestHandler):
        def send_json(self, status_code, payload):
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/healthz":
                self.send_json(200, {"status": "healthy"})
            else:
                self.send_json(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/alerts":
                self.send_json(404, {"error": "not found"})
                return

            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("application/json"):
                self.send_json(415, {"error": "application/json required"})
                return

            raw_length = self.headers.get("Content-Length", "")
            try:
                length = int(raw_length)
            except (TypeError, ValueError):
                self.send_json(411, {"error": "valid Content-Length required"})
                return

            if length < 1 or length > MAX_WEBHOOK_BYTES:
                self.send_json(413, {"error": "invalid payload size"})
                return

            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = controller.process_alertmanager_payload(payload)
            except (ValueError, UnicodeDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
                return
            except Exception:
                log_event("webhook_error", error="internal processing error")
                self.send_json(500, {"error": "internal processing error"})
                return

            self.send_json(200, result)

        def log_message(self, format_string, *args):
            log_event(
                "webhook_http",
                message=format_string % args,
                client=self.client_address[0],
            )

    return AlertmanagerWebhookHandler


def main():
    parser = argparse.ArgumentParser(
        description="Project 8 autonomous DevOps incident controller"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one health check and exit",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Receive Alertmanager webhooks instead of polling",
    )
    args = parser.parse_args()

    controller = IncidentController()

    log_event(
        "controller_started",
        app_url=APP_URL,
        interval_seconds=CHECK_INTERVAL,
        auto_remediate=AUTO_REMEDIATE,
        cooldown_seconds=COOLDOWN_SECONDS,
        mode="webhook" if args.webhook else "polling",
    )

    if args.webhook:
        server = ThreadingHTTPServer(
            (WEBHOOK_HOST, WEBHOOK_PORT),
            make_webhook_handler(controller),
        )
        log_event(
            "webhook_server_started",
            host=WEBHOOK_HOST,
            port=WEBHOOK_PORT,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log_event("controller_stopped", reason="keyboard_interrupt")
        finally:
            server.server_close()
        return

    if args.once:
        raise SystemExit(0 if controller.run_check() else 1)

    try:
        while True:
            controller.run_check()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        log_event("controller_stopped", reason="keyboard_interrupt")


if __name__ == "__main__":
    main()
