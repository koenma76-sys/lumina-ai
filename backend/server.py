from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import io
import zipfile
import base64

app = Flask(__name__)
CORS(app)

@app.route('/')
def health():
    return "Lumina Server Online", 200

# MOTORE 1: POLLINATIONS (Lumina Core)
@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    prompt = data.get('prompt')
    negative = data.get('negative_prompt', '')
    style = data.get('style', 'none')
    ratio = data.get('ratio', '1:1')
    seed = data.get('seed', 42)
    enhance = data.get('enhance', False)

    width, height = 1024, 1024
    if ratio == "16:9": width, height = 1280, 720
    elif ratio == "9:16": width, height = 720, 1280

    full_prompt = f"{prompt} --no {negative} --style {style}"
    if enhance: full_prompt += " high quality, vivid colors, masterpiece"

    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(full_prompt)}?width={width}&height={height}&seed={seed}&nologo=true&model=flux"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return jsonify({"image": response.content.hex(), "seed": seed})
        return jsonify({"error": "Pollinations failed"}), 500
    except:
        return jsonify({"error": "Timeout"}), 500

# MOTORE 2: SUBNP (Experimental)
@app.route('/generate_subnp', methods=['POST'])
def generate_subnp():
    data = request.json
    prompt = data.get('prompt')
    seed = data.get('seed', 42)
    width = data.get('width', 1024)
    height = data.get('height', 1024)
    
    # URL di Subnp come da documentazione
    subnp_url = "https://subnp.com/api/v1/image"
    params = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "seed": seed,
        "model": "flux" 
    }
    
    try:
        # Il server fa la chiamata al posto del browser
        response = requests.get(subnp_url, params=params, timeout=45)
        
        if response.status_code == 200:
            # Inviamo l'immagine al frontend in formato HEX
            return jsonify({
                "image": response.content.hex(), 
                "seed": seed,
                "engine": "subnp"
            })
        else:
            return jsonify({"error": f"Subnp API error: {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/zip', methods=['POST'])
def create_zip():
    data = request.json
    images_hex = data.get('images', [])
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for i, hex_data in enumerate(images_hex):
            try:
                img_data = bytes.fromhex(hex_data)
                zf.writestr(f"lumina_vision_{i}.png", img_data)
            except:
                continue
    
    memory_file.seek(0)
    base64_zip = base64.b64encode(memory_file.read()).decode()
    return jsonify({"zip": base64_zip})

if __name__ == '__main__':
    # Render usa la porta 10000 di default
    app.run(host='0.0.0.0', port=10000)
