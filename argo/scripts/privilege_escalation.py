"""
AWS Privilege Escalation Module

Handles validation, granting, and auditing of temporary AWS privilege escalation requests.
Designed to be called from Kestra workflows with environment variables as inputs.

Usage:
    python privilege_escalation.py <command>

Commands:
    validate    - Validate the escalation request
    grant       - Grant temporary AWS credentials via STS AssumeRole
    audit       - Create audit log entry
"""
from __future__ import annotations

import fnmatch
import json
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class Config:
    """Immutable configuration for privilege escalation."""

    allowed_role_patterns: tuple[str, ...] = (
        "arn:aws:iam::*:role/developer-elevated",
        "arn:aws:iam::*:role/readonly-prod",
        "arn:aws:iam::*:role/debug-access",
    )
    max_duration_hours: int = 8
    min_duration_hours: int = 1
    min_justification_length: int = 10
    max_session_name_length: int = 64


DEFAULT_CONFIG = Config()


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class PrivilegeRequest:
    """Represents a privilege escalation request."""

    user_email: str
    role_arn: str
    duration_hours: int
    justification: str
    approver_email: str
    execution_id: str = ""

    @classmethod
    def from_env(cls) -> PrivilegeRequest:
        """Create request from environment variables."""
        return cls(
            user_email=os.environ.get("USER_EMAIL", ""),
            role_arn=os.environ.get("ROLE_ARN", ""),
            duration_hours=int(os.environ.get("DURATION_HOURS", "0")),
            justification=os.environ.get("JUSTIFICATION", ""),
            approver_email=os.environ.get("APPROVER_EMAIL", ""),
            execution_id=os.environ.get("EXECUTION_ID", ""),
        )


@dataclass
class ValidationResult:
    """Result of request validation."""

    valid: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {"valid": self.valid, "error": self.error}


@dataclass
class GrantResult:
    """Result of granting access."""

    granted: bool
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    session_token: Optional[str] = None
    expires_at: Optional[str] = None
    role_arn: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        result = {"granted": self.granted}
        if self.granted:
            result.update({
                "access_key_id": self.access_key_id,
                "secret_access_key": self.secret_access_key,
                "session_token": self.session_token,
                "expires_at": self.expires_at,
                "role_arn": self.role_arn,
            })
        else:
            result["error"] = self.error
        return result


@dataclass
class AuditEntry:
    """Audit log entry for compliance."""

    timestamp: str
    execution_id: str
    user: str
    role: str
    duration_hours: int
    justification: str
    approver: str
    granted: bool

    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# Services
# =============================================================================

class Command(ABC):
    """Base class for commands."""

    @abstractmethod
    def execute(self, request: PrivilegeRequest) -> dict:
        """Execute the command and return result as dict."""
        pass


class Validator(Command):
    """Validates privilege escalation requests."""

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config

    def execute(self, request: PrivilegeRequest) -> dict:
        result = self.validate(request)
        return result.to_dict()

    def validate(self, request: PrivilegeRequest) -> ValidationResult:
        """Validate the request against all rules."""

        # Check duration bounds
        if request.duration_hours > self.config.max_duration_hours:
            return ValidationResult(
                valid=False,
                error=f"Duration exceeds maximum of {self.config.max_duration_hours} hours"
            )

        if request.duration_hours < self.config.min_duration_hours:
            return ValidationResult(
                valid=False,
                error=f"Duration must be at least {self.config.min_duration_hours} hour"
            )

        # Check role against allowed patterns
        if not self._is_role_allowed(request.role_arn):
            return ValidationResult(
                valid=False,
                error=f"Role {request.role_arn} is not in the allowed list"
            )

        # Check justification
        if not request.justification or len(request.justification) < self.config.min_justification_length:
            return ValidationResult(
                valid=False,
                error=f"Justification must be at least {self.config.min_justification_length} characters"
            )

        return ValidationResult(valid=True)

    def _is_role_allowed(self, role_arn: str) -> bool:
        """Check if role ARN matches any allowed pattern."""
        return any(
            fnmatch.fnmatch(role_arn, pattern)
            for pattern in self.config.allowed_role_patterns
        )


class AccessGranter(Command):
    """Grants temporary AWS access via STS AssumeRole."""

    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self._sts_client = None

    @property
    def sts_client(self):
        """Lazy-load STS client with LocalStack support."""
        if self._sts_client is None:
            self._sts_client = self._create_sts_client()
        return self._sts_client

    def _create_sts_client(self):
        """Create STS client, using LocalStack if configured."""
        endpoint_url = os.environ.get("AWS_ENDPOINT_URL")

        if endpoint_url:
            return boto3.client(
                "sts",
                endpoint_url=endpoint_url,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
            )
        return boto3.client("sts")

    def execute(self, request: PrivilegeRequest) -> dict:
        result = self.grant(request)
        return result.to_dict()

    def grant(self, request: PrivilegeRequest) -> GrantResult:
        """Assume role and return temporary credentials."""

        duration_seconds = min(
            request.duration_hours * 3600,
            43200  # STS max is 12 hours
        )

        session_name = self._create_session_name(request.user_email)

        try:
            response = self.sts_client.assume_role(
                RoleArn=request.role_arn,
                RoleSessionName=session_name,
                DurationSeconds=duration_seconds,
            )

            credentials = response["Credentials"]

            return GrantResult(
                granted=True,
                access_key_id=credentials["AccessKeyId"],
                secret_access_key=credentials["SecretAccessKey"],
                session_token=credentials["SessionToken"],
                expires_at=credentials["Expiration"].isoformat(),
                role_arn=request.role_arn,
            )

        except ClientError as e:
            return GrantResult(granted=False, error=str(e))
        except Exception as e:
            return GrantResult(granted=False, error=f"Unexpected error: {e}")

    def _create_session_name(self, email: str) -> str:
        """Create valid session name from email."""
        # Session name: alphanumeric + =,.@-
        sanitized = email.replace("@", "-at-").replace(".", "-")
        return f"idp-{sanitized}"[:self.config.max_session_name_length]


class Auditor(Command):
    """Creates audit log entries for compliance."""

    def execute(self, request: PrivilegeRequest) -> dict:
        granted = os.environ.get("GRANTED", "true").lower() == "true"
        entry = self.create_entry(request, granted=granted)
        return entry.to_dict()

    def create_entry(self, request: PrivilegeRequest, granted: bool = True) -> AuditEntry:
        """Create structured audit log entry."""
        return AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            execution_id=request.execution_id,
            user=request.user_email,
            role=request.role_arn,
            duration_hours=request.duration_hours,
            justification=request.justification,
            approver=request.approver_email,
            granted=granted,
        )


# =============================================================================
# CLI
# =============================================================================

COMMANDS = {
    "validate": Validator,
    "grant": AccessGranter,
    "audit": Auditor,
}


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <command>", file=sys.stderr)
        print(f"Commands: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    command_name = sys.argv[1]

    if command_name not in COMMANDS:
        print(f"Unknown command: {command_name}", file=sys.stderr)
        print(f"Available: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    # Load request from environment
    request = PrivilegeRequest.from_env()

    # Execute command
    command = COMMANDS[command_name]()
    result = command.execute(request)

    # Output JSON for Kestra
    if command_name == "audit":
        print(f"AUDIT: {json.dumps(result, indent=2)}")
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
