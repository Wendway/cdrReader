"""A small local CDR-to-PDF viewer powered by Inkscape."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import subprocess
import tempfile
import webbrowser


HOST = "127.0.0.1"
PORT = 8765
MAX_UPLOAD = 100 * 1024 * 1024


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CDR Reader</title><style>
:root{font:16px system-ui,sans-serif;color:#182230;background:#f4f6f8}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;flex-direction:column}
header{background:#fff;border-bottom:1px solid #dce2e8;padding:16px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}h1{font-size:20px;margin:0 auto 0 0}
button,.pick{border:0;border-radius:8px;background:#1769e0;color:white;padding:10px 16px;font:inherit;cursor:pointer}.pick input{display:none}button:disabled{opacity:.55;cursor:wait}
#status{color:#536273;font-size:14px}main{flex:1;padding:18px;display:flex;min-height:0}#viewer{width:100%;min-height:65vh;border:1px solid #dce2e8;border-radius:10px;background:#fff;display:grid;place-items:center;overflow:hidden}
#viewer iframe{width:100%;height:calc(100vh - 120px);border:0}#empty{text-align:center;color:#536273;padding:30px}#empty strong{display:block;color:#182230;font-size:20px;margin-bottom:8px}
</style></head><body><header><h1>CDR Reader</h1><label class="pick">Open a CDR file<input id="file" type="file" accept=".cdr,application/octet-stream"></label><span id="status">Files are processed on this computer.</span></header>
<main><section id="viewer"><div id="empty"><strong>View a CorelDRAW file</strong>Choose a .cdr file to convert it to a viewable PDF.</div></section></main>
<script>const input=document.querySelector('#file'),status=document.querySelector('#status'),viewer=document.querySelector('#viewer');let currentUrl;
input.addEventListener('change',async()=>{const file=input.files[0];if(!file)return;status.textContent='Converting '+file.name+'…';input.disabled=true;try{const data=new FormData();data.append('file',file);const response=await fetch('/convert',{method:'POST',body:data});if(!response.ok){const msg=await response.text();throw new Error(msg)}const blob=await response.blob();if(currentUrl)URL.revokeObjectURL(currentUrl);currentUrl=URL.createObjectURL(blob);viewer.innerHTML='';const frame=document.createElement('iframe');frame.title='Converted CDR document';frame.src=currentUrl;viewer.append(frame);status.textContent=file.name}catch(error){status.textContent=error.message;viewer.innerHTML='<div id="empty"><strong>Could not open this file</strong>'+escapeHtml(error.message)+'</div>'}finally{input.disabled=false;input.value=''}});
function escapeHtml(s){const e=document.createElement('div');e.textContent=s;return e.innerHTML}</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        body = PAGE.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/convert":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD + 1024 * 1024:
            self.reply(413, b"File is empty or exceeds the 100 MB limit.", "text/plain")
            return
        content_type = self.headers.get("Content-Type", "")
        boundary = content_type.partition("boundary=")[2].encode()
        if not boundary:
            self.reply(400, b"Expected a multipart file upload.", "text/plain")
            return
        payload = self.rfile.read(length)
        marker = b"--" + boundary
        file_data = None
        filename = "drawing.cdr"
        for part in payload.split(marker):
            head, sep, data = part.partition(b"\r\n\r\n")
            if sep and b'name="file"' in head:
                disposition = head.decode("latin1", "replace")
                for item in disposition.split(";"):
                    item = item.strip()
                    if item.startswith("filename="):
                        filename = Path(item.split("=", 1)[1].strip('"')).name
                file_data = data.removesuffix(b"\r\n").removesuffix(b"--\r\n")
                break
        if file_data is None or len(file_data) > MAX_UPLOAD:
            self.reply(400, b"Choose a CDR file under 100 MB.", "text/plain")
            return
        inkscape = shutil.which("inkscape")
        if not inkscape:
            self.reply(503, b"Inkscape was not found. Install Inkscape and make sure the 'inkscape' command is on PATH.", "text/plain")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="cdr-reader-") as folder:
                source = Path(folder) / filename
                output = Path(folder) / "drawing.pdf"
                source.write_bytes(file_data)
                run = subprocess.run([inkscape, str(source), "--export-type=pdf", f"--export-filename={output}"], capture_output=True, text=True, timeout=120)
                if run.returncode or not output.exists():
                    detail = (run.stderr or run.stdout or "Inkscape could not import this CDR file.").strip()
                    self.reply(422, detail.encode("utf-8", "replace")[:5000], "text/plain; charset=utf-8")
                    return
                self.reply(200, output.read_bytes(), "application/pdf")
        except subprocess.TimeoutExpired:
            self.reply(504, b"Conversion took too long (120 seconds).", "text/plain")
        except OSError as exc:
            self.reply(500, str(exc).encode(), "text/plain")

    def reply(self, status, body, mime):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[reader] " + fmt % args)


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    print(f"CDR Reader running at {url} — press Ctrl+C to stop")
    webbrowser.open(url)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
