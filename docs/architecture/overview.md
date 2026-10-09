# Project 8 — Architecture Overview

## Objective

Build an educational DevOps/SRE platform that detects application
incidents, gathers diagnostic evidence, performs controlled remediation,
and verifies recovery.

## High-Level Architecture

```text
Developer
    |
    v
GitHub Repository
    |
    v
GitHub Actions CI/CD
    |
    v
Container Image
    |
    v
Amazon EKS Application
    |
    +--------------------+
    |                    |
    v                    v
Metrics and Logs     Kubernetes Events
    |                    |
    +---------+----------+
              |
              v
       Alerting Pipeline
              |
              v
       Incident Engine
              |
              v
     Diagnosis and Policy
              |
              v
      Approved Remediation
              |
              v
       Recovery Verification
              |
       +------+------+
       |             |
       v             v
    Recovered     Escalation
       |
       v
  Incident Record
Major Components
Workstation
A dedicated Amazon Linux 2023 EC2 instance hosts development tools,
Terraform, Docker, Git, and operational scripts.
Infrastructure
Terraform manages project-specific AWS infrastructure. State must be
stored securely and must never be committed to Git.
Application
A containerized application exposes health endpoints and generates
observable failure signals.
Observability
Prometheus collects metrics. Grafana provides dashboards. Alertmanager
routes actionable alerts. Logging and Kubernetes events provide
additional diagnostic evidence.
Incident Engine
A Python service correlates alerts, application health, Kubernetes
events, and deployment history. It produces a diagnosis with supporting
evidence.
Remediation
Remediation actions are allowlisted, bounded, logged, and least-privilege.
High-impact actions require human approval. AI-generated suggestions
are not executed directly.
Recovery Verification
After remediation, the platform checks application health and relevant
metrics. Failed recovery is escalated instead of repeatedly retrying
without limits.
Security Boundaries
- The workstation uses an EC2 IAM role instead of stored AWS access keys.
- GitHub authentication uses a dedicated SSH key.
- AWS resources use project-specific names and tags.
- Public access is minimized.
- Remediation permissions are separated from diagnostic permissions.
- Secrets, credentials, Terraform state, and private keys are excluded
  from source control.
Initial Deployment Strategy
1. Build and test components on the dedicated workstation.
2. Validate Terraform configuration before provisioning.
3. Create isolated project networking.
4. Deploy Kubernetes infrastructure only when required.
5. Add observability and incident automation incrementally.
6. Destroy disposable resources when testing is complete.
This is a learning platform. Production use requires additional security,
reliability, resilience, and operational reviews.
