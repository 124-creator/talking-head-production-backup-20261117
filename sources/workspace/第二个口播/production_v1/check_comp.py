"""Preflight the deterministic speech composition before starting a long render."""
from pathlib import Path
import asyncio
import hashlib
import json

from PIL import Image, ImageDraw
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
TIMES = [0.8, 5.8, 10.8, 15.5, 18.8, 21.8, 25.2, 28.0, 35.0,
         36.8, 38.4, 44.8, 50.8, 56.2, 59.0, 61.1, 63.1, 69.95]


async def main():
    errors, rows = [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto((HERE / "comp.html").as_uri())
        await page.evaluate("window.__ready")
        assert await page.evaluate("document.fonts.check('100px Smiley')")
        assert await page.evaluate("[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
        for t in TIMES:
            await page.evaluate("t=>window.__seek(t)", t)
            shot = HERE / "preview" / f"frame_{t:05.2f}.png"
            await page.screenshot(path=str(shot))
            bounds = await page.evaluate("""()=>{
              const ids=['carrier','subtitle','stage-title','stage-note','quote-main','quote-gpt'];
              return Object.fromEntries(ids.map(id=>{const el=document.getElementById(id),b=el.getBoundingClientRect();return[id,{x:b.x,y:b.y,w:b.width,h:b.height,display:getComputedStyle(el).display,text:el.textContent}]}));
            }""")
            b = bounds["carrier"]
            assert b["x"] >= -.01 and b["y"] >= -.01 and b["x"] + b["w"] <= 1920.01 and b["y"] + b["h"] <= 1080.01
            b = bounds["subtitle"]
            if b["display"] != "none":
                assert b["x"] >= 20 and b["x"] + b["w"] <= 1900 and b["y"] + b["h"] <= 1060
            rows.append({"time": t, "bounds": bounds})
        purity = []
        for t in [18.8, 50.8, 69.95]:
            await page.evaluate("t=>window.__seek(t)", t)
            a = await page.screenshot()
            await page.evaluate("window.__seek(1.0)")
            await page.evaluate("t=>window.__seek(t)", t)
            b = await page.screenshot()
            same = hashlib.sha256(a).digest() == hashlib.sha256(b).digest()
            purity.append({"time": t, "pixel_screenshot_identical": same})
            assert same, f"Non-deterministic screenshot at {t}"
        await browser.close()
    assert not errors, errors
    for page_n in range(2):
        sheet = Image.new("RGB", (1440, 900), (30, 30, 30))
        draw = ImageDraw.Draw(sheet)
        for n, t in enumerate(TIMES[page_n * 9:(page_n + 1) * 9]):
            src = Image.open(HERE / "preview" / f"frame_{t:05.2f}.png").convert("RGB")
            src.thumbnail((480, 270), Image.Resampling.LANCZOS)
            x, y = n % 3 * 480, n // 3 * 300
            sheet.paste(src, (x, y)); draw.text((x + 10, y + 278), f"{t:.2f}s", fill="white")
        sheet.save(HERE / "preview" / f"preflight_{page_n + 1:02d}.jpg", quality=94)
    result = {"pass": True, "composition_sha256": hashlib.sha256((HERE / "comp.html").read_bytes()).hexdigest(),
              "data_sha256": hashlib.sha256((HERE / "data.js").read_bytes()).hexdigest(),
              "browser_errors": errors, "determinism": purity, "samples": rows}
    (HERE / "qa" / "composition_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Preflight PASS: fonts/images, 18 frames, framing, captions, deterministic seeks")


if __name__ == "__main__":
    asyncio.run(main())
