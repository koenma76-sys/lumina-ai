import os
import requests
import uvicorn
import random
import base64
import io
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
    # DIZIONARIO STILI: Configurazione 'Hard' per forzare il look desiderato
    style_configs = {
        "photorealistic": {
            "prefix": "Ultra-realistic professional photography, shot on 35mm lens, f/1.8, depth of field, sharp focus, incredibly detailed skin pores, RAW cinematic photo,",
            "negative": "painting, drawing, illustration, glitch, deformed, cartoon, anime, art, sketch, oil painting, watercolor"
        },
        "cyberpunk": {
            "prefix": "Cyberpunk 2077 aesthetic, futuristic sci-fi digital art, neon city lights, high-tech atmosphere, cinematic lighting, sharp details, hyper-detailed,",
            "negative": "classic, nature, rural, sunlight, bright day, vintage, old, traditional art, painting"
        },
        "fantasy": {
            "prefix": "Epic fantasy digital illustration, concept art, magical atmosphere, intricate details, glowing elements, masterpiece, sharp focus,",
            "negative": "modern, car, technology, blurry, low res, real life, photography, mundane"
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

    # Recupero configurazione o uso default
    config = style_configs.get(data.style, {"prefix": "", "negative": ""})
    
    # Costruzione Prompt finale (Prefisso + Prompt Utente)
    final_prompt = f"{config['prefix']} {data.prompt}" if config['prefix'] else data.prompt
    
    if data.enhance:
        final_prompt += ", masterpiece, ultra high resolution, highly detailed, perfect composition"

    current_seed = data.seed if data.seed != -1 else random.randint(0, 999999)
    
    # Gestione Ratio
    w, h = 1024, 1024
    if data.ratio == "16:9": w, h = 1280, 720
    elif data.ratio == "9:16": w, h = 720, 1280

    # Unione Negative Prompts (Base + Specifico Stile + Utente)
    base_neg = "low quality, bad anatomy, worst quality, blurry, watermark, text, signature"
    style_neg = config['negative']
    user_neg = data.negative_prompt
    
    full_neg = f"{base_neg}, {style_neg}, {user_neg}"

    encoded_prompt = requests.utils.quote(final_prompt)
    encoded_neg = requests.utils.quote(full_neg)
    
    api_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?seed={current_seed}&width={w}&height={h}&nologo=true&negative={encoded_neg}"
    
    try:
        r = requests.get(api_url, timeout=60)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail="Pollinations API error")
        return {"image": r.content.hex(), "seed": current_seed}
    except Exception as e:
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
            except: continue
    buf.seek(0)
    return {"zip": base64.b64encode(buf.getvalue()).decode()}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
