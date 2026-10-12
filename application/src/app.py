import os
import threading
from datetime import datetime, timezone

from flask import Flask, Response, jsonify
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    generate_latest,
)

app = Flask(__name__)

APP_NAME = os.getenv("APP_NAME", "self-healing-demo")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

_state = {
    "healthy": True,
    "last_changed_at": datetime.now(timezone.utc).isoformat(),
}
_state_lock = threading.Lock()

HEALTH_CHECKS = Counter(
    "application_health_checks_total",
    "Total application health checks",
    ["result"],
)

SIMULATED_FAILURES = Counter(
    "application_simulated_failures_total",
    "Total simulated application failures",
)

SIMULATED_RECOVERIES = Counter(
    "application_simulated_recoveries_total",
    "Total simulated application recoveries",
)

APPLICATION_HEALTH = Gauge(
    "application_health_status",
    "Application health status: 1 means healthy, 0 means unhealthy",
)
APPLICATION_HEALTH.set(1)


@app.get("/")
def index():
    return jsonify({
        "application": APP_NAME,
        "version": APP_VERSION,
        "message": "Autonomous DevOps Self-Healing Platform",
    })


@app.get("/health")
def health():
    with _state_lock:
        healthy = _state["healthy"]
        last_changed_at = _state["last_changed_at"]

    result = "healthy" if healthy else "unhealthy"
    HEALTH_CHECKS.labels(result=result).inc()

    payload = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": result,
        "last_changed_at": last_changed_at,
    }

    return jsonify(payload), 200 if healthy else 503


@app.get("/metrics")
def metrics():
    return Response(
        generate_latest(),
        mimetype=CONTENT_TYPE_LATEST,
    )


@app.post("/simulate-failure")
def simulate_failure():
    with _state_lock:
        _state["healthy"] = False
        _state["last_changed_at"] = datetime.now(timezone.utc).isoformat()

    APPLICATION_HEALTH.set(0)
    SIMULATED_FAILURES.inc()

    return jsonify({
        "message": "Simulated application failure",
        "status": "unhealthy",
    }), 202


@app.post("/simulate-recovery")
def simulate_recovery():
    with _state_lock:
        _state["healthy"] = True
        _state["last_changed_at"] = datetime.now(timezone.utc).isoformat()

    APPLICATION_HEALTH.set(1)
    SIMULATED_RECOVERIES.inc()

    return jsonify({
        "message": "Application recovered",
        "status": "healthy",
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
