#!/usr/bin/env python3
import os
import sys
import html
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


DEFAULT_BASE = Path.home() / "Desktop" / "Resize-helper"
DEFAULT_IN_PATH = DEFAULT_BASE / "IN"
DEFAULT_OUT_PATH = DEFAULT_BASE / "Out" 

DEFAULT_IN = str(DEFAULT_IN_PATH)
DEFAULT_OUT = str(DEFAULT_OUT_PATH)

DEFAULT_IN_PATH.mkdir(parents=True, exist_ok=True)
DEFAULT_OUT_PATH.mkdir(parents=True, exist_ok=True)


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".gif", ".heic", ".heif"}

STATE = {
    "in_dir": DEFAULT_IN,
    "out_dir": DEFAULT_OUT,
    "mode": "pad",
    "bg": "white",
    "quality": "90",
    "rows": [{"w": "", "h": "", "dpi": "75"} for _ in range(5)],
}

def resource_base() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent

def find_ffmpeg():
    env = os.environ.get("FFMPEG_PATH")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env

    bundled = resource_base() / "bin" / "ffmpeg"
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)

    for c in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c

    return shutil.which("ffmpeg")

def run_cmd(cmd):
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        err = p.stderr.strip() or "unknown error"
        raise RuntimeError(f"{err}  |  cmd: {' '.join(cmd)}")

def qscale_from_quality(q100: int) -> int:
    q100 = max(0, min(100, q100))
    qv = round(31 - (q100 / 100.0) * 29)  # 2(best)..31(worst)
    return int(max(2, min(31, qv)))

def filter_complex(mode: str, w: int, h: int, bg: str) -> str:
    bgsrc = f"color=c={bg}:s={w}x{h}[bg]"
    if mode == "pad":
        fg = (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,format=rgba[fg]"
        )
    elif mode == "crop":
        fg = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=rgba[fg]"
    else:
        fg = f"[0:v]scale={w}:{h},format=rgba[fg]"
    out = "[bg][fg]overlay=0:0,format=rgb24[out]"
    return f"{bgsrc};{fg};{out}"

def convert_all(in_dir, out_dir, jobs, mode, bg, quality100):
    logs = []
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("ffmpeg nicht gefunden. (Erwartet z.B. /opt/homebrew/bin/ffmpeg)")
    sips = "/usr/bin/sips"
    if not (os.path.isfile(sips) and os.access(sips, os.X_OK)):
        raise RuntimeError("sips nicht gefunden (sollte auf macOS vorhanden sein).")

    exiftool = shutil.which("exiftool")  # optional

    in_path = Path(in_dir).expanduser()
    out_path = Path(out_dir).expanduser()
    if not in_path.is_dir():
        raise RuntimeError(f"Input-Ordner existiert nicht: {in_path}")
    out_path.mkdir(parents=True, exist_ok=True)

    files = [p for p in sorted(in_path.iterdir()) if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]
    if not files:
        return ["Keine unterstützten Bilddateien im Input gefunden."]

    total = len(files) * len(jobs)
    done = 0
    qv = qscale_from_quality(int(quality100))

    for infile in files:
        base = infile.stem
        for (w, h, dpi) in jobs:
            out_sub = out_path / f"{w}x{h}px"
            out_sub.mkdir(parents=True, exist_ok=True)
            outfile = out_sub / f"{base}.jpg"

            try:
                fc = filter_complex(mode, w, h, bg)

                run_cmd([
                    ffmpeg,
                    "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(infile),
                    "-filter_complex", fc,
                    "-map", "[out]",
                    "-frames:v", "1",
                    "-q:v", str(qv),
                    str(outfile)
                ])

                run_cmd([
                    sips,
                    "--setProperty", "dpiWidth", str(dpi),
                    "--setProperty", "dpiHeight", str(dpi),
                    str(outfile)
                ])

                if exiftool:
                    try:
                        run_cmd([
                            exiftool,
                            "-overwrite_original",
                            f"-XResolution={dpi}",
                            f"-YResolution={dpi}",
                            "-ResolutionUnit=inches",
                            f"-JFIF:XResolution={dpi}",
                            f"-JFIF:YResolution={dpi}",
                            "-JFIF:ResolutionUnit=inches",
                            str(outfile)
                        ])
                    except Exception:
                        pass

                done += 1
                logs.append(f"[{done}/{total}] OK  {infile.name} -> {w}x{h}px @ {dpi}dpi")
            except Exception as e:
                done += 1
                logs.append(f"[{done}/{total}] FAIL {infile.name} -> {w}x{h}px @ {dpi}dpi  |  {e}")

    logs.append("Fertig.")
    return logs

def render_form(message=""):
    def esc(s): return html.escape(s or "")
    def sel(v): return "selected" if STATE["mode"] == v else ""

    rows_html = ""
    for i, r in enumerate(STATE["rows"], start=1):
        rows_html += (
            "<tr>"
            f"<td><input class='small' type='text' name='w{i}' value='{esc(r['w'])}'></td>"
            f"<td><input class='small' type='text' name='h{i}' value='{esc(r['h'])}'></td>"
            f"<td><input class='small' type='text' name='dpi{i}' value='{esc(r['dpi'] or '75')}'></td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>Resize → JPG helper by RA-moon</title>

<script>
function openExternal(url){{
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_url){{
    window.pywebview.api.open_url(url);
  }} else {{
    window.open(url, "_blank");
  }}
  return false;
}}
</script>

<style>
body{{font-family:-apple-system,system-ui,Segoe UI,Roboto,Arial;margin:18px}}
input[type=text]{{width:660px;padding:6px}} select{{padding:6px}}
table{{border-collapse:collapse;margin-top:10px}}
th,td{{border:1px solid #ddd;padding:8px}} th{{background:#f6f6f6}}
.small{{width:120px!important}} .btn{{padding:10px 16px;font-size:14px}}
.msg{{margin:8px 0;color:#333}}
.footer {{ margin-top: 14px; font-size: 12px; color: #777; }}
.footer a {{ color: inherit; text-decoration: underline; }}
</style></head><body>
<h3>Resize → JPG helper by RA-moon</h3>
<div class="msg">{esc(message)}</div>

<form method="POST" action="/convert">
<div><div>Input folder</div><input type="text" name="in_dir" value="{esc(STATE['in_dir'])}"></div>
<div style="margin-top:10px;"><div>Output folder</div><input type="text" name="out_dir" value="{esc(STATE['out_dir'])}"></div>

<div style="margin-top:10px;">
<label>Mode </label>
<select name="mode">
<option value="pad" {sel("pad")}>pad</option>
<option value="crop" {sel("crop")}>crop</option>
<option value="stretch" {sel("stretch")}>stretch</option>
</select>
&nbsp;&nbsp;<label>BG </label><input class="small" type="text" name="bg" value="{esc(STATE['bg'])}">
&nbsp;&nbsp;<label>JPG quality (0–100) </label><input class="small" type="text" name="quality" value="{esc(STATE['quality'])}">
</div>

<table>
<tr><th>Width (px)</th><th>Height (px)</th><th>DPI</th></tr>
{rows_html}
</table>

<div style="margin-top:10px;"><button class="btn" type="submit">Convert</button></div>
</form>
<div class="footer">© 2026 <a href="https://github.com/RA-moon" onclick="return openExternal(this.href)">RA-moon</a></div>
</body></html>
"""

def render_result(logs):
    log_text = html.escape("\n".join(logs))
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Result</title>

<script>
function openExternal(url){{
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_url){{
    window.pywebview.api.open_url(url);
  }} else {{
    window.open(url, "_blank");
  }}
  return false;
}}
</script>
<style>
body{{font-family:-apple-system,system-ui,Segoe UI,Roboto,Arial;margin:18px}}
pre{{background:#111;color:#eee;padding:14px;white-space:pre-wrap}}
a{{display:inline-block;margin:10px 0}}
.footer {{ margin-top: 14px; font-size: 12px; color: #777; }}
.footer a {{ color: inherit; text-decoration: underline; display:inline; margin:0; }}
</style></head><body>
<a href="/">← Back</a>
<pre>{log_text}</pre>
<div class="footer">© 2026 <a href="https://github.com/RA-moon" onclick="return openExternal(this.href)">RA-moon</a></div>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send(200, render_form(""))
        else:
            self._send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/convert":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        data = parse_qs(raw, keep_blank_values=True)

        def get1(k, default=""):
            v = data.get(k, [""])
            return (v[0] if v else "") or default

        in_dir = get1("in_dir", DEFAULT_IN).strip()
        out_dir = get1("out_dir", DEFAULT_OUT).strip()
        mode = get1("mode", "pad").strip()
        bg = get1("bg", "white").strip() or "white"
        quality = get1("quality", "90").strip() or "90"

        STATE["in_dir"] = in_dir
        STATE["out_dir"] = out_dir
        STATE["mode"] = mode if mode in ("pad", "crop", "stretch") else "pad"
        STATE["bg"] = bg
        STATE["quality"] = quality

        if not quality.isdigit() or not (0 <= int(quality) <= 100):
            self._send(400, render_form("JPG quality muss 0–100 sein."))
            return

        jobs = []
        rows = []
        for i in range(1, 6):
            w = get1(f"w{i}", "").strip()
            h = get1(f"h{i}", "").strip()
            dpi = get1(f"dpi{i}", "75").strip() or "75"
            rows.append({"w": w, "h": h, "dpi": dpi})
            if w == "" and h == "":
                continue
            if w == "" or h == "":
                self._send(400, render_form("In jeder ausgefüllten Zeile müssen Width und Height gesetzt sein."))
                return
            if not (w.isdigit() and h.isdigit() and dpi.isdigit()):
                self._send(400, render_form("Width/Height/DPI müssen ganze Zahlen sein."))
                return
            jobs.append((int(w), int(h), int(dpi)))

        STATE["rows"] = rows

        if not jobs:
            self._send(400, render_form("Bitte mindestens eine Zeile ausfüllen."))
            return

        try:
            logs = convert_all(in_dir, out_dir, jobs, STATE["mode"], bg, int(quality))
            self._send(200, render_result(logs))
        except Exception as e:
            self._send(500, render_result([f"ERROR: {e}"]))

    def log_message(self, fmt, *args):
        return

    def _send(self, code, body, content_type="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

def start_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


class Api:
    def open_url(self, url: str) -> bool:
        try:
            webbrowser.open(url)
            return True
        except Exception:
            return False

def main():
    import webview
    httpd, port = start_server()
    url = f"http://127.0.0.1:{port}/"
    api = Api()
    webview.create_window(
        "Resize → JPG helper by RA-moon",
        url,
        width=900,
        height=620,
        resizable=True,
        js_api=api,
    )
    try:
        webview.start()
    finally:
        try: httpd.shutdown()
        except Exception: pass

if __name__ == "__main__":
    main()
