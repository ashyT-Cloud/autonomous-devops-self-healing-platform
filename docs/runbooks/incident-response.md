# Incident Response Runbook

## 1. Overview

This runbook describes how Project 8 detects application incidents, attempts automated remediation, and verifies recovery.

## 2. Incident Detection

The incident controller checks the application's `/health` endpoint.

| Condition | Controller behavior |
|---|---|
| HTTP 200 and healthy status | Records a successful health check |
| HTTP 503 or unhealthy response | Records an application incident |
| Service unreachable | Records an availability issue without attempting endpoint-based recovery |

## 3. Run a Health Check

Run one health check:

```bash
python3 incident-engine/src/controller.py --once
```

Run continuous monitoring:

```bash
python3 incident-engine/src/controller.py
```

Press `Ctrl+C` to stop continuous monitoring.

## 4. Simulate an Incident

Inject an application failure:

```bash
curl -sS -X POST http://127.0.0.1:8080/simulate-failure
```

Run the incident controller:

```bash
python3 incident-engine/src/controller.py --once
```

The controller should detect the unhealthy response, attempt recovery, and verify the result.

## 5. Verify Recovery

Check the application health:

```bash
curl -i http://127.0.0.1:8080/health
```

Expected result: HTTP 200 with `"status": "healthy"`.

## 6. Detection-Only Mode

Disable automated remediation for a single check:

```bash
AUTO_REMEDIATE=false python3 incident-engine/src/controller.py --once
```

The controller should report the incident and skip remediation.

Restore the demo application manually:

```bash
curl -sS -X POST http://127.0.0.1:8080/simulate-recovery
```

## 7. Configuration

| Variable | Default | Description |
|---|---|---|
| `APP_URL` | `http://127.0.0.1:8080` | Application base URL |
| `CHECK_INTERVAL` | `10` | Seconds between checks |
| `AUTO_REMEDIATE` | `true` | Enables or disables remediation |
| `COOLDOWN_SECONDS` | `30` | Minimum interval between remediation attempts |

## 8. Current Limitations

- Recovery uses a simulated application endpoint.
- The controller does not restart failed containers or repair AWS infrastructure.
- Cooldown state is held in memory and resets when the controller restarts.
- Production use requires durable incident records, authentication, alerting, and carefully authorized remediation actions.
