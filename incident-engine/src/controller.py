#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8080").rstrip("/")
CHECK_INTERVAL = max(1, int(os.getenv("CHECK_INTERVAL", "10")))
COOLDOWN_SECONDS = max(0, int(os.getenv("COOLDOWN_SECONDS", "30")))
AUTO_REMEDIATE = os.getenv("AUTO_REMEDIATE", "true").lower() == "true"


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

    def run_check(self):
        status, body = self.health_request()

        if status == 200 and body.get("status") == "healthy":
            log_event("health_check", result="healthy", http_status=status)
            return True

        # An unreachable service is not the same as an application
        # returning an unhealthy health-check response.
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
            remaining = self.cooldown_seconds - (now - self.last_remediation_at)
            log_event(
                "remediation_skipped",
                reason="cooldown_active",
                retry_after_seconds=round(remaining, 1),
            )
            return False

        # Start the cooldown before attempting remediation so repeated
        # failures cannot trigger a rapid sequence of recovery requests.
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


def main():
    parser = argparse.ArgumentParser(
        description="Project 8 autonomous DevOps incident controller"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one health check and exit",
    )
    args = parser.parse_args()

    controller = IncidentController()

    log_event(
        "controller_started",
        app_url=APP_URL,
        interval_seconds=CHECK_INTERVAL,
        auto_remediate=AUTO_REMEDIATE,
        cooldown_seconds=COOLDOWN_SECONDS,
    )

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
