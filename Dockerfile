# Gunakan base image Python ringan
FROM python:3.9-slim

# Supaya output langsung tampil (no buffering)
ENV PYTHONUNBUFFERED=1

# Install system dependencies + Tesseract OCR (Indonesia & Inggris)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    tesseract-ocr-eng \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements dulu (biar cache Docker optimal)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua file project
COPY . .

# Railway pakai PORT dari environment
EXPOSE 8080

# Run app pakai gunicorn (WAJIB untuk production)
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
