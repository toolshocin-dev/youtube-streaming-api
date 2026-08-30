FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh

ENV DENO_INSTALL=/root/.deno
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

RUN pip install --no-cache-dir \
    yt-dlp \
    bgutil-ytdlp-pot-provider \
    flask \
    gunicorn

WORKDIR /app

COPY . /app

ENV PORT=10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
