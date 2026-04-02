import os
import cv2
import numpy as np
import pytesseract
from flask import Flask, request, jsonify

app = Flask(__name__)

# Konfigurasi Path Tesseract untuk Linux (Railway)
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Matriks Rotasi Round-Robin 8 Player
SCHEDULE = {
    1: {0:2, 2:0, 1:5, 5:1, 3:6, 6:3, 4:7, 7:4},
    2: {0:4, 4:0, 1:7, 7:1, 2:6, 6:2, 3:5, 5:3},
    3: {0:3, 3:0, 1:2, 2:1, 4:6, 6:4, 5:7, 7:5},
    4: {0:6, 6:0, 1:4, 4:1, 2:5, 5:2, 3:7, 7:3},
    5: {0:7, 7:0, 1:6, 6:1, 2:3, 3:2, 4:5, 5:4},
    6: {0:1, 1:0, 2:7, 7:2, 3:4, 4:3, 5:6, 6:5},
    7: {0:5, 5:0, 1:3, 3:1, 2:4, 4:2, 6:7, 7:6},
}

ALL_STAGES = {
    1:"Stage I-2",  2:"Stage I-3",  3:"Stage I-4",
    4:"Stage II-1", 5:"Stage II-2", 6:"Stage II-4",  7:"Stage II-5",
    8:"Stage II-6", 9:"Stage III-1",10:"Stage III-2",
    11:"Stage III-4",12:"Stage III-5",13:"Stage III-6",14:"Stage IV-1",
}

def clean_image_for_ocr(img_crop, invert=False):
    """Preprocessing gambar menggunakan OpenCV"""
    gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    if invert:
        thresh = cv2.bitwise_not(thresh)
    return thresh

def get_stage_index(stage_text):
    """Normalisasi teks Stage dari OCR"""
    stage_clean = stage_text.replace("L", "I").replace("1", "I").replace(" ", "").upper()
    for key, val in ALL_STAGES.items():
        if val.replace(" ", "").upper() in stage_clean:
            return key
    return None

@app.route('/ocr', methods=['GET', 'POST'])
def process_ocr():
    # Mengatasi error 405 Method Not Allowed
    if request.method == 'GET':
        return jsonify({
            "pesan": "Kirim POST request dengan form-data (key: 'image') berisi file gambar ke endpoint /ocr",
            "status": "API OCR Aktif!"
        })

    if 'image' not in request.files:
        return jsonify({"error": "Tidak ada file gambar yang dikirim dengan key 'image'"}), 400
    
    file = request.files['image']
    
    # Baca file dari buffer memori (RAM)
    try:
        file_bytes = file.read()
        npimg = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    except Exception as e:
        return jsonify({"error": f"Gagal membaca file: {str(e)}"}), 400
    
    if img is None:
        return jsonify({"error": "File yang dikirim bukan gambar yang valid"}), 400

    H, W = img.shape[:2]
    
    # --- 1. OCR STAGE ---
    stage_crop = img[int(H*0.015):int(H*0.055), int(W*0.45):int(W*0.55)]
    stage_processed = clean_image_for_ocr(stage_crop, invert=False)
    stage_text = pytesseract.image_to_string(stage_processed, config='--psm 7').strip()
    
    current_round_idx = get_stage_index(stage_text)
    if not current_round_idx:
        return jsonify({"error": f"Stage tidak valid/PvE. Terbaca: '{stage_text}'"}), 400

    # --- 2. DETEKSI PLAYER 'ME' ---
    lb_x1, lb_x2 = int(W*0.84), int(W*0.98)
    lb_y_start, lb_y_end = int(H*0.08), int(H*0.70)
    row_height = (lb_y_end - lb_y_start) / 8.0
    
    my_row = None
    max_brightness = 0
    
    for i in range(8):
        y_center = int(lb_y_start + (i * row_height) + (row_height * 0.2))
        x_center = int((lb_x1 + lb_x2) / 2)
        pixel = img[y_center, x_center]
        brightness = int(pixel[0]) + int(pixel[1]) + int(pixel[2])
        
        if brightness > max_brightness:
            max_brightness = brightness
            my_row = i
            
    if my_row is None or max_brightness < 200:
        return jsonify({"error": "Gagal mendeteksi posisi Anda di leaderboard."}), 400

    # --- 3. CROP NAMA (ME & ENEMY) ---
    enemy_row = my_row + 1 if my_row % 2 == 0 else my_row - 1

    def crop_name(row_idx):
        y1 = int(lb_y_start + (row_idx * row_height))
        y2 = int(y1 + (row_height * 0.45))
        return img[y1:y2, int(W*0.88):int(W*0.95)]

    my_name_processed = clean_image_for_ocr(crop_name(my_row), invert=True)
    enemy_name_processed = clean_image_for_ocr(crop_name(enemy_row), invert=True)

    my_name = pytesseract.image_to_string(my_name_processed, config='--psm 7').strip()
    enemy_name = pytesseract.image_to_string(enemy_name_processed, config='--psm 7').strip()

    # Bersihkan noise teks
    my_name = ''.join(e for e in my_name if e.isalnum()).lower()
    enemy_name = ''.join(e for e in enemy_name if e.isalnum()).lower()

    # --- 4. ALGORITMA MATRIKS ---
    found_map = None
    for slot_a in range(8):
        test_map = {}
        # Simulasi slot A adalah Kita
        test_map[slot_a] = my_name
        # Siapa musuh slot A di round ini menurut jadwal?
        rot_idx = ((current_round_idx - 1) % 7) + 1
        enemy_slot_a = SCHEDULE[rot_idx][slot_a]
        test_map[enemy_slot_a] = enemy_name
        
        # Validasi sederhana (Nama tidak boleh sama di slot berbeda)
        if len(set(test_map.values())) == len(test_map):
            found_map = test_map
            my_slot = slot_a
            break

    if not found_map:
        return jsonify({"error": "Matriks gagal sinkron dengan jadwal game."}), 400

    # --- 5. GENERATE PREDIKSI ---
    predictions = []
    for r_idx in range(1, 15):
        rot_key = ((r_idx - 1) % 7) + 1
        enemy_slt = SCHEDULE[rot_key][my_slot]
        e_name = found_map.get(enemy_slt, f"P-{enemy_slt}").capitalize()
        predictions.append({
            "stage": ALL_STAGES[r_idx],
            "me": my_name.capitalize(),
            "enemy": e_name
        })

    return jsonify({
        "status": "success",
        "scanned_data": {"stage": ALL_STAGES[current_round_idx], "me": my_name.capitalize(), "enemy": enemy_name.capitalize()},
        "predictions": predictions
    })

if __name__ == '__main__':
    # SISTEM ANTI-CRASH PORT RAILWAY
    raw_port = os.environ.get('PORT', '8080')
    try:
        actual_port = int(raw_port)
    except ValueError:
        print(f"Railway Error: Port {raw_port} invalid, forcing 8080")
        actual_port = 8080
        
    app.run(host='0.0.0.0', port=actual_port)
