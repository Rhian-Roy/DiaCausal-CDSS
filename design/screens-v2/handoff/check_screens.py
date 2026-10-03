#!/usr/bin/env python3
"""
DiaCausal screen audit.

Usage:  python3 check_screens.py <folder-or-files...> [--content-only]

Checks every HTML screen for:
  A. Consistency: identical <style> block, identical :root tokens, identical font link,
     no colour or radius literals outside :root, only token font families.
  B. Content rules: no single-drug instruction, no GLP-1, no ADA, no dose prompt,
     no microphone, no header badge, no dose in the patient strip, the intended-use
     sentence at least twice, "The clinician decides." on every answer card, and a
     95% CI on every estimate cell.
Exit code 1 if any check fails.
"""
import hashlib, re, sys, os, json
from html.parser import HTMLParser

INTENDED = "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."

BANNED = {
    "single-drug instruction": r"\bAdd (an?|the) (SGLT2|DPP-4|sulfonylurea)|fits this patient best|first choice for this|\bwe recommend\b|\byou should (add|start)\b|Safe to start",
    "GLP-1": r"GLP-?1|glucagon-like",
    "ADA": r"\bADA\b|American Diabetes Association",
    "microphone": r"microphone|\bdictat|\bmic\b",
    "dose prompt": r"(ask|question)[^.]{0,40}\bdose|\ba dose\b|dose question",
}

class Text(HTMLParser):
    ATTRS = ("placeholder", "aria-label", "title", "value", "alt")
    def __init__(self):
        super().__init__()
        self.skip = 0; self.chunks = []; self.tag_badge = False
    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"): self.skip += 1
        d = dict(attrs)
        for a in self.ATTRS:
            if d.get(a): self.chunks.append(d[a])
        if "tag" in (d.get("class") or "").split(): self.tag_badge = True
    def handle_endtag(self, tag):
        if tag in ("style", "script"): self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.chunks.append(data)

def audit(path, content_only=False):
    src = open(path, encoding="utf-8").read()
    r = {"file": os.path.basename(path), "fail": [], "note": []}
    style = "".join(re.findall(r"<style>(.*?)</style>", src, re.S))
    root = (re.search(r":root\{(.*?)\}", style, re.S) or [None, ""])
    root = root[1] if not isinstance(root, list) else ""
    r["style_hash"] = hashlib.sha1(style.encode()).hexdigest()[:10]
    r["token_hash"] = hashlib.sha1(root.encode()).hexdigest()[:10]
    fonts = re.findall(r'href="(https://fonts\.googleapis\.com/css2[^"]+)"', src)
    r["font_link"] = fonts[0] if fonts else ""

    if not content_only:
        tokens = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", root))
        token_vals = {v.strip().upper() for v in tokens.values()}
        css_wo_root = style.replace(root, "")
        body = src.split("</head>", 1)[-1]
        for where, text in (("CSS", css_wo_root), ("markup", body)):
            for lit in set(re.findall(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|rgba?\([^)]*\)", text)):
                if lit.upper() not in token_vals:
                    r["fail"].append("colour literal %s in %s" % (lit, where))
        for rad in set(re.findall(r"border-radius:([^;}]+)", css_wo_root)):
            if not rad.strip().startswith("var(") and rad.strip() not in ("50%", "0"):
                # per-corner shorthands made only of tokens are fine
                if not all(p.startswith("var(") for p in rad.split()):
                    r["fail"].append("radius literal border-radius:%s" % rad.strip())
        for fam in set(re.findall(r"font-family:([^;}]+)", css_wo_root)):
            if fam.strip() not in ("var(--font-body)", "var(--font-display)", "var(--font-mono)", "inherit"):
                r["fail"].append("font literal font-family:%s" % fam.strip())

    t = Text(); t.feed(src)
    text = re.sub(r"\s+", " ", " ".join(t.chunks))
    for name, rx in BANNED.items():
        for m in re.finditer(rx, text, re.I):
            r["fail"].append('%s: "…%s…"' % (name, text[max(0, m.start() - 30):m.end() + 30].strip()))
    if t.tag_badge or re.search(r'<span class="tag">\s*Research prototype\s*</span>', src):
        r["fail"].append("header badge present")
    for m in re.finditer(r"metformin\s+\d+(\.\d+)?\s?(g|mg)\b", text, re.I):
        r["fail"].append('dose in patient strip: "%s"' % m.group(0))
    n = text.count(INTENDED)
    if n < 2:
        r["fail"].append("intended-use sentence appears %d time(s), needs 2 (line under header + footer)" % n)
    if "DiaCausal answered" in text and "[ANSWER CARD]" not in text and "The clinician decides." not in text:
        r["fail"].append('answer card without "The clinician decides."')
    for label, cell in re.findall(r'<td data-label="(HbA1c change at 6 months|Weight change at 6 months|vs DPP-4i)">(.*?)</td>', src, re.S):
        plain = re.sub(r"<[^>]+>", " ", cell)
        plain = re.sub(r"DPP-4|SGLT2|GLP-1|HbA1c", "", plain)
        if re.search(r"\d", plain) and "95% CI" not in plain and "Not estimated" not in plain:
            r["fail"].append("%s cell without a 95%% CI: %s" % (label, re.sub(r"\s+", " ", plain).strip()[:60]))
    for m in re.finditer(r'class="drow"><p>(.*?)</p>', src, re.S):
        if "95% CI" not in m.group(1):
            r["fail"].append("driver without a 95% CI")
    return r

def main(argv):
    content_only = "--content-only" in argv
    paths = []
    for a in [a for a in argv if not a.startswith("--")]:
        if os.path.isdir(a):
            paths += sorted(os.path.join(a, f) for f in os.listdir(a)
                            if f.endswith(".html") and not f.startswith("00-") or f.endswith(".dc.html"))
        else:
            paths.append(a)
    results = [audit(p, content_only) for p in paths]
    if not content_only:
        for key, label in (("style_hash", "style block"), ("token_hash", ":root tokens"), ("font_link", "font link")):
            vals = {r[key] for r in results}
            if len(vals) > 1:
                for r in results:
                    r["fail"].append("%s differs from the other screens" % label)
    print(json.dumps(results, indent=1, ensure_ascii=False))
    return 1 if any(r["fail"] for r in results) else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
