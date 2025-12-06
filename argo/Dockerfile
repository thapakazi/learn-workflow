FROM python:3.11-slim

WORKDIR /app

# Install boto3
RUN pip install --no-cache-dir boto3

# Copy scripts
COPY scripts/ /app/scripts/

# Set entrypoint
ENTRYPOINT ["python", "/app/scripts/privilege_escalation.py"]
