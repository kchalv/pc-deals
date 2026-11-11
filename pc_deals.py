"""
Σκάνερ προσφορών ΕΛΛΗΝΙΚΩΝ καταστημάτων: έτοιμα gaming PC (Fortnite + CUDA / local LLM / AI agents)
και, σε ξεχωριστή λίστα, περιφερειακά (ποντίκι, πληκτρολόγιο, οθόνη).

Σε κάθε εκτέλεση (κάθε 2 ώρες από το GitHub Actions ή με το κουμπί «Ανανέωση» της σελίδας):
  1. Τραβάει τιμές από ελληνικά καταστήματα που απαντούν σε απλό HTTP (χωρίς bot-bypass):
       Plaisio (κατηγορίες + αστέρια/κριτικές), e-shop.gr (λίστα GAMER με «ελάχιστη 30 ημερών»),
       e-gate (αναζήτηση), msystems (αναζήτηση), Germanos (αναζήτηση περιφερειακών).
     Skroutz / Κωτσόβολος / Public / You / BestPrice μπλοκάρουν bots -> έτοιμα links χειροκίνητου ελέγχου.
  2. Διαβάζει από το όνομα CPU / GPU / VRAM / RAM / SSD και βαθμολογεί κάθε PC:
       Fortnite (CPU-bound: X3D = κορυφή), AI (VRAM για local LLM, AMD −20% χωρίς CUDA), συνολικό, αξία ανά 1.000 €.
     Κρατά μόνο CPU από watchlist.json -> prebuilt.allowed_cpus (9800X3D / 7800X3D / Ultra 7 270K Plus / i9-14900K/KS),
     RAM ≥ 32 GB και κάρτα AMD ή NVIDIA με ≥ 16 GB VRAM. Laptops και εξαρτήματα απορρίπτονται.
  3. Κρατά ιστορικό τιμών (SQLite, ημερήσιο min) -> 30ήμερο χαμηλό, διάμεση, ιστορικό χαμηλό,
     και ελέγχει αν η «έκπτωση» του καταστήματος είναι αληθινή.
  4. Γράφει τη σελίδα reports/latest.html (φιλτράρισμα, ταξινόμηση, κουμπί ανανέωσης μέσω server.py).
  5. Στέλνει email με τις ΝΕΕΣ πραγματικές ευκαιρίες (κανόνες στο watchlist.json -> alerts, SMTP στο notify.json).

Χρήση:  python pc_deals.py               (πλήρης σάρωση)
        python pc_deals.py --open        (+ άνοιγμα σελίδας)
        python pc_deals.py --no-fetch    (ξαναφτιάχνει τη σελίδα από τη βάση)
        python pc_deals.py --no-email    (χωρίς αποστολή email)
        python pc_deals.py --test-email  (στέλνει δοκιμαστικό email και σταματά)
        python pc_deals.py --debug       (δείχνει και όσα απορρίφθηκαν)
"""
import argparse
import datetime as dt
import html
import json
import os
import re
import smtplib
import sqlite3
import statistics
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

try:   # προαιρετικό: πιστοποιητικά του λειτουργικού (π.χ. εταιρικό δίκτυο με TLS inspection). pip install truststore
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

BASE = Path(__file__).resolve().parent
DB = BASE / "history.sqlite"
OLD_DB = BASE / "pc_deals.sqlite"
REPORTS = BASE / "reports"
WATCHLIST = BASE / "watchlist.json"
NOTIFY = BASE / "notify.json"
LOCK = REPORTS / ".scan.lock"
STATUS = REPORTS / "status.json"
VAT = 0.24

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "el-GR,el;q=0.9,en;q=0.7",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
FETCH_LOG = []   # (store, url, status, n, note)
PAGE_CACHE = {}
DEBUG = False


# ============================================================================ helpers
def log(*a):
    print(*a, flush=True)


def get(url, store, delay=0.7):
    if url in PAGE_CACHE:
        return PAGE_CACHE[url]
    time.sleep(delay)
    try:
        r = SESSION.get(url, timeout=45)
        if r.status_code in (429, 503):
            time.sleep(15)
            r = SESSION.get(url, timeout=45)
        txt = r.text if r.status_code == 200 else ""
        if r.status_code != 200:
            FETCH_LOG.append((store, url, r.status_code, 0, f"HTTP {r.status_code}"))
    except requests.RequestException as e:
        txt = ""
        FETCH_LOG.append((store, url, 0, 0, type(e).__name__))
    PAGE_CACHE[url] = txt
    return txt


def parse_price(s):
    """'1.458,72 €' / '1,458.72' / '999.00 &euro;' / '1549' -> float ή None."""
    if s is None:
        return None
    s = html.unescape(str(s)).replace("\xa0", " ").replace("€", "").replace("EUR", "").strip()
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d{1,2}", s) or re.fullmatch(r"\d+,\d{1,2}", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+\.\d{1,2}", s) or re.fullmatch(r"\d+\.\d{1,2}", s):
        s = s.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if 5 <= v <= 30000 else None


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def offer(store, name, url, price, old=None, min30_store=None, rrp=None, rating=None, reviews=None, stock=""):
    return {"store": store, "name": clean(name)[:240], "url": url, "price": price,
            "old": old if old and price and old > price + 0.5 else None,
            "min30_store": min30_store, "rrp": rrp, "rating": rating, "reviews": reviews, "stock": clean(stock)[:80]}


# ============================================================================ store adapters
def plaisio_category(cat_url, max_pages=12):
    """Plaisio: κάρτες προϊόντων με τιμή, παλιά τιμή (fromPrice), αστέρια και αριθμό κριτικών."""
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        url = cat_url if page == 1 else f"{cat_url}?page={page}"
        t = get(url, "plaisio")
        if not t:
            break
        names = {}
        for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', t):
            try:
                d = json.loads(m.group(1))
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("@type") == "ItemList":
                for el in d.get("itemListElement", []):
                    it = el.get("item") or {}
                    if it.get("url"):
                        names[it["url"].split("?")[0]] = it.get("name", "")
        n_new = 0
        for chunk in t.split('data-test="ProductPortrait"')[1:]:
            href = re.search(r'href="(/product/[^"]+)"', chunk)
            price = re.search(r'data-test="price">([^<]+)<', chunk)
            if not (href and price):
                continue
            u = "https://www.plaisio.gr" + href.group(1).split("?")[0]
            p = parse_price(price.group(1))
            if not p or u in seen:
                continue
            seen.add(u)
            n_new += 1
            name = names.get(u)
            if not name:
                h2 = re.search(r'<h2[^>]*>(?:\s*<a[^>]*>)?([\s\S]*?)</(?:a|h2)>', chunk)
                name = clean(h2.group(1)) if h2 else u.rsplit("/", 1)[-1].replace("-", " ")
            old = re.search(r'data-test="fromPrice">\s*([^<]*\d[^<]*)<', chunk)
            stars = re.search(r'starsInner[^"]*"\s*style="width:\s*([\d.]+)%', chunk)
            nrev = re.search(r'nrOfReviews[^>]*>\(\D*?(\d+)', chunk)
            avail = re.search(r'(Άμεσα διαθέσιμο|Διαθέσιμο[^<]{0,30}|Μη διαθέσιμο|Κατόπιν παραγγελίας[^<]{0,30}|Αναμένεται[^<]{0,30})', chunk)
            out.append(offer("plaisio", name, u, p, old=parse_price(old.group(1)) if old else None,
                             rating=round(float(stars.group(1)) / 20, 1) if stars and nrev else None,
                             reviews=int(nrev.group(1)) if nrev else None,
                             stock=avail.group(1) if avail else ""))
        FETCH_LOG.append(("plaisio", url, 200, n_new, ""))
        if n_new == 0:
            break
    return out


def eshop_list(list_url, max_pages=8):
    """e-shop.gr λίστα κατηγορίας: τιμή + «Ελάχιστη 30 ημερών» + «Προτεινόμενη λιανική» + διαθεσιμότητα."""
    out, seen = [], set()
    for page in range(max_pages):
        url = list_url if page == 0 else f"{list_url}&offset={page * 10}"
        t = get(url, "eshop")
        if not t:
            break
        n = 0
        for chunk in t.split('class="web-product-container"')[1:]:
            m = re.search(r'<a href="(https://www\.e-shop\.gr/[^"]+)" class="web-title-link"><h2>([^<]+)</h2>', chunk)
            pr = re.search(r'<td class="web-product-price">\s*<b>([\d.,]+)&nbsp;&euro;</b>', chunk)
            if not (m and pr) or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            n += 1
            mn = re.search(r'Ελάχιστη&nbsp;30&nbsp;ημερών&nbsp;([\d.,]+)', chunk)
            rrp = re.search(r'Προτεινόμενη&nbsp;λιανική&nbsp;([\d.,]+)', chunk)
            av = re.search(r'padding:0 5px 7px 0;">([^<]+)</div>', chunk)
            p = parse_price(pr.group(1))
            out.append(offer("eshop", m.group(2), m.group(1), p, min30_store=parse_price(mn.group(1)) if mn else None,
                             rrp=parse_price(rrp.group(1)) if rrp else None, stock=av.group(1) if av else ""))
        FETCH_LOG.append(("eshop", url, 200, n, ""))
        if n == 0:
            break
    return out


def eshop_search(q):
    url = "https://www.e-shop.gr/search?q=" + urllib.parse.quote_plus(q)
    t = get(url, "eshop")
    out, seen = [], set()
    for m in re.finditer(r"<a href='(https://www\.e-shop\.gr/[^']+-p-[A-Z0-9.]+)' class='faint_link2'>([^<]{5,})</a>[\s\S]{0,900}?<b>([\d.,]+)\s*&euro;</b>", t):
        href, name, price = m.groups()
        p = parse_price(price)
        if p and href not in seen:
            seen.add(href)
            out.append(offer("eshop", name, href, p))
    FETCH_LOG.append(("eshop", url, 200 if t else 0, len(out), ""))
    return out


def germanos_search(q):
    url = "https://www.germanos.gr/search?q=" + urllib.parse.quote(q)
    t = get(url, "germanos")
    out = []
    for m in re.finditer(r'<a[^>]*data-price="([\d.]+)"[^>]*data-promo-price="([\d.]*)"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', t):
        price, promo, href, body = m.groups()
        name = re.search(r"<h3[^>]*>([\s\S]*?)</h3>", body)
        avail = re.search(r"Μη Διαθέσιμο|Διαθέσιμο|Κατόπιν παραγγελίας", body)
        p = parse_price(promo or price)
        if p and name:
            out.append(offer("germanos", name.group(1), "https://www.germanos.gr" + href.split("?")[0], p,
                             old=parse_price(price) if promo and promo != price else None,
                             stock=avail.group(0) if avail else ""))
    FETCH_LOG.append(("germanos", url, 200 if t else 0, len(out), ""))
    return out


def egate_search(q, max_pages=8):
    """e-gate (WooCommerce): /?s=..&post_type=product και /page/N/?s=..; <del>/<ins> για προσφορές."""
    qs = "?s=" + urllib.parse.quote_plus(q) + "&post_type=product"
    return woodmart_list("egate", lambda page: "https://www.e-gate.gr/" + (qs if page == 1 else f"page/{page}/{qs}"), max_pages)


def praxi_category(cat_url, max_pages=10):
    """praxi.gr (WooCommerce/Woodmart όπως το e-gate): κατηγορία με /page/N/."""
    cat_url = cat_url.rstrip("/") + "/"
    return woodmart_list("praxi", lambda page: cat_url if page == 1 else f"{cat_url}page/{page}/", max_pages)


def praxi_search(q, max_pages=1):
    qs = "?s=" + urllib.parse.quote_plus(q) + "&post_type=product"
    return woodmart_list("praxi", lambda page: "https://praxi.gr/homepage/" + (qs if page == 1 else f"page/{page}/{qs}"), max_pages)


def woodmart_list(store, page_url, max_pages):
    out, seen = [], set()
    total = None
    for page in range(1, max_pages + 1):
        url = page_url(page)
        t = get(url, store)
        if not t:
            break
        if total is None:
            m = re.search(r"από (\d+) αποτελέσματα", t) or re.search(r"όλα[^<]{0,5}?(\d+) αποτελέσματα", t)
            total = int(m.group(1)) if m else 0
        n = 0
        for chunk in t.split('<h3 class="wd-entities-title"><a href="')[1:]:
            m = re.match(r'([^"]+)">([^<]+)</a>', chunk)
            if not m:
                continue
            u, name = m.group(1), m.group(2)
            ps = re.search(r'<span class="price">([\s\S]*?)</span>\s*(?:<small|<div|</div)', chunk[:6000])
            if not ps or u in seen:
                continue
            block = ps.group(1)
            amounts = [parse_price(a) for a in re.findall(r'<bdi>(?:<span[^>]*>[^<]*</span>)?\s*([\d.,]+)', block)]
            amounts = [a for a in amounts if a]
            if not amounts:
                continue
            if "<del" in block and len(amounts) >= 2:
                old, p = amounts[0], amounts[1]
            else:
                old, p = None, amounts[0]
            seen.add(u)
            n += 1
            st = re.search(r'custom-availability[^>]*>\s*<span>\s*([^<]+)', chunk) or re.search(r'wd-product-stock[^>]*>([^<]+)<', chunk)
            stars = re.search(r'star-rating[^>]*title="[^"]*?([\d.,]+)[^"]*"', chunk[:6000]) or re.search(r'Βαθμολογήθηκε με <strong[^>]*>([\d.,]+)</strong>', chunk[:6000])
            nrev = re.search(r'\((\d+)\s*(?:κριτικ|αξιολογ|review)', chunk[:6000])
            rating = float(stars.group(1).replace(",", ".")) if stars else None
            out.append(offer(store, name, u, p, old=old, stock=st.group(1) if st else "",
                             rating=rating if rating and 0 < rating <= 5 else None, reviews=int(nrev.group(1)) if nrev and rating else None))
        FETCH_LOG.append((store, url, 200, n, f"σύνολο {total}" if page == 1 else ""))
        if n == 0 or (total and len(seen) >= total):
            break
    return out


def msystems_search(q):
    url = "https://www.msystems.gr/search/?keywords=" + urllib.parse.quote_plus(q)
    t = get(url, "msystems")
    out, seen = [], set()
    for chunk in re.split(r'(?=<h3 class="product-title)', t)[1:]:
        m = re.search(r'<a href="([^"]+)">\s*([^<]+?)\s*</a>', chunk)
        if not m:
            continue
        u = urllib.parse.urljoin("https://www.msystems.gr/", m.group(1))
        pr = re.findall(r'(\d[\d.]*,\d{2})\s*(?:&euro;|€)', chunk[:5000])
        if not pr or u in seen:
            continue
        prices = [parse_price(x) for x in pr if parse_price(x)]
        if not prices:
            continue
        seen.add(u)
        p = min(prices)
        old = max(prices) if len(set(prices)) > 1 else None
        out.append(offer("msystems", m.group(2), u, p, old=old))
    FETCH_LOG.append(("msystems", url, 200 if t else 0, len(out), ""))
    return out


# ---------------------------------------------------------------- WooCommerce Store API (ucase, tetrabyte)
def woo_store_api(store, base, q, max_pages=1, per_page=50):
    """GET {base}/wp-json/wc/store/v1/products?search=.. (δημόσιο, χωρίς κλειδί· επιτρέπεται στο robots.txt).
    None = το API δεν απάντησε."""
    out, seen = [], set()
    for page in range(1, max_pages + 1):
        url = f"{base}/wp-json/wc/store/v1/products?search={urllib.parse.quote(q)}&per_page={per_page}&page={page}"
        t = get(url, store)
        if not t:
            return out if page > 1 else None
        try:
            items = json.loads(t)
        except ValueError:
            FETCH_LOG.append((store, url, 200, 0, "bad JSON"))
            break
        if not isinstance(items, list):
            break
        n = 0
        for it in items:
            u, pr = it.get("permalink"), it.get("prices") or {}
            div = 10 ** int(pr.get("currency_minor_unit") or 0)
            try:
                p = int(pr.get("price") or 0) / div
                reg = int(pr.get("regular_price") or 0) / div
                if (pr.get("price_range") or {}).get("min_amount"):   # προϊόν με παραλλαγές -> «από»
                    p = int(pr["price_range"]["min_amount"]) / div
            except ValueError:
                continue
            p = parse_price(f"{p:.2f}")
            if not (u and p) or u in seen:
                continue
            seen.add(u)
            n += 1
            st = (it.get("stock_availability") or {}).get("text") or ("" if it.get("is_in_stock") else "Εξαντλημένο")
            avg = float(it.get("average_rating") or 0)
            out.append(offer(store, it.get("name", ""), u, p, old=reg if it.get("on_sale") and reg > p else None, stock=st,
                             rating=avg if avg > 0 else None, reviews=it.get("review_count") if avg > 0 else None))
        FETCH_LOG.append((store, url, 200, n, ""))
        if len(items) < per_page:
            break
    return out


def ucase_search(q, max_pages=1):
    return woo_store_api("ucase", "https://ucase.gr", q, max_pages) or []


def tetrabyte_search(q, max_pages=1):
    out = woo_store_api("tetrabyte", "https://tetrabyte.gr", q, max_pages)
    if out is None:   # Store API δεν απαντά -> HTML αναζήτηση (Woodmart)
        qs = "?s=" + urllib.parse.quote_plus(q) + "&post_type=product"
        out = woodmart_list("tetrabyte", lambda page: "https://tetrabyte.gr/" + (qs if page == 1 else f"page/{page}/{qs}"), max_pages)
    return out


# ---------------------------------------------------------------- i-abox (Astro, χωρίς αναζήτηση)
IABOX = "https://i-abox.com"


def _iabox_get(path):
    """Το i-abox στέλνει text/html χωρίς charset -> το requests διαβάζει latin-1. Διόρθωση σε UTF-8."""
    t = get(IABOX + path, "iabox")
    try:
        return t.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return t


def _has_tokens(q, text):
    text = text.lower()
    return all(tok in text for tok in q.lower().split())


def iabox_search(q="", max_pages=8):
    """Δεν έχει αναζήτηση: διαβάζουμε τη λίστα /products?shid=true&page=N (περιφερειακά) και τα έτοιμα PC
    /products/prebuild/<slug> (JSON-LD ProductGroup: κάθε παραλλαγή με τιμή + CPU/GPU/RAM/SSD).
    Φιλτράρουμε τοπικά με τις λέξεις του q (κενό q = όλα). Οι σελίδες cache-άρονται για όλη τη σάρωση."""
    out, seen, listing, prebuilds = [], set(), [], []
    for page in range(1, max_pages + 1):
        t = _iabox_get("/products?shid=true" + (f"&page={page}" if page > 1 else ""))
        if not t:
            break
        if page == 1:
            prebuilds = list(dict.fromkeys(re.findall(r'href="(/products/prebuild/[a-z0-9-]+)"', t)))
        cards = re.findall(r'<a class="text-text-primary-fade[^"]*" href="(/products/[^"]+)"[^>]*>([\s\S]*?)</a>', t)
        if not cards:
            break
        listing += cards
        if f"page={page + 1}" not in t:
            break
    for path in prebuilds:
        t = _iabox_get(path)
        n0 = len(out)
        for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', t):
            try:
                d = json.loads(m.group(1))
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("@type") != "ProductGroup":
                continue
            for v in d.get("hasVariant", []):
                props = {p.get("name"): p.get("value", "") for p in v.get("additionalProperty", [])}
                spec = " / ".join(re.sub(r"\s*\[[^\]]*core\]", "", props[k]) for k in ("CPU", "GPU", "RAM", "Main Storage") if props.get(k))
                name = f"i-aBox Gaming PC {v.get('name', '')} ({spec})"
                o = v.get("offers") or {}
                p, u = parse_price(o.get("price")), v.get("url")
                if not (p and u) or u in seen or not _has_tokens(q, name + " " + " ".join(props.values())):
                    continue
                seen.add(u)
                avail = o.get("availability", "")
                out.append(offer("iabox", name, u, p, stock="Διαθέσιμο" if avail.endswith("InStock") else avail.rsplit("/", 1)[-1]))
        FETCH_LOG.append(("iabox", IABOX + path, 200 if t else 0, len(out) - n0, "prebuild JSON-LD"))
    for href, body in listing:
        if href.startswith("/products/prebuild/"):
            continue
        h2 = re.search(r"<h2[^>]*>([\s\S]*?)</h2>", body)
        pr = re.search(r'font-medium mb-0">\s*€\s*([\d.,]+)', body)
        if not (h2 and pr):
            continue
        name, u = clean(h2.group(1)), IABOX + urllib.parse.quote(href, safe="/?=&")
        if u in seen or not parse_price(pr.group(1)) or not _has_tokens(q, name):
            continue
        seen.add(u)
        old = re.search(r'line-through">\s*€\s*([\d.,]+)', body)
        st = re.search(r'<span class="text-[a-z-]*stock">([^<]+)</span>', body)
        out.append(offer("iabox", name, u, parse_price(pr.group(1)), old=parse_price(old.group(1)) if old else None,
                         stock=st.group(1) if st else ""))
    return out


# ---------------------------------------------------------------- mgmanager (VENDD, robots.txt: Crawl-delay 5)
def mgmanager_search(q, max_pages=1):
    out, seen = [], set()
    qs = urllib.parse.urlencode({"ps": 45, "search-for": q})
    for page in range(1, max_pages + 1):
        url = f"https://www.mgmanager.gr/page/search-products/p{page}/?{qs}"
        t = get(url, "mgmanager", delay=5)
        if not t:
            break
        n = 0
        for chunk in t.split('class="x-control x-box x-product-box')[1:]:
            m = re.search(r'<h2 class="heading"[^>]*><a href="([^"]+)"[^>]*>([\s\S]*?)</a>', chunk)
            pr = re.search(r'class="current-price"[^>]*>([^<]+)<', chunk)
            if not (m and pr):
                continue
            u, p = urllib.parse.urljoin("https://www.mgmanager.gr/", m.group(1)), parse_price(pr.group(1))
            if not p or u in seen:
                continue
            seen.add(u)
            n += 1
            old = re.search(r'"DisplayDeletedPrice":\{"Value":([\d.]+)', chunk)
            av = re.search(r'<span class="availability[^"]*">([^<]+)<', chunk)
            out.append(offer("mgmanager", m.group(2), u, p, old=float(old.group(1)) if old else None, stock=av.group(1) if av else ""))
        pc = re.search(r'data-page-count="(\d+)"', t)
        FETCH_LOG.append(("mgmanager", url, 200, n, ""))
        if n == 0 or not pc or page >= int(pc.group(1)):
            break
    return out


# ---------------------------------------------------------------- kpl.gr (OpenCart· το robots.txt απαγορεύει την αναζήτηση)
def _compact(s):
    return re.sub(r"[^0-9a-zα-ω]+", "", s.lower())


def kpl_search(q, max_pages=1):
    """Η αναζήτηση και η σελιδοποίηση απαγορεύονται στο robots.txt -> ταιριάζουμε το q στο sitemap.xml
    (<image:caption> = όνομα) και διαβάζουμε έως 15·max_pages σελίδες προϊόντων (JSON-LD / τιμή Journal3)."""
    t = get("https://kpl.gr/sitemap.xml", "kpl")
    toks, qc = [_compact(x) for x in q.split() if _compact(x)], _compact(q)
    hits = []
    for blk in re.findall(r"<url>([\s\S]*?)</url>", t):
        loc = re.search(r"<loc>\s*([^<]+?)\s*</loc>", blk)
        cap = re.search(r"<image:caption>([\s\S]*?)</image:caption>", blk)
        if not loc:
            continue
        cap = html.unescape(cap.group(1)) if cap else ""
        hay = _compact(cap + " " + loc.group(1).rsplit("/", 1)[-1])
        if qc in hay or all(tk in hay for tk in toks):
            hits.append((loc.group(1), cap))
    FETCH_LOG.append(("kpl", "https://kpl.gr/sitemap.xml #" + q, 200 if t else 0, len(hits), "ταίριαξαν στο sitemap"))
    out = []
    for loc, cap in hits[: 15 * max_pages]:
        t = get(loc, "kpl")
        if not t:
            continue
        price = old = None
        ld_name, stock = "", ""
        for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>([\s\S]*?)</script>', t):
            try:
                d = json.loads(m.group(1))
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("@type") == "Product":
                ld_name = d.get("name", "")
                of = d.get("offers") or {}
                of = (of[0] if of else {}) if isinstance(of, list) else of
                price = parse_price(of.get("price"))
                stock = (of.get("availability") or "").rsplit("/", 1)[-1]
        new = re.search(r'class="product-price-new">([^<]+)<', t)
        oldm = re.search(r'class="product-price-old">([^<]+)<', t)
        if new:
            price = parse_price(new.group(1)) or price
            old = parse_price(oldm.group(1)) if oldm else None
        elif not price:
            pm = re.search(r'class="product-price">([^<]+)<', t)
            price = parse_price(pm.group(1)) if pm else None
        st = re.search(r'class="product-stock[^"]*"><b>[^<]*</b>\s*<span>([^<]+)<', t)
        title = re.search(r'class="title page-title">([^<]+)<', t)
        name = (title.group(1) if title else "") or ld_name or cap
        if price:
            out.append(offer("kpl", name, loc, price, old=old, stock=st.group(1) if st else stock))
        else:
            FETCH_LOG.append(("kpl", loc, 200, 0, "δεν βρέθηκε τιμή"))
    return out


# ---------------------------------------------------------------- Κωτσόβολος (μόνο κατηγορίες· η αναζήτηση απαγορεύεται στο robots.txt)
KOTS_API = "https://www.kotsovolos.gr/api/ext/getProductsByCategory"   # robots.txt: Allow: /api/ext/getProductsByCategory*
KOTS_CATS = {"35750": "desktops", "35519": "gaming-mice", "35520": "gaming-keyboards"}
KOTS_STOCK = {"1": "Άμεσα διαθέσιμο", "2": "Διαθέσιμο", "3": "Κατόπιν παραγγελίας", "4": "Μη διαθέσιμο"}
_GREEK_LOOKALIKE = str.maketrans("ΑΒΕΖΗΙΚΜΝΟΡΤΥΧαβεικνορτυχ", "ABEZHIKMNOPTYXaBeikvopTyx")


def _kots_norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").translate(_GREEK_LOOKALIKE).lower()).strip()


def _kots_attr(e, *names):
    for a in e.get("attributes") or []:
        if (a.get("name") or "").strip() in names:
            vals = [v.get("value") for v in a.get("values") or [] if v.get("value")]
            if vals:
                return clean(vals[0])
    return ""


def kotsovolos_search(q="", max_pages=1):
    """Διαβάζει τις κατηγορίες desktops / gaming ποντίκια / gaming πληκτρολόγια (200 ανά κλήση, cache ανά σάρωση)
    και φιλτράρει με τις λέξεις του q (κενό q = όλα). Στα PC προσθέτει CPU / GPU / VRAM / RAM στο όνομα."""
    toks, out, seen = _kots_norm(q).split(), [], set()
    for cat_id in KOTS_CATS:
        url = KOTS_API + "?" + urllib.parse.urlencode({"params": "pageNumber=1&pageSize=200", "catId": cat_id, "storeId": "10151", "isCPage": "false"})
        t = get(url, "kotsovolos")
        try:
            entries = (json.loads(t) if t else {}).get("catalogEntryView") or []
        except ValueError:
            FETCH_LOG.append(("kotsovolos", url, 200, 0, "bad JSON"))
            continue
        n = 0
        for e in entries:
            name = e.get("name") or ""
            cpu = _kots_attr(e, "Μοντέλο Επεξεργαστή")
            gpu = _kots_attr(e, "Κάρτα Γραφικών").translate(_GREEK_LOOKALIKE)
            hay = " " + _kots_norm(" ".join([name, cpu, gpu])) + " "
            if not all(f" {tk} " in hay or (len(tk) > 3 and tk in hay) for tk in toks):
                continue
            ud = (e.get("UserData") or [{}])[0]
            if not ud.get("seo_url"):
                continue
            u = "https://www.kotsovolos.gr/" + ud["seo_url"].lstrip("/")
            prices = {p.get("usage"): parse_price(p.get("value")) for p in e.get("price") or []}
            price = parse_price(e.get("price_EUR")) or prices.get("Offer")
            if not price or u in seen:
                continue
            seen.add(u)
            n += 1
            full = name
            if cat_id == "35750":
                vram, ram = _kots_attr(e, "Μνήμη Κάρτας Γραφικών (GB)"), _kots_attr(e, "RAM Memory", "Μνήμη")
                parts = [x for x in (cpu, (gpu + (f" {vram}GB" if vram.isdigit() else "")) if gpu else "", f"{ram} RAM" if ram else "") if x]
                full = f"Desktop PC {name} ({' / '.join(parts)})" if parts else name
            out.append(offer("kotsovolos", full, u, price, old=prices.get("Display"),
                             stock=KOTS_STOCK.get(str(ud.get("x_availability_hd")), "")))
        FETCH_LOG.append(("kotsovolos", url, 200 if t else 0, n, f"q={q}" if q else ""))
    return out


SEARCHERS = {"eshop": eshop_search, "germanos": germanos_search, "egate": lambda q: egate_search(q, max_pages=1),
             "msystems": msystems_search, "praxi": praxi_search, "ucase": ucase_search, "tetrabyte": tetrabyte_search,
             "iabox": iabox_search, "mgmanager": mgmanager_search, "kpl": kpl_search, "kotsovolos": kotsovolos_search}
# kind -> συνάρτηση(arg, max_pages) για τις πηγές έτοιμων PC στο watchlist.json
PC_SOURCES = {"egate": egate_search, "praxi": praxi_search, "ucase": ucase_search, "tetrabyte": tetrabyte_search,
              "iabox": iabox_search, "mgmanager": mgmanager_search, "kpl": kpl_search, "kotsovolos": kotsovolos_search}


# ============================================================================ specs & scoring (έτοιμα PC)
GPU_TABLE = {  # key: (σχετική απόδοση gaming 0-100, VRAM GB)  -- NVIDIA RTX
    "5090": (100, 32), "4090": (88, 24), "5080": (74, 16), "4080 super": (70, 16), "4080": (68, 16),
    "5070 ti": (64, 16), "4070 ti super": (60, 16), "4070 ti": (55, 12), "5070": (52, 12), "4070 super": (52, 12),
    "4070": (45, 12), "3090 ti": (58, 24), "3090": (55, 24), "3080 ti": (50, 12), "3080": (46, 10),
    "5060 ti": (40, 8), "4060 ti": (36, 8), "3070 ti": (38, 8), "3070": (36, 8), "5060": (33, 8),
    "3060 ti": (30, 8), "4060": (28, 8), "3060": (24, 12), "5050": (24, 8), "3050": (14, 8),
}
AMD_GPU_TABLE = {  # AMD Radeon RX: (απόδοση gaming 0-100, VRAM GB)
    "9070 xt": (66, 16), "9070 gre": (52, 12), "9070": (59, 16), "9060 xt": (40, 8), "9060": (33, 8),
    "7900 xtx": (72, 24), "7900 xt": (62, 20), "7900 gre": (54, 16), "7800 xt": (50, 16), "7700 xt": (43, 12),
    "7600 xt": (31, 16), "7600": (29, 8), "6950 xt": (52, 16), "6900 xt": (49, 16), "6800 xt": (46, 16), "6800": (41, 16),
}
VRAM_VALUES = (6, 8, 10, 12, 16, 20, 24, 32)
VRAM_SCORE = {32: 100, 24: 85, 20: 70, 16: 60, 12: 38, 10: 30, 8: 18, 6: 8}
RAM_SIZES = {8, 16, 24, 32, 48, 64, 96, 128, 192, 256}
X3D_SCORE = {9800: 100, 9850: 100, 9950: 97, 9900: 93, 7800: 92, 7950: 90, 7900: 86, 9600: 88,
             7600: 84, 7500: 82, 5800: 74, 5700: 72, 5600: 70}


def parse_specs(name):
    n = name.replace("‑", "-").translate(_GREEK_LOOKALIKE).lower()   # «RX 9070 ΧΤ» με ελληνικά Χ/Τ
    sp = {"cpu": None, "cpu_score": 50, "x3d": False, "x3d9k": False, "gpu": None, "nvidia": False, "amd": False,
          "gpu_perf": 0, "vram": None, "ram": None, "ssd": None}
    # ---- GPU: NVIDIA RTX ή AMD Radeon RX (η VRAM από τον πίνακα, ή από το «16GB» που ακολουθεί)
    rest = n
    g = re.search(r"rtx\s*-?\s*(\d{4})\s*(ti\s*super|ti|super)?", n)
    a = None if g else (re.search(r"\brx\s*-?\s*(\d{4})\s*(xtx|xt|gre)?", n)
                        or re.search(r"(?<![\d.-])(9070|9060|7900|7800|7700|7600)\s*(xtx|xt|gre)\b", n))   # «9070XT» χωρίς «RX»
    key, table = None, None
    if g:
        key, table = (g.group(1) + (" " + re.sub(r"\s+", " ", g.group(2)) if g.group(2) else "")).strip(), GPU_TABLE
    elif a:
        key, table, g = (a.group(1) + (" " + a.group(2) if a.group(2) else "")).strip(), AMD_GPU_TABLE, a
    if key and key in table:
        perf, vram = table[key]
        vm = re.match(r"[^/()+,]{0,16}?(\d{1,2})\s*gb", n[g.end():])
        if vm and int(vm.group(1)) in VRAM_VALUES:
            vram = int(vm.group(1))
        if table is GPU_TABLE:
            sp.update(gpu="RTX " + key.upper().replace("TI", "Ti").replace("SUPER", "Super"), nvidia=True)
        else:
            sp.update(gpu="Radeon RX " + key.upper(), amd=True)
        sp.update(gpu_perf=perf, vram=vram)
        rest = n[:g.start()] + " " + n[g.end() + (vm.end() if vm else 0):]
    elif re.search(r"\b(rx\s*\d{4}|radeon|arc\s*[ab]\d{3}|intel arc)", n):
        sp["gpu"] = "AMD/Intel (μοντέλο;)"
    # ---- CPU
    c = re.search(r"(?:ryzen\s*|\br)([3579])\s*[- ]?\s*(\d{4})\s*(hx3d|x3d2?|xt|x|f|g|hx|hs|h)?", n)
    if c:
        tier, model, suf = c.group(1), int(c.group(2)), (c.group(3) or "")
    else:   # σκέτο «9800X3D» χωρίς «Ryzen 7»: η βαθμίδα από το μοντέλο (x800X3D = Ryzen 7, x900/x950X3D = Ryzen 9)
        c = re.search(r"(?<![\d.])([579]\d00)\s*(x3d)\b", n)
        if c:
            model, suf = int(c.group(1)), "x3d"
            tier = "9" if model % 1000 >= 900 else "7" if model % 1000 >= 700 else "5"
    if c:
        label = f"Ryzen {tier} {model}{suf.upper()}"
        if suf == "hx3d":   # mobile X3D σε mini-tower (π.χ. Lenovo LOQ Tower 9955HX3D)
            sc = 84
            sp.update(x3d=True)
        elif suf.startswith("x3d"):
            sc = X3D_SCORE.get(model, 85)
            sp.update(x3d=True, x3d9k=model in (9800, 9850, 9900, 9950))
        else:
            sc = {9: 78, 8: 62, 7: 72, 5: 55, 4: 45, 3: 40}.get(model // 1000, 50)
            sc += {9: 4, 7: 2, 6: 0, 5: -2, 4: -4}.get((model % 1000) // 100, 0)
            if suf in ("hx", "hs", "h"):
                sc -= 8
        sp.update(cpu=label, cpu_score=sc)
    else:
        c = re.search(r"(?:ul?i?tra\s*|\bu)([3579])\s*[- ]?\s*(\d{3})\s*(kf|k|f|hx|h|u|v)?(\s*plus)?", n)
        if c:
            tier, model, suf = int(c.group(1)), int(c.group(2)), (c.group(3) or "")
            sc = {9: 81, 7: 78, 5: 70, 3: 60}[tier] + (1 if "k" in suf else 0) + (2 if c.group(4) else 0)
            if suf in ("hx", "h", "u", "v"):
                sc -= 8
            sp.update(cpu=f"Core Ultra {tier} {model}{suf.upper()}{' Plus' if c.group(4) else ''}", cpu_score=sc)
        else:
            c = (re.search(r"\bi([3579])\s*[- ]\s*(\d{4,5})(kf|ks|k|f|hx|h)?", n)
                 or re.search(r"(?:\bcore\s*|\bintel\s*)()(1[234]900)(kf|ks|k|f)?\b", n))   # «Intel 14900K» χωρίς «i9»
            if c:
                tier, num, suf = int(c.group(1) or 9), c.group(2), (c.group(3) or "")
                gen = int(num[:2])
                sc = {9: 80, 7: 77, 5: 70, 3: 58}[tier] - (4 if gen <= 12 else 0) - (8 if suf in ("hx", "h") else 0) + (1 if suf == "ks" else 0)
                sp.update(cpu=f"Core i{tier}-{num}{suf.upper()}", cpu_score=sc)
            else:
                c = re.search(r"(ryzen|ultra)\s*([3579])\b", n)
                if c:
                    sp.update(cpu=f"{c.group(1).title()} {c.group(2)} (μοντέλο;)", cpu_score=55 if c.group(1) == "ryzen" else 68)
    # ---- RAM / SSD (αφού αφαιρεθεί το VRAM)
    kit = re.search(r"\b([1-4])\s*x\s*(8|16|24|32|48|64)\s*gb", rest)   # «2x16GB» = 32 GB
    if kit and int(kit.group(1)) * int(kit.group(2)) in RAM_SIZES:
        sp["ram"] = int(kit.group(1)) * int(kit.group(2))
    for m in ([] if kit else re.finditer(r"(\d{1,3})\s*gb(?!\s*(ssd|nvme|hdd|m\.2|emmc))", rest)):
        v = int(m.group(1))
        if v in RAM_SIZES:
            sp["ram"] = v
            break
    s = re.search(r"(\d(?:[.,]\d)?)\s*tb", rest) or re.search(r"(\d{3,4})\s*gb\s*(?:ssd|nvme|m\.2)?", rest)
    if s:
        v = s.group(1).replace(",", ".")
        sp["ssd"] = f"{v} TB" if "tb" in s.group(0) else f"{v} GB"
    return sp


def score_pc(sp, price, wl):
    perf = sp["gpu_perf"]
    fn = 0.65 * sp["cpu_score"] + 0.35 * min(100, perf * 1.6)
    vs = VRAM_SCORE.get(sp["vram"] or 0, 0)
    ai = min(100, 0.75 * vs + 0.25 * perf) * (0.8 if sp.get("amd") else 1)   # AMD: ROCm αντί για CUDA, λιγότερη υποστήριξη
    ram = sp["ram"] or 0
    ram_adj = 5 if ram >= 64 else 2 if ram >= 48 else 0 if ram >= 32 else -8 if ram else 0
    total = 0.5 * fn + 0.5 * ai + ram_adj
    target_gpus = set(wl["prebuilt"]["target_gpus"])
    gkey = (sp["gpu"] or "").lower().replace("rtx ", "").replace("radeon ", "")
    return {"fn": round(fn), "ai": round(ai), "total": round(total), "value": round(total / (price / 1000), 1),
            "target": bool(sp["x3d9k"] and gkey in target_gpus), "gkey": gkey}


def pc_reject_reason(sp, pre):
    """Κανόνες του watchlist (prebuilt): CPU από τη λίστα, κάρτα AMD/NVIDIA με ≥ min_vram, RAM ≥ min_ram. None = δεκτό."""
    if not sp["cpu"] or not any(re.fullmatch(rx, sp["cpu"], re.I) for rx in pre["allowed_cpus"]):
        return "CPU εκτός λίστας"
    if not (sp["nvidia"] or sp["amd"]) or (sp["vram"] or 0) < pre["min_vram"]:
        return f"VRAM < {pre['min_vram']} GB"
    if (sp["ram"] or 0) < pre["min_ram"]:
        return f"RAM < {pre['min_ram']} GB ή άγνωστη"
    return None


# ============================================================================ matching περιφερειακών
def norm(s):
    s = s.lower().replace("‑", "-")
    return re.sub(r"\s+", " ", re.sub(r"[™®]", "", s))


def matches(target, name, price, wl):
    n = norm(name)
    if not all(re.search(p, n) for p in target["include"]):
        return False
    if any(re.search(p, n) for p in target.get("exclude", []) + wl.get("global_exclude", [])):
        return False
    lo, hi = wl["categories"][target["cat"]].get("min_price", 0), wl["categories"][target["cat"]].get("max_price", 1e9)
    return lo <= price <= hi


def tags_of(target, name):
    n = norm(name)
    return [label for label, rx in target.get("tags", {}).items() if re.search(rx, n)]


# ============================================================================ συλλογή
def collect(wl):
    pre = wl["prebuilt"]
    raw = []
    # --- έτοιμα PC
    log("Έτοιμα PC:")
    for src in pre["sources"]:
        st, kind, arg = src["store"], src["kind"], src["arg"]
        log(f"  {st:9s} {kind:9s} {arg[:70]}")
        if kind == "plaisio":
            raw += plaisio_category(arg)
        elif kind == "eshop_list":
            raw += eshop_list(arg)
        elif kind == "msystems":
            raw += msystems_search(arg)
        elif kind in PC_SOURCES:
            raw += PC_SOURCES[kind](arg, max_pages=src.get("pages", 1))
    imp = load_imports()
    if imp:
        log(f"  import    {len(imp)} τιμές από τον browser (bookmarklet)")
    raw += imp
    return classify(wl, raw, fetch_peripherals=True)


IMPORTS = REPORTS / "imports.json"
SRC_LABEL = {"skroutz": "Skroutz", "kotsovolos": "Κωτσόβολος", "public": "Public", "bestprice": "BestPrice", "you": "You.gr",
             "amazon.de": "Amazon.de", "amazon.it": "Amazon.it", "amazon": "Amazon", "cosmodata": "Cosmodata"}


def load_imports(max_age_h=24):
    """Τιμές που έστειλε ο χρήστης από τον browser του (bookmarklet) – ισχύουν max_age_h ώρες."""
    if not IMPORTS.exists():
        return []
    try:
        items = json.loads(IMPORTS.read_text(encoding="utf-8"))
    except ValueError:
        return []
    cutoff = (dt.datetime.now() - dt.timedelta(hours=max_age_h)).isoformat()
    out = []
    for it in items:
        if it.get("ts", "") < cutoff:
            continue
        p = parse_price(it.get("price"))
        if not p or not it.get("url"):
            continue
        host = urllib.parse.urlparse(it["url"]).netloc
        src = next((v for k, v in SRC_LABEL.items() if k in host), host)
        try:
            rating = float(str(it.get("rating")).replace(",", ".")) if it.get("rating") else None
        except ValueError:
            rating = None
        out.append(offer("import", it.get("name", ""), it["url"], p, rating=rating if rating and rating <= 5 else None,
                         reviews=int(it["reviews"]) if str(it.get("reviews") or "").isdigit() else None,
                         stock=f"από {src}, {it['ts'][11:16]} {it['ts'][8:10]}/{it['ts'][5:7]}"))
    return out


def classify(wl, raw, fetch_peripherals):
    pre = wl["prebuilt"]
    pcs, seen = [], set()
    rejected = {"όχι desktop/εξάρτημα": 0, "CPU εκτός λίστας": 0, f"VRAM < {pre['min_vram']} GB": 0,
                f"RAM < {pre['min_ram']} GB ή άγνωστη": 0, "εκτός εύρους τιμής": 0}
    raw = [o for o in raw if o.get("price")]
    imported = [o for o in raw if o["store"] == "import"]
    for o in raw:
        n = norm(o["name"])
        if o["url"] in seen:
            continue
        seen.add(o["url"])
        if re.search(pre["exclude"], n) or not re.search(pre["require"], n):
            rejected["όχι desktop/εξάρτημα"] += 1
            if DEBUG:
                log(f"      x(desktop) {o['price']:8.0f}  {o['name'][:100]}")
            continue
        sp = parse_specs(o["name"] + " " + o.get("specs", ""))
        why = pc_reject_reason(sp, pre)
        if why:
            rejected[why] += 1
            if DEBUG:
                log(f"      x({why[:10]}) {o['price']:8.0f}  {sp['cpu']} | {sp['gpu']} {sp['vram']} | {sp['ram']}  {o['name'][:80]}")
            continue
        if not (pre["min_price"] <= o["price"] <= pre["max_price"]):
            rejected["εκτός εύρους τιμής"] += 1
            continue
        o.update(cat="prebuilt", target="pc", spec=sp, score=score_pc(sp, o["price"], wl))
        pcs.append(o)
    log(f"  -> {len(pcs)} έτοιμα PC από {len(raw)} προϊόντα ({', '.join(f'{k}: {v}' for k, v in rejected.items())})")

    # --- περιφερειακά
    log("Περιφερειακά:")
    cat_pages = {}
    if fetch_peripherals:
        for cat_key, url in wl["peripheral_categories"]["plaisio"].items():
            log(f"  plaisio   {cat_key}")
            cat_pages.setdefault(cat_key, []).extend(plaisio_category(url))
    pers = []
    for t in wl["targets"]:
        n_hit = 0
        for o in cat_pages.get(t["cat"], []) + imported:
            if matches(t, o["name"], o["price"], wl):
                pers.append(dict(o, cat=t["cat"], target=t["key"], tags=tags_of(t, o["name"])))
                n_hit += 1
        for sk in (wl["peripheral_search_stores"] if fetch_peripherals else []):
            res = SEARCHERS[sk](t.get("q_" + sk) or t["q"])
            for o in res:
                if matches(t, o["name"], o["price"], wl):
                    pers.append(dict(o, cat=t["cat"], target=t["key"], tags=tags_of(t, o["name"])))
                    n_hit += 1
                elif DEBUG:
                    log(f"      x {o['price']:8.2f} {sk:8s} {o['name'][:90]}")
        log(f"  {t['key']:14s} {n_hit} προσφορές")
    seen, out = set(), []
    for o in pcs + pers:
        k = (o["store"], o["url"], o["target"])
        if k not in seen:
            seen.add(k)
            out.append(o)
    return out


# ============================================================================ ιστορικό
def db_open():
    con = sqlite3.connect(DB)
    con.execute("create table if not exists seen(key text primary key, store text, cat text, target text, name text, url text,"
                " first_seen text, last_seen text, last_price real)")
    con.execute("create table if not exists hist(key text, day text, pmin real, plast real, primary key(key, day))")
    con.execute("create table if not exists alerts(key text primary key, price real, ts text)")
    if con.execute("select count(*) from hist").fetchone()[0] == 0 and OLD_DB.exists():
        # μεταφορά ιστορικού ελληνικών καταστημάτων από την προηγούμενη έκδοση
        old = sqlite3.connect(OLD_DB)
        try:
            for k, day, price in old.execute("select key, day, price from hist"):
                if k.split("|", 1)[0] in ("plaisio", "eshop", "germanos"):
                    con.execute("insert or ignore into hist values(?,?,?,?)", (k, day, price, price))
        except sqlite3.Error:
            pass
        old.close()
    return con


def history_sync(con, offers, today):
    first_run = con.execute("select count(distinct day) from hist where day<>?", (today,)).fetchone()[0] == 0
    d30 = (dt.date.fromisoformat(today) - dt.timedelta(days=30)).isoformat()
    now = dt.datetime.now().isoformat(timespec="minutes")
    for o in offers:
        k = o["store"] + "|" + o["url"]
        o["key"] = k
        rows = con.execute("select day, pmin, plast from hist where key=? order by day", (k,)).fetchall()
        prior = [(d, pm) for d, pm, _ in rows if d < today]
        p30 = [pm for d, pm in prior if d >= d30]
        row = con.execute("select first_seen, last_price from seen where key=?", (k,)).fetchone()
        o["stats"] = {
            "days": len({d for d, *_ in rows} | {today}),
            "min30": min(p30) if p30 else None,
            "med30": round(statistics.median(p30), 2) if p30 else None,
            "allmin": min(pm for _, pm in prior) if prior else None,
            "first_seen": row[0] if row else today,
        }
        o["is_new"] = (row is None or row[0] == today) and not first_run
        o["drop_from"] = row[1] if row and o["price"] < row[1] - 0.5 else None
        if row is None:
            con.execute("insert into seen values(?,?,?,?,?,?,?,?,?)",
                        (k, o["store"], o["cat"], o["target"], o["name"], o["url"], today, now, o["price"]))
        else:
            con.execute("update seen set name=?, cat=?, target=?, last_seen=?, last_price=? where key=?",
                        (o["name"], o["cat"], o["target"], now, o["price"], k))
        con.execute("insert into hist values(?,?,?,?) on conflict(key, day) do update set pmin=min(pmin, excluded.pmin), plast=excluded.plast",
                    (k, today, o["price"], o["price"]))
        series = con.execute("select day, pmin from hist where key=? order by day desc limit 90", (k,)).fetchall()
        o["series"] = [[d, p] for d, p in reversed(series)]
    con.commit()
    return first_run


def history_load(con, wl):
    """Για --no-fetch: οι προσφορές της τελευταίας εκτέλεσης."""
    last = con.execute("select max(last_seen) from seen").fetchone()[0]
    if not last:
        return [], dt.date.today().isoformat()
    day = last[:10]
    rows = con.execute("select key, store, cat, target, name, url, last_price from seen where substr(last_seen,1,10)=?", (day,)).fetchall()
    out = []
    for k, store, cat, target, name, url, price in rows:
        o = offer(store, name, url, price)
        o.update(cat=cat, target=target)
        if cat == "prebuilt":
            o["spec"] = parse_specs(name)
            o["score"] = score_pc(o["spec"], price, wl)
        else:
            t = next((t for t in wl["targets"] if t["key"] == target), None)
            o["tags"] = tags_of(t, name) if t else []
        out.append(o)
    return out, day


# ============================================================================ αξιολόγηση προσφοράς
def assess(o, wl, today):
    al = wl["alerts"]
    p, st = o["price"], o["stats"]
    notes, badges = [], []
    disc = (1 - p / o["old"]) if o.get("old") else None
    real = None
    if disc and disc >= 0.03:
        badges.append(["disc", f"-{disc * 100:.0f}% από {fmt(o['old'])} €"])
    if o.get("rrp") and o["rrp"] > p * 1.03 and not o.get("old"):
        notes.append(f"προτεινόμενη λιανική {fmt(o['rrp'])} €")
    if st["min30"] is not None:
        if p < st["min30"] - 0.5:
            real = True
            notes.append(f"φθηνότερο από κάθε τιμή των τελευταίων 30 ημερών (πριν: {fmt(st['min30'])} €)")
        elif disc and st["min30"] <= p + 0.5:
            real = False
            notes.append(f"η «έκπτωση» ΔΕΝ είναι πραγματική: ήταν {fmt(st['min30'])} € μέσα στις τελευταίες 30 μέρες")
    if o.get("min30_store"):
        if p <= o["min30_store"] + 0.5:
            notes.append(f"στο χαμηλότερο 30 ημερών του καταστήματος ({fmt(o['min30_store'])} €)")
            if disc and real is None:
                real = True
        else:
            notes.append(f"ακριβότερο από το 30ήμερο χαμηλό του καταστήματος ({fmt(o['min30_store'])} €)")
            real = False if disc else real
    if disc and real is None:
        notes.append("έκπτωση καταστήματος: δεν επιβεβαιώνεται ακόμα από ιστορικό")
    drop_med = (p / st["med30"] - 1) if st["med30"] else None
    if st["allmin"] is not None and p < st["allmin"] - 0.5:
        badges.append(["low", "ιστορικό χαμηλό"])
    if real is False:
        badges.append(["fake", "ψεύτικη έκπτωση"])
    elif real is True and disc:
        badges.append(["real", "πραγματική έκπτωση"])
    if o.get("is_new"):
        badges.append(["new", "ΝΕΟ"])
    if o.get("drop_from"):
        badges.append(["drop", f"↓ από {fmt(o['drop_from'])} €"])
    bf = wl.get("black_friday", {})
    if bf and bf["start"] <= today <= bf["end"] and disc and disc >= 0.05 and real is not False:
        badges.append(["bf", "Black Friday"])
    if "black friday" in o["name"].lower():
        badges.append(["bf", "Black Friday"])

    # ---- εξαιρετική προσφορά (email)
    why = []
    hist_ok = st["days"] >= al["min_history_days"]
    if drop_med is not None and hist_ok and drop_med <= -al["drop_vs_median30"] and (st["min30"] is None or p < st["min30"] - 0.5):
        why.append(f"{-drop_med * 100:.0f}% κάτω από τη διάμεση 30 ημερών")
    if st["allmin"] and st["days"] >= 3 and p <= st["allmin"] * (1 - al["below_alltime_low"]):
        why.append(f"{(1 - p / st['allmin']) * 100:.0f}% κάτω από το προηγούμενο ιστορικό χαμηλό")
    if real is True and disc and disc >= al["verified_store_discount"]:
        why.append(f"επιβεβαιωμένη έκπτωση {disc * 100:.0f}%")
    if o["cat"] == "prebuilt":
        sc = o["score"]
        ref = al["prebuilt_target_max_price"].get(sc["gkey"])
        if sc["target"] and ref and p <= ref:
            why.append(f"στόχος (X3D + {o['spec']['gpu']}) ≤ {fmt(ref)} €")
        if sc["total"] < al["prebuilt_min_score"]:
            why = []   # δεν μας ενδιαφέρουν αδύναμα PC όσο φθηνά κι αν είναι
    else:
        t = next((t for t in wl["targets"] if t["key"] == o["target"]), {})
        ref = t.get("ref_price")
        if ref and p <= ref * (1 - al["peripheral_below_ref"]):
            why.append(f"{(1 - p / ref) * 100:.0f}% κάτω από την τιμή αναφοράς {fmt(ref)} €")
    unavailable = bool(o.get("stock") and re.search(r"(?i)μη διαθέσιμο|εξαντλ", o["stock"]))
    if unavailable:
        why = []
    o["excellent"] = bool(why)
    o["why"] = why
    if why:
        badges.insert(0, ["exc", "ΕΞΑΙΡΕΤΙΚΗ"])
    # ---- «πραγματική ευκαιρία» για το email (κάθε 2 ώρες): εξαιρετική, επιβεβαιωμένη έκπτωση, ή νέο ιστορικό χαμηλό
    opp = list(why)
    if not opp and not unavailable:
        if real is True and disc and disc >= al.get("email_real_discount_min", 0.05):
            opp.append(f"πραγματική έκπτωση {disc * 100:.0f}% (επιβεβαιωμένη από ιστορικό)")
        elif real is True and st["min30"] is not None and p <= st["min30"] * (1 - al.get("email_real_discount_min", 0.05)):
            opp.append(f"{(1 - p / st['min30']) * 100:.0f}% κάτω από κάθε τιμή των τελευταίων 30 ημερών")
        if al.get("email_new_low", True) and st["allmin"] is not None and st["days"] >= 3 and p < st["allmin"] * 0.98:
            opp.append(f"νέο ιστορικό χαμηλό (πριν {fmt(st['allmin'])} €)")
        if o["cat"] == "prebuilt" and o["score"]["total"] < al["prebuilt_min_score"]:
            opp = []
    o["opportunity"] = opp
    if opp and not why:
        badges.insert(0, ["real", "ευκαιρία (email)"])
    o["badges"], o["notes"] = badges, notes
    o["real_disc"] = real
    o["drop_med"] = round(drop_med, 3) if drop_med is not None else None
    o["net"] = round(p / (1 + VAT), 2)


def fmt(n):
    if n is None:
        return "–"
    return f"{n:,.0f}".replace(",", ".") if n >= 100 else f"{n:.2f}".replace(".", ",")


# ============================================================================ email
def notify_cfg():
    """notify.json ή (στο GitHub Actions) η μεταβλητή PC_DEALS_NOTIFY με το ίδιο JSON, από secret."""
    if os.environ.get("PC_DEALS_NOTIFY"):
        cfg = json.loads(os.environ["PC_DEALS_NOTIFY"].lstrip("﻿"))
    elif NOTIFY.exists():
        cfg = json.loads(NOTIFY.read_text(encoding="utf-8"))
    else:
        return {}
    cfg["smtp_password"] = os.environ.get("PC_DEALS_SMTP_PASSWORD") or cfg.get("smtp_password", "")
    return cfg


def shown_addr(cfg):
    """Στο GitHub Actions τα logs είναι δημόσια: δεν τυπώνουμε τη διεύθυνση."""
    return "(παραλήπτης από secret)" if os.environ.get("GITHUB_ACTIONS") else cfg["to"]


def email_ready(cfg):
    return bool(cfg.get("enabled") and cfg.get("to") and cfg.get("smtp_host") and cfg.get("smtp_password"))


def send_email(cfg, subject, body_html):
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, cfg.get("from") or cfg["smtp_user"], cfg["to"]
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    port = int(cfg.get("smtp_port", 587))
    if port == 465:
        srv = smtplib.SMTP_SSL(cfg["smtp_host"], port, timeout=30)
    else:
        srv = smtplib.SMTP(cfg["smtp_host"], port, timeout=30)
        if cfg.get("starttls", True):
            srv.starttls()
    srv.login(cfg.get("smtp_user") or cfg["to"], cfg["smtp_password"])
    srv.sendmail(msg["From"], [a.strip() for a in cfg["to"].split(",")], msg.as_string())
    srv.quit()


def email_alerts(con, offers, wl):
    cfg = notify_cfg()
    opps = [o for o in offers if o.get("opportunity")]
    fresh = []
    for o in opps:   # μόνο νέες: μία φορά ανά προϊόν, ξανά μόνο αν πέσει ≥2% από την τιμή του τελευταίου email
        row = con.execute("select price from alerts where key=?", (o["key"],)).fetchone()
        if row is None or o["price"] < row[0] * 0.98:
            fresh.append(o)
    if not fresh:
        log(f"Email: καμία νέα πραγματική ευκαιρία ({len(opps)} ήδη ειδοποιημένες ή καμία).")
        return "καμία νέα πραγματική ευκαιρία"
    if not email_ready(cfg):
        log(f"Email: {len(fresh)} νέες ευκαιρίες αλλά το notify.json δεν έχει ρυθμιστεί (κωδικός SMTP).")
        return f"{len(fresh)} νέες ευκαιρίες – email ΔΕΝ στάλθηκε (λείπει κωδικός SMTP στο notify.json)"
    labels = {t["key"]: t["label"] for t in wl["targets"]}
    n_exc = sum(1 for o in fresh if o.get("excellent"))
    exc_tag = "<b style='color:#16a34a'>ΕΞΑΙΡΕΤΙΚΗ</b> "
    rows = "".join(
        f"<tr><td style='padding:6px;border-bottom:1px solid #ddd'>{exc_tag if o.get('excellent') else ''}"
        f"<a href='{html.escape(o['url'])}'>{html.escape(o['name'][:120])}</a>"
        f"<br><small>{html.escape(wl['stores'][o['store']]['label'])} · {html.escape('PC' if o['cat'] == 'prebuilt' else labels.get(o['target'], o['target']))}"
        f" · {html.escape('; '.join(o['opportunity']))}</small></td>"
        f"<td style='padding:6px;border-bottom:1px solid #ddd;white-space:nowrap'><b>{fmt(o['price'])} €</b>"
        f"{'<br><s>' + fmt(o['old']) + ' €</s>' if o.get('old') else ''}</td></tr>"
        for o in sorted(fresh, key=lambda o: (not o.get("excellent"), o["cat"] != "prebuilt", o["price"])))
    body = (f"<p>Βρέθηκαν <b>{len(fresh)}</b> νέες πραγματικές ευκαιρίες σε ελληνικά καταστήματα"
            f"{f' ({n_exc} εξαιρετικές)' if n_exc else ''}. «Πραγματική» = επιβεβαιωμένη από το ιστορικό τιμών, όχι φουσκωμένη αρχική τιμή.</p>"
            f"<table style='border-collapse:collapse;font:14px system-ui'>{rows}</table>"
            f"<p><a href='{html.escape(cfg.get('page_url', 'https://kchalv.github.io/pc-deals/'))}'>Άνοιγμα σελίδας προσφορών</a></p>")
    try:
        send_email(cfg, f"PC deals: {len(fresh)} νέες πραγματικές ευκαιρίες" + (f" ({n_exc} εξαιρετικές)" if n_exc else ""), body)
    except Exception as e:  # noqa: BLE001
        log(f"Email: αποτυχία αποστολής: {type(e).__name__}: {e}")
        return f"αποτυχία email: {type(e).__name__}"
    now = dt.datetime.now().isoformat(timespec="minutes")
    for o in fresh:
        con.execute("insert or replace into alerts values(?,?,?)", (o["key"], o["price"], now))
    con.commit()
    log(f"Email: στάλθηκε για {len(fresh)} προσφορές -> {shown_addr(cfg)}")
    return f"email στάλθηκε για {len(fresh)} προσφορές"


# ============================================================================ σελίδα
def render(wl, offers, today, email_msg, first_run):
    cfg = notify_cfg()
    data = {
        "generated": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "today": today,
        "first_run": first_run,
        "email": {"ready": email_ready(cfg), "msg": email_msg, "to": cfg.get("to", "")},
        "stores": {k: {"label": v["label"], "note": v.get("note", "")} for k, v in wl["stores"].items()},
        "targets": [{k: t.get(k) for k in ("key", "cat", "label", "ref_price", "review", "links")} for t in wl["targets"]],
        "cats": {k: v["label"] for k, v in wl["categories"].items()},
        "manual": wl["manual_links"],
        "advice": wl["advice"],
        "bf": wl.get("black_friday", {}),
        "fetch": [{"store": s, "url": u, "code": c, "n": n, "note": note} for s, u, c, n, note in FETCH_LOG],
        "offers": [{k: o.get(k) for k in ("store", "cat", "target", "name", "url", "price", "net", "old", "min30_store", "rrp",
                                          "rating", "reviews", "stock", "spec", "score", "stats", "series", "badges", "notes",
                                          "excellent", "why", "opportunity", "real_disc", "drop_med", "tags")} for o in offers],
    }
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return PAGE_TEMPLATE.replace("__DATA__", blob)


PAGE_TEMPLATE = r"""<!doctype html><html lang="el"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gaming PC προσφορές</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--mut:#6b7280;--line:#e5e7eb;--acc:#2563eb;--good:#16a34a;--goodbg:#dcfce7;--warn:#b45309;--warnbg:#fef3c7;--bad:#dc2626;--badbg:#fee2e2;--chip:#eef2ff;--chipfg:#3730a3;--bar:#c7d2fe}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1218;--card:#171b23;--fg:#e5e7eb;--mut:#9ca3af;--line:#2a303b;--acc:#60a5fa;--good:#4ade80;--goodbg:#13291c;--warn:#fbbf24;--warnbg:#2b2210;--bad:#f87171;--badbg:#2c1515;--chip:#1e2340;--chipfg:#c7d2fe;--bar:#3b4a8a}}
:root[data-theme="dark"]{--bg:#0f1218;--card:#171b23;--fg:#e5e7eb;--mut:#9ca3af;--line:#2a303b;--acc:#60a5fa;--good:#4ade80;--goodbg:#13291c;--warn:#fbbf24;--warnbg:#2b2210;--bad:#f87171;--badbg:#2c1515;--chip:#1e2340;--chipfg:#c7d2fe;--bar:#3b4a8a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;flex:1 1 260px}
.btn{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:7px 12px;border-radius:8px;cursor:pointer;font:inherit}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#fff}.btn:disabled{opacity:.55;cursor:default}
main{max-width:1500px;margin:0 auto;padding:12px 16px 40px}
.tabs{display:flex;gap:6px;margin:6px 0 12px;flex-wrap:wrap}.tab{padding:7px 14px;border-radius:999px;border:1px solid var(--line);background:var(--card);cursor:pointer}
.tab.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0}
.mut{color:var(--mut)}.small{font-size:12px}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}
select,input[type=search]{font:inherit;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
.tbl{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.tbl th{font-size:12px;text-align:left;color:var(--mut);font-weight:600;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}
.tbl td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
tr.exc td{background:var(--goodbg)}
.b{display:inline-block;font-size:11px;padding:1px 7px;border-radius:8px;margin:0 4px 3px 0;white-space:nowrap;background:var(--line);color:var(--fg)}
.b.exc{background:var(--good);color:#fff;font-weight:700}.b.low{background:#7c3aed;color:#fff}.b.new{background:var(--acc);color:#fff}
.b.drop{background:var(--bad);color:#fff}.b.fake{background:var(--badbg);color:var(--bad)}.b.real{background:var(--goodbg);color:var(--good)}
.b.bf{background:#111;color:#fde047}.b.tgt{background:#f59e0b;color:#111;font-weight:700}.b.disc{background:var(--warnbg);color:var(--warn)}
.chip{display:inline-block;font-size:12px;padding:1px 7px;border-radius:6px;background:var(--chip);color:var(--chipfg);margin:2px 4px 0 0}
.price{font-weight:700;font-size:15px;white-space:nowrap}.old{text-decoration:line-through;color:var(--mut);font-size:12px}
.bars{min-width:150px}.bar{display:flex;align-items:center;gap:6px;font-size:12px}.bar i{display:block;height:6px;border-radius:3px;background:var(--bar)}
.bar i.f{background:var(--acc)}.bar span{width:58px;color:var(--mut)}
.stars{color:#f59e0b;white-space:nowrap}
.notes{font-size:12px;color:var(--mut);margin-top:3px}.notes b{color:var(--fg)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card h4{margin:2px 0 6px;font-size:14px}
svg.spark{display:block}
.grp{margin-top:18px}.grp h3{margin:0 0 6px}
.links a{margin-right:8px;white-space:nowrap}
#status{font-size:12px}
@media (max-width:820px){.hide-m{display:none}.tbl td,.tbl th{padding:6px}}
</style></head><body>
<header>
 <h1>Gaming PC προσφορές · ελληνικά καταστήματα</h1>
 <span id="status" class="mut"></span>
 <a class="btn" href="/bookmarklet" title="Εισαγωγή τιμών από Skroutz / Κωτσόβολο / Public / BestPrice μέσω του browser σου">➕ Skroutz κ.ά.</a>
 <button class="btn primary" id="refresh">↻ Ανανέωση τιμών</button>
</header>
<main>
<div class="tabs" id="tabs"></div>
<div id="view"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const $ = (s, el=document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const eur = n => n == null ? '–' : (n >= 100 ? Math.round(n).toLocaleString('el-GR') : n.toFixed(2).replace('.', ',')) + ' €';
const ls = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) { return null; } };
const st = { tab: ls('tab') || 'pc', pcf: ['target', 'all', 'nvidia', 'amd', 'x3d', 'exc'].includes(ls('pcf')) ? ls('pcf') : 'all', sort: ls('sort') || 'deal', q: '', store: 'all' };
const tlabel = Object.fromEntries(D.targets.map(t => [t.key, t]));

function spark(series) {
  if (!series || series.length < 2) return '<span class="small mut">ιστορικό από σήμερα</span>';
  const w = 110, h = 28, p = series.map(s => s[1]), mn = Math.min(...p), mx = Math.max(...p), r = (mx - mn) || 1;
  const pts = p.map((v, i) => `${(i / (p.length - 1) * w).toFixed(1)},${(h - 3 - (v - mn) / r * (h - 6)).toFixed(1)}`).join(' ');
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline fill="none" stroke="currentColor" stroke-width="1.5" points="${pts}" style="color:var(--acc)"/></svg>`;
}
function stars(o) {
  if (o.rating == null) return '<span class="small mut">–</span>';
  const full = Math.round(o.rating);
  return `<span class="stars">${'★'.repeat(full)}${'☆'.repeat(5 - full)}</span> <span class="small">${o.rating.toFixed(1)} (${o.reviews})</span>`;
}
function badges(o) {
  let b = (o.badges || []).map(x => `<span class="b ${x[0]}">${esc(x[1])}</span>`).join('');
  if (o.score && o.score.target) b = '<span class="b tgt">★ ΣΤΟΧΟΣ</span>' + b;
  (o.tags || []).forEach(t => b += `<span class="b">${esc(t)}</span>`);
  return b;
}
function hist(o) {
  const s = o.stats || {};
  return `${spark(o.series)}<div class="small mut">30ήμ. χαμηλό ${eur(s.min30)}<br>ιστορικό χαμηλό ${eur(s.allmin)} · ${s.days || 1} μέρες</div>`;
}
function ext(name) {
  const q = encodeURIComponent(name.replace(/\(.*?\)/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 70));
  return `<span class="links small"><a target="_blank" href="https://www.skroutz.gr/search?keyphrase=${q}">Skroutz</a><a target="_blank" href="https://www.bestprice.gr/search?q=${q}">BestPrice</a><a target="_blank" href="https://www.youtube.com/results?search_query=${q}+review">YouTube review</a></span>`;
}
function priceCell(o) {
  return `<div class="price">${eur(o.price)}</div>${o.old ? `<div class="old">${eur(o.old)}</div>` : ''}<div class="small mut">${eur(o.net)} χωρίς ΦΠΑ</div>`;
}
function dealKey(o) { // μικρότερο = καλύτερη προσφορά
  let d = 0;
  if (o.excellent) d -= 100;
  if (o.drop_med != null) d += o.drop_med * 100;
  if (o.real_disc === true && o.old) d -= (1 - o.price / o.old) * 100;
  if (o.real_disc === false) d += 5;
  return d;
}

// ---------------------------------------------------------------- tabs
const TABS = [['pc', 'Έτοιμα PC'], ['per', 'Ποντίκι · Πληκτρολόγιο · Οθόνη'], ['top', 'Κορυφαίες προσφορές'], ['info', 'Οδηγός & καταστήματα']];
function drawTabs() {
  $('#tabs').innerHTML = TABS.map(([k, l]) => `<span class="tab ${st.tab === k ? 'on' : ''}" data-k="${k}">${l}</span>`).join('');
  document.querySelectorAll('.tab').forEach(t => t.onclick = () => { st.tab = t.dataset.k; ls('tab', st.tab); draw(); });
}
function summary() {
  const pcs = D.offers.filter(o => o.cat === 'prebuilt'), per = D.offers.filter(o => o.cat !== 'prebuilt');
  const exc = D.offers.filter(o => o.excellent).length;
  const bfDays = D.bf.date ? Math.ceil((new Date(D.bf.date) - new Date(D.today)) / 864e5) : null;
  return `<div class="box"><b>${pcs.length}</b> έτοιμα PC (9800X3D / 7800X3D / 270K Plus / 14900K · ≥ 32 GB RAM · ≥ 16 GB VRAM) · <b>${per.length}</b> προσφορές περιφερειακών · <b>${exc}</b> εξαιρετικές ·
  ενημέρωση ${esc(D.generated)}${bfDays != null && bfDays >= 0 ? ` · Black Friday σε <b>${bfDays}</b> μέρες (${esc(D.bf.label || '')})` : ''}
  <div class="small mut" style="margin-top:4px">Email: ${D.email.ready ? 'ενεργό προς ' + esc(D.email.to) : '<b style="color:var(--warn)">δεν έχει ρυθμιστεί κωδικός SMTP (notify.json)</b>'} · ${esc(D.email.msg || '')}
  ${D.first_run ? ' · <b>Πρώτη μέρα ιστορικού</b>: ΝΕΟ / ιστορικό χαμηλό / ψεύτικη έκπτωση γεμίζουν όσο μαζεύονται τιμές.' : ''}</div></div>`;
}

// ---------------------------------------------------------------- PCs
function pcRows(list) {
  return list.map(o => {
    const s = o.spec, sc = o.score;
    const chips = [s.cpu, s.gpu ? `${s.gpu}${s.vram ? ' ' + s.vram + ' GB' : ''}` : null, s.ram ? s.ram + ' GB RAM' : null, s.ssd].filter(Boolean)
      .map(c => `<span class="chip">${esc(c)}</span>`).join('');
    const notes = (o.why && o.why.length ? `<b>Γιατί εξαιρετική:</b> ${esc(o.why.join(' · '))}<br>` : '') + esc((o.notes || []).join(' · '));
    return `<tr class="${o.excellent ? 'exc' : ''}"><td>${badges(o)}<div><a target="_blank" href="${esc(o.url)}">${esc(o.name)}</a></div>${chips}
      <div class="notes">${notes}${o.stock ? ` <span>· ${esc(o.stock)}</span>` : ''}</div><div>${ext(o.name)}</div></td>
      <td>${esc(D.stores[o.store].label)}</td><td>${priceCell(o)}</td><td class="hide-m">${hist(o)}</td>
      <td class="bars"><div class="bar"><span>Fortnite</span><i class="f" style="width:${sc.fn}px"></i>${sc.fn}</div>
        <div class="bar"><span>AI</span><i style="width:${sc.ai}px"></i>${sc.ai}</div>
        <div class="bar"><span>Σύνολο</span><b>${sc.total}</b>&nbsp;· αξία <b>${sc.value}</b></div></td>
      <td class="hide-m">${stars(o)}</td></tr>`;
  }).join('');
}
function drawPC() {
  let list = D.offers.filter(o => o.cat === 'prebuilt');
  const stores = [...new Set(list.map(o => o.store))];
  if (st.pcf === 'target') list = list.filter(o => o.score.target);
  if (st.pcf === 'x3d') list = list.filter(o => o.spec.x3d);
  if (st.pcf === 'nvidia') list = list.filter(o => o.spec.nvidia);
  if (st.pcf === 'amd') list = list.filter(o => o.spec.amd);
  if (st.pcf === 'exc') list = list.filter(o => o.excellent);
  if (st.store !== 'all') list = list.filter(o => o.store === st.store);
  if (st.q) { const q = st.q.toLowerCase(); list = list.filter(o => o.name.toLowerCase().includes(q)); }
  const sorters = { deal: (a, b) => dealKey(a) - dealKey(b) || b.score.value - a.score.value, value: (a, b) => b.score.value - a.score.value,
    price: (a, b) => a.price - b.price, fn: (a, b) => b.score.fn - a.score.fn || a.price - b.price, ai: (a, b) => b.score.ai - a.score.ai || a.price - b.price,
    total: (a, b) => b.score.total - a.score.total || a.price - b.price };
  list.sort(sorters[st.sort] || sorters.deal);
  return `${summary()}
  <div class="controls">
   <select id="pcf"><option value="all">Όλα (AMD + NVIDIA)</option><option value="target">★ Στόχος: 9800X3D & RTX 5070 Ti / 5080 / 5090 / 4090 / RX 9070 XT / 7900 XTX</option>
     <option value="nvidia">Μόνο NVIDIA (CUDA)</option><option value="amd">Μόνο AMD Radeon</option>
     <option value="x3d">CPU X3D (Fortnite)</option><option value="exc">Μόνο εξαιρετικές</option></select>
   <select id="sort"><option value="deal">Ταξινόμηση: καλύτερη προσφορά</option><option value="value">Αξία (βαθμός / 1.000 €)</option><option value="price">Τιμή ↑</option>
     <option value="total">Συνολικός βαθμός</option><option value="fn">Fortnite</option><option value="ai">AI / local LLM</option></select>
   <select id="store"><option value="all">Όλα τα καταστήματα</option>${stores.map(s => `<option value="${s}">${esc(D.stores[s].label)}</option>`).join('')}</select>
   <input type="search" id="q" placeholder="αναζήτηση (π.χ. 5080, Omen)" value="${esc(st.q)}">
   <span class="small mut">${list.length} PC</span>
  </div>
  <table class="tbl"><thead><tr><th>PC</th><th>Κατάστημα</th><th>Τιμή</th><th class="hide-m">Ιστορικό τιμής</th><th>Βαθμολογία</th><th class="hide-m">Κριτικές</th></tr></thead>
  <tbody>${pcRows(list) || '<tr><td colspan="6" class="mut">Κανένα PC με αυτό το φίλτρο. Δοκίμασε «Όλα (AMD + NVIDIA)».</td></tr>'}</tbody></table>
  <p class="small mut">Βαθμολογία: Fortnite = 65% CPU (X3D κορυφή) + 35% GPU · AI = 75% VRAM + 25% GPU (AMD ×0,8: χωρίς CUDA) · Σύνολο = μέσος όρος ± RAM (64 GB +5, 16 GB −8) · Αξία = σύνολο ανά 1.000 €.</p>`;
}

// ---------------------------------------------------------------- περιφερειακά
function drawPer() {
  let html = summary();
  for (const cat of ['monitor', 'keyboard', 'mouse']) {
    html += `<div class="grp"><h3>${esc(D.cats[cat])}</h3>`;
    for (const t of D.targets.filter(t => t.cat === cat)) {
      const list = D.offers.filter(o => o.target === t.key).sort((a, b) => a.price - b.price);
      const links = Object.entries(t.links || {}).map(([l, u]) => `<a target="_blank" href="${esc(u)}">${esc(l)}</a>`).join('');
      html += `<div class="box"><b>${esc(t.label)}</b> ${t.ref_price ? `<span class="small mut">· τιμή αναφοράς ${eur(t.ref_price)}</span>` : ''}
        <div class="small" style="margin:4px 0">${esc(t.review || '')}</div><div class="links small">${links}${ext(t.label)}</div>
        ${list.length ? `<table class="tbl" style="margin-top:8px"><tbody>${list.map(o => `<tr class="${o.excellent ? 'exc' : ''}"><td>${badges(o)}<div><a target="_blank" href="${esc(o.url)}">${esc(o.name)}</a></div>
          <div class="notes">${o.why && o.why.length ? '<b>Γιατί εξαιρετική:</b> ' + esc(o.why.join(' · ')) + '<br>' : ''}${esc((o.notes || []).join(' · '))}${o.stock ? ' · ' + esc(o.stock) : ''}</div></td>
          <td>${esc(D.stores[o.store].label)}</td><td>${priceCell(o)}</td><td class="hide-m">${hist(o)}</td><td class="hide-m">${stars(o)}</td></tr>`).join('')}</tbody></table>`
          : '<div class="small mut" style="margin-top:6px">Δεν βρέθηκε σε κατάστημα που διαβάζεται αυτόματα. Δες τα links (Skroutz/BestPrice).</div>'}</div>`;
    }
    html += '</div>';
  }
  return html;
}

// ---------------------------------------------------------------- κορυφαίες
function drawTop() {
  const pcs = D.offers.filter(o => o.cat === 'prebuilt');
  const pick = (arr, n) => arr.slice(0, n);
  const card = (o, extra) => `<div class="card">${badges(o)}<h4><a target="_blank" href="${esc(o.url)}">${esc(o.name)}</a></h4>
    <div>${priceCell(o)}</div><div class="small mut">${esc(D.stores[o.store].label)}${extra ? ' · ' + extra : ''}</div>
    <div class="notes">${esc([...(o.why || []), ...(o.notes || [])].join(' · '))}</div></div>`;
  const best = (f, key) => pick(pcs.filter(f).sort(key), 4);
  const sec = (title, arr, ex) => `<div class="grp"><h3>${title}</h3>${arr.length ? `<div class="cards">${arr.map(o => card(o, ex(o))).join('')}</div>` : '<p class="mut">Κανένα σήμερα.</p>'}</div>`;
  const pcx = o => `Fortnite ${o.score.fn} · AI ${o.score.ai} · αξία ${o.score.value}`;
  const exc = D.offers.filter(o => o.excellent);
  return summary()
    + sec('🔥 Εξαιρετικές προσφορές (στέλνουν email)', exc, o => o.cat === 'prebuilt' ? pcx(o) : (tlabel[o.target] || {}).label)
    + sec('★ Στόχος: 9800X3D με RTX 5070 Ti / 5080 / 5090 / RX 9070 XT / 7900 XTX – φθηνότερα', best(o => o.score.target, (a, b) => a.price - b.price), pcx)
    + sec('Καλύτερη αξία για Fortnite + AI', best(o => true, (a, b) => b.score.value - a.score.value), pcx)
    + sec('Καλύτερο για local LLM (περισσότερη VRAM)', best(o => (o.spec.vram || 0) >= 24, (a, b) => a.price - b.price), pcx)
    + sec('Φθηνότερο σοβαρό PC για Fortnite (X3D)', best(o => o.spec.x3d, (a, b) => a.price - b.price), pcx)
    + sec('Περιφερειακά: χαμηλότερη τιμή ανά μοντέλο', D.targets.map(t => D.offers.filter(o => o.target === t.key).sort((a, b) => a.price - b.price)[0]).filter(Boolean), o => (tlabel[o.target] || {}).label);
}

// ---------------------------------------------------------------- οδηγός
function drawInfo() {
  const adv = D.advice.map(a => `<li>${esc(a)}</li>`).join('');
  const man = D.manual.map(m => `<li><a target="_blank" href="${esc(m.url)}">${esc(m.label)}</a> <span class="small mut">${esc(m.note || '')}</span></li>`).join('');
  const stores = Object.entries(D.stores).map(([k, s]) => `<li><b>${esc(s.label)}</b> <span class="small mut">${esc(s.note)}</span></li>`).join('');
  const fetch = D.fetch.map(f => `<tr><td>${esc(f.store)}</td><td><a target="_blank" href="${esc(f.url)}">${esc(f.url.slice(0, 90))}</a></td><td>${f.code}</td><td>${f.n}</td><td>${esc(f.note)}</td></tr>`).join('');
  return `<div class="box"><h3 style="margin-top:0">Τι να αγοράσεις (Fortnite + local LLM / AI agents)</h3><ul>${adv}</ul></div>
  <div class="box"><h3 style="margin-top:0">Καταστήματα που διαβάζονται αυτόματα</h3><ul>${stores}</ul></div>
  <div class="box"><h3 style="margin-top:0">Χειροκίνητος έλεγχος (μπλοκάρουν αυτόματη ανάγνωση) · Black Friday σελίδες · ιστορικό τιμών</h3><ul>${man}</ul></div>
  <div class="box"><h3 style="margin-top:0">Τεχνικά: τι τραβήχτηκε</h3><table class="tbl small"><tr><th>Κατάστημα</th><th>URL</th><th>HTTP</th><th>προϊόντα</th><th></th></tr>${fetch}</table></div>`;
}

function draw() {
  drawTabs();
  const v = $('#view');
  v.innerHTML = st.tab === 'pc' ? drawPC() : st.tab === 'per' ? drawPer() : st.tab === 'top' ? drawTop() : drawInfo();
  if (st.tab === 'pc') {
    $('#pcf').value = st.pcf; $('#sort').value = st.sort; $('#store').value = st.store;
    $('#pcf').onchange = e => { st.pcf = e.target.value; ls('pcf', st.pcf); draw(); };
    $('#sort').onchange = e => { st.sort = e.target.value; ls('sort', st.sort); draw(); };
    $('#store').onchange = e => { st.store = e.target.value; draw(); };
    $('#q').oninput = e => { st.q = e.target.value; const pos = e.target.selectionStart; draw(); const q = $('#q'); q.focus(); q.setSelectionRange(pos, pos); };
  }
}
draw();

// ---------------------------------------------------------------- ανανέωση μέσω server.py
const btn = $('#refresh'), status = $('#status');
const served = location.protocol.startsWith('http') && /^(127\.0\.0\.1|localhost)$/.test(location.hostname);
const online = location.protocol === 'https:' && !served;
let poll = null;
async function checkStatus(reloadWhenDone) {
  try {
    const r = await fetch('/api/status', { cache: 'no-store' }); const s = await r.json();
    if (s.state === 'running') {
      btn.disabled = true; btn.textContent = '⏳ Σάρωση…';
      status.textContent = 'σάρωση σε εξέλιξη από ' + (s.started || '').slice(11, 16) + (s.msg ? ' · ' + s.msg : '');
      if (!poll) poll = setInterval(() => checkStatus(true), 4000);
    } else {
      if (poll) { clearInterval(poll); poll = null; }
      btn.disabled = false; btn.textContent = '↻ Ανανέωση τιμών';
      status.textContent = s.finished ? 'τελευταία σάρωση ' + s.finished.slice(11, 16) + (s.state === 'error' ? ' (σφάλμα: ' + (s.msg || '') + ')' : '') : '';
      if (reloadWhenDone && s.finished && s.finished !== window.__fin) location.reload();
      window.__fin = s.finished;
    }
  } catch (e) { status.textContent = 'ο server δεν απαντά'; }
}
if (served) {
  checkStatus(false);
  btn.onclick = async () => {
    btn.disabled = true; btn.textContent = '⏳ Σάρωση…';
    try { await fetch('/api/refresh', { method: 'POST' }); } catch (e) {}
    setTimeout(() => checkStatus(true), 1500);
  };
} else if (online) {
  // online αντίγραφο (GitHub Pages): ενημερώνεται αυτόματα κάθε 2 ώρες (GitHub Actions)
  const bm = document.querySelector('a[href="/bookmarklet"]'); if (bm) bm.style.display = 'none';
  btn.textContent = '↻ Φόρτωση νεότερης';
  btn.onclick = () => { location.href = location.pathname + '?t=' + Date.now(); };
  status.textContent = 'online αντίγραφο · ενημερώνεται αυτόματα κάθε 2 ώρες';
} else {
  btn.disabled = true; btn.title = 'Άνοιξε τη σελίδα από http://127.0.0.1:8765/ (server.py) για ανανέωση';
  status.innerHTML = 'Ανοιχτό ως αρχείο: για ανανέωση άνοιξε <a href="http://127.0.0.1:8765/">http://127.0.0.1:8765/</a>';
}
</script></body></html>"""


# ============================================================================ δημοσίευση (GitHub Pages)
PUBLISH_CFG = BASE / "publish.json"
GIT_EXE = r"C:\Program Files\Git\cmd\git.exe"


def public_page(page):
    """Η σελίδα χωρίς τις διευθύνσεις email, για δημόσια ανάρτηση."""
    n = notify_cfg()
    for addr in {n.get("to"), n.get("from"), n.get("smtp_user")} - {None, ""}:
        page = page.replace(addr, "")
    return page


def publish(page):
    """Ανεβάζει ΜΟΝΟ τη σελίδα (χωρίς emails) στο repo του GitHub Pages. Ρύθμιση: publish.json."""
    try:
        cfg = json.loads(PUBLISH_CFG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "δημοσίευση: δεν έχει ρυθμιστεί"
    if not cfg.get("enabled"):
        return "δημοσίευση: απενεργοποιημένη"
    site = BASE / cfg.get("repo_dir", "site")
    if not (site / ".git").exists():
        return f"δημοσίευση: δεν υπάρχει repo στο {site}"
    (site / "index.html").write_text(public_page(page), encoding="utf-8")
    (site / ".nojekyll").touch()

    def git(*a):
        return subprocess.run([GIT_EXE, *a], cwd=site, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120, creationflags=0x08000000 if os.name == "nt" else 0)
    git("add", "index.html", ".nojekyll")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return "δημοσίευση: καμία αλλαγή"
    git("commit", "-q", "-m", f"update {dt.datetime.now():%Y-%m-%d %H:%M}")
    r = git("push", "-q", "origin", "HEAD")
    if r.returncode:
        log(f"Δημοσίευση απέτυχε: {r.stderr.strip()[:300]}")
        return "δημοσίευση: αποτυχία push"
    log(f"Δημοσιεύτηκε: {cfg.get('url', '')}")
    return "δημοσιεύτηκε"


# ============================================================================ main
def write_status(**kw):
    REPORTS.mkdir(exist_ok=True)
    cur = {}
    if STATUS.exists():
        try:
            cur = json.loads(STATUS.read_text(encoding="utf-8"))
        except ValueError:
            cur = {}
    cur.update(kw)
    STATUS.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")


def acquire_lock():
    REPORTS.mkdir(exist_ok=True)
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 45 * 60:
        return False
    LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--test-email", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--no-publish", action="store_true", help="χωρίς ανέβασμα στο GitHub Pages")
    ap.add_argument("--public-out", help="γράψε και δημόσιο αντίγραφο της σελίδας (χωρίς emails) σε αυτό το αρχείο")
    ap.add_argument("--log", help="γράψε την έξοδο σε αρχείο (για pythonw / Task Scheduler)")
    args = ap.parse_args()
    global DEBUG
    DEBUG = args.debug
    if args.log:
        Path(args.log).parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8")
        log(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M} =====")
    elif sys.stdout:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.test_email:
        cfg = notify_cfg()
        if not email_ready(cfg):
            log("Το notify.json δεν είναι πλήρες (enabled / to / smtp_host / smtp_password ή PC_DEALS_SMTP_PASSWORD).")
            sys.exit(1)
        send_email(cfg, "PC deals: δοκιμαστικό email", "<p>Το email ειδοποιήσεων για εξαιρετικές προσφορές λειτουργεί.</p>")
        log(f"Στάλθηκε δοκιμαστικό email στο {shown_addr(cfg)}.")
        return

    wl = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    if not args.no_fetch and not acquire_lock():
        log("Τρέχει ήδη άλλη σάρωση (reports/.scan.lock) – έξοδος.")
        return
    started = dt.datetime.now().isoformat(timespec="seconds")
    write_status(state="running", started=started, msg="")
    try:
        today = dt.date.today().isoformat()
        con = db_open()
        if args.no_fetch:
            offers = []
            try:   # πλήρη δεδομένα της τελευταίας σάρωσης (παλιές τιμές, κριτικές κ.λπ.)
                last = json.loads((REPORTS / "data.json").read_text(encoding="utf-8"))
                keep = ("store", "cat", "target", "name", "url", "price", "old", "min30_store", "rrp", "rating", "reviews", "stock", "spec", "score", "tags")
                offers = [{k: o.get(k) for k in keep} for o in last["offers"]]
                today = last["generated"][:10]
            except (OSError, ValueError, KeyError):
                offers, today = history_load(con, wl)
            offers = [o for o in offers if o["store"] != "import"]
            # οι κανόνες του watchlist μπορεί να άλλαξαν από την τελευταία σάρωση
            keys = {t["key"] for t in wl["targets"]}
            offers = [o for o in offers if (o["cat"] == "prebuilt" and not pc_reject_reason(parse_specs(o["name"]), wl["prebuilt"]))
                      or o["target"] in keys]
            have = {(o["store"], o["url"], o["target"]) for o in offers}
            offers += [o for o in classify(wl, load_imports(), fetch_peripherals=False)
                       if (o["store"], o["url"], o["target"]) not in have]
        else:
            offers = collect(wl)
        first_run = history_sync(con, offers, today)
        for o in offers:
            assess(o, wl, today)
        email_msg = "email απενεργοποιημένο σε αυτή την εκτέλεση"
        if not args.no_email and not args.no_fetch:
            email_msg = email_alerts(con, offers, wl)
        con.close()
        REPORTS.mkdir(exist_ok=True)
        page = render(wl, offers, today, email_msg, first_run)
        out = REPORTS / f"deals_{today}.html"
        out.write_text(page, encoding="utf-8")
        (REPORTS / "latest.html").write_text(page, encoding="utf-8")
        (REPORTS / "data.json").write_text(json.dumps({"generated": started, "offers": offers}, ensure_ascii=False, indent=0), encoding="utf-8")
        if args.public_out:   # GitHub Actions: δημόσιο αντίγραφο για το GitHub Pages
            Path(args.public_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.public_out).write_text(public_page(page), encoding="utf-8")
        if not args.no_publish:
            try:
                publish(page)
            except Exception as e:  # noqa: BLE001  (η δημοσίευση δεν πρέπει να χαλάει τη σάρωση)
                log(f"Δημοσίευση: σφάλμα {type(e).__name__}: {e}")
        pcs =[o for o in offers if o["cat"] == "prebuilt"]
        log(f"\n{len(pcs)} PC + {len(offers) - len(pcs)} περιφερειακά, {sum(o['excellent'] for o in offers)} εξαιρετικές -> {REPORTS / 'latest.html'}")
        for o in sorted(pcs, key=lambda o: -o["score"]["value"])[:10]:
            log(f"  {o['price']:7.0f} €  {o['store']:8s} FN {o['score']['fn']:3d} AI {o['score']['ai']:3d} αξία {o['score']['value']:5.1f}"
                f"{' ★' if o['score']['target'] else '  '} {o['name'][:80]}")
        write_status(state="done", finished=dt.datetime.now().isoformat(timespec="seconds"),
                     msg=f"{len(pcs)} PC, {len(offers) - len(pcs)} περιφερειακά", email=email_msg)
        if args.open:
            webbrowser.open(out.as_uri())
    except Exception as e:  # noqa: BLE001
        write_status(state="error", finished=dt.datetime.now().isoformat(timespec="seconds"), msg=f"{type(e).__name__}: {e}")
        raise
    finally:
        if not args.no_fetch and LOCK.exists():
            LOCK.unlink()


if __name__ == "__main__":
    main()
