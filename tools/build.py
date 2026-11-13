#!/usr/bin/env python3
"""組出 dist/：頁面 src/app.html → dist/index.html，資料 data/bus.json → dist/bus.json。"""
import pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
shutil.copyfile(ROOT / "src" / "app.html", DIST / "index.html")
shutil.copyfile(ROOT / "data" / "bus.json", DIST / "bus.json")
(DIST / ".nojekyll").write_text("")
print("dist/index.html", (DIST / "index.html").stat().st_size, "bytes; dist/bus.json", (DIST / "bus.json").stat().st_size, "bytes")
