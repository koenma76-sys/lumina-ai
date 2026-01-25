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
# Assicurati che questa chiave sia corretta!
EVOLINK_API_KEY = "sk-2iVlG1abuFFZKCT4D5E46nUL92rJAvqtwdDRB8moBNIB75YZ" 
EVOLINK_BASE_URL = "https://api.evolink.ai/v1"

def keep_alive():
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
    return {"status": "online", "message": "Lumina Backend is running"}

@app.post("/generate")
async def generate(data: GenRequest):
    headers = {
        "Authorization": f"Bearer {EVOLINK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    current_seed = data.seed if data.seed != -1 else random.randint(1, 2147483647)
    
    # Adattamento nomi parametri per Evolink
    payload = {
        "model": "z-image-turbo",
        "prompt": data.prompt,
        "size": data.ratio,
        "seed": current_seed
    }

    try:
        # 1. Avvio Task
        print(f"DEBUG: Invio prompt a Evolink: {data.prompt}")
        create_resp = requests.post(f"{EVOLINK_BASE_URL}/images/generations", json=payload, headers=headers, timeout=30)
        
        if create_resp.status_code != 200:
            print(f"DEBUG ERROR: {create_resp.text}")
            raise HTTPException(status_code=500, detail="Evolink Start Failed")
        
        task_data = create_resp.json()
        task_id = task_data.get("id") or task_data.get("task_id")
        
        if not task_id:
            raise HTTPException(status_code=500, detail="No Task ID received")

        # 2. Polling (Attesa)
        image_url = None
        for i in range(25):
            time.sleep(1.5) # Diamo un po' più di respiro tra i controlli
            status_resp = requests.get(f"{EVOLINK_BASE_URL}/tasks/{task_id}", headers=headers)
            
            if status_resp.status_code != 200: continue
            
            status_data = status_resp.json()
            print(f"DEBUG: Status Task {task_id}: {status_data.get('status')}")
            
            if status_data.get("status") == "completed":
                # Gestione flessibile del campo immagine
                images = status_data.get("images", [])
                if images and len(images) > 0:
                    image_url = images[0]
                    break
            elif status_data.get("status") == "failed":
                raise HTTPException(status_code=500, detail="Evolink failed generation")

        if not image_url:
            raise HTTPException(status_code=504, detail="Polling Timeout - Image not ready")

        # 3. Scaricamento immagine
        img_res = requests.get(image_url, timeout=20)
        return {"image": img_res.content.hex(), "seed": current_seed}

    except Exception as e:
        print(f"SYSTEM ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/zip")
async def make_zip(data: dict):
    imgs = data.get("images", [])
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as f:
        for i, hex_data in enumerate(imgs):
            try:
                img_data = bytes.fromhex(hex_data)
                f.writestr(f"lumina_art_{i}.png", img_data)
            except: continue
    buf.seek(0)
    return {"zip": base64.b64encode(buf.getvalue()).decode()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
