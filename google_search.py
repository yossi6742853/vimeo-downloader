"""Multi-source web search scraper for VideoGrab.

Tries DuckDuckGo (no rate limit) first, then Bing as fallback.
Returns JSON with title, url, snippet, source per result.

Supports types: web (default), image, video, doc, presentation
"""
import sys, json, re, urllib.parse, os, time

try:
    import requests
except ImportError:
    os.system("pip install requests beautifulsoup4 -q")
    import requests
from bs4 import BeautifulSoup

query = sys.argv[1] if len(sys.argv) > 1 else ""
search_type = sys.argv[2] if len(sys.argv) > 2 else "web"

if not query:
    print(json.dumps({"query": "", "results": [], "error": "no query"}))
    sys.exit(1)

# Adjust query for type
typed_query = query
if search_type == "doc":
    typed_query = f'{query} filetype:pdf OR filetype:doc OR filetype:docx'
elif search_type == "presentation":
    typed_query = f'{query} filetype:ppt OR filetype:pptx'
elif search_type == "video":
    typed_query = f'{query} site:youtube.com OR site:vimeo.com OR site:dailymotion.com OR site:hidabroot.org'

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "he,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

results = []

def classify(link):
    lower = link.lower()
    if any(lower.endswith(ext) for ext in [".pdf", ".doc", ".docx"]): return "doc"
    if any(lower.endswith(ext) for ext in [".ppt", ".pptx"]): return "presentation"
    if "youtube.com/watch" in lower or "youtu.be/" in lower or "vimeo.com/" in lower: return "video"
    if any(lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]): return "image"
    return "web"

# === SOURCE 1: DuckDuckGo HTML (most reliable, no rate limit) ===
try:
    if search_type == "image":
        # DDG image search via i.js endpoint (need vqd token first)
        vr = requests.get(f"https://duckduckgo.com/?q={urllib.parse.quote(typed_query)}&iax=images&ia=images", headers=headers, timeout=10)
        m = re.search(r"vqd=['\"]?(\d+-[\d-]+)['\"]?", vr.text)
        if m:
            vqd = m.group(1)
            ir = requests.get(f"https://duckduckgo.com/i.js?o=json&q={urllib.parse.quote(typed_query)}&vqd={vqd}&p=1", headers={**headers, "Referer": "https://duckduckgo.com/"}, timeout=10)
            if ir.status_code == 200:
                for img in ir.json().get("results", [])[:24]:
                    results.append({
                        "title": img.get("title", "תמונה"),
                        "url": img.get("image"),
                        "snippet": img.get("source", ""),
                        "source": "DuckDuckGo Images",
                        "type": "image"
                    })
    else:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": typed_query}, headers=headers, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        for div in soup.select("div.result, div.web-result")[:25]:
            try:
                a = div.select_one("a.result__a")
                if not a: continue
                link = a.get("href", "")
                # DDG redirects via /l/?uddg=...
                m = re.search(r"uddg=([^&]+)", link)
                if m: link = urllib.parse.unquote(m.group(1))
                if not link.startswith("http"): continue
                title = a.get_text(strip=True)
                snip = div.select_one("a.result__snippet, .result__snippet")
                snippet = snip.get_text(strip=True) if snip else ""
                results.append({
                    "title": title[:200],
                    "url": link,
                    "snippet": snippet[:300],
                    "source": "DuckDuckGo",
                    "type": classify(link)
                })
            except: continue
        print(f"DDG: {len(results)} results", file=sys.stderr)
except Exception as e:
    print(f"DDG error: {e}", file=sys.stderr)

# === SOURCE 2: Bing fallback if DDG returned <5 ===
if len(results) < 5 and search_type != "image":
    try:
        br = requests.get(f"https://www.bing.com/search?q={urllib.parse.quote(typed_query)}&setlang=he", headers=headers, timeout=12)
        soup = BeautifulSoup(br.text, "html.parser")
        for li in soup.select("li.b_algo")[:20]:
            try:
                h2 = li.find("h2")
                if not h2: continue
                a = h2.find("a")
                if not a: continue
                link = a.get("href", "")
                if not link.startswith("http"): continue
                title = a.get_text(strip=True)
                cap = li.select_one(".b_caption p, .b_snippetBigText, .b_dList p")
                snippet = cap.get_text(strip=True) if cap else ""
                results.append({
                    "title": title[:200],
                    "url": link,
                    "snippet": snippet[:300],
                    "source": "Bing",
                    "type": classify(link)
                })
            except: continue
        print(f"Bing total: {len(results)} results", file=sys.stderr)
    except Exception as e:
        print(f"Bing error: {e}", file=sys.stderr)

# Deduplicate by URL
seen = set()
deduped = []
for r in results:
    if r["url"] not in seen:
        seen.add(r["url"])
        deduped.append(r)

output = {
    "query": query,
    "type": search_type,
    "results": deduped,
    "count": len(deduped),
    "time": int(time.time() * 1000)
}

# Write to docs/google_results.json
os.makedirs("docs", exist_ok=True)
with open("docs/google_results.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=1)

print(json.dumps({"query": query, "count": len(deduped)}, ensure_ascii=False))
