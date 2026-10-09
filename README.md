# Autonomous DevOps Incident & Self-Healing Platform

A hands-on DevOps/SRE engineering project demonstrating incident
detection, diagnosis, controlled remediation, progressive delivery,
and recovery verification on AWS.

## Project Goals

- Provision isolated infrastructure using Terraform.
- Build and deploy a containerized application.
- Monitor service health, metrics, and logs.
- Detect incidents using actionable alerts.
- Correlate alerts with Kubernetes events and deployment history.
- Implement safe, bounded, auditable remediation workflows.
- Test recovery through controlled chaos scenarios.
- Explore AI-assisted incident analysis with human approval for
  sensitive actions.

## Planned Technology Stack

- AWS and Amazon EKS
- Terraform
- Docker
- Git and GitHub
- Python
- Prometheus and Grafana
- Alertmanager
- Kubernetes tooling and Helm
- GitHub Actions

Tools will be introduced incrementally and validated as the project
evolves.

## Architecture

The planned system will connect application deployment, observability,
incident analysis, remediation, and recovery verification.

1. Deploy an application through CI/CD.
2. Collect metrics, events, and logs.
3. Detect unhealthy behavior.
4. Correlate available evidence to identify probable causes.
5. Execute approved, least-privilege remediation where appropriate.
6. Verify service health and record the incident outcome.

## Repository Structure

- `application/` — application code and tests
- `chaos/` — controlled failure scenarios
- `docs/` — architecture, runbooks, and postmortems
- `incident-engine/` — incident analysis and remediation logic
- `infrastructure/terraform/` — infrastructure as code
- `monitoring/` — monitoring and alert configuration
- `scripts/` — development and operational scripts

## Security Principles

- Never commit credentials, private keys, or secret values.
- Keep Terraform state out of version control.
- Apply least-privilege IAM permissions.
- Restrict and audit remediation actions.
- Require human approval for high-impact operations.
- Use controlled test scenarios rather than disrupting production.

## Cost Strategy

This project prioritizes cost awareness. Local or lightweight tests
will be preferred where practical. Cloud resources will be provisioned
only when required, monitored for cost, and destroyed when disposable
environments are no longer needed.

AWS charges may still apply for resources that remain provisioned,
including storage and managed services.

## Project Status

**Phase 1 — Foundation in progress**

- [x] Dedicated EC2 workstation
- [x] IAM instance role and Session Manager access
- [x] Docker and Terraform installed
- [x] GitHub SSH authentication
- [x] Initial repository structure
- [ ] Initial repository commit
- [ ] Infrastructure design and cost review

## Disclaimer

This is an educational portfolio project. Production use requires
additional security review, operational testing, and environment-specific
reliability controls.
