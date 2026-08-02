FROM python:3.11-slim

WORKDIR /app

# ffmpeg/ffprobe for RTSP health + single-frame preview; libs for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libjpeg62-turbo \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY api ./api
COPY dashboard ./dashboard
COPY configs ./configs
COPY scripts ./scripts
COPY artifacts ./artifacts
COPY models ./models

RUN pip install --no-cache-dir -e ".[camera]" \
    && pip install --no-cache-dir Pillow>=10.0.0

EXPOSE 8080

# Inventory (1.cameras.json) is mounted at runtime — never baked into the image.
CMD ["python", "-m", "api.app", "--port", "8080"]
