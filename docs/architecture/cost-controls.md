# Project 8 — Cost Controls

## Principles

- Prefer local container tests on the dedicated workstation.
- Avoid always-on managed Kubernetes resources.
- Provision infrastructure only when a phase requires it.
- Destroy disposable environments after testing.
- Keep persistent resources only when explicitly required.
- Review AWS billing and resource inventory regularly.

## Workstation

- Instance: t3.medium
- Operating system: Amazon Linux 2023
- Storage: 20 GiB encrypted gp3
- Access: Systems Manager Session Manager

Stop the workstation when it is not needed. Stopping it does not remove
EBS storage charges or necessarily all other associated charges.

## Kubernetes

Amazon EKS has a cluster-management charge while the cluster exists.
Worker compute, storage, networking, logging, and load balancers can
generate additional charges.

Create the cluster only for Kubernetes-specific implementation and
testing. Delete disposable cluster resources when finished.

## Networking

Avoid NAT Gateways unless a demonstrated requirement justifies their
cost. Evaluate alternatives carefully before creating VPC endpoints,
load balancers, or other billable networking resources.

Any cost-saving network design must still enforce appropriate access
controls and must not expose administrative services publicly.

## Monitoring

Begin with the minimum required metrics and alerts. Expand retention,
logging, and dashboards only when useful.

## Budget and Cleanup

- Configure a billing budget and notifications where available.
- Budget alerts are not hard spending caps.
- Inspect resources before and after every infrastructure phase.
- Review Terraform plans before applying changes.
- Never destroy resources blindly; confirm ownership and dependencies.
- Verify that disposable resources are actually deleted.

## Cost Review Checklist

- [ ] Region and instance type confirmed
- [ ] Estimated charges reviewed
- [ ] Unnecessary NAT Gateways avoided
- [ ] Load balancers created only when required
- [ ] Logging retention bounded
- [ ] Cleanup procedure documented
- [ ] Post-test resource inventory checked
