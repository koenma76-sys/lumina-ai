
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
    # STILI RIFINITI PER EVITARE L'EFFETTO "DIPINTO/ACQUERELLO"
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
    
    # Prefisso prima del prompt per dominare la generazione
    final_prompt = f"{config['prefix']} {data.prompt}" if config['prefix'] else data.prompt
    
    if data.enhance:
        final_prompt += ", cinematic lighting, masterpiece, ultra high resolution, highly detailed"

    current_seed = data.seed if data.seed != -1 else random.randint(0, 999999)
    
    # Ratio logic
    w, h = 1024, 1024
    if data.ratio == "16:9": w, h = 1280, 720
    elif data.ratio == "9:16": w, h = 720, 1280

    # Negative Prompt consolidato
    base_neg = "low quality, blurry, worst quality, distorted, watermark, signature"
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
