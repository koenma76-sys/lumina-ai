import os
import requests
import uvicorn
import random
import base64
import io
import threading
import time
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from zipfile import ZipFile, ZIP_DEFLATED

# Configura logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURAZIONE Z IMAGE TURBO ---
EVOLINK_API_KEY = os.environ.get("EVOLINK_API_KEY")
if not EVOLINK_API_KEY:
    logger.error("EVOLINK_API_KEY not found in environment variables!")
    raise ValueError("Missing EVOLINK_API_KEY environment variable")
EVOLINK_API_URL = "https://api.evolink.ai/v1/images/generations"
# -----------------------------------

# --- LOGICA CRONJOB INTERNA (KEEP-ALIVE) ---
def keep_alive():
    """Invia una richiesta al server stesso ogni 10 minuti per evitare lo sleep di Render."""
    time.sleep(30)
    server_url = "http://0.0.0.0:" + os.environ.get("PORT", "8000")
    while True:
        try:
            requests.get(server_url)
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()
# -------------------------------------------

class GenRequest(BaseModel):
    prompt: str
    negative_prompt: str = ""
    style: str = "none"
    seed: int = -1
    ratio: str = "1:1"
    enhance: bool = False

@app.get("/")
async def health_check():
    return {"status": "online", "message": "Lumina Backend is running with Z Image Turbo"}

@app.post("/generate")
async def generate(data: GenRequest):
    logger.info(f"Received request - Prompt: {data.prompt[:50]}...")
    
    # STILI RIFINITI
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

    current_seed = data.seed if data.seed != -1 else random.randint(0, 999999)
    
    # Negative Prompt consolidato
    base_neg = "low quality, blurry, worst quality, distorted, watermark, signature"
    style_neg = config['negative']
    user_neg = data.negative_prompt
    
    full_neg = f"{base_neg}, {style_neg}, {user_neg}"

    # Headers per Evolink API
    headers = {
        "Authorization": f"Bearer {EVOLINK_API_KEY}",
        "Content-Type": "application/json"
    }

    # Payload corretto per Z Image Turbo (usa "size" invece di width/height)
    payload = {
        "model": "z-image-turbo",
        "prompt": final_prompt,
        "negative_prompt": full_neg,
        "size": data.ratio,  # "1:1", "16:9", "9:16"
        "seed": current_seed,
        "n": 1
    }
    
    logger.info(f"Calling Evolink API with seed: {current_seed}, ratio: {data.ratio}")
    
    try:
        # Chiamata all'API
        r = requests.post(EVOLINK_API_URL, headers=headers, json=payload, timeout=90)
        
        logger.info(f"API Response Status: {r.status_code}")
        
        if r.status_code != 200:
            error_detail = r.text
            logger.error(f"API Error: {error_detail}")
            raise HTTPException(status_code=500, detail=f"Evolink API error ({r.status_code}): {error_detail}")
        
        response_data = r.json()
        logger.info(f"API Response keys: {list(response_data.keys())}")
        logger.info(f"Full API Response: {response_data}")
        
        # CASO 1: Risposta sincrona con immagine diretta
        if "data" in response_data and len(response_data["data"]) > 0:
            first_item = response_data["data"][0]
            
            # Sub-caso A: base64 diretto
            if "b64_json" in first_item:
                logger.info("Found b64_json in response")
                b64_image = first_item["b64_json"]
                img_bytes = base64.b64decode(b64_image)
                hex_image = img_bytes.hex()
                logger.info(f"Successfully converted b64 to hex, length: {len(hex_image)}")
                return {"image": hex_image, "seed": current_seed}
            
            # Sub-caso B: URL diretto
            elif "url" in first_item:
                logger.info(f"Found URL in response: {first_item['url']}")
                img_response = requests.get(first_item["url"], timeout=30)
                if img_response.status_code == 200:
                    hex_image = img_response.content.hex()
                    logger.info(f"Successfully downloaded image, hex length: {len(hex_image)}")
                    return {"image": hex_image, "seed": current_seed}
        
        # CASO 2: Sistema asincrono task-based
        if "id" in response_data and "status" in response_data:
            task_id = response_data["id"]
            logger.info(f"Async task created: {task_id}, initial status: {response_data['status']}")
            
            
            # Polling del task
            # Step 2: Polling per ottenere il risultato con backoff
            max_attempts = 120  # 120 tentativi = fino a 2 minuti
            wait_time = 0.5  # Inizia con 0.5 secondi
            
            for attempt in range(max_attempts):
                time.sleep(wait_time)
                
                # Aumenta gradualmente il tempo di attesa (backoff esponenziale)
                if attempt > 10:
                    wait_time = min(2.0, wait_time * 1.1)  # Max 2 secondi
                
                # Query del task
                task_url = f"https://api.evolink.ai/v1/tasks/{task_id}"
                task_check = requests.get(task_url, headers=headers, timeout=30)
                
                if task_check.status_code == 200:
                    task_data = task_check.json()
                    logger.info(f"Task status: {task_data.get('status')}, attempt {attempt+1}")
                    
                    # Se completato (può essere "succeeded" o "completed")
                    if task_data.get("status") in ["succeeded", "completed"]:
                        logger.info(f"Task completed! Full response: {task_data}")
                        
                        # Prova diversi formati di risposta possibili
                        image_url = None
                        b64_data = None
                        
                        # Formato 1: data array con url
                        if "data" in task_data and isinstance(task_data["data"], list) and len(task_data["data"]) > 0:
                            first_item = task_data["data"][0]
                            image_url = first_item.get("url")
                            b64_data = first_item.get("b64_json")
                        
                        # Formato 2: data object con url/b64
                        elif "data" in task_data and isinstance(task_data["data"], dict):
                            image_url = task_data["data"].get("url")
                            b64_data = task_data["data"].get("b64_json")
                        
                        # Formato 3: url diretto nel task
                        elif "url" in task_data:
                            image_url = task_data["url"]
                        
                        # Formato 4: result object
                        elif "result" in task_data:
                            if isinstance(task_data["result"], dict):
                                image_url = task_data["result"].get("url")
                                b64_data = task_data["result"].get("b64_json")
                        
                        # Prova prima b64 se disponibile
                        if b64_data:
                            logger.info(f"Found base64 data in response")
                            try:
                                img_bytes = base64.b64decode(b64_data)
                                hex_image = img_bytes.hex()
                                logger.info(f"Successfully converted b64 to hex, length: {len(hex_image)}")
                                return {"image": hex_image, "seed": current_seed}
                            except Exception as e:
                                logger.error(f"Failed to decode b64: {e}")
                        
                        # Altrimenti prova URL
                        if image_url:
                            logger.info(f"Downloading image from: {image_url}")
                            img_response = requests.get(image_url, timeout=30)
                            if img_response.status_code == 200:
                                hex_image = img_response.content.hex()
                                logger.info(f"Successfully generated image, hex length: {len(hex_image)}")
                                return {"image": hex_image, "seed": current_seed}
                            else:
                                logger.error(f"Failed to download image, status: {img_response.status_code}")
                        
                        logger.error(f"Image URL not found in response: {task_data}")
                        raise HTTPException(status_code=500, detail=f"Image URL not found in response: {task_data}")
                    
                    # Se fallito
                    elif task_data.get("status") in ["failed", "canceled"]:
                        error_msg = task_data.get("error", "Unknown error")
                        raise HTTPException(status_code=500, detail=f"Task failed: {error_msg}")
            
            
            # Timeout dopo polling
            logger.error("Task polling timeout after 120 attempts")
            raise HTTPException(status_code=504, detail="Task timeout - image generation took too long (>2 minutes)")
        
        # CASO 3: Formato non riconosciuto
        logger.error(f"Unexpected response format: {response_data}")
        raise HTTPException(status_code=500, detail=f"Unexpected API response format. Keys: {list(response_data.keys())}")
            
    except requests.exceptions.Timeout:
        logger.error("Request timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/zip")
async def make_zip(data: dict):
    imgs = data.get("images", [])
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as f:
        for i, hex_data in enumerate(imgs):
            try:
                img_data = base64.b16decode(hex_data.upper())
                f.writestr(f"lumina_art_{i}.png", img_data)
            except: 
                continue
    buf.seek(0)
    return {"zip": base64.b64encode(buf.getvalue()).decode()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
