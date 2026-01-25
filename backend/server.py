import os
import requests
import uvicorn
import random
import base64
import io
import threading
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from zipfile import ZipFile, ZIP_DEFLATED

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAZIONE EVOLINK ---
EVOLINK_API_KEY = "sk-2iVlG1abuFFZKCT4D5E46nUL92rJAvqtwdDRB8moBNIB75YZ" 
EVOLINK_BASE_URL = "https://api.evolink.ai/v1"

# --- LOGICA CRONJOB INTERNA (KEEP-ALIVE) ---
def keep_alive():
    """Invia una richiesta al server stesso ogni 10 minuti per evitare lo sleep di Render."""
    time.sleep(30)
    port = os.environ.get("PORT", "8000")
    server_url = f"http://0.0.0.0:{port}"
    while True:
        try:
            requests.get(server_url)
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

class GenRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style: str = "none"
    seed: int = -1
    ratio: str = "1:1"
    enhance: bool = False

@app.get("/")
async def health_check():
    return {"status": "online", "message": "Lumina Backend (Evolink Turbo) is running"}

@app.post("/generate")
async def generate(data: GenRequest):
    # Configurazione stili (mantenuta dal tuo backup)
    style_configs = {
        "photorealistic": {
            "prefix": "Photorealistic cinematic shot, high detail, 8k, f/1.8, high skin detail, detailed eyes, masterwork photography, sharp focus,",
            "negative": "painting, oil, watercolor, sketch, drawing, illustration, cartoon, anime, CGI, 3d render, doll, plastic"
        },
        "cyberpunk": {
            "prefix": "Cinematic movie still, cyberpunk setting, realistic neon lighting, volumetric fog, Ray Tracing, Unreal Engine 5 render, hyper-realistic, metallic textures,",
            "negative": "painting, drawing, art, sketch, illustration, oil, watercolor, canvas, flat colors, cartoon"
        },
        "fantasy": {
            "prefix": "Cinematic film still, realistic fantasy setting, natural dramatic lighting, highly detailed textures, movie shot, 8k, hyper-realistic, realistic scale,",
            "negative": "illustration, painting, digital art, drawing, sketch, cartoon, anime, low poly, oil, watercolor, canvas texture"
        },
        "anime": {
            "prefix": "Official anime style, high quality 2D, cel shaded, flat colors, clean lineart, Makoto Shinkai style, high resolution anime, trending on pixiv,",
            "negative": "realistic, 3d, rendering, photo, realistic skin, oil painting, watercolor, rough sketch, traditional media"
        },
        "oil": {
            "prefix": "Traditional oil painting on canvas, heavy impasto brushstrokes, rich textures, museum quality masterpiece, classical lighting,",
            "negative": "photography, clean, digital art, flat colors, anime, 3d render, vector, plastic"
        }
    }

    config = style_configs.get(data.style, {"prefix": "", "negative": ""})
    final_prompt = f"{config['prefix']} {data.prompt}" if config['prefix'] else data.prompt
    if data.enhance:
        final_prompt += ", cinematic lighting, masterpiece, ultra high resolution, highly detailed"

    current_seed = data.seed if data.seed != -1 else random.randint(1, 2147483647)
    
    # Payload per Evolink (z-image-turbo usa 'size' come stringa es. "1:1")
    headers = {
        "Authorization": f"Bearer {EVOLINK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "z-image-turbo",
        "prompt": final_prompt,
        "negative_prompt": f"{config['negative']}, {data.negative_prompt}",
        "size": data.ratio,
        "seed": current_seed
    }

    try:
        # 1. Crea il Task
        create_resp = requests.post(f"{EVOLINK_BASE_URL}/images/generations", json=payload, headers=headers, timeout=30)
        if create_resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Evolink Error: {create_resp.text}")
        
        task_id = create_resp.json().get("id")

        # 2. Polling (Attesa dell'immagine)
        image_url = None
        for _ in range(20): # Massimo 20 secondi (Turbo è quasi istantaneo)
            time.sleep(1)
            status_resp = requests.get(f"{EVOLINK_BASE_URL}/tasks/{task_id}", headers=headers)
            status_data = status_resp.json()
            
            if status_data.get("status") == "completed":
                image_url = status_data.get("images", [None])[0]
                break
            elif status_data.get("status") == "failed":
                raise HTTPException(status_code=500, detail="Evolink task failed")

        if not image_url:
            raise HTTPException(status_code=504, detail="Generation timed out")

        # 3. Scarica l'immagine e convertila in HEX per il frontend
        img_content = requests.get(image_url).content
        return {"image": img_content.hex(), "seed": current_seed}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/zip")
async def make_zip(data: dict):
    imgs = data.get("images", [])
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as f:
        for i, hex_data in enumerate(imgs):
            try:
                # Correzione: usiamo bytes.fromhex per maggiore stabilità con i dati Evolink
                img_data = bytes.fromhex(hex_data)
                f.writestr(f"lumina_art_{i}.png", img_data)
            except: continue
    buf.seek(0)
    return {"zip": base64.b64encode(buf.getvalue()).decode()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
