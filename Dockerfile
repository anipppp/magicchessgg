# Menggunakan base image OS Linux yang sudah ada Python-nya
FROM python:3.9-slim

# Update server Linux dan Install Tesseract OCR beserta bahasa Indonesia & Inggris
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-ind \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Menentukan folder kerja di dalam server Railway
WORKDIR /app

# Memasukkan file requirements dan menginstal semua library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Memasukkan seluruh sisa kode aplikasi (app.py)
COPY . .

# Menjalankan aplikasi menggunakan Gunicorn
# $PORT akan otomatis diisi oleh sistem Railway
CMD gunicorn --bind 0.0.0.0:$PORT app:app
