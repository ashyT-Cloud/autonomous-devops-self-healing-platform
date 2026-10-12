
import os
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify

app = Flask(__name__)

APP_NAME = os.getenv("APP_NAME", "self-healing-demo")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

_state = {
    "healthy": True,
    "last_changed_at": datetime.now(timezone.utc).isoformat(),
}

_state_lock = threading.Lock()


@app.get("/")
def index():
    return jsonify({
        "application": APP_NAME,
        "version": APP_VERSION,
        "message": "Automous DevOps Self Healing Platform",
    })

@app.get ("/health")
def health():
    with _state_lock:
        healthy = _state["healthy"]
        last_changed_at = _state["last_changed_at"]

    payload = {
        "application": APP_NAME,
        "version": APP_VERSION,
        "status": "healthy" if healthy else "unhealthy",
        "last_changed_at": last_changed_at,
    }

    return jsonify(payload), 200 if healthy else 503

@app.post("/simulate-failure")
def simulate_failure():
    with _state_lock:
        _state["healthy"] = False
        _state["last_changed_at"] = datetime.now(timezone.utc).isoformat()

    return jsonify({
        "message": "Simulated application failure",
        "status": "unhealthy",
    }), 202


@app.post("/simulate-recovery")
def simulate_recovery():
    with _state_lock:
        _state["healthy"] = True
        _state["last_changed_at"] = datetime.now(timezone.utc).isoformat()

    return jsonify({
        "message": "Application recovered",
        "status": "healthy",
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

