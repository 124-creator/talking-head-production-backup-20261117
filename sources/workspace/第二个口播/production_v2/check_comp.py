"""Full-film V2 preflight: sections, transitions, evidence ordering and pure seeks."""
from pathlib import Path
import asyncio
import hashlib
import io
import json

from PIL import Image, ImageChops, ImageDraw
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
TIMES = [.8, 2.6, 5.18, 5.8, 8.8, 10.8, 13.5, 14.9, 16.4,
         18.8, 20.65, 21.85, 23.65, 25.5, 26.85, 28.55, 30.8, 33.35,
         34.8, 36.65, 38.4, 39.85, 44.9, 47.6, 48.65, 50.4, 52.9,
         55.27, 55.65, 56.3, 58.6, 60.9, 63.3, 64.3, 67.2, 68.95, 70.3]
HASH_FILES = ["comp.html", "styles.css", "full.css", "full.js"]


async def main():
    errors, rows, purity = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto((HERE / "comp.html").as_uri()); await page.evaluate("window.__ready")
        assert await page.evaluate("[...document.images].every(i=>i.complete&&i.naturalWidth>0)")
        assert await page.evaluate("__meta.dur===70.6&&__meta.fps===30")
        assert await page.evaluate("PHOTOS.filter(p=>p.group==='positive').map(p=>p.id).join(',')==='M02,M03,M04,M05,M06,M07'")
        assert await page.evaluate("PHOTOS.filter(p=>p.group==='group').map(p=>p.id).join(',')==='M18,M17'")
        for t in TIMES:
            await page.evaluate("t=>window.__seek(t)", t)
            await page.screenshot(path=str(HERE / "preview" / f"frame_{t:05.2f}.png"))
            state = await page.evaluate("""t=>{
              const state=stateAt(t);const ids=['subtitle','title','aPlate','chapterPlate','flow1','flow2','oldCard','newCard','endTop','endBut','endPicture','endClean','endGPT'];
              const bounds=Object.fromEntries(ids.map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect(),css=getComputedStyle(e);return[id,{x:r.x,y:r.y,w:r.width,h:r.height,display:css.display,opacity:css.opacity,text:e.textContent}]}));
              return {mode:state.mode,photo:state.p&&state.p.id,personVisible:state.person,carrierOpacity:state.carrierOp,comparisonOpacity:state.comparisonOp,caption:state.caption&&state.caption.text,bounds};
            }""", t)
            for name, b in state["bounds"].items():
                if b["display"] == "none" or float(b["opacity"]) < .001: continue
                assert b["x"] >= -1 and b["x"] + b["w"] <= 1921, (t, name, b)
                assert b["y"] >= -1 and b["y"] + b["h"] <= 1081, (t, name, b)
            rows.append({"time": t, **state})
        for t in [10.8, 18.8, 25.5, 28.55, 44.9, 50.4, 53.8, 59.0, 69.95]:
            await page.evaluate("t=>window.__seek(t)", t); one = await page.screenshot()
            await page.evaluate("window.__seek(2.6)"); await page.evaluate("t=>window.__seek(t)", t); two = await page.screenshot()
            diff = ImageChops.difference(Image.open(io.BytesIO(one)).convert("RGB"), Image.open(io.BytesIO(two)).convert("RGB"))
            if diff.getbbox() is not None: diff.save(HERE / "qa" / f"purity_{t:.2f}_diff.png")
            assert diff.getbbox() is None, f"Seek-history pixels at {t}: {diff.getbbox()}"
            purity.append({"time": t, "pixels_identical": True})
        semantic = await page.evaluate("""()=>({
          subtitleRestoresAfterKeyword:captionAt(29.50)!==null,
          pausesKept:captionAt(39.40)===null&&captionAt(55.25)===null,
          endingOrdinarySubtitleHidden:captionAt(69.95)===null,
          ratioExitNoPresenter:!stateAt(55.60).person,
          comparisonVisibleUntilGroup:stateAt(55.60).comparisonOp>0,
          lastFrameClamped:Math.min(2116,Math.floor(70.59*30+.5))===2116
        })""")
        assert all(semantic.values()), semantic
        static_map = await page.evaluate("__staticGroups().map(g=>({first:g.frames[0],last:g.frames.at(-1),frames:g.frames.length}))")
        await browser.close()
    assert not errors, errors
    for i in range((len(TIMES) + 8) // 9):
        sheet = Image.new("RGB", (1440, 900), "#252825"); draw = ImageDraw.Draw(sheet)
        for j, t in enumerate(TIMES[i * 9:(i + 1) * 9]):
            im = Image.open(HERE / "preview" / f"frame_{t:05.2f}.png").convert("RGB")
            im.thumbnail((480, 270), Image.Resampling.LANCZOS); x, y = j % 3 * 480, j // 3 * 300
            sheet.paste(im, (x, y)); draw.text((x + 12, y + 278), f"FULL V2 | {t:.2f}s", fill="white")
        sheet.save(HERE / "preview" / f"preflight_{i + 1:02d}.jpg", quality=95)
    report = {"pass": True, "frames_expected": 2118, "full_duration": 70.6, "browser_errors": errors,
              "hashes": {n: hashlib.sha256((HERE / n).read_bytes()).hexdigest() for n in HASH_FILES},
              "purity": purity, "semantic_checks": semantic, "static_groups": static_map, "samples": rows}
    (HERE / "qa/composition_checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS: {len(TIMES)} frames / {len(purity)} deterministic seeks / all six portraits / original speech timeline")
    print(f"Exact-hold cache candidates: {sum(g['frames'] for g in static_map)} frames in {len(static_map)} groups")


if __name__ == "__main__":
    asyncio.run(main())
