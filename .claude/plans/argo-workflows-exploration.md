# Task: Implement AWS Privilege Escalation with Argo Workflows (Kind)

**Status**: 🟡 Planning
**Created**: 2025-12-06
**Last Updated**: 2025-12-06

---

## Overview

### Goal
Implement the AWS privilege escalation workflow using Argo Workflows on a minimal Kind (Kubernetes in Docker) cluster. Reuse the Python module from Kestra implementation.

### Success Criteria
- [ ] Kind cluster running locally
- [ ] Argo Workflows installed and accessible via UI
- [ ] Workflow accepts inputs (user_email, role_arn, duration_hours, justification, approver_email)
- [ ] Workflow validates, grants temporary AWS credentials, notifies, and audits
- [ ] LocalStack integration for STS AssumeRole
- [ ] Can trigger workflow via `argo submit` or UI

### Scope
**In Scope:**
- Kind cluster setup (minimal, single-node)
- Argo Workflows installation (quick-start)
- Workflow YAML definition
- Custom Docker image with Python + boto3
- LocalStack as external service (Docker)
- justfile for dev commands

**Out of Scope:**
- Argo CD (GitOps - different from Argo Workflows)
- Production hardening (RBAC, persistence, HA)
- Argo Events (event triggers)

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Kind Cluster                      │
│  ┌───────────────────────────────────────────────┐  │
│  │              Argo Workflows                    │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐       │  │
│  │  │validate │→ │ grant   │→ │ notify  │       │  │
│  │  │  (pod)  │  │  (pod)  │  │  (pod)  │       │  │
│  │  └─────────┘  └─────────┘  └─────────┘       │  │
│  │                    ↓                          │  │
│  │              ┌─────────┐                      │  │
│  │              │  audit  │                      │  │
│  │              │  (pod)  │                      │  │
│  │              └─────────┘                      │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
          │
          │ (STS AssumeRole)
          ▼
┌─────────────────────┐
│    LocalStack       │
│   (Docker, :4566)   │
└─────────────────────┘
```

---

## Implementation Plan

### Directory Structure
```
argo/
├── docker-compose.yml          # LocalStack only
├── Dockerfile                  # Python image with boto3 + scripts
├── scripts/
│   └── privilege_escalation.py # Copy from kestra/scripts/
├── workflows/
│   └── aws-privilege.yaml      # Argo Workflow definition
├── k8s/
│   └── localstack-endpoint.yaml  # ExternalName service for LocalStack
├── justfile                    # Dev commands
├── CLAUDE.md                   # Documentation
└── .env                        # Environment variables
```

### Files to Create

| File | Purpose |
|------|---------|
| `argo/justfile` | Dev commands (kind, argo, kubectl) |
| `argo/docker-compose.yml` | LocalStack service |
| `argo/Dockerfile` | Python 3.11 + boto3 + scripts |
| `argo/scripts/privilege_escalation.py` | Copy from kestra |
| `argo/workflows/aws-privilege.yaml` | Main workflow |
| `argo/k8s/localstack-endpoint.yaml` | K8s service pointing to host LocalStack |
| `argo/CLAUDE.md` | Project docs |

---

### Step 1: Create justfile with Kind + Argo commands

```just
# Argo Workflows Development Commands

set dotenv-load

CLUSTER_NAME := "argo-dev"
ARGO_VERSION := "v3.5.11"

# Default - show help
default:
    @just --list

# === Cluster Management ===

# Create Kind cluster
cluster-create:
    kind create cluster --name {{CLUSTER_NAME}}
    kubectl cluster-info --context kind-{{CLUSTER_NAME}}

# Delete Kind cluster
cluster-delete:
    kind delete cluster --name {{CLUSTER_NAME}}

# === Argo Workflows ===

# Install Argo Workflows
argo-install:
    kubectl create namespace argo --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -n argo -f https://github.com/argoproj/argo-workflows/releases/download/{{ARGO_VERSION}}/quick-start-minimal.yaml
    @echo "Waiting for Argo server to be ready..."
    kubectl wait --for=condition=available --timeout=120s deployment/argo-server -n argo
    @echo "Argo Workflows installed!"

# Port forward to Argo UI
argo-ui:
    @echo "Argo UI: https://localhost:2746"
    kubectl -n argo port-forward deployment/argo-server 2746:2746

# === LocalStack ===

# Start LocalStack
localstack-up:
    docker-compose up -d
    @echo "LocalStack: http://localhost:4566"

# Stop LocalStack
localstack-down:
    docker-compose down

# Apply LocalStack endpoint to cluster
localstack-endpoint:
    kubectl apply -f k8s/localstack-endpoint.yaml

# === Workflow ===

# Build and load custom image into Kind
image-build:
    docker build -t idp-privilege:latest .
    kind load docker-image idp-privilege:latest --name {{CLUSTER_NAME}}

# Deploy workflow
deploy:
    kubectl apply -f workflows/aws-privilege.yaml -n argo

# Submit workflow with test inputs
trigger:
    argo submit workflows/aws-privilege.yaml -n argo \
      -p user_email="developer@example.com" \
      -p role_arn="arn:aws:iam::000000000000:role/developer-elevated" \
      -p duration_hours="2" \
      -p justification="Debugging production issue INCIDENT-1234" \
      -p approver_email="manager@example.com" \
      --watch

# List workflows
list:
    argo list -n argo

# Get workflow logs
logs name:
    argo logs {{name}} -n argo

# === Full Setup ===

# Complete setup: cluster + argo + localstack + image + workflow
setup: cluster-create argo-install localstack-up localstack-endpoint image-build deploy
    @echo ""
    @echo "Setup complete!"
    @echo "Run 'just argo-ui' in a separate terminal"
    @echo "Then 'just trigger' to run the workflow"

# Teardown everything
teardown: cluster-delete localstack-down
    @echo "Teardown complete"
```

---

### Step 2: Create docker-compose.yml (LocalStack only)

```yaml
services:
  localstack:
    image: localstack/localstack:latest
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sts,iam
      - DEBUG=1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 5s
      timeout: 5s
      retries: 10
```

---

### Step 3: Create Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install boto3
RUN pip install --no-cache-dir boto3

# Copy scripts
COPY scripts/ /app/scripts/

# Set entrypoint
ENTRYPOINT ["python", "/app/scripts/privilege_escalation.py"]
```

---

### Step 4: Create K8s service for LocalStack access

```yaml
# k8s/localstack-endpoint.yaml
# Allows pods to reach LocalStack running on host
apiVersion: v1
kind: Service
metadata:
  name: localstack
  namespace: argo
spec:
  type: ExternalName
  externalName: host.docker.internal  # Docker Desktop / Kind
  ports:
    - port: 4566
```

---

### Step 5: Create Argo Workflow YAML

```yaml
# workflows/aws-privilege.yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
metadata:
  generateName: aws-privilege-escalation-
  labels:
    workflow: privilege-escalation
spec:
  entrypoint: privilege-workflow

  arguments:
    parameters:
      - name: user_email
      - name: role_arn
        value: "arn:aws:iam::000000000000:role/developer-elevated"
      - name: duration_hours
        value: "2"
      - name: justification
      - name: approver_email
        value: "manager@example.com"

  templates:
    # Main DAG
    - name: privilege-workflow
      dag:
        tasks:
          - name: validate
            template: run-command
            arguments:
              parameters:
                - name: command
                  value: validate

          - name: log-approval
            template: log-message
            arguments:
              parameters:
                - name: message
                  value: |
                    Approval request:
                      User: {{workflow.parameters.user_email}}
                      Role: {{workflow.parameters.role_arn}}
                      Duration: {{workflow.parameters.duration_hours}} hours
                      Status: AUTO-APPROVED (testing mode)
            dependencies: [validate]

          - name: grant
            template: run-command
            arguments:
              parameters:
                - name: command
                  value: grant
            dependencies: [log-approval]

          - name: notify
            template: log-message
            arguments:
              parameters:
                - name: message
                  value: |
                    Notification to {{workflow.parameters.user_email}}:
                    Access granted for role {{workflow.parameters.role_arn}}
                    Duration: {{workflow.parameters.duration_hours}} hours
            dependencies: [grant]

          - name: audit
            template: run-command
            arguments:
              parameters:
                - name: command
                  value: audit
            dependencies: [grant]

    # Python command template
    - name: run-command
      inputs:
        parameters:
          - name: command
      container:
        image: idp-privilege:latest
        args: ["{{inputs.parameters.command}}"]
        env:
          - name: USER_EMAIL
            value: "{{workflow.parameters.user_email}}"
          - name: ROLE_ARN
            value: "{{workflow.parameters.role_arn}}"
          - name: DURATION_HOURS
            value: "{{workflow.parameters.duration_hours}}"
          - name: JUSTIFICATION
            value: "{{workflow.parameters.justification}}"
          - name: APPROVER_EMAIL
            value: "{{workflow.parameters.approver_email}}"
          - name: EXECUTION_ID
            value: "{{workflow.name}}"
          - name: GRANTED
            value: "true"
          # LocalStack connection
          - name: AWS_ENDPOINT_URL
            value: "http://localstack.argo.svc.cluster.local:4566"
          - name: AWS_ACCESS_KEY_ID
            value: "test"
          - name: AWS_SECRET_ACCESS_KEY
            value: "test"
          - name: AWS_REGION
            value: "us-east-1"

    # Simple log template
    - name: log-message
      inputs:
        parameters:
          - name: message
      container:
        image: alpine:latest
        command: [echo]
        args: ["{{inputs.parameters.message}}"]
```

---

### Step 6: Copy Python script from Kestra

```bash
cp kestra/scripts/privilege_escalation.py argo/scripts/
```

---

### Step 7: Provision IAM roles in LocalStack

Reuse the OpenTofu config from kestra/infra/ or hatchet/infra/:

```bash
cd kestra/infra && tofu apply  # Creates IAM roles in LocalStack
```

---

## Prerequisites

```bash
# Check prerequisites
kind --version      # Kubernetes in Docker
kubectl version     # Kubernetes CLI
argo version        # Argo Workflows CLI (optional but recommended)
docker --version    # Docker
```

Install if missing:
```bash
# Kind
brew install kind

# kubectl
brew install kubectl

# Argo CLI
brew install argo
```

---

## Quick Start (After Implementation)

```bash
cd argo

# Full setup
just setup

# In separate terminal - access UI
just argo-ui
# Open https://localhost:2746

# Trigger workflow
just trigger

# View logs
just logs aws-privilege-escalation-xxxxx
```

---

## Testing Plan

- [ ] `just cluster-create` - Kind cluster starts
- [ ] `just argo-install` - Argo Workflows pods running
- [ ] `just argo-ui` - UI accessible at https://localhost:2746
- [ ] `just localstack-up` - LocalStack healthy
- [ ] `just image-build` - Image built and loaded into Kind
- [ ] `just deploy` - Workflow template applied
- [ ] `just trigger` - Workflow executes successfully
- [ ] Validate step passes
- [ ] Grant step returns STS credentials
- [ ] Audit step logs correctly

---

## Comparison: Kestra vs Argo Setup

| Aspect | Kestra | Argo (Kind) |
|--------|--------|-------------|
| Infrastructure | Docker Compose (2 containers) | Kind + Docker (LocalStack) |
| Install time | ~30 seconds | ~2 minutes |
| Memory usage | ~1GB | ~2GB (Kind + Argo) |
| Workflow deploy | Terraform provider | kubectl apply |
| Trigger | curl / UI | argo submit / UI |
| YAML lines | ~113 | ~130 |

---

## Implementation Checklist

- [ ] **Step 1**: Create `argo/justfile`
- [ ] **Step 2**: Create `argo/docker-compose.yml`
- [ ] **Step 3**: Create `argo/Dockerfile`
- [ ] **Step 4**: Create `argo/k8s/localstack-endpoint.yaml`
- [ ] **Step 5**: Create `argo/workflows/aws-privilege.yaml`
- [ ] **Step 6**: Copy `privilege_escalation.py` from kestra
- [ ] **Step 7**: Create `argo/CLAUDE.md`
- [ ] **Step 8**: Test end-to-end with `just setup && just trigger`

---

## Completion Checklist

Before marking as 🟢 Completed:
- [ ] All implementation steps completed
- [ ] Workflow executes successfully
- [ ] Documentation updated (CLAUDE.md)
- [ ] Screenshots added (optional)
- [ ] No outstanding blockers
