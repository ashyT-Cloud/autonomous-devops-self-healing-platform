#!/usr/bin/env python3

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

APP_URL = os.getenv("APP_URL", "http://127.0.0.1:8080").rstrip("/")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))
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
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError, ValueError) as exc:
        return None, {"error": str(exc)}


def run_check():
    status, body = request_health()

    if status == 200 and body.get("status") == "healthy":
        log_event("health_check", result="healthy", http_status=status)
        return True

    log_event(
        "incident_detected",
        result="unhealthy",
        http_status=status,
        details=body,
    )

    if not AUTO_REMEDIATE:
        log_event("remediation_skipped", reason="AUTO_REMEDIATE is disabled")
        return False

    recovery_status, recovery_body = trigger_recovery()
    log_event(
        "remediation_attempt",
        http_status=recovery_status,
        details=recovery_body,
    )

    # Give the application a moment to update its state.
    time.sleep(1)
    verify_status, verify_body = request_health()

    recovered = (
        verify_status == 200 and verify_body.get("status") == "healthy"
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

    log_event(
        "controller_started",
        app_url=APP_URL,
        interval_seconds=CHECK_INTERVAL,
        auto_remediate=AUTO_REMEDIATE,
    )

    if args.once:
        raise SystemExit(0 if run_check() else 1)

    try:
        while True:
            run_check()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        log_event("controller_stopped", reason="keyboard_interrupt")


if __name__ == "__main__":
    main()
