#!/usr/bin/env bash

set -Eeuo pipefail

APP_URL="${APP_URL:-http://localhost:8080}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
RECOVERY_TIMEOUT="${RECOVERY_TIMEOUT:-90}"

log() {
    printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

fail() {
    log "FAIL: $*"
    exit 1
}

get_health() {
    curl -fsS --max-time 5 "$APP_URL/health"
}

get_metric() {
    local query="$1"
    local response

    response=$(curl -fsSG --max-time 5 \
        "$PROMETHEUS_URL/api/v1/query" \
        --data-urlencode "query=$query") || return 1

    python3 -c '
import json
import sys

data = json.load(sys.stdin)
if data.get("status") != "success":
    raise SystemExit(1)

results = data["data"]["result"]
print(sum(float(item["value"][1]) for item in results))
' <<< "$response"
}

log "Checking application health..."
health=$(get_health) || fail "Application health endpoint is unreachable."

python3 -c '
import json, sys
data = json.load(sys.stdin)
if data.get("status") != "healthy":
    raise SystemExit(1)
' <<< "$health" || fail "Application must be healthy before testing."

log "Reading initial Prometheus counters..."

incidents_before=$(get_metric 'sum(incidents_detected_total{incident_type="application_unhealthy"})') \
    || fail "Could not query incident counter."

remediations_before=$(get_metric 'sum(remediation_attempts_total{result="success"})') \
    || fail "Could not query successful-remediation counter."

log "Incidents before test: $incidents_before"
log "Successful remediations before test: $remediations_before"

log "Triggering simulated application failure..."

failure_response=$(curl -fsS --max-time 10 \
    -X POST "$APP_URL/simulate-failure") \
    || fail "Could not trigger simulated failure."

printf '%s\n' "$failure_response"

log "Waiting for automatic recovery (timeout: ${RECOVERY_TIMEOUT}s)..."

deadline=$((SECONDS + RECOVERY_TIMEOUT))

while (( SECONDS < deadline )); do
    health=$(get_health 2>/dev/null || true)

    if [[ -n "$health" ]] && python3 -c '
import json, sys
try:
    healthy = json.load(sys.stdin).get("status") == "healthy"
except (ValueError, AttributeError):
    healthy = False
raise SystemExit(0 if healthy else 1)
' <<< "$health"; then
        log "Application reports healthy."
        break
    fi

    sleep 2
done

[[ -n "${health:-}" ]] || fail "Application did not recover before timeout."

python3 -c '
import json, sys
if json.load(sys.stdin).get("status") != "healthy":
    raise SystemExit(1)
' <<< "$health" || fail "Application did not recover before timeout."

log "Waiting for Prometheus to scrape updated counters..."

deadline=$((SECONDS + 30))
incidents_after="$incidents_before"
remediations_after="$remediations_before"

while (( SECONDS < deadline )); do
    incidents_after=$(get_metric 'sum(incidents_detected_total{incident_type="application_unhealthy"})') \
        || incidents_after="$incidents_before"

    remediations_after=$(get_metric 'sum(remediation_attempts_total{result="success"})') \
        || remediations_after="$remediations_before"

    if python3 - "$incidents_before" "$incidents_after" \
        "$remediations_before" "$remediations_after" <<'PY'
import sys
ib, ia, rb, ra = map(float, sys.argv[1:])
raise SystemExit(0 if ia > ib and ra > rb else 1)
PY
    then
        break
    fi

    sleep 2
done

log "Incidents after test: $incidents_after"
log "Successful remediations after test: $remediations_after"

python3 - "$incidents_before" "$incidents_after" \
    "$remediations_before" "$remediations_after" <<'PY'
import sys
ib, ia, rb, ra = map(float, sys.argv[1:])

if ia <= ib:
    print("FAIL: Incident counter did not increase.")
    raise SystemExit(1)

if ra <= rb:
    print("FAIL: Successful-remediation counter did not increase.")
    raise SystemExit(1)
PY

log "PASS: Application recovered and Prometheus confirmed a new incident and successful remediation."
