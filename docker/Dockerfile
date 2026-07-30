FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY api ./api
COPY dashboard ./dashboard
COPY configs ./configs
COPY scripts ./scripts

RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["python", "-m", "api.app", "--port", "8080"]
