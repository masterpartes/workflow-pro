# ── Stage 1: base Python image ────────────────────────────────────────────────
FROM python:3.11-slim

# Install system dependencies required by Playwright / Chromium
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    # Chromium shared libraries
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libglib2.0-0 \
    fonts-liberation libappindicator3-1 lsb-release xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python deps ────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Install Playwright Chromium (with all OS deps) ────────────────────────────
RUN playwright install chromium --with-deps

# ── Copy source ────────────────────────────────────────────────────────────────
COPY . .

# ── Runtime ───────────────────────────────────────────────────────────────────
# Railway injects $PORT; default to 8000 for local testing
ENV PORT=8000

EXPOSE 8000

# Use exec form so Railway can send signals properly
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT} --workers 1"]
