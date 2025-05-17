# docker/fusion-controller.Dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    iproute2 \
    net-tools \
    curl \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY config/ ./config/

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.fusion_controller"]