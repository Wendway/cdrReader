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
:root{font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#1d2633;background:#f3f5f8}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#f3f5f8}
header{height:60px;background:#fff;border-bottom:1px solid #dfe4eb;display:flex;align-items:center;padding:0 24px;gap:18px}.brand{display:flex;align-items:center;gap:10px;margin-right:auto;font-size:15px;font-weight:600}.brand-mark{width:30px;height:30px;border-radius:9px;background:#2f62dc;color:white;display:grid;place-items:center;font-size:16px}.local{font-size:12px;color:#667387}.local::before{content:"●";color:#16845b;margin-right:7px}
button,.pick{font:inherit;border:1px solid #dfe4eb;background:#fff;color:#1d2633;border-radius:8px;padding:9px 13px;cursor:pointer}.primary{background:#2f62dc;color:#fff;border-color:#2f62dc;font-weight:600}.quiet{border-color:transparent;color:#667387}.pick input{display:none}button:disabled{opacity:.55;cursor:wait}
main{max-width:1000px;margin:0 auto;padding:28px 24px}.intro h1{font-size:22px;line-height:1.25;margin:0 0 6px;font-weight:600}.intro p{margin:0;color:#667387}.drop{margin-top:22px;min-height:240px;border:1px dashed #bdc8d7;border-radius:12px;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:26px;transition:background .15s,border-color .15s}.drop.dragging{border-color:#2f62dc;background:#eef3ff}.drop-icon{width:48px;height:48px;border-radius:14px;background:#eef2fc;color:#2f62dc;display:grid;place-items:center;font-size:24px;margin-bottom:15px}.drop h2{font-size:17px;margin:0 0 5px;font-weight:600}.drop p{color:#667387;margin:0 0 15px}.hint{font-size:12px;color:#667387;margin-top:14px}.message{min-height:20px;margin-top:14px;font-size:13px;color:#667387}.message.error{color:#ad332b}
#result[hidden],#start[hidden],#download[hidden]{display:none}.result-head{display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:18px}.result-head h1{font-size:20px;margin:0 0 4px;font-weight:600}.result-head p{margin:0;color:#667387}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 242px;gap:18px}.preview{min-height:570px;background:#e9edf3;border:1px solid #dfe4eb;border-radius:12px;overflow:hidden}.preview iframe{display:block;width:100%;height:570px;border:0;background:white}.side{align-self:start;background:#fff;border:1px solid #dfe4eb;border-radius:12px;padding:16px}.side h2{font-size:13px;margin:0 0 12px;font-weight:600}.file-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-top:1px solid #e6eaf0}.file-icon{width:34px;height:38px;display:grid;place-items:center;border-radius:6px;color:#526da9;background:#edf1fb;flex:none}.filename{font-size:12px;font-weight:500;overflow-wrap:anywhere}.subline{font-size:11px;color:#667387}.done{display:flex;align-items:center;gap:8px;margin:14px 0;color:#16845b;font-size:12px}.side button{width:100%;margin-top:7px}.privacy{text-align:center;color:#667387;font-size:12px;margin:16px 0 0}
@media(max-width:720px){header{padding:0 14px}.local{display:none}main{padding:20px 14px}.result-head{align-items:flex-start;flex-direction:column}.workspace{grid-template-columns:1fr}.side{order:-1}.preview,.preview iframe{min-height:420px;height:68vh;max-height:650px}}
</style></head><body>
<header><div class="brand"><span class="brand-mark" aria-hidden="true">▧</span>CDR Reader</div><span class="local">Files stay on this device</span><button class="quiet" id="open-another" hidden>Open another</button></header>
<main><section id="start" class="intro"><h1>View your CorelDRAW file</h1><p>Convert a CDR file to PDF and preview it right here.</p><div class="drop" id="drop-zone"><span class="drop-icon" aria-hidden="true">↥</span><h2>Drop a CDR file here</h2><p>or choose one from your computer</p><label class="pick primary">Choose a CDR file<input id="file" type="file" accept=".cdr"></label><span class="hint">Files are processed locally · Up to 100 MB</span></div><div class="message" id="status" role="status" aria-live="polite">Conversion runs locally with Inkscape.</div></section>
<section id="result" hidden><div class="result-head"><div><h1>PDF preview</h1><p id="result-name">Your CDR is ready as a PDF.</p></div><button class="primary" id="download" hidden>↓ &nbsp;Download PDF</button></div><div class="workspace"><div class="preview"><iframe id="pdf-preview" title="Converted PDF preview"></iframe></div><aside class="side"><h2>Converted file</h2><div class="file-row"><span class="file-icon" aria-hidden="true">CDR</span><div><div class="filename" id="source-name"></div><div class="subline">Original file</div></div></div><div class="file-row"><span class="file-icon" aria-hidden="true">PDF</span><div><div class="filename" id="pdf-name"></div><div class="subline">Converted document</div></div></div><div class="done">✓ Conversion complete</div><button class="primary" id="download-side">↓ &nbsp;Download PDF</button><button id="convert-another">Convert another file</button></aside></div><p class="privacy">Conversion runs locally with Inkscape. Your original CDR is unchanged.</p><div class="message" id="result-status" role="status" aria-live="polite"></div></section></main>
<script>
const input=document.querySelector('#file'),start=document.querySelector('#start'),result=document.querySelector('#result'),status=document.querySelector('#status'),resultStatus=document.querySelector('#result-status'),drop=document.querySelector('#drop-zone'),openAnother=document.querySelector('#open-another'),download=document.querySelector('#download');let pdfUrl='',pdfName='';
function chooseFile(file){if(!file)return;if(!file.name.toLowerCase().endsWith('.cdr')){status.textContent='Please choose a .cdr file.';status.classList.add('error');return}status.classList.remove('error');convert(file)}
async function convert(file){status.textContent='Converting '+file.name+'…';input.disabled=true;openAnother.disabled=true;try{const data=new FormData();data.append('file',file);const response=await fetch('/convert',{method:'POST',body:data});if(!response.ok)throw new Error(await response.text());const blob=await response.blob();if(pdfUrl)URL.revokeObjectURL(pdfUrl);pdfUrl=URL.createObjectURL(blob);pdfName=file.name.replace(/\\.[^.]+$/,'')+'.pdf';document.querySelector('#pdf-preview').src=pdfUrl;document.querySelector('#source-name').textContent=file.name;document.querySelector('#pdf-name').textContent=pdfName;document.querySelector('#result-name').textContent='Converted from '+file.name;start.hidden=true;result.hidden=false;openAnother.hidden=false;download.hidden=false;status.textContent=''}catch(error){status.textContent=error.message;status.classList.add('error')}finally{input.disabled=false;openAnother.disabled=false;input.value=''}}
function savePdf(){if(!pdfUrl)return;const a=document.createElement('a');a.href=pdfUrl;a.download=pdfName;a.click()}
input.addEventListener('change',()=>chooseFile(input.files[0]));drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragging')});drop.addEventListener('dragleave',()=>drop.classList.remove('dragging'));drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragging');chooseFile(event.dataTransfer.files[0])});
download.addEventListener('click',savePdf);document.querySelector('#download-side').addEventListener('click',savePdf);function reset(){result.hidden=true;start.hidden=false;openAnother.hidden=true;status.textContent='Conversion runs locally with Inkscape.';status.classList.remove('error');resultStatus.textContent=''}openAnother.addEventListener('click',()=>input.click());document.querySelector('#convert-another').addEventListener('click',reset);
</script></body></html>"""


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
        if file_data is None or len(file_data) > MAX_UPLOAD or Path(filename).suffix.lower() != ".cdr":
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
