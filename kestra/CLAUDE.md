# IDP Kestra Project

## Overview
Internal Developer Platform (IDP) using Kestra for workflow orchestration.

## Project Structure
```
kestra/
├── docker-compose.yml      # Kestra + LocalStack infrastructure
├── flows/
│   └── aws-privilege.yml   # AWS privilege escalation workflow
├── scripts/                # Python scripts (namespace files)
│   ├── validate.py         # Request validation logic
│   ├── grant_access.py     # STS AssumeRole logic
│   ├── audit.py            # Audit logging
│   └── requirements.txt    # Python dependencies
├── infra/                  # OpenTofu IaC for LocalStack + Kestra
│   ├── providers.tf        # AWS + Kestra providers
│   ├── variables.tf
│   ├── iam.tf              # LocalStack IAM roles
│   ├── kestra.tf           # Kestra flows + namespace files
│   └── outputs.tf
└── justfile                # Dev commands
```

## Kestra Concepts
- **Flows**: YAML workflow definitions with `id`, `namespace`, `tasks`
- **Tasks**: Sequential units of work (Python scripts, logs, etc.)
- **Inputs**: Dynamic values accessed via `{{ inputs.name }}`
- **Outputs**: Task results accessed via `{{ outputs.task_id.vars.property }}`
- **Namespace Files**: External scripts stored in Kestra and accessed via `namespaceFiles.enabled: true`

## Current Focus: AWS Privilege Escalation

### Workflow Steps
1. **validate** - Check role is allowed, duration valid
2. **approve** - Log approval (auto-approve for testing)
3. **grant** - Use AWS STS AssumeRole for temp credentials
4. **notify** - Log result to user
5. **audit** - Log for compliance

### Quick Start

```bash
# 1. Start infrastructure (Kestra + LocalStack)
just up

# 2. Provision IAM roles in LocalStack
just infra-init
just infra-apply

# 3. Open Kestra dashboard
open http://localhost:8080

# 4. In Kestra UI:
#    - Go to Flows → Create
#    - Paste contents of flows/aws-privilege.yml
#    - Go to Files (namespace files)
#    - Create scripts/ folder
#    - Upload validate.py, grant_access.py, audit.py
#    - Save flow and Execute with test inputs
```

### Test Inputs
```yaml
user_email: "developer@example.com"
role_arn: "arn:aws:iam::000000000000:role/developer-elevated"
duration_hours: 2
justification: "Need elevated access for debugging production issue"
approver_email: "manager@example.com"
```

## Development Commands

```bash
just up          # Start Kestra + LocalStack
just down        # Stop all services
just logs        # View logs
just setup       # Full setup (start + provision IAM)
just dashboard   # Open Kestra UI
just health      # Check service health
just clean       # Remove everything including volumes
```

## Ports
- Kestra Dashboard: http://localhost:8080
- LocalStack: http://localhost:4567

## Future Workflows (Planned)
- [ ] Log checker (service logs)
- [ ] Metrics fetcher (Datadog/Grafana)
- [ ] Access request with approvals
- [ ] Pipeline runner
- [ ] Business report generator
