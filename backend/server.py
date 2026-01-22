@app.route('/generate_subnp', methods=['POST'])
def generate_subnp():
    data = request.json
    prompt = data.get('prompt')
    width = data.get('width', 1024)
    height = data.get('height', 1024)
    seed = data.get('seed', 42)
    
    # Costruiamo l'URL per Subnp
    subnp_url = f"https://subnp.com/api/v1/image?prompt={prompt}&width={width}&height={height}&seed={seed}&model=flux"
    
    try:
        response = requests.get(subnp_url)
        if response.status_code == 200:
            # Convertiamo l'immagine in HEX per mantenere la compatibilità con il tuo sistema ZIP
            image_hex = response.content.hex()
            return jsonify({"image": image_hex, "seed": seed})
        else:
            return jsonify({"error": "Subnp failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
