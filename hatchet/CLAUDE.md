# IDP Hatchet Project

## Overview
Internal Developer Platform (IDP) using Hatchet for workflow orchestration.

## Project Structure
```
hatchet/
├── docker-compose.yml      # Hatchet + LocalStack infrastructure
├── infra/                  # OpenTofu IaC for AWS/LocalStack resources
│   ├── providers.tf
│   ├── variables.tf
│   ├── iam.tf              # IAM roles for privilege escalation
│   ├── outputs.tf
│   └── terraform.tfvars
├── src/
│   ├── client.py           # Shared Hatchet client singleton
│   ├── workflows/
│   │   └── aws_privilege.py
│   └── workers/
│       └── main.py
├── scripts/
│   └── test_workflow.py    # Test script
└── requirements.txt
```

## Conventions
- Python 3.11+
- Use pydantic for input/output validation
- Tasks are atomic units of work
- Workflows compose tasks into DAGs
- Environment variables for secrets (never hardcode)
- OpenTofu for infrastructure (supports LocalStack + real AWS)

## Current Focus: AWS Privilege Escalation

### Workflow Steps
1. **validate** - Check role is allowed, duration valid
2. **approve** - Notify approver (auto-approve for testing)
3. **grant** - Use AWS STS AssumeRole for temp credentials
4. **notify** - Notify user of result
5. **audit** - Log for compliance (runs parallel with notify)

### Environment Variables
```bash
# Hatchet
export HATCHET_CLIENT_TOKEN="<from http://localhost:8081>"

# LocalStack (for local dev)
export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_REGION="us-east-1"
```

## Quick Start

```bash
# 1. Start infrastructure (Hatchet + LocalStack)
docker-compose up -d

# 2. Wait for services to be healthy
docker-compose ps

# 3. Get Hatchet token from dashboard
open http://localhost:8081
# Go to Settings > API Tokens > Create Token

# 4. Provision IAM roles in LocalStack
cd infra
tofu init
tofu apply

# 5. Install Python deps
pip install -r requirements.txt

# 6. Set environment variables
export HATCHET_CLIENT_TOKEN="<your-token>"
export AWS_ENDPOINT_URL="http://localhost:4566"

# 7. Start worker (in separate terminal)
python -m src.workers.main

# 8. Run tests
python scripts/test_workflow.py
```

## Future Workflows (Planned)
- [ ] Log checker (service logs)
- [ ] Metrics fetcher (Datadog/Grafana)
- [ ] Access request with approvals
- [ ] Pipeline runner
- [ ] Business report generator
