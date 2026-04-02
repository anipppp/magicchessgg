from flask import Flask, request, jsonify
import pytesseract
from PIL import Image
import io

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "API OCR Aktif!", 
        "pesan": "Kirim POST request dengan form-data (key: 'image') berisi file gambar ke endpoint /ocr"
    })

@app.route('/ocr', methods=['POST'])
def process_ocr():
    # Cek apakah ada file gambar dengan key 'image'
    if 'image' not in request.files:
        return jsonify({"error": "Tidak ada file gambar yang dikirim. Pastikan menggunakan form-data dengan key 'image'."}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({"error": "Nama file kosong."}), 400

    try:
        # Membaca gambar dari memory menggunakan Pillow
        img = Image.open(file.stream)
        
        # Konversi ke RGB jika gambar memiliki format RGBA (misal PNG transparan) 
        # untuk mencegah error pada Tesseract
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Eksekusi OCR (Mendeteksi teks Bahasa Indonesia & Inggris)
        extracted_text = pytesseract.image_to_string(img, lang='ind+eng')
        
        return jsonify({
            "status": "success",
            "text": extracted_text.strip()
        })
        
    except Exception as e:
        return jsonify({"error": f"Terjadi kesalahan saat memproses gambar: {str(e)}"}), 500

if __name__ == '__main__':
    # Mode ini hanya jalan jika dieksekusi lokal. 
    # Di Railway, Gunicorn yang akan mengambil alih.
    app.run(debug=True, host='0.0.0.0')
