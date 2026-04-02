import os
import cv2
import numpy as np
import pytesseract
from flask import Flask, request, jsonify

app = Flask(__name__)

# Matriks Rotasi Round-Robin (0-7 adalah ID slot)
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
    """Fungsi OpenCV untuk membuat teks lebih tajam dibaca OCR"""
    # Ubah ke Grayscale
    gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
    # Perbesar gambar agar teks lebih jelas (Interpolasi)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    # Binarization (Jadikan murni Hitam/Putih)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    if invert:
        thresh = cv2.bitwise_not(thresh)
    return thresh

def get_stage_index(stage_text):
    stage_clean = stage_text.replace("L", "I").replace("1", "I").replace(" ", "").upper()
    for key, val in ALL_STAGES.items():
        if val.replace(" ", "").upper() in stage_clean:
            return key
    return None

@app.route('/predict', methods=['POST'])
def predict_matchup():
    if 'screenshot' not in request.files:
        return jsonify({"error": "Tidak ada file gambar yang dikirim"}), 400
    
    file = request.files['screenshot']
    npimg = np.fromfile(file, np.uint8)
    img = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    
    H, W = img.shape[:2]
    
    # KORDINAT CROP (Bisa kamu sesuaikan rasionya jika meleset)
    # img[y1:y2, x1:x2]
    stage_crop = img[int(H*0.015):int(H*0.055), int(W*0.45):int(W*0.55)]
    
    # Lakukan OCR pada Stage
    stage_processed = clean_image_for_ocr(stage_crop, invert=False)
    stage_text = pytesseract.image_to_string(stage_processed, config='--psm 7').strip()
    current_round_idx = get_stage_index(stage_text)
    
    if not current_round_idx:
        return jsonify({"error": f"Stage tidak dikenali atau PvE. Teks terbaca: '{stage_text}'"}), 400

    # SIMULASI PENCARIAN BARIS PEMAIN
    # Mengingat gambar leaderboard ukurannya tetap, kita bagi menjadi 8 baris
    lb_x1, lb_x2 = int(W*0.84), int(W*0.98)
    lb_y_start, lb_y_end = int(H*0.08), int(H*0.70)
    row_height = (lb_y_end - lb_y_start) / 8.0
    
    my_row = None
    max_brightness = 0
    
    # Deteksi baris yang punya background paling terang (Itu adalah Kamu/Biel)
    for i in range(8):
        y_center = int(lb_y_start + (i * row_height) + (row_height * 0.2))
        x_center = int((lb_x1 + lb_x2) / 2)
        pixel = img[y_center, x_center]
        brightness = int(pixel[0]) + int(pixel[1]) + int(pixel[2]) # B+G+R
        
        if brightness > max_brightness:
            max_brightness = brightness
            my_row = i
            
    if my_row is None or max_brightness < 200:
        return jsonify({"error": "Gagal menemukan player utama (Highlight background tidak terdeteksi)"}), 400

    enemy_row = my_row + 1 if my_row % 2 == 0 else my_row - 1

    def crop_name(row_idx):
        y1 = int(lb_y_start + (row_idx * row_height))
        y2 = int(y1 + (row_height * 0.45)) # Ambil area atas saja (menghindari bar HP)
        # Ambil x1 sedikit lebih ke kanan untuk menghindari ikon Avatar
        return img[y1:y2, int(W*0.88):int(W*0.95)]

    my_name_crop = crop_name(my_row)
    enemy_name_crop = crop_name(enemy_row)

    my_name_processed = clean_image_for_ocr(my_name_crop, invert=True)
    enemy_name_processed = clean_image_for_ocr(enemy_name_crop, invert=True)

    my_name = pytesseract.image_to_string(my_name_processed, config='--psm 7').strip()
    enemy_name = pytesseract.image_to_string(enemy_name_processed, config='--psm 7').strip()

    # --- LOGIKA MATRIKS PREDIKSI ---
    def add_to_map(test_map, slot, name):
        if not name: return True
        name = name.lower()
        if slot in test_map and test_map[slot] != name: return False
        if name in test_map.values() and list(test_map.keys())[list(test_map.values()).index(name)] != slot: return False
        test_map[slot] = name
        return True

    found_map = None
    for slot_a in range(8):
        test_map = {}
        valid = True
        valid &= add_to_map(test_map, slot_a, my_name)
        enemy_slot_a = SCHEDULE[((current_round_idx - 1) % 7) + 1][slot_a]
        valid &= add_to_map(test_map, enemy_slot_a, enemy_name)
        
        if valid:
            found_map = test_map
            break

    if not found_map:
        return jsonify({"error": f"Matriks Gagal. {my_name} vs {enemy_name} di Stage Index {current_round_idx} tidak sesuai jadwal algoritma."}), 400

    # Buat Peta Riwayat Pertemuan Lengkap (14 Round)
    name_to_slot = {v: k for k, v in found_map.items()}
    my_slot = name_to_slot.get(my_name.lower())
    
    predictions = []
    for round_idx in range(1, 15):
        rot_key = ((round_idx - 1) % 7) + 1
        enemy_slt = SCHEDULE[rot_key][my_slot]
        e_name = found_map.get(enemy_slt, f"Slot_{enemy_slt}").capitalize()
        predictions.append({
            "stage": ALL_STAGES[round_idx],
            "me": my_name.capitalize(),
            "enemy": e_name
        })

    return jsonify({
        "status": "success",
        "scanned_data": {"stage": ALL_STAGES[current_round_idx], "me": my_name, "enemy": enemy_name},
        "predictions": predictions
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))
