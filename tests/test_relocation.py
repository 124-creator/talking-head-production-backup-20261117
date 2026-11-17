"""Temporary-directory regression tests; never applies to the original projects."""

from __future__ import annotations

import ast
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import relocate_workspace as relocation
import smoke_restored as smoke


class RelocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="talking-head-relocation-")
        self.root = Path(self.temporary.name) / "恢复 副本"
        (self.root / "workspace").mkdir(parents=True)
        self.root = self.root.resolve()
        (self.root / "skills/onetake").mkdir(parents=True)
        (self.root / "environment").mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative: str, data: str | bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        return path

    def directory_link(self, link: Path, target: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            # Windows junctions do not require the symlink privilege. Path.resolve
            # must also defend against these, not only Path.is_symlink().
            subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                           capture_output=True, check=True)
        self.assertEqual(link.resolve(), target.resolve())

    def test_default_plan_has_no_writes(self) -> None:
        original = json.dumps({"source": relocation.OLD_WORKSPACE + r"\第二个口播\原视频.mp4"}, ensure_ascii=False)
        path = self.write("workspace/input.json", original)
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        root, changes, report = relocation.build_plan(self.root)
        self.assertEqual(root, self.root.resolve())
        self.assertGreater(len(changes), 0)
        self.assertEqual(report["mode"], "plan")
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse((self.root / ".relocation").exists())
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(relocation.main([str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "plan")
        self.assertFalse((self.root / ".relocation").exists())

    def test_path_forms_and_specific_wechat_aliases(self) -> None:
        first = self.root / relocation.FIRST
        videos = relocation.OLD_STORAGE + "\\Video\\2026-11\\"
        inputs = {
            "windows": relocation.OLD_WORKSPACE + r"\第二个口播\原视频.mp4",
            "forward": relocation.OLD_WORKSPACE.replace("\\", "/") + "/第二个口播/原视频.mp4",
            "uri": "file:///" + relocation.OLD_WORKSPACE.replace("\\", "/") + "/第二个口播/原视频.mp4",
            "raw": videos + relocation.RAW_SOURCE_NAME,
            "old720": videos + "7c1fa1f1aaae6edc410a3c1471c65f4d.mp4",
            "approved": videos + "a7a87b4c54f8a1abe5efd6f6834decef_raw.mp4",
            "style": "file:///" + videos.replace("\\", "/") + "fd430e380a94fa855533d80b9f71fe1b_raw.mp4",
            "unrelated": "E:/other-project/source.mp4",
            "same_prefix": relocation.OLD_WORKSPACE + "_GitHub备份/repository/file.json",
            "historical_sha256": "93dfe4aeddead66652af44422e2b643a9b6f258deaf683874f700955b2e03bd1",
        }
        for index, name in enumerate(("c6f1c46e77e1dfcf177f979469073d2.png", "3240d4bc8609f9d5a923cc1c900df7e.png",
                                      "4f98b2f1ce21006ccbcd93b6954cdee.png", "63303cdc6b75415123b12c0590b4b7a.png"), 1):
            inputs[f"image{index}"] = relocation.OLD_STORAGE + "\\Temp\\" + name
        path = self.write("workspace/input.json", json.dumps(inputs, ensure_ascii=False, indent=2))
        relocation.apply_relocation(self.root)
        output = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(Path(output["windows"]), self.root / "workspace/第二个口播/原视频.mp4")
        self.assertEqual(output["forward"], (self.root / "workspace/第二个口播/原视频.mp4").as_posix())
        self.assertEqual(output["uri"], (self.root / "workspace").as_uri() + "/第二个口播/原视频.mp4")
        self.assertEqual(output["raw"], (first / "raw_v3/assets/source.mp4").as_posix())
        self.assertEqual(output["old720"], (first / "assets/source.mp4").as_posix())
        self.assertEqual(output["approved"], (self.root / "reference/approved_first.mp4").as_posix())
        self.assertEqual(output["style"], (self.root / "reference/style_reference.mp4").as_uri())
        for index in range(1, 5):
            self.assertEqual(output[f"image{index}"], (first / f"assets/image_{index:02d}.png").as_posix())
        for key in ("unrelated", "same_prefix", "historical_sha256"):
            self.assertEqual(output[key], inputs[key])

    def test_escaped_json_nested_text_and_file_uri(self) -> None:
        root = relocation.OLD_WORKSPACE
        text = "\n".join([root, root.replace("\\", "/"), root.replace("\\", "\\\\"),
                           "file:///" + root.replace("\\", "/")])
        changed = relocation.relocate_text(text, self.root, "workspace/note.txt")
        lines = changed.splitlines()
        self.assertEqual(lines[:3], [(self.root / "workspace").as_posix()] * 3)
        self.assertEqual(lines[3], (self.root / "workspace").as_uri())
        encoded = "file:///" + quote(root.replace("\\", "/"), safe="/:")
        self.assertEqual(relocation.relocate_text(encoded, self.root, "workspace/note.txt"),
                         (self.root / "workspace").as_uri())
        uri = "file:///" + relocation.OLD_STORAGE.replace("\\", "/").replace(" ", "%20") + "/Temp/c6f1c46e77e1dfcf177f979469073d2.png"
        self.assertEqual(relocation.relocate_text(uri, self.root, "workspace/note.txt"),
                         (self.root / relocation.FIRST / "assets/image_01.png").as_uri())

    def test_python_home_skill_model_and_derived_raw_source(self) -> None:
        source = "\n".join([
            "from pathlib import Path",
            "SKILL = Path.home()/'.codex'/'skills'/'onetake'",
            'SCRIPT = str(Path.home() / ".codex/skills/onetake/scripts/render.py")',
            "UNRELATED = Path.home() / 'Documents'",
            "MODEL = Path.home()/'.cache'/'huggingface'/'hub'/'models--Systran--faster-whisper-small'/'snapshots'/'" + relocation.SNAPSHOT + "'",
            "PROJECT = Path(__file__).resolve().parents[2]",
            "source = Path(original['sources'][0]['original']).with_name('" + relocation.RAW_SOURCE_NAME + "')",
        ])
        path = self.write(relocation.FIRST + "/raw_v3/prepare.py", source)
        asr = self.write("workspace/第二个口播/analysis/transcribe_local.py",
                         'from pathlib import Path\nMODEL = (\n Path.home() / ".cache/huggingface/hub/models--Systran--faster-whisper-small"\n'
                         ' / "snapshots/' + relocation.SNAPSHOT + '"\n)\nWORDS = "保留原始识别内容"\n')
        relocation.apply_relocation(self.root)
        changed = path.read_text(encoding="utf-8")
        ast.parse(changed)
        self.assertIn((self.root / "skills/onetake/scripts/render.py").as_posix(), changed)
        self.assertIn((self.root / "models/faster-whisper-small" / relocation.SNAPSHOT).as_posix(), changed)
        self.assertIn((self.root / relocation.FIRST / "raw_v3/assets/source.mp4").as_posix(), changed)
        self.assertNotIn(".with_name", changed)
        self.assertIn("UNRELATED = Path.home() / 'Documents'", changed)
        self.assertIn(".parents[2]", changed)
        ast.parse(asr.read_text(encoding="utf-8"))
        self.assertIn("保留原始识别内容", asr.read_text(encoding="utf-8"))
        self.assertNotIn("Path.home()", asr.read_text(encoding="utf-8"))

    def test_original_backup_journal_sha_and_repeat_apply(self) -> None:
        historical = "f" * 64
        original = (json.dumps({"original": relocation.OLD_WORKSPACE + "/file.txt", "sha256": historical}, ensure_ascii=False) + "\r\n").encode("utf-8")
        source = self.write("workspace/report.json", original)
        result = relocation.apply_relocation(self.root)
        self.assertGreater(result["applied_files"], 0)
        backup = self.root / ".relocation/originals/workspace/report.json"
        self.assertEqual(backup.read_bytes(), original)
        log = self.root / ".relocation/relocation_log.json"
        journal = json.loads(log.read_text(encoding="utf-8"))
        entry = next(item for item in journal["runs"][0]["changes"] if item["path"] == "workspace/report.json")
        self.assertEqual(entry["before_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(entry["after_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(json.loads(source.read_text(encoding="utf-8"))["sha256"], historical)
        self.assertEqual(journal["runs"][0]["status"], "complete")
        state = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        second = relocation.apply_relocation(self.root)
        self.assertEqual(second["applied_files"], 0)
        self.assertEqual(second["changed_files"], 0)
        self.assertEqual(state, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_runtime_rebuilt_without_claiming_a_live_browser(self) -> None:
        original = json.dumps({"ffmpeg": {"path": "C:/legacy/ffmpeg.exe", "available": True},
                               "browser": {"connected": True, "cdp_url": "http://127.0.0.1:9333"}})
        runtime = self.write(relocation.RUNTIME, original)
        self.write("runtimes/ffmpeg/bin/ffmpeg.exe", b"not-executed")
        self.write("runtimes/ffmpeg/bin/ffprobe.exe", b"not-executed")
        relocation.apply_relocation(self.root)
        data = json.loads(runtime.read_text(encoding="utf-8"))
        self.assertEqual(data["ffmpeg"]["path"], (self.root / "runtimes/ffmpeg/bin/ffmpeg.exe").as_posix())
        self.assertFalse(data["ffmpeg"]["verified_in_restored_environment"])
        self.assertFalse(data["browser"]["connected"])
        self.assertIsNone(data["browser"]["cdp_url"])
        self.assertEqual((self.root / ".relocation/originals" / relocation.RUNTIME).read_text(encoding="utf-8"), original)

    def test_binary_non_utf8_models_and_venvs_untouched(self) -> None:
        old = relocation.OLD_WORKSPACE.encode("utf-8")
        paths = [self.write("workspace/keep.bin", old), self.write("workspace/not_utf8.txt", b"\xff" + old),
                 self.write("models/faster-whisper-small/tokenizer.json", json.dumps({"text": relocation.OLD_WORKSPACE})),
                 self.write("environment/.venv-render/lib/foreign.py", "X=" + repr(relocation.OLD_WORKSPACE))]
        before = [path.read_bytes() for path in paths]
        result = relocation.apply_relocation(self.root)
        self.assertEqual([path.read_bytes() for path in paths], before)
        self.assertTrue(any("not UTF-8" in line for line in result["skipped"]))

    def test_linked_resources_do_not_write_outside_destination(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        target = outside / "outside.json"
        original = json.dumps({"path": relocation.OLD_WORKSPACE})
        target.write_text(original, encoding="utf-8")
        self.directory_link(self.root / "workspace/linked-directory", outside)
        result = relocation.apply_relocation(self.root)
        self.assertEqual(target.read_text(encoding="utf-8"), original)
        self.assertTrue(any("linked directory" in line for line in result["skipped"]))

    def test_backup_link_escape_is_rejected_before_source_write(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        self.directory_link(self.root / ".relocation", outside)
        original = json.dumps({"path": relocation.OLD_WORKSPACE})
        path = self.write("workspace/input.json", original)
        with self.assertRaises(ValueError):
            relocation.apply_relocation(self.root)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertEqual(list(outside.iterdir()), [])

    def test_python_and_json_destinations_with_quotes_are_safe(self) -> None:
        self.root = self.root / "quote's and double\"" if os.name != "nt" else self.root / "quote's"
        (self.root / "workspace").mkdir(parents=True)
        path = self.write("workspace/config.py", "from pathlib import Path\nSOURCE = " + repr(relocation.OLD_WORKSPACE + "/a.mp4") + "\n")
        data = self.write("workspace/config.json", json.dumps({"source": relocation.OLD_WORKSPACE + "/a.mp4"}))
        relocation.apply_relocation(self.root)
        ast.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(data.read_text(encoding="utf-8"))["source"], (self.root / "workspace/a.mp4").as_posix())

    def test_powershell_skill_assignment_and_utf8_bom_preserved(self) -> None:
        ps = self.write("environment/install.ps1", "$skill = Join-Path $HOME '.codex\\skills\\onetake'\r\n")
        data = b"\xef\xbb\xbf" + (relocation.OLD_WORKSPACE + "/source.mp4\r\n").encode("utf-8")
        bom = self.write("workspace/bom.txt", data)
        relocation.apply_relocation(self.root)
        self.assertIn((self.root / "skills/onetake").as_posix(), ps.read_text(encoding="utf-8"))
        self.assertNotIn("Join-Path", ps.read_text(encoding="utf-8"))
        self.assertTrue(bom.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertTrue(bom.read_bytes().endswith(b"\r\n"))

    def test_smoke_environment_records_python_and_has_no_import_side_effect(self) -> None:
        state = {p.relative_to(self.root) for p in self.root.rglob("*")}
        information = smoke.environment_info()
        self.assertEqual(information["executable"], sys.executable)
        self.assertIn("prefix", information)
        self.assertIn("base_prefix", information)
        self.assertEqual(state, {p.relative_to(self.root) for p in self.root.rglob("*")})

    def test_smoke_requires_isolated_venv_unless_explicit_diagnostic(self) -> None:
        information = {"windows_x64": True, "isolated_venv": False}
        with patch.object(smoke, "environment_info", return_value=information), \
             patch.object(smoke, "verify_pngs", return_value={}) as pngs, \
             patch.object(smoke, "verify_masters", return_value=[]) as masters, \
             patch.object(smoke, "verify_browser", return_value={}) as browser:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(smoke.main([str(self.root)]), 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "failed")
            pngs.assert_not_called()
            masters.assert_not_called()
            browser.assert_not_called()
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(smoke.main([str(self.root), "--allow-system-python"]), 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "diagnostic_passed")
            browser.assert_called_once()

    def test_skip_browser_is_only_a_partial_diagnostic(self) -> None:
        with patch.object(smoke, "environment_info", return_value={"windows_x64": True, "isolated_venv": True}), \
             patch.object(smoke, "verify_pngs", return_value={}), \
             patch.object(smoke, "verify_masters", return_value=[]), \
             patch.object(smoke, "verify_browser", return_value={}) as browser:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(smoke.main([str(self.root), "--skip-browser"]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["status"], "diagnostic_passed")
            self.assertEqual(report["browser"]["status"], "skipped")
            browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
