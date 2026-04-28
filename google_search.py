"""Google Web Search scraper for VideoGrab.

Scrapes Google's HTML search results since GitHub Actions runners have
clean IPs and aren't rate-limited by Google. Returns JSON with title,
url, snippet, source per result.

Supports types: web (default), image, video, doc, presentation
"""
import sys, json, re, html as ihtml, urllib.parse, os, time

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

# Build search URL based on type
if search_type == "image":
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=isch&hl=he&safe=active"
elif search_type == "video":
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=vid&hl=he&safe=active"
elif search_type == "doc":
    url = f"https://www.google.com/search?q={urllib.parse.quote(query + ' filetype:pdf OR filetype:doc OR filetype:docx')}&hl=he&safe=active"
elif search_type == "presentation":
    url = f"https://www.google.com/search?q={urllib.parse.quote(query + ' filetype:ppt OR filetype:pptx')}&hl=he&safe=active"
else:
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&hl=he&safe=active&num=20"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept-Language": "he,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

results = []

try:
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"Google returned {r.status_code}", file=sys.stderr)
        sys.exit(1)

    soup = BeautifulSoup(r.text, "html.parser")

    if search_type == "image":
        # Image results are in <img> tags within <table> or specific divs
        for img in soup.select("img[src^='http']")[:30]:
            src = img.get("src", "")
            alt = img.get("alt", "")
            if src and "gstatic" not in src and "google.com" not in src:
                results.append({
                    "title": alt or "תמונה",
                    "url": src,
                    "snippet": "",
                    "source": "Google Images",
                    "type": "image"
                })
    else:
        # Standard web results
        # Google's structure: each result in a div with class containing 'g'
        # Title in h3, link in parent <a>, snippet in following text
        for result_div in soup.select("div.g, div.tF2Cxc, div[data-hveid]"):
            try:
                a_tag = result_div.find("a", href=True)
                if not a_tag: continue
                link = a_tag["href"]
                if not link.startswith("http"): continue
                if "google.com/search" in link or "/url?q=" in link: continue

                h3 = result_div.find("h3")
                title = h3.get_text(strip=True) if h3 else a_tag.get_text(strip=True)
                if not title: continue

                # Snippet: look for description spans
                snippet = ""
                for sel in ["div.VwiC3b", "span.aCOpRe", "div.kb0PBd", "div[data-sncf='1']"]:
                    s = result_div.select_one(sel)
                    if s:
                        snippet = s.get_text(strip=True)
                        break
                if not snippet:
                    # Fallback: any text below the title
                    snippet = result_div.get_text(separator=" ", strip=True)[:200]

                # Determine type from URL
                rtype = "web"
                lower = link.lower()
                if any(lower.endswith(ext) for ext in [".pdf", ".doc", ".docx"]):
                    rtype = "doc"
                elif any(lower.endswith(ext) for ext in [".ppt", ".pptx"]):
                    rtype = "presentation"
                elif "youtube.com/watch" in lower or "youtu.be/" in lower or "vimeo.com/" in lower:
                    rtype = "video"

                results.append({
                    "title": title[:200],
                    "url": link,
                    "snippet": snippet[:300],
                    "source": "Google",
                    "type": rtype
                })

                if len(results) >= 25: break
            except: continue

except Exception as e:
    print(f"Search error: {e}", file=sys.stderr)
    sys.exit(1)

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
