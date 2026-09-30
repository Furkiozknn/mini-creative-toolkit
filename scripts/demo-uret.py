#!/usr/bin/env python3
"""Regenerate the README terminal demo from real command output.

    uv sync
    uv run python scripts/demo-uret.py [output-dir]      # default: docs/demo

Nothing on screen is typed by hand. Each command below runs in a scratch
folder against the `mct` installed in this environment; its exit code and
everything it printed are recorded, and the terminal page replays that record
with a typing animation. `komutlar.txt` is the same record as plain text
(command, output, exit code, date).

The only file that is not the toolkit's own output is `photo.jpg`: a
synthetic 1600x1200 picture with EXIF and GPS tags written by `make_photo()`
below, so the demo never shows a real person's photo or location.

Files written:
    komutlar.txt      the record
    demo.html         the replay; add ?dikey for the 1080x1920 layout
    demo.mp4/.gif     landscape recording   } only if node + playwright + ffmpeg
    demo-dikey.mp4    vertical recording    } are available (scripts/demo-kayit.js)

`--kurulum` also times a cold `uvx --from git+... mct --version` with an empty
uv cache and writes kurulum.txt. It needs the network and GitHub.

The look is the FRK-OS terminal scene of the daily videos (sosyal/uret/tema.mjs,
theme "klasik"): black #0e0d0b, cream #f1ece2, yellow #ffc21a, JetBrains Mono
(SIL OFL 1.1, assets/yazi/).
"""
from __future__ import annotations

import base64
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The pipeline is `set -o pipefail`, so `| grep` reports mct's own exit code.
COMMANDS = [
    "mct --version",
    'mct inspect photo.jpg | grep -E "format|width|height|has_exif|network"',
    "mct strip-metadata photo.jpg -o clean.jpg",
    'mct inspect clean.jpg | grep -E "has_exif|network"',
    "python mcp_probe.py photo.jpg",
]


def bash() -> str:
    found = shutil.which("bash")
    if not found:
        sys.exit("bash is needed to run the demo commands (Git Bash on Windows).")
    return found


def make_photo(path: Path) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1600, 1200), (30, 60, 110))
    draw = ImageDraw.Draw(image)
    for x in range(0, 1600, 80):
        draw.line([(x, 0), (1600 - x, 1200)], fill=(255, 194, 26), width=6)
    draw.ellipse((500, 300, 1100, 900), fill=(241, 236, 226))
    exif = Image.Exif()
    exif[0x010F] = "DemoCam"
    exif[0x0110] = "X100"
    exif[0x0132] = "2026:09:30 10:00:00"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (41.0, 0.0, 30.0), "E", (29.0, 0.0, 0.0)
    image.save(path, exif=exif, quality=90)


def run_all(workdir: Path) -> list[dict]:
    make_photo(workdir / "photo.jpg")
    shutil.copy(ROOT / "scripts" / "mcp_probe.py", workdir / "mcp_probe.py")
    # The environment this script runs in provides `mct` and `python`.
    scripts = str(Path(sys.executable).parent)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", NO_COLOR="1", COLUMNS="100",
               PATH=scripts + os.pathsep + os.environ["PATH"],
               MCT_OUTPUT_DIR=str(workdir / "output"))
    env.pop("PYTHONPATH", None)
    record = []
    for command in COMMANDS:
        started = time.time()
        done = subprocess.run(
            [bash(), "-c", "set -o pipefail; " + command],
            cwd=workdir, env=env, capture_output=True, encoding="utf-8", errors="replace",
        )
        output = (done.stdout + done.stderr).replace("\r", "").rstrip()
        # The scratch folder is a temp path that means nothing to a reader.
        output = output.replace(str(workdir), "~").replace(str(workdir).replace("\\", "/"), "~")
        record.append({"k": command, "c": output, "kod": done.returncode,
                       "sure": round(time.time() - started, 2)})
    return record


def write_record(out: Path, record: list[dict], version: str) -> None:
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        "# mini-creative-toolkit terminal demo: real commands, real output",
        f"# tarih: {now}",
        f"# surum: {version} (uv sync ile kuruldu, ortamdaki mct)",
        "# photo.jpg: scripts/demo-uret.py make_photo() ile uretilen SENTETIK resim (EXIF + GPS etiketli), gercek fotograf degil",
        "# her komut bash -c 'set -o pipefail; ...' ile bos bir klasorde kosuldu; hicbir cikti satiri elle yazilmadi",
        "# '~' = o gecici klasorun yolu (okunabilirlik icin yer degistirildi)",
        "",
    ]
    for item in record:
        lines.append("$ " + item["k"])
        if item["c"]:
            lines.append(item["c"])
        lines.append(f"[cikis kodu {item['kod']}] ({item['sure']:.2f} s)")
        lines.append("")
    (out / "komutlar.txt").write_text("\n".join(lines), encoding="utf-8", newline="\n")


PAGE = r"""<!doctype html><html lang="en"><meta charset="utf-8"><title>mini-creative-toolkit demo</title>
<style>
@font-face{font-family:JB;font-weight:400;src:url(data:font/ttf;base64,__FONT400__) format("truetype")}
@font-face{font-family:JB;font-weight:700;src:url(data:font/ttf;base64,__FONT700__) format("truetype")}
:root{--zemin:#0e0d0b;--panel:#14120e;--krem:#f1ece2;--sari:#ffc21a;--sonuk:#b6ae9d;--mercan:#ff4d6d;--turuncu:#ff7a1a;--cam:#19d3e6}
html,body{margin:0;height:100%;background:var(--zemin)}
body{display:flex;align-items:center;justify-content:center;background-image:linear-gradient(rgba(241,236,226,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(241,236,226,.045) 1px,transparent 1px);background-size:48px 48px}
.p{display:flex;flex-direction:column;width:1120px;height:640px;box-sizing:border-box;background:var(--panel);border:1px solid #3a352b;border-left:6px solid var(--sari);border-radius:8px;padding:22px 28px;font:400 20px/1.5 JB,Consolas,monospace;color:var(--krem);overflow:hidden;position:relative}
.b{font:700 13px JB,monospace;letter-spacing:.12em;color:var(--sari);margin:0 0 14px;text-transform:uppercase}
.y{color:var(--sari);font-weight:700}.d{color:var(--sonuk)}.k{color:var(--mercan)}.t{color:var(--turuncu)}.c{color:var(--cam)}
.w{flex:1;overflow:hidden;min-height:0}
pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
.im{display:inline-block;width:11px;height:22px;background:var(--sari);vertical-align:-4px;margin-left:2px}
body.v .p{width:1040px;height:1760px;font-size:24px;padding:36px 36px}
body.v .b{display:none}
body.v .im{width:13px;height:28px;vertical-align:-6px}
@media (prefers-reduced-motion:reduce){.im{display:none}}
</style>
<div class="p"><div class="b">mini-creative-toolkit &middot; real commands, real output</div><div class="w"><pre id="t" aria-live="off"></pre></div></div>
<script>
const DIKEY=location.search.includes("dikey");
if(DIKEY)document.body.classList.add("v");
const K=__DATA__;
const HIZ=30; // ms per typed character
let olay=[],t=700;
for(const x of K){
  olay.push({t,tip:"komut",k:x.k}); t+=x.k.length*HIZ+300;
  const s=x.c?x.c.split("\n"):[];
  const adim=s.length>8?70:200;
  for(const l of s){olay.push({t,tip:"satir",l});t+=adim}
  t+=s.length?800:500;
}
const el=document.getElementById("t");
const esc=s=>s.replace(/&/g,"&amp;").replace(/</g,"&lt;");
// Colour is presentation only: it never changes a character.
function boya(s){
  s=esc(s);
  s=s.replace(/(network[:=] ?)(none)/g,'$1<span class="c">$2</span>');
  s=s.replace(/(has_exif[:=] ?)(True)/g,'$1<span class="k">$2</span>');
  s=s.replace(/(has_exif[:=] ?)(False)/g,'$1<span class="c">$2</span>');
  s=s.replace(/(removed_exif[:=] ?)(True)/g,'$1<span class="y">$2</span>');
  return s;
}
const t0=performance.now();
function ciz(){
  const now=performance.now()-t0;let g="";
  for(const o of olay){
    if(o.t>now)break;
    if(o.tip==="komut"){const n=Math.min(o.k.length,Math.floor((now-o.t)/HIZ));g+='<span class="y">$ </span>'+esc(o.k.slice(0,n))+(n<o.k.length?'<span class="im"></span>':"")+"\n"}
    else g+='<span class="d">'+boya(o.l)+"</span>\n";
  }
  if(now>olay[olay.length-1].t+300)g+='<span class="y">$ </span><span class="im"></span>';
  el.innerHTML=g;
  el.style.marginTop=Math.min(0,el.parentNode.clientHeight-el.getBoundingClientRect().height)+"px";
  requestAnimationFrame(ciz);
}
window.__bitis=olay[olay.length-1].t+1500;
ciz();
</script></html>
"""


def write_pages(out: Path, record: list[dict]) -> None:
    data = json.dumps([{"k": r["k"], "c": r["c"]} for r in record], ensure_ascii=False)
    fonts = ROOT / "assets" / "yazi"

    def embed(name: str) -> str:
        return base64.b64encode((fonts / name).read_bytes()).decode()

    html = (PAGE.replace("__DATA__", data)
            .replace("__FONT400__", embed("JetBrainsMono-Regular.ttf"))
            .replace("__FONT700__", embed("JetBrainsMono-Bold.ttf")))
    # One page: landscape by default, 1080x1920 with `?dikey`. Fonts are embedded
    # (assets/yazi, SIL OFL 1.1), so it plays from file:// with nothing beside it.
    (out / "demo.html").write_text(html, encoding="utf-8", newline="\n")


def record_video(out: Path) -> None:
    recorder = Path(__file__).with_name("demo-kayit.js")
    if not (shutil.which("node") and shutil.which("ffmpeg") and recorder.exists()):
        print("node/ffmpeg not found: wrote komutlar.txt and the html page only.")
        return
    subprocess.run(["node", str(recorder), str(out)], check=True)


def measure_install(out: Path) -> None:
    """Cold `uvx` install, with an empty uv cache, timed."""
    uvx = shutil.which("uvx")
    if not uvx:
        print("uvx not found: skipping the install timing.")
        return
    cache = tempfile.mkdtemp(prefix="mct-uv-")
    env = dict(os.environ, UV_CACHE_DIR=cache, PYTHONIOENCODING="utf-8")
    command = [uvx, "--from", "git+https://github.com/Furkiozknn/mini-creative-toolkit", "mct", "--version"]
    rows = []
    for label in ("cold (empty uv cache)", "warm (same cache)"):
        started = time.time()
        done = subprocess.run(command, env=env, capture_output=True, encoding="utf-8", errors="replace")
        rows.append(f"{label}: {time.time() - started:.2f} s, exit {done.returncode}, "
                    f"output {done.stdout.strip()!r}")
    shutil.rmtree(cache, ignore_errors=True)
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    (out / "kurulum.txt").write_text(
        "# uvx --from git+https://github.com/Furkiozknn/mini-creative-toolkit mct --version\n"
        f"# tarih: {stamp}\n" + "\n".join(rows) + "\n",
        encoding="utf-8", newline="\n",
    )
    print("\n".join(rows))


def main(argv: list[str]) -> int:
    flags = [a for a in argv if a.startswith("--")]
    args = [a for a in argv if not a.startswith("--")]
    out = Path(args[0]).resolve() if args else ROOT / "docs" / "demo"
    out.mkdir(parents=True, exist_ok=True)
    if not shutil.which("mct", path=str(Path(sys.executable).parent)):
        sys.exit("mct is not installed in this environment: run `uv sync`, then `uv run python scripts/demo-uret.py`.")
    from mini_creative_toolkit import __version__

    with tempfile.TemporaryDirectory(prefix="mct-demo-") as work:
        record = run_all(Path(work))
    write_record(out, record, __version__)
    write_pages(out, record)
    if "--kurulum" in flags:
        measure_install(out)
    if "--sadece-kayit" not in flags:
        record_video(out)
    print(f"demo: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
