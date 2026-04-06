# Build stage for mkp224o
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    autoconf \
    automake \
    m4 \
    libsodium-dev \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/mkp224o
COPY mkp224o /app/mkp224o
RUN chmod +x autogen.sh && ./autogen.sh && ./configure && make

# Runtime stage
FROM python:3.12-slim

ARG USER_ID=1000
ARG GROUP_ID=1000
RUN apt-get update && apt-get install -y --no-install-recommends libsodium-dev \
 && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid "$GROUP_ID" appuser \
 && adduser --disabled-password --gecos "" --uid "$USER_ID" --gid "$GROUP_ID" appuser

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/
COPY --from=builder /app/mkp224o /app/mkp224o

RUN mkdir -p /app/mkp224o/onions \
 && chown -R appuser:appuser /app

ENV PYTHONUNBUFFERED=1
EXPOSE 2000
USER appuser
CMD ["python", "app.py"]
