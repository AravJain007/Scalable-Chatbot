FROM python:3.9-slim

# Install system dependencies for Playwright
RUN apt-get update && \
    apt-get install -y \
    curl \
    git \
    gcc \
    g++ \
    libglib2.0-0 \
    libnss3 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    fonts-noto \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browsers
RUN playwright install chromium
RUN playwright install-deps chromium

COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5069"]