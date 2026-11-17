"""Validate the encoded movie, original audio, source integrity and image ordering."""
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
SAMPLES = [(5.8, "M09"), (8.9, "M10"), (10.8, "M11"),
           (15.5, "M02"), (18.8, "M03"), (20.8, "M04"), (22.0, "M05"),
           (23.7, "M06"), (25.2, "M07"), (35.0, "M19"), (36.8, "M24"),
           (38.4, "M23"), (44.8, "M08"), (50.8, "M01"), (56.2, "M18"), (61.1, "M17")]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def main():
    rt = json.loads((ROOT.parent / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "output/render_manifest.json").read_text(encoding="utf-8"))
    video, source = Path(manifest["file"]), ROOT / "原视频.mp4"
    baseline = json.loads((ROOT / "analysis/analysis_checks.json").read_text(encoding="utf-8"))
    probe, ffmpeg = rt["ffprobe"]["path"], rt["ffmpeg"]["path"]
    meta = json.loads(run([probe, "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)]))
    vs = next(s for s in meta["streams"] if s["codec_type"] == "video")
    aus = next(s for s in meta["streams"] if s["codec_type"] == "audio")
    assert (vs["width"], vs["height"], vs["r_frame_rate"], int(vs["nb_read_frames"])) == (1920, 1080, "30/1", 2118)
    assert float(aus["duration"]) >= 70.589 - 0.001
    assert sha(source) == baseline["source_sha256"]
    assert sha(ROOT / "1.txt") == baseline["script_sha256"]
    assert sha(video) == manifest["sha256"]
    assert sha(HERE / "comp.html") == manifest["composition_sha256"]
    assert sha(HERE / "data.js") == manifest["data_sha256"]
    packet_lists, pcm_hashes = [], []
    for path in [source, video]:
        packets = json.loads(run([probe, "-v", "error", "-select_streams", "a:0", "-show_packets",
                                  "-show_data_hash", "sha256", "-show_entries",
                                  "packet=pts,dts,duration,size,data_hash", "-of", "json", str(path)]))["packets"]
        packet_lists.append(packets)
        pcm_hashes.append(run([ffmpeg, "-v", "error", "-i", str(path), "-map", "0:a:0", "-c:a", "pcm_s16le",
                               "-f", "hash", "-hash", "sha256", "-"]).strip())
    assert packet_lists[0] == packet_lists[1], "Source AAC packets or timing changed"
    assert pcm_hashes[0] == pcm_hashes[1], "Decoded original speech changed"
    decoded = subprocess.run([ffmpeg, "-v", "error", "-i", str(video), "-f", "null", "NUL"], capture_output=True, text=True, encoding="utf-8")
    assert decoded.returncode == 0 and not decoded.stderr.strip(), decoded.stderr
    cap = cv2.VideoCapture(str(video))
    photo_checks = []
    for t, asset in SAMPLES:
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(t * 30)); ok, frame = cap.read(); assert ok
        crop = cv2.resize(cv2.cvtColor(frame[152:928, 96:1488], cv2.COLOR_BGR2GRAY), (192, 108))
        original = cv2.imdecode(np.frombuffer((HERE / "assets" / (asset + ".png")).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert original is not None
        original = cv2.resize(original, (1408, 792))[8:-8, 8:-8]
        target = cv2.resize(cv2.cvtColor(original, cv2.COLOR_BGR2GRAY), (192, 108))
        corr = float(np.corrcoef(crop.flatten(), target.flatten())[0, 1])
        photo_checks.append({"time": t, "asset": asset, "image_correlation": round(corr, 5)})
        assert corr > .97, f"Wrong photo, crop or corruption at {t}s / {asset}: {corr}"
    cap.release()
    cap = cv2.VideoCapture(str(video)); black, blank, count = [], [], 0
    sample_times = [0.8, 5.8, 10.8, 15.5, 18.8, 21.8, 25.2, 28.0, 35.0, 36.8, 38.4, 44.8, 50.8, 56.2, 59.0, 61.1, 63.1, 69.95]
    target_frames = {round(t * 30): t for t in sample_times}
    while True:
        ok, frame = cap.read()
        if not ok: break
        tiny = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (192, 108))
        if tiny.mean() < 6 and tiny.std() < 3: black.append(count)
        if tiny.std() < 2: blank.append(count)
        if count in target_frames:
            t = target_frames[count]
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(HERE / "preview" / f"encoded_{t:05.2f}.jpg", quality=95)
        count += 1
    cap.release()
    assert count == 2118 and not black and not blank
    for n in range(2):
        sheet = Image.new("RGB", (1440, 900), (24, 24, 24)); draw = ImageDraw.Draw(sheet)
        for j, t in enumerate(sample_times[n * 9:(n + 1) * 9]):
            im = Image.open(HERE / "preview" / f"encoded_{t:05.2f}.jpg").convert("RGB")
            im.thumbnail((480, 270), Image.Resampling.LANCZOS)
            x, y = j % 3 * 480, j // 3 * 300
            sheet.paste(im, (x, y)); draw.text((x + 10, y + 278), f"ENCODED | {t:.2f}s", fill="white")
        sheet.save(HERE / "preview" / f"encoded_contact_{n + 1:02d}.jpg", quality=94)
    for asset in json.loads((ROOT / "analysis/assets_manifest.json").read_text(encoding="utf-8")):
        assert sha(asset["file"]) == asset["sha256"]
    delivery = ROOT / video.name
    assert not delivery.exists(), "Never overwrite an existing delivery"
    shutil.copy2(video, delivery); assert sha(delivery) == sha(video)
    report = {"pass": True, "file": str(video), "delivery": str(delivery), "sha256": sha(video),
              "width": 1920, "height": 1080, "fps": 30, "frames": count, "duration_seconds": 70.6,
              "source_audio_packets": len(packet_lists[0]), "output_audio_packets": len(packet_lists[1]),
              "original_aac_packets_and_timing_identical": True, "decoded_pcm_identical": True,
              "source_pcm_hash": pcm_hashes[0], "output_pcm_hash": pcm_hashes[1],
              "source_video_and_script_unchanged": True, "all_original_images_unchanged": True,
              "full_decode_errors": [], "black_frames": black, "empty_frames": blank,
              "photo_sequence_checks": photo_checks, "source_resolution": [1280, 720],
              "native_4k_claimed": False, "full_speed_human_listening_verified": False,
              "aesthetic_acceptance_claimed": False}
    (HERE / "output/final_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
