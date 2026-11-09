import base64
import os
import subprocess
import ddddocr
import nodriver as uc
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr = ddddocr.DdddOcr(show_ad=False)


class ImageRequest(BaseModel):
    image_base64: str


class TurnstileRequest(BaseModel):
    sitekey: str
    url: str


@app.get("/")
def health():
    return {"status": "ready"}


@app.post("/solve-image")
def solve_image(req: ImageRequest):
    try:
        raw_b64 = req.image_base64.split(",")[-1]
        img_bytes = base64.b64decode(raw_b64)
        result = ocr.classification(img_bytes)
        return {"solution": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/solve-turnstile")
async def solve_turnstile(req: TurnstileRequest):
    os.environ["DISPLAY"] = ":99"
    xvfb = subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1024x768x16"])
    browser = None
    try:
        browser = await uc.start(
            browser_executable_path="/usr/bin/chromium",
            headless=False,
            sandbox=False,
            browser_args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--single-process",
            ],
        )
        page = await browser.get(req.url)
        await page.sleep(5)
        token = await page.evaluate(
            'document.querySelector(\'[name="cf-turnstile-response"]\')?.value || ""'
        )
        if not token:
            raise HTTPException(status_code=408, detail="Turnstile token not found")
        return {"token": token}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if browser:
            browser.stop()
        xvfb.terminate()
