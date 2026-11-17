"""Verify the complete V2 encode before delivering it beside the preserved V1."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SAMPLES = [(5.8, "M09"), (8.8, "M10"), (10.8, "M11"), (16.4, "M02"), (18.8, "M03"),
           (20.65, "M04"), (21.85, "M05"), (23.65, "M06"), (25.5, "M07"), (34.8, "M19"),
           (36.65, "M24"), (38.4, "M23"), (56.3, "M18"), (60.9, "M17")]
POSTERS = [.8, 5.8, 10.8, 16.4, 18.8, 20.65, 21.85, 23.65, 25.5,
           28.55, 30.8, 33.35, 34.8, 36.65, 38.4, 44.9, 50.4, 52.9,
           55.27, 55.65, 56.3, 58.6, 60.9, 63.3, 64.3, 68.95, 70.3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output(args):
    return subprocess.run(args, capture_output=True, check=True, text=True, encoding="utf-8").stdout


def similarity(a, b):
    a = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (192, 108))
    b = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (192, 108))
    return float(np.corrcoef(a.flatten(), b.flatten())[0, 1])


def read_png(path):
    return cv2.imdecode(np.frombuffer(Path(path).read_bytes(), np.uint8), cv2.IMREAD_COLOR)


def main():
    rt = json.loads((ROOT.parent / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    inputs = json.loads((HERE / "qa/input_manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "output/render_manifest.json").read_text(encoding="utf-8"))
    initial = json.loads((ROOT / "analysis/analysis_checks.json").read_text(encoding="utf-8"))
    video, source = Path(manifest["file"]), Path(inputs["source_video"])
    probe, ffmpeg = rt["ffprobe"]["path"], rt["ffmpeg"]["path"]
    meta = json.loads(output([probe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)]))
    vs = next(s for s in meta["streams"] if s["codec_type"] == "video")
    audio = next(s for s in meta["streams"] if s["codec_type"] == "audio")
    assert (vs["width"], vs["height"], vs["r_frame_rate"], int(vs["nb_read_frames"])) == (1920, 1080, "30/1", 2118)
    assert abs(float(vs["duration"]) - 70.6) < .001
    assert abs(float(audio["duration"]) - 70.589002) < .001
    assert sha(video) == manifest["sha256"] and manifest["full_video"]
    assert all(sha(HERE / n) == h for n, h in manifest["hashes"].items())
    assert sha(source) == inputs["source_sha256"] == initial["source_sha256"]
    assert sha(inputs["v1_file"]) == inputs["v1_sha256"]
    assert sha(ROOT / "1.txt") == initial["script_sha256"]
    packets, pcm = [], []
    for path in [source, video]:
        rows = json.loads(output([probe, "-v", "error", "-select_streams", "a:0", "-show_packets", "-show_data_hash", "sha256",
                                  "-show_entries", "packet=pts,dts,duration,size,data_hash", "-of", "json", str(path)]))["packets"]
        packets.append(rows)
        pcm.append(output([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "hash", "-hash", "sha256", "-"]).strip())
    assert len(packets[0]) == len(packets[1]) == 3041 and packets[0] == packets[1]
    assert pcm[0] == pcm[1]
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(video), "-f", "null", "NUL"], capture_output=True, text=True, encoding="utf-8")
    assert decoded.returncode == 0 and not decoded.stderr.strip(), decoded.stderr
    cap = cv2.VideoCapture(str(video)); photo_checks = []
    for t, name in SAMPLES:
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * 30)); ok, frame = cap.read(); assert ok
        actual = frame[198:965, 88:1464]
        expected = cv2.resize(read_png(ROOT / "production_v1/assets" / (name + ".png")), (1392, 783))[8:-8, 8:-8]
        corr = similarity(actual, expected)
        assert corr > .97, (t, name, corr)
        photo_checks.append({"time": t, "asset": name, "correlation": round(corr, 6)})
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(44.9 * 30)); ok, frame = cap.read(); assert ok
    actual = frame[211:958, 105:1447]
    expected = cv2.resize(read_png(ROOT / "production_v1/assets/M08.png"), (1358, 763))[8:-8, 8:-8]
    corr = similarity(actual, expected); assert corr > .97, corr
    photo_checks.append({"time": 44.9, "asset": "M08 full comparison source", "correlation": round(corr, 6)})
    cap.set(cv2.CAP_PROP_POS_FRAMES, round(50.4 * 30)); ok, frame = cap.read(); assert ok
    for name, box, size in [("M08_front", (358, 221, 602, 949), (244, 728)), ("M01_front", (1280, 223, 1520, 947), (240, 724))]:
        x0, y0, x1, y1 = box
        corr = similarity(frame[y0:y1, x0:x1], cv2.resize(read_png(HERE / "assets" / (name + ".png")), size))
        assert corr > .97, (name, corr)
        photo_checks.append({"time": 50.4, "asset": name, "correlation": round(corr, 6)})
    cap.release()
    cap = cv2.VideoCapture(str(video)); n = 0; black, empty = [], []
    target = {round(t * 30): t for t in POSTERS}
    while True:
        ok, frame = cap.read()
        if not ok: break
        tiny = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (192, 108))
        if tiny.std() < 2: empty.append(n)
        if tiny.mean() < 6 and tiny.std() < 3: black.append(n)
        if n in target:
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(HERE / "preview" / f"encoded_{target[n]:05.2f}.jpg", quality=96)
        n += 1
    cap.release(); assert n == 2118 and not black and not empty
    for page in range(3):
        sheet = Image.new("RGB", (1440, 900), "#252825"); draw = ImageDraw.Draw(sheet)
        for j, t in enumerate(POSTERS[page * 9:(page + 1) * 9]):
            im = Image.open(HERE / "preview" / f"encoded_{t:05.2f}.jpg").convert("RGB")
            im.thumbnail((480, 270), Image.Resampling.LANCZOS); x, y = j % 3 * 480, j // 3 * 300
            sheet.paste(im, (x, y)); draw.text((x + 12, y + 278), f"ENCODED V2 | {t:.2f}s", fill="white")
        sheet.save(HERE / "preview" / f"encoded_contact_{page + 1:02d}.jpg", quality=95)
    for row in json.loads((ROOT / "analysis/assets_manifest.json").read_text(encoding="utf-8")):
        assert sha(row["file"]) == row["sha256"]
    for name, box in [("M08", (865, 40, 1320, 1400)), ("M01", (1050, 40, 1500, 1400))]:
        crop = Image.open(ROOT / "production_v1/assets" / (name + ".png")).convert("RGB").crop(box)
        assert crop.tobytes() == Image.open(HERE / "assets" / (name + "_front.png")).convert("RGB").tobytes()
    cache = json.loads(Path(manifest["static_cache_proof"]).read_text(encoding="utf-8"))
    render_folder = Path(manifest["render_directory"])
    for hold in cache["accepted_groups"]:
        assert sha(hold["source"]) == hold["png_sha256"]
        for number in [hold["frames"][0], hold["frames"][-1]]:
            assert sha(render_folder / "_frames" / f"{number:05d}.png") == hold["png_sha256"]
    delivery = ROOT / video.name
    assert not delivery.exists(), "Never overwrite a previous full version"
    shutil.copy2(video, delivery); assert sha(delivery) == sha(video)
    report = {"pass": True, "full_video": True, "file": str(video), "delivery": str(delivery), "sha256": sha(video),
              "width": 1920, "height": 1080, "fps": 30, "frames": n, "duration_seconds": 70.6,
              "source_audio_packets": 3041, "output_audio_packets": 3041, "original_aac_packets_and_timing_identical": True,
              "decoded_pcm_identical": True, "source_pcm_hash": pcm[0], "output_pcm_hash": pcm[1],
              "v1_preserved": True, "source_video_script_and_images_preserved": True,
              "decode_errors": [], "black_frames": black, "empty_frames": empty, "photo_sequence_checks": photo_checks,
              "front_crops_exact_original_pixels": True, "source_resolution": [1280, 720], "native_4k_claimed": False,
              "cached_frames_verified": cache["cached_frames"], "test_audio_used": False,
              "full_speed_human_listening_verified": False, "user_aesthetic_acceptance_claimed": False}
    (HERE / "output/final_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
