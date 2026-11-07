"""
Τοπικός server για τη σελίδα προσφορών:  http://127.0.0.1:8765/

  GET  /              -> reports/latest.html (η σελίδα)
  GET  /api/status    -> κατάσταση σάρωσης (reports/status.json)
  POST /api/refresh   -> ξεκινά πλήρη σάρωση (pc_deals.py) στο παρασκήνιο
  GET  /import        -> σελίδα που δέχεται δεδομένα από το bookmarklet (Skroutz / Κωτσόβολος / Public / BestPrice)
  POST /api/import    -> αποθηκεύει τα δεδομένα στο reports/imports.json και ξαναφτιάχνει τη σελίδα (χωρίς internet)
  GET  /bookmarklet   -> οδηγίες + το bookmarklet για σύρσιμο στη γραμμή σελιδοδεικτών

Ακούει ΜΟΝΟ στο 127.0.0.1 (όχι από άλλους υπολογιστές). Ξεκινά αυτόματα στο login (task «PC Deals Server»).
"""
import datetime as dt
import json
import subprocess
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORTS = BASE / "reports"
LOGS = BASE / "logs"
STATUS = REPORTS / "status.json"
LOCK = REPORTS / ".scan.lock"
IMPORTS = REPORTS / "imports.json"
PORT = 8765
PYTHON = Path(sys.executable).with_name("python.exe") if sys.executable.lower().endswith("pythonw.exe") else Path(sys.executable)
NO_WINDOW = 0x08000000

BOOKMARKLET = r"""javascript:(()=>{const out=[],seen=new Set();document.querySelectorAll('a[href]').forEach(a=>{const h=a.href.split('#')[0];if(seen.has(h)||!/^https?:/.test(h))return;const card=a.closest('li,article,[class*="card"],[class*="product"],[class*="Product"]');if(!card)return;const txt=card.innerText||'';const m=txt.match(/(\d{1,3}(?:\.\d{3})*,\d{2})\s*€/);if(!m)return;let name=(a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim();if(name.length<12){const h2=card.querySelector('h2,h3');name=h2?h2.innerText.trim():name;}if(name.length<12)return;seen.add(h);const r=txt.match(/(\d[.,]\d)\s*(?:\/\s*5)?\s*\(?\s*(\d+)\s*(?:αξιολογ|κριτικ|review)/i);out.push({name:name.slice(0,240),price:m[1],url:h,rating:r?r[1]:null,reviews:r?r[2]:null});});if(!out.length){alert('Δεν βρέθηκαν προϊόντα με τιμή σε αυτή τη σελίδα.');return;}window.open('http://127.0.0.1:8765/import#'+encodeURIComponent(JSON.stringify({src:location.hostname,page:location.href,items:out})));})();"""

IMPORT_PAGE = """<!doctype html><html lang="el"><head><meta charset="utf-8"><title>Εισαγωγή τιμών</title>
<style>body{font:15px system-ui;margin:40px auto;max-width:640px;padding:0 16px;background:#f6f7f9;color:#1d2330}
@media (prefers-color-scheme:dark){body{background:#0f1218;color:#e5e7eb}a{color:#60a5fa}}</style></head><body>
<h2>Εισαγωγή τιμών από τον browser</h2><p id="m">Αποστολή…</p>
<script>
(async()=>{const m=document.getElementById('m');try{const d=JSON.parse(decodeURIComponent(location.hash.slice(1)));
const r=await fetch('/api/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});const s=await r.json();
m.innerHTML='Εισήχθησαν <b>'+s.added+'</b> τιμές από '+d.src+' ('+s.total+' συνολικά, ισχύουν 24 ώρες). Η σελίδα ξαναφτιάχνεται…<br><br><a href="/">Άνοιγμα σελίδας προσφορών</a>';
history.replaceState(null,'','/import');setTimeout(()=>location.href='/',6000);}catch(e){m.textContent='Σφάλμα: '+e;}})();
</script></body></html>"""


def read_status():
    try:
        s = json.loads(STATUS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        s = {}
    if s.get("state") == "running" and not LOCK.exists() and s.get("mode") != "rebuild":
        s["state"] = "done"
    return s


def run_scan(extra=()):
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 45 * 60:
        return False
    LOGS.mkdir(exist_ok=True)
    log = LOGS / f"manual_{dt.date.today():%Y-%m-%d}.log"
    # email και online σελίδα τα αναλαμβάνει πλέον η ωριαία σάρωση στο GitHub Actions
    subprocess.Popen([str(PYTHON), str(BASE / "pc_deals.py"), "--log", str(log), "--no-email", "--no-publish", *extra], cwd=BASE,
                     creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(REPORTS), **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_body(self, body, ctype="application/json; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.path = "/latest.html"
        elif path == "/api/status":
            return self.send_body(json.dumps(read_status(), ensure_ascii=False))
        elif path == "/import":
            return self.send_body(IMPORT_PAGE, "text/html; charset=utf-8")
        elif path == "/bookmarklet":
            href = BOOKMARKLET.replace("&", "&amp;").replace('"', "&quot;")
            page = (f"<!doctype html><meta charset='utf-8'><title>Bookmarklet</title><body style='font:15px system-ui;max-width:700px;margin:40px auto;padding:0 16px'>"
                    f"<h2>Bookmarklet εισαγωγής τιμών</h2><p>Σύρε αυτό το κουμπί στη γραμμή σελιδοδεικτών του browser:</p>"
                    f"<p><a href=\"{href}\" style='padding:8px 14px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none'>➕ PC deals: εισαγωγή</a></p>"
                    f"<ol><li>Άνοιξε μια σελίδα αποτελεσμάτων στο Skroutz, τον Κωτσόβολο, το Public ή το BestPrice (π.χ. αναζήτηση «gaming pc rtx 5070 ti»).</li>"
                    f"<li>Πάτα το bookmarklet. Ανοίγει νέα καρτέλα που στέλνει τα προϊόντα και τις τιμές της σελίδας στη σελίδα προσφορών.</li>"
                    f"<li>Οι τιμές μπαίνουν στη λίστα ως «Εισαγωγή από browser», με ιστορικό και βαθμολογία, για 24 ώρες.</li></ol>"
                    f"<p><a href='/'>← πίσω στις προσφορές</a></p></body>")
            return self.send_body(page, "text/html; charset=utf-8")
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/refresh":
            started = run_scan()
            return self.send_body(json.dumps({**read_status(), "accepted": started}, ensure_ascii=False))
        if path == "/api/import":
            n = int(self.headers.get("Content-Length") or 0)
            try:
                d = json.loads(self.rfile.read(min(n, 5_000_000)).decode("utf-8"))
                items = d.get("items", [])[:2000]
            except (ValueError, AttributeError):
                return self.send_body(json.dumps({"error": "bad json"}), code=400)
            try:
                cur = json.loads(IMPORTS.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cur = []
            now = dt.datetime.now().isoformat(timespec="seconds")
            cutoff = (dt.datetime.now() - dt.timedelta(hours=24)).isoformat()
            by_url = {it["url"]: it for it in cur if it.get("ts", "") >= cutoff and it.get("url")}
            added = 0
            for it in items:
                if not isinstance(it, dict) or not str(it.get("url", "")).startswith("http"):
                    continue
                by_url[it["url"]] = {"name": str(it.get("name", ""))[:240], "price": str(it.get("price", ""))[:20], "url": it["url"][:500],
                                     "rating": it.get("rating"), "reviews": it.get("reviews"), "ts": now, "page": str(d.get("page", ""))[:500]}
                added += 1
            REPORTS.mkdir(exist_ok=True)
            IMPORTS.write_text(json.dumps(list(by_url.values()), ensure_ascii=False, indent=0), encoding="utf-8")
            # γρήγορη αναδημιουργία σελίδας χωρίς internet ώστε να φανούν αμέσως
            LOGS.mkdir(exist_ok=True)
            subprocess.Popen([str(PYTHON), str(BASE / "pc_deals.py"), "--no-fetch", "--log", str(LOGS / "import.log")], cwd=BASE,
                             creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return self.send_body(json.dumps({"added": added, "total": len(by_url)}))
        self.send_body(json.dumps({"error": "not found"}), code=404)


def main():
    REPORTS.mkdir(exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"PC deals: http://127.0.0.1:{PORT}/", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
