import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests, uvicorn, random, base64, io
from zipfile import ZipFile, ZIP_DEFLATED

app = FastAPI()

# CORS: Qui devi mettere l'URL che ti darà Vercel (es. https://lumina.vercel.app)
# Per ora lasciamo "*" per facilità, ma in produzione è meglio l'URL specifico.
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
    # Questo endpoint serve per il "ping" di risveglio
    return {"status": "online", "message": "Lumina Backend is Awake"}

@app.post("/generate")
async def generate(data: GenRequest):
    styles = {
        "photorealistic": "professional photography, raw photo, 8k, highly detailed",
        "cyberpunk": "neon lights, synthwave aesthetic, futuristic city",
        "fantasy": "ethereal lighting, magical world, highly detailed digital art",
        "anime": "studio ghibli style, vibrant colors, clean lines",
        "oil": "classical oil painting, textured canvas, brushstrokes"
    }

    style_mod = styles.get(data.style, "")
    final_prompt = f"{style_mod}, {data.prompt}" if style_mod else data.prompt
    
    if data.enhance:
        final_prompt += ", cinematic lighting, masterpiece, high resolution"

    current_seed = data.seed if data.seed != -1 else random.randint(0, 999999)
    
    # Dimensioni basate sul ratio
    w, h = 1024, 1024
    if data.ratio == "16:9": w, h = 1280, 720
    elif data.ratio == "9:16": w, h = 720, 1280

    api_url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(final_prompt)}?seed={current_seed}&width={w}&height={h}&nologo=true"
    
    try:
        r = requests.get(api_url, timeout=60)
        # Inviamo l'immagine come stringa hex per evitare problemi di buffering su Render Free
        return {"image": r.content.hex(), "seed": current_seed}
    except:
        raise HTTPException(status_code=500, detail="Errore generazione")

@app.post("/zip")
async def make_zip(data: dict):
    imgs = data.get("images", [])
    buf = io.BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as f:
        for i, hex_data in enumerate(imgs):
            f.writestr(f"lumina_{i}.png", base64.b16decode(hex_data.upper()))
    buf.seek(0)
    return {"zip": base64.b64encode(buf.getvalue()).decode()}

if __name__ == "__main__":
    # IMPORTANTE: Render assegna una porta dinamica tramite variabile d'ambiente
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
