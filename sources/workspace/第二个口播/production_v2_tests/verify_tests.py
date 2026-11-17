"""Verify test encodes, original-speech segment alignment, crops and V1 preservation."""
from pathlib import Path
import hashlib
import json
import subprocess
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    rt = json.loads((ROOT.parent / "enterprise_demo/runtime_status.json").read_text(encoding="utf-8"))
    manifest = json.loads((HERE / "output/test_render_manifest.json").read_text(encoding="utf-8"))
    inputs = json.loads((HERE / "input_checks.json").read_text(encoding="utf-8"))
    original = json.loads((ROOT / "analysis/analysis_checks.json").read_text(encoding="utf-8"))
    results = []
    for row in manifest["cases"]:
        video = Path(row["file"])
        assert sha(video) == row["sha256"]
        meta = json.loads(subprocess.run([rt["ffprobe"]["path"], "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
        vs = next(s for s in meta["streams"] if s["codec_type"] == "video")
        aus = next(s for s in meta["streams"] if s["codec_type"] == "audio")
        assert (vs["width"], vs["height"], vs["r_frame_rate"], int(vs["nb_read_frames"])) == (1920, 1080, "30/1", row["frames"])
        assert abs(float(aus["duration"]) - row["duration"]) < .025
        with wave.open(str(HERE / "assets" / f"speech_{row['case']}.wav"), "rb") as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (44100, 2, 2)
            expected = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64)
        pcm = subprocess.run([rt["ffmpeg"]["path"], "-v", "error", "-i", str(video), "-map", "0:a:0", "-c:a", "pcm_s16le", "-f", "s16le", "-"], capture_output=True, check=True).stdout
        actual = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
        n = min(len(actual), len(expected)); corr = float(np.corrcoef(expected[:n], actual[:n])[0, 1])
        assert corr > .98, f"Speech segment misalignment {row['case']}: {corr}"
        cap = cv2.VideoCapture(str(video)); count = 0; blank = []
        while True:
            ok, frame = cap.read()
            if not ok: break
            tiny = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (192, 108))
            if tiny.std() < 2: blank.append(count)
            count += 1
        cap.release(); assert count == row["frames"] and not blank
        results.append({"case": row["case"], "file": str(video), "pass": True, "frames": count,
                        "duration": row["duration"], "speech_pcm_correlation_zero_lag": round(corr, 7),
                        "audio_note": "One AAC re-encode for tests; aligned original speech, not byte-identical source AAC", "empty_frames": blank})
    summary = Path(manifest["summary"])
    assert sha(summary) == manifest["summary_sha256"]
    meta = json.loads(subprocess.run([rt["ffprobe"]["path"], "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(summary)], capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    vs = next(s for s in meta["streams"] if s["codec_type"] == "video")
    assert (vs["width"], vs["height"], int(vs["nb_read_frames"])) == (1920, 660, 591)
    assert abs(float(vs["duration"]) - 19.7) < .001
    assert len([s for s in meta["streams"] if s["codec_type"] == "audio"]) == 1
    selected = {"a": 2.4, "b": 6.8, "c": 5.7}
    contact = Image.new("RGB", (1440, 1530), "#252825")
    for i, (row, path) in enumerate(zip(manifest["cases"], manifest["comparisons"])):
        cap = cv2.VideoCapture(path); cap.set(cv2.CAP_PROP_POS_FRAMES, round(selected[row["case"]] * 30)); ok, frame = cap.read(); cap.release(); assert ok
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        im.save(HERE / "preview" / f"encoded_comparison_{row['case']}.jpg", quality=96)
        im.thumbnail((1440, 495), Image.Resampling.LANCZOS); contact.paste(im, (0, i * 510))
        cap = cv2.VideoCapture(row["file"]); cap.set(cv2.CAP_PROP_POS_FRAMES, round(selected[row["case"]] * 30)); ok, frame = cap.read(); cap.release(); assert ok
        Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(HERE / "preview" / f"encoded_test_{row['case']}.jpg", quality=96)
    contact.save(HERE / "preview/encoded_comparison_contact.jpg", quality=95)
    for crop in json.loads((HERE / "qa/crop_provenance.json").read_text(encoding="utf-8")):
        source = Image.open(HERE / crop["source"]).convert("RGB").crop(crop["box"])
        target = Image.open(HERE / crop["output"]).convert("RGB")
        assert source.size == target.size and source.tobytes() == target.tobytes()
    assert sha(inputs["v1_file"]) == inputs["v1_sha256"]
    assert sha(inputs["reference"]) == inputs["reference_sha256"]
    assert sha(ROOT / "原视频.mp4") == original["source_sha256"]
    assert sha(ROOT / "1.txt") == original["script_sha256"]
    for asset in json.loads((ROOT / "analysis/assets_manifest.json").read_text(encoding="utf-8")):
        assert sha(asset["file"]) == asset["sha256"]
    report = {"pass": True, "case_results": results, "summary": str(summary), "summary_frames": 591,
              "summary_duration": 19.7, "summary_size": [1920, 660], "comparison_has_single_audio_track": True,
              "v1_unchanged": True, "reference_unchanged": True, "source_video_and_script_unchanged": True,
              "all_original_images_unchanged": True,
              "front_crops_exact_original_pixels": True, "full_v2_completed": False,
              "human_full_speed_listening_verified": False, "user_aesthetic_acceptance_claimed": False}
    (HERE / "qa/final_test_qa.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
