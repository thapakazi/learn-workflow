"""
AWS Privilege Escalation Workflow

Grants temporary elevated AWS permissions with approval flow.
"""
import os
import json
from datetime import datetime, timedelta
from pydantic import BaseModel
from hatchet_sdk import Context
import boto3

from src.client import hatchet

# --- AWS Client Factory (supports LocalStack) ---

def get_aws_client(service: str):
    """Get AWS client, using LocalStack if AWS_ENDPOINT_URL is set."""
    endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint_url:
        return boto3.client(
            service,
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    return boto3.client(service)


# --- Input/Output Models ---

class PrivilegeRequest(BaseModel):
    user_email: str
    role_arn: str
    duration_hours: int  # Max 8 hours recommended
    justification: str
    approver_email: str


# --- Configuration ---

ALLOWED_ROLES = [
    "arn:aws:iam::*:role/developer-elevated",
    "arn:aws:iam::*:role/readonly-prod",
    "arn:aws:iam::*:role/debug-access",
]

MAX_DURATION_HOURS = 8


# --- Helper Functions ---

def _match_role_pattern(pattern: str, role_arn: str) -> bool:
    """Simple wildcard matching for role ARNs."""
    import fnmatch
    return fnmatch.fnmatch(role_arn, pattern)


# --- Workflow Definition ---

aws_privilege_workflow = hatchet.workflow(
    name="aws-privilege-escalation",
    input_validator=PrivilegeRequest,
    on_events=["aws:privilege:request"],
)


@aws_privilege_workflow.task(name="validate")
def validate_task(input: PrivilegeRequest, ctx: Context) -> dict:
    """Validate the privilege escalation request."""
    request_id = ctx.workflow_run_id

    # Check duration
    if input.duration_hours > MAX_DURATION_HOURS:
        return {
            "valid": False,
            "request_id": request_id,
            "error": f"Duration exceeds maximum of {MAX_DURATION_HOURS} hours",
        }

    if input.duration_hours < 1:
        return {
            "valid": False,
            "request_id": request_id,
            "error": "Duration must be at least 1 hour",
        }

    # Check role is in allowed list (supports wildcards)
    role_allowed = False
    for allowed_role in ALLOWED_ROLES:
        if _match_role_pattern(allowed_role, input.role_arn):
            role_allowed = True
            break

    if not role_allowed:
        return {
            "valid": False,
            "request_id": request_id,
            "error": f"Role {input.role_arn} is not in the allowed list",
        }

    # Check justification is not empty
    if not input.justification or len(input.justification) < 10:
        return {
            "valid": False,
            "request_id": request_id,
            "error": "Justification must be at least 10 characters",
        }

    ctx.log(f"Request {request_id} validated successfully")
    return {"valid": True, "request_id": request_id, "error": None}


@aws_privilege_workflow.task(name="approve", parents=[validate_task])
def approve_task(input: PrivilegeRequest, ctx: Context) -> dict:
    """Send approval request to approver."""
    validation = ctx.task_output(validate_task)

    # Stop if validation failed
    if not validation.get("valid"):
        return {
            "approved": False,
            "approver": None,
            "denied_reason": validation.get("error"),
        }

    ctx.log(f"Sending approval request to {input.approver_email}")
    ctx.log(f"Request ID: {validation.get('request_id')}")
    ctx.log(f"User: {input.user_email}")
    ctx.log(f"Role: {input.role_arn}")
    ctx.log(f"Duration: {input.duration_hours} hours")
    ctx.log(f"Justification: {input.justification}")

    # TODO: In production:
    # 1. Send Slack message with approve/deny buttons
    # 2. Use durable sleep to wait for callback
    # 3. Webhook endpoint updates workflow state

    # For demo, simulate auto-approval
    return {
        "approved": True,
        "approver": input.approver_email,
        "approved_at": datetime.utcnow().isoformat(),
        "denied_reason": None,
    }


@aws_privilege_workflow.task(name="grant", parents=[approve_task])
def grant_task(input: PrivilegeRequest, ctx: Context) -> dict:
    """Grant temporary AWS access using STS AssumeRole."""
    validation = ctx.task_output(validate_task)
    approval = ctx.task_output(approve_task)

    if not approval.get("approved"):
        ctx.log("Request was denied, skipping access grant")
        return {"granted": False, "reason": approval.get("denied_reason")}

    role_arn = input.role_arn
    duration_hours = input.duration_hours
    user_email = input.user_email
    request_id = validation.get("request_id", "unknown")

    # Calculate duration in seconds (STS max is 12 hours)
    duration_seconds = min(duration_hours * 3600, 43200)

    try:
        sts = get_aws_client("sts")

        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"idp-{user_email.replace('@', '-at-').replace('.', '-')[:32]}",
            DurationSeconds=duration_seconds,
        )

        credentials = response["Credentials"]
        expires_at = credentials["Expiration"].isoformat()

        ctx.log(f"Access granted, expires at {expires_at}")

        return {
            "granted": True,
            "access_key_id": credentials["AccessKeyId"],
            "secret_access_key": credentials["SecretAccessKey"],
            "session_token": credentials["SessionToken"],
            "expires_at": expires_at,
            "role_arn": role_arn,
        }

    except Exception as e:
        ctx.log(f"Failed to assume role: {str(e)}")
        return {"granted": False, "error": str(e)}


@aws_privilege_workflow.task(name="notify", parents=[grant_task])
def notify_task(input: PrivilegeRequest, ctx: Context) -> dict:
    """Notify user of the result."""
    access_grant = ctx.task_output(grant_task)
    user_email = input.user_email

    if access_grant.get("granted"):
        ctx.log(f"Notifying {user_email}: Access granted until {access_grant.get('expires_at')}")
        # TODO: Send credentials securely (e.g., encrypted Slack DM, 1Password share)
        return {
            "notified": True,
            "message": f"Access granted until {access_grant.get('expires_at')}",
        }
    else:
        error = access_grant.get("error") or access_grant.get("reason")
        ctx.log(f"Notifying {user_email}: Access denied - {error}")
        return {
            "notified": True,
            "message": f"Access denied: {error}",
        }


@aws_privilege_workflow.task(name="audit", parents=[grant_task])
def audit_task(input: PrivilegeRequest, ctx: Context) -> dict:
    """Log the entire request for audit trail."""
    validation = ctx.task_output(validate_task)
    approval = ctx.task_output(approve_task)
    access_grant = ctx.task_output(grant_task)

    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "request_id": validation.get("request_id"),
        "user": input.user_email,
        "role": input.role_arn,
        "duration_hours": input.duration_hours,
        "justification": input.justification,
        "approved": approval.get("approved"),
        "approver": approval.get("approver"),
        "granted": access_grant.get("granted", False),
    }

    # TODO: Send to audit log system (CloudWatch, Splunk, etc.)
    ctx.log(f"AUDIT: {json.dumps(audit_entry)}")

    return {"logged": True, "audit_entry": audit_entry}
