# IDP Argo Workflows Project

## Overview
Internal Developer Platform (IDP) using Argo Workflows for Kubernetes-native workflow orchestration.

## Project Structure
```
argo/
├── Dockerfile                  # Python image with boto3 + scripts
├── scripts/
│   └── privilege_escalation.py # Python module (validate, grant, audit)
├── workflows/
│   └── aws-privilege.yaml      # Argo Workflow definition
├── k8s/
│   └── localstack.yaml         # LocalStack deployment in K8s
├── infra/
│   ├── providers.tf            # AWS provider for LocalStack
│   ├── variables.tf
│   ├── iam.tf                  # IAM roles
│   └── outputs.tf
├── justfile                    # Dev commands
└── CLAUDE.md                   # This file
```

## Prerequisites

```bash
# Required tools
kind --version      # Kubernetes in Docker
kubectl version     # Kubernetes CLI
argo version        # Argo Workflows CLI
docker --version    # Docker
tofu --version      # OpenTofu

# Install if missing (macOS)
brew install kind kubectl argo opentofu
```

## Quick Start

```bash
# Full setup (creates cluster, installs Argo, deploys LocalStack, builds image)
just setup

# In terminal 1: port forward to LocalStack
just localstack-port-forward

# In terminal 2: provision IAM roles
just iam-provision

# In terminal 1 (ctrl+c first): port forward to Argo UI
just argo-ui
# Open https://localhost:2746 (accept self-signed cert)

# In terminal 2: trigger the workflow
just trigger
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kind Cluster                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    argo namespace                        │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │    │
│  │  │validate │→ │  grant  │→ │ notify  │  │  audit  │    │    │
│  │  │  (pod)  │  │  (pod)  │  │  (pod)  │  │  (pod)  │    │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              │ STS AssumeRole                    │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 localstack namespace                     │    │
│  │  ┌──────────────────────────────────────────────────┐   │    │
│  │  │              LocalStack (STS, IAM)                │   │    │
│  │  │         localstack.localstack.svc:4566            │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Workflow Steps

1. **validate** - Check role is allowed, duration valid (1-8 hours)
2. **log-approval** - Log approval (auto-approve for testing)
3. **grant** - AWS STS AssumeRole for temporary credentials
4. **notify** - Log result to user (parallel with audit)
5. **audit** - Log for compliance (parallel with notify)

## Commands Reference

```bash
# Cluster management
just cluster-create    # Create Kind cluster
just cluster-delete    # Delete Kind cluster

# Argo Workflows
just argo-install      # Install Argo Workflows
just argo-ui           # Port forward to UI (https://localhost:2746)
just argo-logs         # View Argo server logs

# LocalStack (in-cluster)
just localstack-deploy       # Deploy LocalStack to cluster
just localstack-port-forward # Port forward for tofu (http://localhost:4566)
just localstack-logs         # View LocalStack logs

# Infrastructure
just infra-init        # Initialize OpenTofu
just iam-provision     # Create IAM roles (needs port-forward)

# Workflow
just image-build       # Build and load Docker image into Kind
just trigger           # Submit workflow with test inputs
just list              # List all workflows
just logs <name>       # View workflow logs
just watch <name>      # Watch workflow progress

# Full lifecycle
just setup             # Complete setup
just teardown          # Tear down everything
just status            # Check status of all components
```

## Ports

- Argo UI: https://localhost:2746 (port-forward)
- LocalStack: http://localhost:4566 (port-forward, for tofu only)
- In-cluster: http://localstack.localstack.svc.cluster.local:4566

## Troubleshooting

### Pods can't reach LocalStack
```bash
# Check LocalStack pod
kubectl get pods -n localstack
kubectl logs -n localstack deployment/localstack

# Test connectivity from a debug pod
just debug-shell
# Inside pod: curl http://localstack.localstack.svc.cluster.local:4566/_localstack/health
```

### Image not found
```bash
# Rebuild and reload image
just image-build
```

### IAM provision fails
```bash
# Make sure port-forward is running
just localstack-port-forward  # in terminal 1
just iam-provision            # in terminal 2
```

### Workflow stuck pending
```bash
# Check pod status
kubectl get pods -n argo
kubectl describe pod <pod-name> -n argo
```
