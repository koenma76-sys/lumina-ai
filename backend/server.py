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
    # STILI OTTIMIZZATI CON PAROLE CHIAVE "PESANTI"
    styles = {
        "photorealistic": "RAW photo, 8k uhd, dslr, soft lighting, high quality, film grain, Fujifilm XT4",
        "cyberpunk": "cyberpunk style, futuristic city, neon glow, blue and magenta lighting, high contrast, synthwave art",
        "fantasy": "fantasy art, dnd character style, intricate armor, magical glow, epic background, cinematic atmosphere",
        "anime": "official anime style, high quality 2D, cel shaded, flat colors, clean lineart, Makoto Shinkai style, high resolution anime, trending on pixiv",
        "oil": "oil on canvas, heavy impasto, visible brushstrokes, classic art style, textured painting"
    }

    style_prefix = styles.get(data.style, "")
    
    # Costruzione del prompt: lo stile viene messo PRIMA del prompt utente per dominare il risultato
    final_prompt = f"{style_prefix}, {data.prompt}" if style_prefix else data.prompt
    
    if data.enhance:
        final_prompt += ", masterpiece, ultra high res, detailed shadows"

    current_seed = data.seed if data.seed != -1 else random.randint(0, 999999)
    
    w, h = 1024, 1024
    if data.ratio == "16:9": w, h = 1280, 720
    elif data.ratio == "9:16": w, h = 720, 1280

    # NEGATIVE PROMPT AGGRESSIVO per lo stile Anime
    neg_base = "low quality, blurry, photo, 3d, realism, realistic, rendering, gradient background, oil painting, watercolor"
    
    # Se è anime, aggiungiamo divieto assoluto di acquerello e texture
    if data.style == "anime":
        neg_base += ", canvas texture, brush strokes, rough sketch, painterly, traditional media"
    
    full_neg = f"{neg_base}, {data.negative_prompt}" if data.negative_prompt else neg_base

    encoded_prompt = requests.utils.quote(final_prompt)
    encoded_neg = requests.utils.quote(full_neg)
    
    # URL di Pollinations con i parametri corretti
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
