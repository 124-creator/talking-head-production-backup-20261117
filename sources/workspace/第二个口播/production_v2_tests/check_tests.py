"""Capture and validate the three reference-informed experiments before rendering."""
from pathlib import Path
import asyncio
import hashlib
import io
import json

from PIL import Image, ImageChops, ImageDraw, ImageFont
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
TIMES = {"a": [.5, 1.6, 1.96, 2.4, 3.2, 3.8],
         "b": [.3, 1.0, 2.7, 3.2, 5.6, 6.8],
         "c": [.4, 1.5, 2.4, 3.8, 5.7, 8.2]}


async def main():
    all_checks = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for case, times in TIMES.items():
            errors = []
            page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
            page.on("pageerror", lambda e: errors.append(str(e)))
            await page.goto((HERE / f"test_{case}.html").as_uri()); await page.evaluate("window.__ready")
            assert await page.evaluate("[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
            rows = []
            for t in times:
                await page.evaluate("t=>window.__seek(t)", t)
                await page.screenshot(path=str(HERE / "preview" / f"{case}_{t:.2f}.png"))
                states = await page.evaluate("""()=>Object.fromEntries([...document.querySelectorAll('#subtitle,#title,#aPlate,.fact,#newCard')].map(el=>{const b=el.getBoundingClientRect(),s=getComputedStyle(el);return[el.id,{x:b.x,y:b.y,w:b.width,h:b.height,opacity:s.opacity,display:s.display,text:el.textContent}]}))""")
                for name, b in states.items():
                    if b["display"] == "none" or float(b["opacity"]) < .001: continue
                    assert b["x"] >= -1 and b["x"] + b["w"] <= 1921, (case, t, name, b)
                    assert b["y"] >= -1 and b["y"] + b["h"] <= 1081, (case, t, name, b)
                rows.append({"time": t, "elements": states})
            t = times[-2]
            await page.evaluate("t=>window.__seek(t)", t); one = await page.screenshot()
            await page.evaluate("window.__seek(0)"); await page.evaluate("t=>window.__seek(t)", t); two = await page.screenshot()
            first = Image.open(io.BytesIO(one)).convert("RGB")
            second = Image.open(io.BytesIO(two)).convert("RGB")
            diff = ImageChops.difference(first, second)
            if diff.getbbox() is not None:
                first.save(HERE / "qa" / f"determinism_{case}_before.png")
                second.save(HERE / "qa" / f"determinism_{case}_after.png")
                diff.save(HERE / "qa" / f"determinism_{case}_diff.png")
            assert diff.getbbox() is None, f"Non deterministic {case}: {diff.getbbox()}"
            assert not errors, errors
            all_checks[case] = {"pass": True, "browser_errors": errors, "deterministic": True, "samples": rows}
            await page.close()
        await browser.close()
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 20)
    for case, times in TIMES.items():
        sheet = Image.new("RGB", (1440, 640), "#252825"); draw = ImageDraw.Draw(sheet)
        for i, t in enumerate(times):
            im = Image.open(HERE / "preview" / f"{case}_{t:.2f}.png").convert("RGB")
            im.thumbnail((480, 270), Image.Resampling.LANCZOS); x, y = i % 3 * 480, i // 3 * 320
            sheet.paste(im, (x, y)); draw.text((x + 12, y + 282), f"{case.upper()} / +{t:.2f}s", font=font, fill="white")
        sheet.save(HERE / "preview" / f"test_{case}_contact.jpg", quality=95)
    result = {"pass": True, "cases": all_checks,
              "hashes": {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest()
                         for n in ["tests.js", "tests.css", "test_a.html", "test_b.html", "test_c.html"]}}
    (HERE / "qa/preflight.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: 3 tests / 18 frames / bounds / fonts / image decode / deterministic seeks")


if __name__ == "__main__":
    asyncio.run(main())
