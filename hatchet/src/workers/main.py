"""
Hatchet Worker

Registers workflows and starts listening for tasks.
"""
from src.client import hatchet
from src.workflows.aws_privilege import aws_privilege_workflow


def main():
    worker = hatchet.worker(
        name="idp-worker",
        workflows=[aws_privilege_workflow],
    )

    print("Starting IDP worker...")
    print("Registered workflows:")
    print(f"  - {aws_privilege_workflow.name}")
    worker.start()


if __name__ == "__main__":
    main()
