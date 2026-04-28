FROM python:3.12-slim

LABEL org.opencontainers.image.title="treescape EVIDENT base runner"
LABEL org.opencontainers.image.description="Lightweight runner for treescape manifest structural validation. Domain validation (oracle pytest runs) lives in separate workflow/ images."

WORKDIR /workspace

RUN pip install --no-cache-dir PyYAML==6.0.2

COPY workflow/validate_manifest.py /usr/local/bin/treescape-validate
RUN chmod +x /usr/local/bin/treescape-validate

CMD ["treescape-validate", "evident.yaml"]
