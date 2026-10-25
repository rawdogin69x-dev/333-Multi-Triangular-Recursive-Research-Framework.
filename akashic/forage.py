"""The Forager: polite, deterministic fetching into a content-addressed blob store.

No LLM runs here and nothing fetched is ever executed or obeyed. Text extraction keeps the
page's own words verbatim so quotes can be anchored against it later.
"""

from __future__ import annotations

import gzip
import hashlib
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .ids import now

USER_AGENT = "akashic-research-bot/0.1 (+https://github.com/rawdogin69x-dev/333-Multi-Triangular-Recursive-Research-Framework.)"
TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|ref$|ref_src$)")
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]")
# Phrases that suggest a page is talking to an AI rather than a reader. Flagged, never obeyed.
_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior) instructions|you are (now )?an? (ai|assistant|language model)|"
    r"system prompt|disregard the above|as an ai language model)", re.I)


def canonical_url(url: str) -> str:
    """Lower-case scheme and host, drop fragments, default ports and tracking parameters, sort the query."""
    p = urlsplit(url.strip())
    scheme = (p.scheme or "https").lower()
    host = (p.hostname or "").lower()
    port = p.port
    netloc = host if port is None or (scheme, port) in (("http", 80), ("https", 443)) else f"{host}:{port}"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                             if not TRACKING_PARAMS.match(k)))
    path = re.sub(r"/{2,}", "/", p.path or "/")
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((scheme, netloc, path, query, ""))


class BlobStore:
    """Raw bytes, gzip-compressed, addressed by the sha256 of the uncompressed content."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def path(self, sha: str) -> Path:
        return self.root / sha[:2] / sha[2:4] / f"{sha}.gz"

    def put(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        p = self.path(sha)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress(data, mtime=0))
            tmp.replace(p)
        return sha

    def get(self, sha: str) -> bytes:
        return gzip.decompress(self.path(sha).read_bytes())


# -- text extraction ---------------------------------------------------------------

_SKIP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "template", "iframe"}
_BLOCK = {"p", "div", "section", "article", "main", "li", "ul", "ol", "br", "tr", "table", "blockquote",
          "h1", "h2", "h3", "h4", "h5", "h6", "pre", "figcaption", "dd", "dt"}
_META_KEYS = {
    "citation_author": "authors", "author": "authors", "dc.creator": "authors", "article:author": "authors",
    "citation_publication_date": "published_at", "citation_date": "published_at",
    "article:published_time": "published_at", "dc.date": "published_at", "date": "published_at",
    "citation_title": "title", "og:title": "title",
    "citation_doi": "doi", "dc.identifier": "doi",
}


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_title = False
        self.title = ""
        self.meta: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in _SKIP:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key in _META_KEYS and a.get("content"):
                self.meta.setdefault(_META_KEYS[key], []).append(a["content"].strip())
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in _SKIP:
            self.skip_depth -= 1

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "title":
            self.in_title = False
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip_depth:
            self.parts.append(data)


@dataclass
class Extracted:
    text: str
    title: str | None = None
    authors: str | None = None
    published_at: str | None = None
    doi: str | None = None


def html_to_text(html: str) -> Extracted:
    ex = _Extractor()
    ex.feed(html)
    ex.close()
    raw = _ZERO_WIDTH.sub("", "".join(ex.parts))
    lines = [re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in raw.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    m = ex.meta
    return Extracted(
        text=text,
        title=(m.get("title") or [ex.title.strip() or None])[0],
        authors="; ".join(dict.fromkeys(m["authors"])) if m.get("authors") else None,
        published_at=(m.get("published_at") or [None])[0],
        doi=(m.get("doi") or [None])[0],
    )


def pdf_to_text(data: bytes) -> Extracted:
    try:
        from pypdf import PdfReader  # optional dependency: pip install akashic[pdf]
    except ImportError as e:  # pragma: no cover - depends on environment
        raise RuntimeError("PDF support needs the optional 'pypdf' package (pip install -e '.[pdf]')") from e
    import io

    reader = PdfReader(io.BytesIO(data))
    pages = [(p.extract_text() or "") for p in reader.pages]
    meta = reader.metadata or {}
    return Extracted(text=_ZERO_WIDTH.sub("", "\n\n".join(pages)).strip(),
                     title=getattr(meta, "title", None), authors=getattr(meta, "author", None))


# -- signals (heuristics, labelled as such) -----------------------------------------

_TRANSPARENCY = [
    re.compile(r"\b(data|dataset)s? (are|is) (publicly )?available\b", re.I),
    re.compile(r"\b(code|source code|scripts?) (is|are) available\b|github\.com/|gitlab\.com/|zenodo\.org", re.I),
    re.compile(r"\b(methods?|methodology|materials and methods|experimental setup)\b", re.I),
    re.compile(r"\bdoi\.org/|\bdoi:\s*10\.", re.I),
    re.compile(r"\b(supplementary|appendix|pre-?registered|preregistration)\b", re.I),
    re.compile(r"\b(n\s*=\s*\d+|sample size|confidence interval|p\s*[<=]\s*0?\.\d+)", re.I),
]


def transparency_signals(text: str) -> float:
    """D10 heuristic: share of transparency markers present (data, code, methods, DOI, supplements, stats).

    A cheap prior only. It can be gamed and misses transparent prose; refined by resolved predictions.
    """
    return sum(1 for rx in _TRANSPARENCY if rx.search(text)) / len(_TRANSPARENCY)


def injection_flags(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in _INJECTION.finditer(text)})


# -- politeness -------------------------------------------------------------------

@dataclass
class Politeness:
    min_interval_s: float = 5.0
    _last: dict[str, float] = field(default_factory=dict)
    _robots: dict[str, urllib.robotparser.RobotFileParser] = field(default_factory=dict)

    def wait(self, host: str, clock=time.monotonic, sleep=time.sleep) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = self.min_interval_s - (clock() - last)
            if gap > 0:
                sleep(gap)
        self._last[host] = clock()

    def allowed(self, client: httpx.Client, url: str) -> bool:
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = client.get(base + "/robots.txt", timeout=15)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self._robots[base] = rp
        return rp.can_fetch(USER_AGENT, url)


@dataclass
class Fetched:
    url: str
    canonical: str
    status: int
    content_type: str
    sha256: str
    extracted: Extracted
    transparency: float
    injection: list[str]
    captured_at: str


class Forager:
    def __init__(self, blobs: BlobStore, client: httpx.Client | None = None, politeness: Politeness | None = None,
                 max_bytes: int = 25_000_000):
        self.blobs = blobs
        self.client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60)
        self.politeness = politeness or Politeness()
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> Fetched:
        canon = canonical_url(url)
        if not self.politeness.allowed(self.client, canon):
            raise PermissionError(f"robots.txt disallows {canon}")
        self.politeness.wait(urlsplit(canon).hostname or "")
        r = self.client.get(canon)
        r.raise_for_status()
        data = r.content[: self.max_bytes]
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        sha = self.blobs.put(data)
        if ctype == "application/pdf" or canon.lower().endswith(".pdf"):
            ex = pdf_to_text(data)
        elif ctype.startswith("text/plain"):
            ex = Extracted(text=_ZERO_WIDTH.sub("", data.decode(r.encoding or "utf-8", "replace")))
        else:
            ex = html_to_text(data.decode(r.encoding or "utf-8", "replace"))
        return Fetched(url, canonical_url(str(r.url)), r.status_code, ctype, sha, ex,
                       transparency_signals(ex.text), injection_flags(ex.text), now())

    def from_file(self, path: str | Path) -> Fetched:
        """Ingest a local file (txt, html, pdf) the owner supplies. Its 'URL' is a file: URI."""
        p = Path(path)
        data = p.read_bytes()
        sha = self.blobs.put(data)
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            ex = pdf_to_text(data)
        elif suffix in (".html", ".htm"):
            ex = html_to_text(data.decode("utf-8", "replace"))
        else:
            ex = Extracted(text=_ZERO_WIDTH.sub("", data.decode("utf-8", "replace")), title=p.stem)
        uri = f"file://local/{sha[:16]}/{p.name}"  # never the owner's real path: the repo and DB may be shared
        return Fetched(uri, uri, 200, suffix.lstrip("."), sha, ex, transparency_signals(ex.text),
                       injection_flags(ex.text), now())
