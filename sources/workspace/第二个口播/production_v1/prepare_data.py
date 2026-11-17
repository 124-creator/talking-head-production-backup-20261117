"""Package reviewed photo cues and subtitles without changing any source media."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROWS = [
    (5.32, 8.20, "M09", "真实感 / 对照样图", "01 / 03", "光照\n材质", "办公室样图\n先看整体观感"),
    (8.20, 9.84, "M10", "真实感 / 对照样图", "02 / 03", "皮肤\n质感", "另一组光照\n对照观察"),
    (9.84, 13.20, "M11", "真实感 / 对照样图", "03 / 03", "油亮\n过曝", "网球场样图\n观察高光"),
    (14.54, 17.22, "M02", "真实感 / 5.5 人像", "01 / 06", "自然\n人像", "室内侧光\n保留原始纹理"),
    (17.22, 19.90, "M03", "真实感 / 5.5 人像", "02 / 06", "皮肤\n纹理", "近景观察\n眼下与脸颊"),
    (19.90, 21.24, "M04", "真实感 / 5.5 人像", "03 / 06", "光影\n过渡", "室内柔光\n明暗层次"),
    (21.24, 22.68, "M05", "真实感 / 5.5 人像", "04 / 06", "室外\n光照", "网球场\n侧向日光"),
    (22.68, 24.50, "M06", "真实感 / 5.5 人像", "05 / 06", "发丝\n细节", "马尾与侧光\n保持原图"),
    (24.50, 26.62, "M07", "真实感 / 5.5 人像", "06 / 06", "空间\n层次", "球拍前景\n室外人像"),
    (34.26, 36.02, "M19", "改图能力 / 三视图", "01 / 03", "改\n三视图", "正面 · 侧面 · 背面\n完整展示"),
    (36.02, 37.12, "M24", "改图能力 / 换服装", "02 / 03", "换\n服装", "衬衫裤装 → 旗袍\n观察服装变化"),
    (37.12, 39.66, "M23", "改图能力 / 提供的分镜样例", "03 / 03", "改\n分镜", "按所供样图展示\n保留原始版式"),
    (39.66, 48.36, "M08", "三视图 / 旧版样图", "4.5", "旧版\n比例", "完整全身\n观察头身关系"),
    (48.36, 55.50, "M01", "三视图 / 5.5 样图", "5.5", "新版\n比例", "同类样图对照\n非定量测量"),
    (55.50, 60.50, "M18", "群像 / 6461 样图", "01 / 02", "群像\n表现", "先看完整合照\n再观察局部"),
    (60.50, 63.82, "M17", "群像 / 5921 样图", "02 / 02", "多人\n同框", "来自同一张原图\n观察面部多样性"),
]

photos = [
    {"start": s, "end": e, "id": image, "section": section, "counter": counter,
     "title": title, "note": note, "group": image in ("M17", "M18")}
    for s, e, image, section, counter, title, note in ROWS
]
subtitles = json.loads((HERE / "subtitles.json").read_text(encoding="utf-8"))
assert len(photos) == 16
assert all((HERE / "assets" / (row["id"] + ".png")).exists() for row in photos)
assert all(a["end"] <= b["start"] for a, b in zip(subtitles, subtitles[1:]))
assert max(len(row["text"]) for row in subtitles) <= 24
data = {"photos": photos, "subtitles": subtitles}
(HERE / "data.js").write_text("window.DATA=" + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
(HERE / "qa" / "authored_cues.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Packaged {len(photos)} photo cues and {len(subtitles)} subtitles")
