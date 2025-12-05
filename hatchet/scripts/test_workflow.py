#!/usr/bin/env python3
"""
Test script to trigger the AWS privilege escalation workflow.

Usage:
    python scripts/test_workflow.py

Requires:
    - Hatchet engine running (docker-compose up -d)
    - Worker running (python -m src.workers.main)
    - LocalStack running with IAM roles provisioned (tofu apply)
    - HATCHET_CLIENT_TOKEN environment variable set
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client import hatchet
from src.workflows.aws_privilege import aws_privilege_workflow, PrivilegeRequest


async def test_successful_escalation():
    """Test a successful privilege escalation request."""
    print("\n" + "=" * 60)
    print("TEST: Successful Privilege Escalation")
    print("=" * 60)

    input_data = PrivilegeRequest(
        user_email="developer@example.com",
        role_arn="arn:aws:iam::000000000000:role/developer-elevated",
        duration_hours=2,
        justification="Need elevated access for debugging production issue INCIDENT-1234",
        approver_email="manager@example.com",
    )

    print(f"\nInput: {input_data.model_dump()}")
    print("\nTriggering workflow...")

    try:
        result = await aws_privilege_workflow.aio_run(input_data)
        print(f"\nWorkflow triggered! Run ref: {result}")

        # Wait for result
        final_result = await result.aio_result()
        print(f"\nWorkflow completed!")
        print(f"Result: {final_result}")
        return True
    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_invalid_duration():
    """Test request with invalid duration (should fail validation)."""
    print("\n" + "=" * 60)
    print("TEST: Invalid Duration (should fail validation)")
    print("=" * 60)

    input_data = PrivilegeRequest(
        user_email="developer@example.com",
        role_arn="arn:aws:iam::000000000000:role/developer-elevated",
        duration_hours=24,  # Exceeds MAX_DURATION_HOURS (8)
        justification="Need access for a very long time",
        approver_email="manager@example.com",
    )

    print(f"\nInput: {input_data.model_dump()}")
    print("\nTriggering workflow (expecting validation failure)...")

    try:
        result = await aws_privilege_workflow.aio_run(input_data)
        final_result = await result.aio_result()
        print(f"\nWorkflow completed!")
        print(f"Result: {final_result}")
        return True
    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        return False


async def test_unauthorized_role():
    """Test request for unauthorized role (should fail validation)."""
    print("\n" + "=" * 60)
    print("TEST: Unauthorized Role (should fail validation)")
    print("=" * 60)

    input_data = PrivilegeRequest(
        user_email="developer@example.com",
        role_arn="arn:aws:iam::000000000000:role/admin-root",  # Not in allowed list
        duration_hours=1,
        justification="Trying to get admin access sneakily",
        approver_email="manager@example.com",
    )

    print(f"\nInput: {input_data.model_dump()}")
    print("\nTriggering workflow (expecting validation failure)...")

    try:
        result = await aws_privilege_workflow.aio_run(input_data)
        final_result = await result.aio_result()
        print(f"\nWorkflow completed!")
        print(f"Result: {final_result}")
        return True
    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        return False


async def test_via_event():
    """Test triggering workflow via event."""
    print("\n" + "=" * 60)
    print("TEST: Trigger via Event")
    print("=" * 60)

    input_data = {
        "user_email": "developer@example.com",
        "role_arn": "arn:aws:iam::000000000000:role/readonly-prod",
        "duration_hours": 1,
        "justification": "Need read access to investigate customer report",
        "approver_email": "manager@example.com",
    }

    print(f"\nInput: {input_data}")
    print("\nPushing event 'aws:privilege:request'...")

    try:
        await hatchet.event.aio_push("aws:privilege:request", input_data)
        print("\nEvent pushed successfully!")
        print("Check Hatchet dashboard at http://localhost:8081 to see the workflow run")
        return True
    except Exception as e:
        print(f"\nFailed to push event: {e}")
        return False


async def main():
    print("AWS Privilege Escalation Workflow Tests")
    print("=" * 60)
    token = os.environ.get('HATCHET_CLIENT_TOKEN', 'NOT SET')
    print(f"Hatchet token: {token[:20]}..." if len(token) > 20 else f"Hatchet token: {token}")
    print(f"AWS endpoint: {os.environ.get('AWS_ENDPOINT_URL', 'default (real AWS)')}")
    print("=" * 60)

    # Run tests
    tests = [
        ("Successful Escalation", test_successful_escalation),
        ("Invalid Duration", test_invalid_duration),
        ("Unauthorized Role", test_unauthorized_role),
        ("Event Trigger", test_via_event),
    ]

    results = []
    for name, test_fn in tests:
        try:
            success = await test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\nTest '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}")


if __name__ == "__main__":
    asyncio.run(main())
