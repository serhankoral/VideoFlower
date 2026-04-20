#!/usr/bin/env python3
"""
VideoFlower v1.0 — Otonom Video İndirme Aracı
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Desteklenen siteler:
   • Genel siteler (otomatik algılama)

Özellikler:
  ✓ Otomatik reklam tespiti ve atlama  (text-based: "Skip", "Reklamı Geç", ...)
  ✓ Reklam sonrası "Videoyu Başlat" butonu algılama
  ✓ Pop-up / overlay reklam kapatma
  ✓ Otomatik video başlatma  (JWPlayer / Video.js / HTML5)
  ✓ YouTube playlist sıralı indirme
  ✓ En iyi kalite (bestvideo+bestaudio)
  ✓ Detaylı Türkçe log  (konsol + dosya)
  ✓ Net-export log parse desteği
"""

__version__ = "1.0.0"
__author__ = "VideoFlower"

# ── Encoding düzeltmesi (Windows konsol) ─────────────────────────────────────
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                              errors="replace", write_through=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                              errors="replace", write_through=True)

import argparse
import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urljoin

import requests
import urllib3
urllib3.disable_warnings()

# Opsiyonel bağımlılıklar
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    async_playwright = None
    HAS_PLAYWRIGHT = False

try:
    import playwright_stealth  # type: ignore
    HAS_STEALTH = True
except ImportError:
    playwright_stealth = None
    HAS_STEALTH = False

try:
    import nodriver as uc
    from nodriver import cdp
    HAS_NODRIVER = True
except ImportError:
    uc = None
    cdp = None
    HAS_NODRIVER = False


# ══════════════════════════════════════════════════════════════════════════════
#   SABİTLER
# ══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR  = os.path.join(SCRIPT_DIR, "_chrome_profile")
COOKIES_FILE = os.path.join(SCRIPT_DIR, "_cookies.txt")
LOG_FILE     = os.path.join(SCRIPT_DIR, "videoflower.log")
OUTPUT_DIR   = os.path.join(SCRIPT_DIR, "indirilenler")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/136.0.0.0 Safari/537.36")

STREAM_EXT = [".m3u8", ".mp4", ".mpd", ".ts"]

STREAM_HINTS = [
    "m3u8", "mpd", "master", "manifest", "playlist", "hls", "dash", "segment",
    "video", "stream", "playback", "source", "file",
]

BAD_STREAM_PARTS = [
    "blob:", "/embed/", ".css", ".js", "cloudfront.net/\\", "|", "(", ")", "{", "}",
    ".webmanifest", "manifest.json", "favicon", "browserconfig",
]

AD_DOMAINS = [
    "cvt-s2", "agl005", ".xml", "vast", "doubleclick",
    "googlesyndication", "adserver", "adsystem", "pagead",
    "securepubads", "moatads", "adnxs", "advertising",
    "tpc.googlesyndication",
]

DEFAULT_TEST_URLS = [
   "",
]

SITE_RULES = {
    "youtube": {
        "label": "YouTube",
        "domains": ["youtube.com", "youtu.be"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": False,
    },
    "hdfilmizle": {
        "label": "hdfilmizle.so",
        "domains": ["hdfilmizle.so"],
        "direct_html_first": True,
        "prefer_browser_embed": False,
        "prefer_playwright": False,
        "embed_host_priority": ["vidrame", "rapidrame", "photomag"],
        "page_fallback_first": True,
        "use_nodriver_fallback": False,
    },
    "hdfilmcehennemi": {
        "label": "hdfilmcehennemi",
        "domains": ["hdfilmcehennemi.llc", "hdfilmcehennemi.nl"],
        "direct_html_first": True,
        "prefer_browser_embed": True,
        "prefer_playwright": True,
        "embed_host_priority": ["pichive", "rapidrame", "vidrame"],
        "blocked_title_markers": ["just a moment", "cloudflare"],
        "use_nodriver_fallback": True,
    },
    "dizi54": {
        "label": "dizi54.life",
        "domains": ["dizi54.life"],
        "direct_html_first": False,
        "prefer_browser_embed": True,
        "prefer_playwright": True,
        "embed_host_priority": ["pichive", "vidrame", "rapidrame"],
        "use_nodriver_fallback": True,
    },
    "jetfilmizle": {
        "label": "jetfilmizle.net",
        "domains": ["jetfilmizle.net"],
        "direct_html_first": False,
        "prefer_browser_embed": True,
        "prefer_playwright": True,
        "embed_host_priority": ["mail.ru", "vidrame", "rapidrame", "pichive"],
        "use_nodriver_fallback": True,
    },
    "izleplus": {
        "label": "izleplus.com",
        "domains": ["izleplus.com", "izleplus.cc"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["hotstream.club"],
        "page_fallback_first": False,
        "use_nodriver_fallback": False,
    },
    "zeusdizi": {
        "label": "zeusdizi31.com",
        "domains": ["zeusdizi31.com", "zeusdizi29.com"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["japierdolevid", "drakkarhls"],
        "use_nodriver_fallback": False,
    },
    "dizibox": {
        "label": "dizibox.live",
        "domains": ["dizibox.live"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["player/king/king.php", "molystream", "dbx.molystream", "vidrame"],
        "allow_same_domain_embed": True,
        "use_nodriver_fallback": True,
    },
    "pichive": {
        "label": "pichive.online",
        "domains": ["pichive.online"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["pichive.online"],
        "use_nodriver_fallback": False,
    },
    "vidrame": {
        "label": "vidrame/rapidrame",
        "domains": ["vidrame.pro", "rapidrame.com", "rapidrame.net", "photomag.biz"],
        "direct_html_first": True,
        "prefer_browser_embed": False,
        "prefer_playwright": False,
        "page_fallback_first": True,
        "use_nodriver_fallback": False,
    },
    "hotstream": {
        "label": "hotstream.club",
        "domains": ["hotstream.club"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["hotstream.club"],
        "use_nodriver_fallback": False,
    },
    "molystream": {
        "label": "molystream",
        "domains": ["molystream.org", "dbx.molystream.org"],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": ["molystream"],
        "use_nodriver_fallback": False,
    },
    "generic": {
        "label": "Genel",
        "domains": [],
        "direct_html_first": False,
        "prefer_browser_embed": False,
        "prefer_playwright": True,
        "embed_host_priority": [],
        "use_nodriver_fallback": True,
    },
}

SKIP_DOMAINS = [
    "google", "gtag", "analytics", "facebook", "twitter",
    "cloudflare", "jquery", "bootstrap", "gstatic",
    "doubleclick", "googleapis", "fontawesome", "recaptcha",
    "youtube.com", "youtu.be",  # Embed olarak fragman alınmasın
]

SKIP_EXT = [
    ".jpg", ".png", ".webp", ".gif", ".ico",
    ".css", ".woff", ".woff2", ".svg", ".ttf", ".eot",
]

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins',   { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR','tr','en-US','en'] });
window.chrome = { runtime: {} };
"""

# ── Kapsamlı Reklam Atlama + Video Başlatma JavaScript ───────────────────────
# Her 3 saniyede tüm frame'lerde çalıştırılır.
# Adım 1: Reklam atlama butonları (text-based)
# Adım 2: Pop-up / overlay kapatma
# Adım 3: "Videoyu Başlat" butonu
# Adım 4: Player API ile oynatma (JWPlayer / Video.js / HTML5)
# Adım 5: Play butonları (selector-based fallback)

AD_HANDLER_JS = r"""
(function() {
    var result = {found: false, actions: []};

    function log(msg) { result.actions.push(msg); }

    function isVisible(el) {
        if (!el) return false;
        try {
            var style = getComputedStyle(el);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            if (el.offsetParent === null && style.position !== 'fixed') return false;
            var r = el.getBoundingClientRect();
            return r.width > 5 && r.height > 5;
        } catch(e) { return false; }
    }

    function findByText(texts, maxLen) {
        maxLen = maxLen || 80;
        var sels = 'button, a[href="#"], a[role="button"], div[onclick], span[onclick], ' +
                   '[role="button"], label, input[type="button"], input[type="submit"], ' +
                   'div[class*="btn"], span[class*="btn"], div[class*="button"], ' +
                   'div[class*="skip"], div[class*="close"], div[class*="kapat"]';
        var els = document.querySelectorAll(sels);
        for (var i = 0; i < els.length; i++) {
            var el = els[i];
            if (!isVisible(el)) continue;
            var t = (el.innerText || el.textContent || '').trim();
            if (t.length > maxLen || t.length === 0) continue;
            var tl = t.toLowerCase();
            for (var j = 0; j < texts.length; j++) {
                if (tl.indexOf(texts[j]) !== -1 || tl === texts[j]) {
                    try { el.click(); } catch(e) {}
                    log('CLICK: "' + t.substring(0, 40) + '" [' + texts[j] + ']');
                    result.found = true;
                    return true;
                }
            }
        }
        return false;
    }

    // ADIM 0: "Baştan başla / Continue from beginning" diyalogları
    if (findByText([
        'baştan başla', 'başa dön', 'başından başla', 'en baştan',
        'start over', 'start from beginning', 'restart', 'from the beginning',
        'yeniden başlat'
    ])) return result;

    // ADIM 1: Reklam atlama butonları
    if (findByText([
        'reklamı geç', 'reklam geç', 'reklamı kapat', 'reklamı atla',
        'skip ad', 'skip ads', 'skip', 'atla', 'geç',
        'reklam', 'close ad', 'skip now', 'advertisement'
    ])) return result;

    // ADIM 2: Pop-up / overlay kapatma
    var overlays = document.querySelectorAll(
        'div, section, aside, [class*="modal"], [class*="popup"], [class*="overlay"], ' +
        '[class*="interstitial"], [class*="lightbox"]'
    );
    for (var k = 0; k < overlays.length; k++) {
        try {
            var oel = overlays[k];
            var ostyle = getComputedStyle(oel);
            var oz = parseInt(ostyle.zIndex) || 0;
            if (oz > 500 && (ostyle.position === 'fixed' || ostyle.position === 'absolute')) {
                var orect = oel.getBoundingClientRect();
                if (orect.width > window.innerWidth * 0.25 && orect.height > window.innerHeight * 0.25) {
                    var closeBtn = oel.querySelector(
                        '[class*="close"], [class*="kapat"], [class*="dismiss"], ' +
                        '[aria-label*="close"], [aria-label*="kapat"], ' +
                        '[title*="close"], [title*="kapat"], ' +
                        'button[class*="x"], .close-btn, .btn-close'
                    );
                    if (closeBtn && isVisible(closeBtn)) {
                        try { closeBtn.click(); } catch(e) {}
                        log('OVERLAY_CLOSE: z=' + oz);
                        result.found = true;
                        return result;
                    }
                    // Kapatma butonu yoksa gizle
                    oel.style.display = 'none';
                    log('OVERLAY_HIDE: z=' + oz);
                    result.found = true;
                    return result;
                }
            }
        } catch(e) {}
    }

    // Metin tabanlı kapatma
    if (findByText(['kapat', 'close', '\u00d7', '\u2715', '\u2716', 'dismiss', 'tamam', 'ok'])) {
        return result;
    }

    // ADIM 3: "Videoyu Başlat" butonu
    if (findByText([
        'videoyu başlat', 'başlat', 'oynat', 'izle', 'play video', 'watch now',
        'videoyu oynat', 'başlatma', 'tap to unmute'
    ])) {
        return result;
    }

    // ADIM 4: Player API ile oynatma
    try {
        if (typeof jwplayer !== 'undefined') {
            var state = jwplayer().getState ? jwplayer().getState() : '';
            if (state !== 'playing' && state !== 'buffering') {
                jwplayer().play();
                log('JW_PLAY: önceki=' + state);
                result.found = true;
                return result;
            }
        }
    } catch(e) {}

    try {
        if (typeof videojs !== 'undefined') {
            var players = videojs.getPlayers ? videojs.getPlayers() : {};
            var keys = Object.keys(players);
            for (var pi = 0; pi < keys.length; pi++) {
                var vp = players[keys[pi]];
                if (vp && vp.paused && vp.paused()) {
                    vp.play();
                    log('VJS_PLAY: ' + keys[pi]);
                    result.found = true;
                    return result;
                }
            }
        }
    } catch(e) {}

    try {
        var videos = document.querySelectorAll('video');
        for (var vi = 0; vi < videos.length; vi++) {
            var v = videos[vi];
            if (v.paused && (v.src || v.querySelector('source'))) {
                v.muted = true;
                v.playsInline = true;
                try { v.setAttribute('playsinline', ''); } catch(e) {}
                v.play();
                log('HTML5_PLAY');
                result.found = true;
                return result;
            }
        }
    } catch(e) {}

    // ADIM 5: Play butonları (selector fallback)
    var playSelectors = [
        '.jw-icon-display', '.jw-svg-icon-play',
        '.vjs-big-play-button', '.vjs-play-control',
        '.play-btn', '.play-button',
        '[class*="play-button"]', '[class*="play-icon"]',
        'button[aria-label*="Play"]', 'button[aria-label*="Oynat"]',
        'button[title*="Play"]', 'button[title*="Oynat"]',
    ];
    for (var si = 0; si < playSelectors.length; si++) {
        try {
            var sel = playSelectors[si];
            var pel = document.querySelector(sel);
            if (pel && isVisible(pel)) {
                pel.click();
                log('PLAY_SEL: ' + sel);
                result.found = true;
                return result;
            }
        } catch(e) {}
    }

    return result;
})()
"""


FORCE_AUTOPLAY_JS = r"""
(function() {
    var out = {started: 0, attempted: 0, clicked: 0};
    try {
        var vids = document.querySelectorAll('video');
        for (var i = 0; i < vids.length; i++) {
            var v = vids[i];
            if (!v) continue;
            out.attempted += 1;
            try {
                v.muted = true;
                v.autoplay = true;
                v.playsInline = true;
                v.setAttribute('playsinline', '');
                v.setAttribute('webkit-playsinline', '');
                // Poster/overlay kapat
                v.removeAttribute('poster');
                // Kullanıcı aksiyonu simülasyonu
                try {
                    var mouseEvt = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                    v.dispatchEvent(mouseEvt);
                    out.clicked += 1;
                } catch(e2) {}
                if (v.paused) {
                    var p = v.play();
                    if (p && p.catch) p.catch(function(){});
                }
                if (!v.paused) out.started += 1;
            } catch(e) {}
        }

        // Bazı player'larda başlangıç için kullanıcı aksiyonu gerekir.
        if (out.started === 0) {
            var playSelectors = [
                '.jw-icon-display', '.jw-display-icon-container',
                '.vjs-big-play-button', '.vjs-play-control',
                '.play-btn', '.play-button',
                '[class*="play-button"]', '[class*="play-icon"]',
                '[aria-label*="Play"]', '[aria-label*="Oynat"]',
                '[class*="start"]', '[class*="başlat"]'
            ];
            for (var si = 0; si < playSelectors.length; si++) {
                var btn = document.querySelector(playSelectors[si]);
                if (btn) {
                    try { btn.click(); out.clicked += 1; } catch(e) {}
                    break;
                }
            }
        }
        // Player API çağrıları
        try {
            if (typeof jwplayer !== 'undefined' && jwplayer().play) {
                if (jwplayer().getState && jwplayer().getState() !== 'playing') {
                    jwplayer().play();
                    out.started += 1;
                }
            }
        } catch(e) {}
        try {
            if (typeof videojs !== 'undefined') {
                var players = videojs.getPlayers ? videojs.getPlayers() : {};
                for (var k in players) {
                    var vp = players[k];
                    if (vp && vp.paused && vp.paused()) {
                        vp.play();
                        out.started += 1;
                    }
                }
            }
        } catch(e) {}
    } catch(e) {}
    return out;
})()
"""


EXTRACT_PLAYER_STREAMS_JS = r"""
(function() {
    var out = [];
    function push(u) {
        try {
            if (!u || typeof u !== 'string') return;
            if (u.indexOf('http') !== 0 && u.indexOf('/') !== 0) return;
            if (out.indexOf(u) < 0) out.push(u);
        } catch(e) {}
    }

    try {
        if (typeof jwplayer !== 'undefined') {
            var item = jwplayer().getPlaylistItem ? jwplayer().getPlaylistItem() : null;
            if (item) {
                push(item.file || '');
                if (item.sources && item.sources.length) {
                    for (var i = 0; i < item.sources.length; i++) {
                        push(item.sources[i].file || '');
                        push(item.sources[i].src || '');
                    }
                }
                if (item.tracks && item.tracks.length) {
                    for (var ti = 0; ti < item.tracks.length; ti++) {
                        push(item.tracks[ti].file || '');
                    }
                }
            }
            // getConfig — setup sırasında set edilen dosya
            try {
                var cfg = jwplayer().getConfig ? jwplayer().getConfig() : null;
                if (cfg && cfg.playlist && cfg.playlist.length) {
                    var pi2 = cfg.playlist[0];
                    push(pi2.file || '');
                    if (pi2.sources) {
                        for (var si2 = 0; si2 < pi2.sources.length; si2++) {
                            push(pi2.sources[si2].file || '');
                            push(pi2.sources[si2].src || '');
                        }
                    }
                }
            } catch(e2) {}
            // Internal model — bazı JW versiyonları
            try {
                var jw = jwplayer();
                if (jw._model && jw._model.get) {
                    push(jw._model.get('playlist')[0].file || '');
                    push(jw._model.get('mediaModel') && jw._model.get('mediaModel').get('url') || '');
                }
            } catch(e3) {}
        }
    } catch(e) {}

    try {
        if (typeof videojs !== 'undefined') {
            var players = videojs.getPlayers ? videojs.getPlayers() : {};
            var keys = Object.keys(players);
            for (var pi = 0; pi < keys.length; pi++) {
                var vp = players[keys[pi]];
                if (vp && vp.currentSource) {
                    var cs = vp.currentSource();
                    if (cs && cs.src) push(cs.src);
                }
            }
        }
    } catch(e) {}

    try {
        var videos = document.querySelectorAll('video');
        for (var vi = 0; vi < videos.length; vi++) {
            var v = videos[vi];
            push(v.currentSrc || '');
            push(v.src || '');
            var srcs = v.querySelectorAll('source');
            for (var si = 0; si < srcs.length; si++) {
                push(srcs[si].src || '');
            }
        }
    } catch(e) {}

    try {
        var perf = performance.getEntriesByType('resource') || [];
        for (var ri = 0; ri < perf.length; ri++) {
            var n = perf[ri].name || '';
            if (/(m3u8|mpd|manifest|playlist|master|hls|dash|\.mp4|\/stream\/|\/video\/|\/hls\/|segment)(\?|$|\/)/i.test(n)) {
                push(n);
            }
        }
    } catch(e) {}

    return out;
})()
"""


# ══════════════════════════════════════════════════════════════════════════════
#   LOGLAMA
# ══════════════════════════════════════════════════════════════════════════════

def setup_logging(verbose=False):
    logger = logging.getLogger("vf")
    logger.setLevel(logging.DEBUG)

    # Varsa eski handler'ları temizle
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    logger.addHandler(fh)

    return logger


log = setup_logging()


# ══════════════════════════════════════════════════════════════════════════════
#   DECODE FONKSİYONLARI
# ══════════════════════════════════════════════════════════════════════════════

def decode_hdfilmcehennemi(parts):
    """hdfilmcehennemi dc_XXXX([...]) decode."""
    value = "".join(parts)[::-1]
    value = base64.b64decode(value).decode("latin-1")
    value = base64.b64decode(value).decode("latin-1")
    out = ""
    for i, ch in enumerate(value):
        out += chr((ord(ch) - (399756995 % (i + 5)) + 256) % 256)
    return out


def decode_rapidvid(e):
    """rapidvid / fullhdfilmizlesene K9L decode."""
    t = base64.b64decode(e[::-1]).decode("latin-1")
    o, key = "", "K9L"
    for i, ch in enumerate(t):
        o += chr((ord(ch) - (ord(key[i % 3]) % 5 + 1)) % 256)
    return base64.b64decode(o).decode("latin-1")


def _rot13(s):
    r = ""
    for c in s:
        if "a" <= c <= "z":
            r += chr((ord(c) - ord("a") + 13) % 26 + ord("a"))
        elif "A" <= c <= "Z":
            r += chr((ord(c) - ord("A") + 13) % 26 + ord("A"))
        else:
            r += c
    return r


def decode_bd2(s):
    """bd2the.net / hdfilmizle.to  EE.dd decode."""
    s = s.replace("-", "+").replace("_", "/")
    while len(s) % 4:
        s += "="
    return _rot13(base64.b64decode(s).decode("latin-1"))[::-1]


def decode_pichive_jwt(token):
    """pichive JWT payload → data.u  stream URL."""
    parts = token.split(".")
    payload = parts[0] if len(parts) == 2 else (parts[1] if len(parts) >= 3 else None)
    if not payload:
        return None
    payload += "=" * (4 - len(payload) % 4)
    try:
        data = json.loads(base64.b64decode(payload).decode("utf-8"))
        return data.get("data", {}).get("u")
    except Exception:
        return None


def decode_pichive_jwt_cdn_all(token):
    """pichive JWT → tüm CDN domain URL adayları listesi."""
    parts = token.split(".")
    payload = parts[0] if len(parts) == 2 else (parts[1] if len(parts) >= 3 else None)
    if not payload:
        return []
    payload += "=" * (4 - len(payload) % 4)
    try:
        data = json.loads(base64.b64decode(payload).decode("utf-8")).get("data", {})
        raw_url = data.get("u", "")
        domains = data.get("domains", [])
        parsed = urlparse(raw_url) if raw_url else None
        candidates = []
        for d in domains:
            if parsed:
                candidates.append(f"https://{d['d_name']}/{d['d_url_prefix']}{parsed.path}")
        if not candidates and raw_url:
            candidates.append(raw_url)
        return candidates
    except Exception:
        pass
    return []


def decode_pichive_jwt_cdn(token):
    """pichive JWT → CDN domain URL (ilk erişilebilir domain)."""
    candidates = decode_pichive_jwt_cdn_all(token)
    return candidates[0] if candidates else None


# ══════════════════════════════════════════════════════════════════════════════
#   URL YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════════════

def fix_url(url, base_url=""):
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    return url


def is_youtube(url):
    return any(d in url.lower() for d in ["youtube.com", "youtu.be"])


def is_pichive(url):
    return "pichive" in url.lower()


def match_site_rule(url):
    """URL için en uygun site kuralını bul."""
    low = (url or "").lower()
    for key, rule in SITE_RULES.items():
        if any(domain in low for domain in rule.get("domains", [])):
            return key, rule
    return "generic", SITE_RULES["generic"]


def log_site_rule(url, rule_key, rule):
    log.info(f"Site kuralı: {rule.get('label', rule_key)} [{rule_key}]")
    log.debug(f"  Kural URL: {url}")


def choose_preferred_embed_url(urls, rule=None):
    """Kural önceliğine göre embed URL seç."""
    if not urls:
        return None
    if len(urls) == 1 or not rule:
        return urls[0]

    priorities = [p.lower() for p in rule.get("embed_host_priority", [])]
    if priorities:
        for pr in priorities:
            for url in urls:
                if pr in url.lower():
                    return url
    return urls[0]


def is_cloudflare_blocked(html):
    lower = html.lower()
    return (
        "<title>just a moment" in lower
        or "attention required" in lower
        or "sorry, you have been blocked" in lower
        or ("just a moment" in lower and "checking your browser" in lower)
        or ("cloudflare" in lower and "just a moment" in lower)
        or (len(html) < 1000 and "challenge" in lower)
    )


def extract_stream_url(html):
    """HTML içinden encode edilmiş stream URL çıkar."""
    # dc_XXXX([...]) — hdfilmcehennemi
    m = re.search(r"dc_\w+\(\[([^\]]+)\]\)", html)
    if m:
        parts = re.findall(r'"([^"]+)"', m.group(1))
        try:
            url = decode_hdfilmcehennemi(parts)
            if url.startswith("http"):
                log.info(f"  Stream URL (hdfilmcehennemi decode): {url}")
                return url
        except Exception as e:
            log.debug(f"  hdfilmcehennemi decode hatası: {e}")

    # av('...') / _('...') — rapidvid
    m = re.search(r'"file"\s*:\s*(?:av|_)\([\'"]([A-Za-z0-9+/=]+)[\'"]\)', html)
    if m:
        try:
            url = decode_rapidvid(m.group(1))
            if url.startswith("http"):
                log.info(f"  Stream URL (rapidvid decode): {url}")
                return url
        except Exception as e:
            log.debug(f"  rapidvid decode hatası: {e}")

    # EE.dd('...') — bd2the.net
    m = re.search(r"EE\.dd\(['\"]([A-Za-z0-9+/=_-]+)['\"]\)", html)
    if m:
        try:
            url = decode_bd2(m.group(1))
            if url.startswith("http"):
                log.info(f"  Stream URL (bd2 decode): {url}")
                return url
        except Exception as e:
            log.debug(f"  bd2 decode hatası: {e}")

    # Direkt "file": "..."
    m = re.search(r'"file"\s*:\s*"(https?://[^"]+\.(?:m3u8|mp4)[^"]*)"', html)
    if m:
        log.info(f"  Stream URL (direkt file): {m.group(1)}")
        return m.group(1)

    # Genel m3u8
    m = re.search(r"(https?://[^\s\"'<>]+\.m3u8[^\s\"'<>]*)", html)
    if m:
        log.info(f"  Stream URL (m3u8 pattern): {m.group(1)}")
        return m.group(1)

    return None


def extract_stream_urls_from_text(text):
    """JSON/JS metninden olası stream URL'lerini toplu çıkar."""
    out = []
    if not text:
        return out

    # Direkt stream uzantıları
    for u in re.findall(r"(https?://[^\s\"'<>]+\.(?:m3u8|mp4|mpd|ts)[^\s\"'<>]*)", text, re.I):
        nu = u.strip()
        if is_valid_stream_url(nu) and nu not in out:
            out.append(nu)

    # Escape edilmiş URL'ler (https:\/\/...)
    for u in re.findall(r"https?:\\/\\/[^\"'\s]+", text, re.I):
        nu = u.replace("\\/", "/")
        if is_valid_stream_url(nu) and any(h in nu.lower() for h in STREAM_HINTS) and nu not in out:
            out.append(nu)

    # Relative master/manifest yolları
    for path in re.findall(r"(/[^\"'\s]+(?:master|manifest|playlist|index|m3u)[^\"'\s]*(?:\.m3u8|\.mpd)?[^\"'\s]*)", text, re.I):
        if path not in out:
            out.append(path)

    return out


def looks_like_stream_candidate(url):
    low = url.lower()
    if any(ad in low for ad in AD_DOMAINS):
        return False
    # Stream uzantısı varsa BAD_STREAM_PARTS'ı atla (örn: /embed/stream.m3u8)
    if any(ext in low for ext in STREAM_EXT):
        # Yine de gerçek kötü parçaları filtrele (.css/.js/blob: gibi)
        hard_bad = ["blob:", ".css", ".js", "cloudfront.net/\\", "|", "(", ")", "{", "}",
                    ".webmanifest", "manifest.json", "favicon", "browserconfig"]
        if not any(b in low for b in hard_bad):
            return True
    if any(b in low for b in BAD_STREAM_PARTS):
        return False
    strong_hints = [
        "master", "manifest", "playlist", "variant", "index.m3u8", "/hls/", "/dash/", "/m3u/",
        "/stream/", "/video/", "/content/",
    ]
    cdn_hints = [
        "molystream", "dbx.molystream", "caec6083", "b6e10087", "seyret9.top",
        "hotstream.club/m3u", "videopark.top",
    ]
    if any(h in low for h in cdn_hints):
        return True
    if any(h in low for h in strong_hints):
        # Salt embed/player sayfalarını stream zannetme.
        if "/embed/" in low and ".m3u8" not in low and ".mpd" not in low and "manifest" not in low:
            return False
        return True
    return False


def is_valid_stream_url(url):
    """Yanlış pozitif URL'leri elemek için temel doğrulama."""
    if not url:
        return False
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://") or u.startswith("/")):
        return False
    low = u.lower()
    if any(b in low for b in BAD_STREAM_PARTS):
        return False
    if " " in u or "\\" in u:
        return False
    if u.count("http://") + u.count("https://") > 1:
        return False
    return True


def stream_score(url):
    """En iyi stream adayını seçmek için skor."""
    low = url.lower()
    if not is_valid_stream_url(url):
        return -999
    score = 0
    if ".m3u8" in low:
        score += 100
    if ".mpd" in low:
        score += 90
    if ".mp4" in low:
        score += 80
    if "master" in low:
        score += 30
    if "variant" in low:
        score += 15
    if "/m3u/" in low or "/hls/" in low:
        score += 20
    if ".ts" in low:
        score -= 20
    return score


def pick_best_stream_url(urls):
    """Adaylar arasından en güvenilir URL'yi seç."""
    if not urls:
        return None
    valid = [u for u in urls if is_valid_stream_url(u)]
    if not valid:
        return None
    valid.sort(key=stream_score, reverse=True)
    return valid[0]


def normalize_stream_candidate(url, base_url=""):
    """Ağdan yakalanan URL'leri indirilebilir forma normalize et."""
    if not url:
        return url
    if url.startswith("//"):
        parsed = urlparse(base_url) if base_url else None
        scheme = parsed.scheme if parsed and parsed.scheme else "https"
        return f"{scheme}:{url}"
    if base_url and url.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    if base_url:
        parsed = urlparse(base_url)
        dup = f"{parsed.scheme}://{parsed.netloc}//{parsed.netloc}/"
        if url.startswith(dup):
            return f"{parsed.scheme}://{parsed.netloc}/" + url[len(dup):]
    return url


def extract_hls_variants(master_url, referer):
    """Master playlist içinden varyant URL'lerini sırala."""
    try:
        resp = requests.get(
            master_url,
            headers={
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            },
            verify=False,
            timeout=20,
        )
        text = resp.text
        if resp.status_code != 200 or "#EXTM3U" not in text:
            return []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        variants = []
        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.startswith("http://") or next_line.startswith("https://"):
                    full = next_line
                else:
                    full = urljoin(master_url, next_line)
                variants.append(full)
        preferred = []
        for needle in ["720.m3u8", "480.m3u8", "360.m3u8", "1080.m3u8"]:
            for variant in variants:
                if needle in variant and variant not in preferred:
                    preferred.append(variant)
        for variant in variants:
            if variant not in preferred:
                preferred.append(variant)
        return preferred
    except Exception as e:
        log.debug(f"  HLS varyant çıkarımı başarısız: {e}")
        return []


def is_healthy_hls_variant(variant_url, referer):
    """Varyant playlist'in medya segmenti içerip içermediğini kontrol et."""
    try:
        resp = requests.get(
            variant_url,
            headers={
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            },
            verify=False,
            timeout=20,
        )
        text = resp.text
        if resp.status_code != 200 or "#EXTM3U" not in text:
            return False
        # Gerçek medya segmentleri (ts/m4s/mp4) veya yeniden adlandırılmış (jpg/png) içeriyor mu?
        return bool(re.search(r"\.(?:ts|m4s|mp4|jpg|jpeg|png)(?:\?|$)", text, re.I))
    except Exception:
        return False


def materialize_remote_playlist(stream_url, referer):
    """Uzantısız remote playlist URL'sini lokal .m3u8 dosyasına yaz."""
    try:
        resp = requests.get(
            stream_url,
            headers={
                "User-Agent": UA,
                "Referer": referer,
                "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            },
            verify=False,
            timeout=20,
        )
        text = resp.text
        if resp.status_code != 200 or "#EXTM3U" not in text:
            return None

        # Relative URL'leri çözümlemek için playlist URL'sinin dizinini kullan
        playlist_base = stream_url.split("?")[0].rsplit("/", 1)[0] + "/"
        fixed_lines = []
        for line in text.splitlines():
            ln = line.strip()
            if not ln or ln.startswith("#"):
                fixed_lines.append(line)
                continue
            if ln.startswith("http://") or ln.startswith("https://"):
                fixed_lines.append(ln)
            elif ln.startswith("//"):
                fixed_lines.append(f"{urlparse(stream_url).scheme}:{ln}")
            elif ln.startswith("/"):
                parsed = urlparse(stream_url)
                fixed_lines.append(f"{parsed.scheme}://{parsed.netloc}{ln}")
            else:
                fixed_lines.append(urljoin(playlist_base, ln))

        out_path = os.path.join(SCRIPT_DIR, f"_hotstream_{abs(hash(stream_url)) % 100000}.m3u8")
        with open(out_path, "w", encoding="utf-8") as wf:
            wf.write("\n".join(fixed_lines))
        return out_path
    except Exception as e:
        log.debug(f"  hotstream playlist dosyası oluşturulamadı: {e}")
        return None


def build_ffmpeg_headers(referer):
    try:
        origin = f"https://{referer.split('/')[2]}"
    except Exception:
        origin = referer
    return f"Referer: {referer}\r\nOrigin: {origin}\r\nUser-Agent: {UA}\r\n"


def download_jpg_hls(variant_url, out_file, referer, snippet_seconds=0):
    """
    .jpg uzantılı segment kullanan HLS stream'lerini Python requests ile indir.
    ffmpeg hls.c'deki hardcode extension kontrolünü bypass eder.
    Master playlist gelirse en iyi varyantı seçip takip eder.
    """
    import tempfile
    hdrs = {
        "Referer": referer,
        "User-Agent": UA,
    }
    try:
        origin = f"https://{referer.split('/')[2]}"
        hdrs["Origin"] = origin
    except Exception:
        pass

    # Lokal dosya veya remote URL'den m3u8 içeriğini oku
    try:
        if variant_url.startswith("http://") or variant_url.startswith("https://"):
            r = requests.get(variant_url, headers=hdrs, verify=False, timeout=20)
            r.raise_for_status()
            text = r.text
            base_url = variant_url.rsplit("/", 1)[0] + "/"
        else:
            with open(variant_url, encoding="utf-8") as f:
                text = f.read()
            base_url = ""
        if "#EXTM3U" not in text:
            log.debug("  Python HLS: geçerli m3u8 değil")
            return False
    except Exception as e:
        log.warning(f"  Python HLS: variant m3u8 indirilemedi: {e}")
        return False

    # Master playlist ise en iyi varyantı seç ve recurse et
    if "#EXT-X-STREAM-INF" in text:
        best_variant = None
        best_bw = -1
        lines_master = text.splitlines()
        for i, line in enumerate(lines_master):
            if line.startswith("#EXT-X-STREAM-INF"):
                bw = 0
                m = re.search(r"BANDWIDTH=(\d+)", line)
                if m:
                    bw = int(m.group(1))
                for j in range(i + 1, len(lines_master)):
                    seg = lines_master[j].strip()
                    if seg and not seg.startswith("#"):
                        full = seg if seg.startswith("http") else urljoin(base_url, seg) if base_url else seg
                        if bw > best_bw:
                            best_bw = bw
                            best_variant = full
                        break
        if best_variant:
            log.info(f"  Python HLS: master → varyant: {best_variant.split('/')[-1].split('?')[0]}")
            return download_jpg_hls(best_variant, out_file, referer, snippet_seconds)
        log.warning("  Python HLS: master'da varyant bulunamadı")
        return False

    lines = text.splitlines()
    segments = []
    target_duration = 6.0
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith("#EXT-X-TARGETDURATION:"):
            try:
                target_duration = float(line.split(":")[1])
            except Exception:
                pass
        elif line.startswith("#EXTINF:"):
            try:
                dur = float(line.split(":")[1].rstrip(",").split(",")[0])
            except Exception:
                dur = target_duration
            for j in range(i + 1, len(lines)):
                seg = lines[j].strip()
                if seg and not seg.startswith("#"):
                    seg_url = seg if seg.startswith("http") else urljoin(base_url, seg)
                    segments.append((seg_url, dur))
                    break

    if not segments:
        log.debug("  Python HLS: segment bulunamadı")
        return False

    if snippet_seconds and int(snippet_seconds) > 0:
        limited, acc = [], 0.0
        for su, sd in segments:
            limited.append((su, sd))
            acc += sd
            if acc >= int(snippet_seconds):
                break
        segments = limited

    log.info(f"  Python HLS indirme: {len(segments)} segment ({variant_url.split('/')[-1]})")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            seg_files = []
            for idx, (seg_url, _) in enumerate(segments):
                seg_path = os.path.join(tmpdir, f"seg{idx:05d}.ts")
                try:
                    sr = requests.get(seg_url, headers=hdrs, verify=False, timeout=30)
                    sr.raise_for_status()
                    with open(seg_path, "wb") as f:
                        f.write(sr.content)
                    seg_files.append(seg_path)
                except Exception as e:
                    log.debug(f"  Segment {idx} atlandı: {e}")

            if not seg_files:
                log.warning("  Python HLS: hiç segment indirilemedi")
                return False

            concat_list = os.path.join(tmpdir, "concat.txt")
            with open(concat_list, "w", encoding="utf-8") as f:
                for sf in seg_files:
                    f.write(f"file '{sf}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                out_file,
            ]
            result = subprocess.run(cmd, encoding="utf-8", errors="replace",
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if result.returncode == 0:
                log.info("  ✓ Python HLS indirme tamamlandı")
                return True
            log.warning(f"  Python HLS ffmpeg concat hatası: {result.stderr[-300:]}")
            return False
    except Exception as e:
        log.warning(f"  Python HLS genel hata: {e}")
        return False


def run_ffmpeg_direct(input_url, output_file, referer, snippet_seconds=0):
    """ffmpeg ile HLS/manifest URL'sini doğrudan kopyala."""
    is_remote = input_url.startswith("http://") or input_url.startswith("https://")
    cmd = ["ffmpeg", "-y"]
    if is_remote:
        cmd += [
            "-f", "hls",
            "-allowed_extensions", "ALL",
            "-headers", build_ffmpeg_headers(referer),
        ]
    else:
        cmd += ["-f", "hls", "-allowed_extensions", "ALL"]
    cmd += [
        "-i", input_url,
        "-map", "0:v:0?",
        "-map", "0:a:0?",
        "-c", "copy",
    ]
    if snippet_seconds and int(snippet_seconds) > 0:
        cmd += ["-t", str(int(snippet_seconds))]
    cmd.append(output_file)
    log.debug(f"  ffmpeg komutu: {' '.join(cmd[:12])}...")
    result = subprocess.run(cmd, encoding="utf-8", errors="replace")
    return result.returncode == 0


def resolve_special_stream_targets(stream_url, referer):
    """Host bazlı özel indirme hedefleri üret."""
    targets = []
    low = (stream_url or "").lower()
    if "hotstream.club/m3u/" in low:
        local_playlist = materialize_remote_playlist(stream_url, referer)
        if local_playlist:
            targets.append(("python_hls", local_playlist))
            targets.append(("ffmpeg", local_playlist))
        else:
            targets.append(("python_hls", stream_url))
            targets.append(("ffmpeg", stream_url))
    # dizi54 CDN — segmentler uzantısız URL'lere redirect ediyor, ffmpeg reddediyor
    if any(h in low for h in ["caec6083d6b01cf5.click", "b6e10087171e6873.click"]):
        local_playlist = materialize_remote_playlist(stream_url, referer)
        if local_playlist:
            targets.append(("python_hls", local_playlist))
            targets.append(("ffmpeg", local_playlist))
        else:
            targets.append(("python_hls", stream_url))
            targets.append(("ffmpeg", stream_url))
    if low.endswith("master.m3u8") and any(host in low for host in ["photomag.biz", "photoflick.org"]):
        healthy = []
        fallback = []
        for variant in extract_hls_variants(stream_url, referer):
            if is_healthy_hls_variant(variant, referer):
                healthy.append(variant)
            else:
                fallback.append(variant)
        for variant in healthy + fallback:
            targets.append(("python_hls", variant))
        targets.append(("python_hls", stream_url))
    return targets


def get_embed_url_from_html(main_url, html, rule=None):
    """Ana sayfa HTML'inden embed iframe URL'sini çıkar."""
    main_domain = main_url.split("/")[2]
    candidates = []
    allow_same_domain = bool(rule and rule.get("allow_same_domain_embed"))

    for url in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
        url = fix_url(url, main_url)
        if main_domain in url and not allow_same_domain:
            continue
        if any(s in url.lower() for s in SKIP_DOMAINS):
            continue
        if any(url.lower().endswith(e) for e in SKIP_EXT):
            continue
        candidates.append(url)

    for pat in [
        r'(https?://[^"\'\s]+/(?:embed|iframe|player|v|vod|video)/[^"\'\s]+)',
        r'src=["\']([^"\']*(?:embed|iframe|player)[^"\']*)["\']',
    ]:
        for url in re.findall(pat, html, re.I):
            url = fix_url(url, main_url)
            if main_domain in url and not allow_same_domain:
                continue
            if any(s in url.lower() for s in SKIP_DOMAINS):
                continue
            candidates.append(url)

    selected = choose_preferred_embed_url(candidates, rule)
    if selected:
        log.info(f"  Embed URL seçildi: {selected}")
        if len(candidates) > 1:
            log.debug(f"  Embed adayları: {len(candidates)} adet")
        return selected

    return None


# ══════════════════════════════════════════════════════════════════════════════
#   FİLM BİLGİLERİ
# ══════════════════════════════════════════════════════════════════════════════

def get_film_meta(main_url, html):
    """Film başlığı ve poster URL'si çıkar."""
    title = poster = None
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    )
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            title = m.group(1).strip()
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.I,
    )
    if m:
        poster = m.group(1).strip()
    return title, poster


def format_size(size_bytes):
    try:
        n = int(size_bytes)
        if n >= 1024**3:
            return f"{n / 1024**3:.2f} GB"
        if n >= 1024**2:
            return f"{n / 1024**2:.2f} MB"
        if n >= 1024:
            return f"{n / 1024:.2f} KB"
        return f"{n} B"
    except Exception:
        return "bilinmiyor"


def _run_ytdlp_download(target_url, out_path, referer, cookie_file=None, snippet_seconds=0, fmt=None):
    """Tek bir hedef URL için yt-dlp çalıştır ve başarı durumunu döndür."""
    # referer'dan origin çıkar
    try:
        ref_origin = f"https://{referer.split('/')[2]}"
    except Exception:
        ref_origin = referer

    cmd = [
        "yt-dlp",
        "-f", fmt or "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--referer", referer,
        "--add-header", f"Origin:{ref_origin}",
        "--no-check-certificate",
        "--concurrent-fragments", "4",
        "--retries", "5",
        "--fragment-retries", "5",
        "--retry-sleep", "fragment:2",
        "--no-warnings",
        "--newline",
        "--hls-prefer-native",
        "--downloader-args", "ffmpeg_i:-allowed_extensions ALL",
        "-o", out_path,
    ]

    section_expr = build_download_sections(snippet_seconds)
    if section_expr:
        cmd += ["--download-sections", section_expr]

    if cookie_file and os.path.exists(cookie_file):
        cmd += ["--cookies", cookie_file]

    cmd.append(target_url)

    log.debug(f"  yt-dlp komutu: {' '.join(cmd[:12])}...")
    result = subprocess.run(cmd, encoding="utf-8", errors="replace")
    return result.returncode == 0


def get_stream_info(stream_url, referer):
    """yt-dlp ile stream format bilgisi al."""
    log.info("Format bilgileri alınıyor...")
    try:
        result = subprocess.run(
            [
                "yt-dlp", stream_url,
                "--referer", referer,
                "--add-header", f"Origin:https://{referer.split('/')[2]}",
                "--no-check-certificate",
                "--print",
                "%(format_id)s | %(resolution)s | %(filesize_approx)s | %(ext)s | %(duration_string)s",
                "--no-warnings",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=30,
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if lines:
            log.info("[Video Bilgisi]")
            for line in lines:
                parts = line.split("|")
                if len(parts) == 5:
                    size_str = (
                        format_size(parts[2].strip())
                        if parts[2].strip() not in ("None", "NA", "")
                        else "~bilinmiyor"
                    )
                    log.info(f"  Çözünürlük: {parts[1].strip()}  "
                             f"Boyut: {size_str}  "
                             f"Format: {parts[0].strip()}")
    except Exception as e:
        log.debug(f"  Format bilgisi alınamadı: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#   NET-EXPORT LOG PARSE
# ══════════════════════════════════════════════════════════════════════════════

def parse_net_log(log_path):
    """Chrome net-export JSON log dosyasından stream URL çıkar."""
    log.info(f"Net-export log analiz ediliyor: {log_path}")
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # pichive master token
        matches = re.findall(
            r"pichive\.online/edge/master\.php\?t=([A-Za-z0-9._=-]{100,})", content
        )
        if matches:
            token = matches[-1]
            stream_url = decode_pichive_jwt(token)
            if stream_url:
                domain_m = re.search(r"([\w-]+\.pichive\.online)", content)
                domain = domain_m.group(1) if domain_m else "four.pichive.online"
                master_url = f"https://{domain}/edge/master.php?t={token}"
                log.info(f"  Stream URL (net log JWT): {stream_url}")
                return master_url, f"https://{domain}/"

        # Direkt m3u8
        for u in re.findall(r"(https?://[^\s\"'\\]+\.m3u8[^\s\"'\\]*)", content):
            if "vast" not in u and "ad" not in u.lower():
                log.info(f"  M3U8 (net log): {u}")
                return u, ""
    except Exception as e:
        log.error(f"  Log parse hatası: {e}")
    return None, None


def build_download_sections(snippet_seconds):
    """yt-dlp --download-sections parametresini üret."""
    if not snippet_seconds or int(snippet_seconds) <= 0:
        return None
    return f"*0-{int(snippet_seconds)}"


# ══════════════════════════════════════════════════════════════════════════════
#   YOUTUBE HANDLER
# ══════════════════════════════════════════════════════════════════════════════

def process_youtube(url, output_dir, snippet_seconds=0):
    """YouTube URL'sini yt-dlp ile indir (tek video veya playlist)."""
    is_playlist = "list=" in url

    if is_playlist:
        log.info("YouTube PLAYLIST tespit edildi — tüm videolar sırasıyla indirilecek")
        out_template = os.path.join(
            output_dir, "%(playlist_title)s",
            "%(playlist_index)03d-%(title)s.%(ext)s",
        )
    else:
        log.info("YouTube tek video tespit edildi")
        out_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--no-check-certificate",
        "--concurrent-fragments", "4",
        "--no-warnings",
        "--newline",
        "--progress",
        "-o", out_template,
    ]
    if is_playlist:
        cmd.append("--yes-playlist")

    section_expr = build_download_sections(snippet_seconds)
    if section_expr:
        cmd += ["--download-sections", section_expr]
        log.info(f"Test modu aktif: Her video için ilk {snippet_seconds} saniye indirilecek")

    cmd.append(url)

    log.info(f"yt-dlp başlatılıyor...")
    log.debug(f"  Komut: {' '.join(cmd)}")

    result = subprocess.run(cmd, encoding="utf-8", errors="replace")
    if result.returncode == 0:
        log.info("YouTube indirme tamamlandı ✓")
        return True
    else:
        log.error(f"YouTube indirme hatası (kod: {result.returncode})")
        return False


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYWRIGHT REKLAM ATLAMA DÖNGÜSÜ
# ══════════════════════════════════════════════════════════════════════════════

async def run_ad_handler(page_or_frame, label=""):
    """Tek bir frame'de reklam atlama JS'ini çalıştır."""
    try:
        result = await page_or_frame.evaluate(AD_HANDLER_JS)
        if result and result.get("found"):
            for action in result.get("actions", []):
                log.info(f"  [{label}] {action}")
        return result
    except Exception:
        return None


async def force_autoplay(page_or_frame, label=""):
    """Video elementlerinde autoplay'i zorlayarak oynatmayı başlat."""
    try:
        result = await page_or_frame.evaluate(FORCE_AUTOPLAY_JS)
        if result and result.get("started", 0) > 0:
            log.info(
                f"  [{label}] AUTOPLAY: {result.get('started')} video oynuyor "
                f"(deneme: {result.get('attempted', 0)})"
            )
        return result
    except Exception:
        return None


async def extract_player_stream_candidates(page_or_frame, found_streams, label=""):
    """Player API ve performance üzerinden gerçek stream adaylarını topla."""
    try:
        urls = await page_or_frame.evaluate(EXTRACT_PLAYER_STREAMS_JS)
        if not urls:
            return 0
        added = 0
        for u in urls:
            if not u:
                continue
            full = str(u)
            if full.startswith("/"):
                try:
                    cur = await page_or_frame.evaluate("() => location.origin")
                    full = str(cur).rstrip("/") + full
                except Exception:
                    continue
            if looks_like_stream_candidate(full) and full not in found_streams:
                found_streams.append(full)
                added += 1
                log.info(f"  [{label}] STREAM (player): {full}")
        return added
    except Exception:
        return 0


async def _click_video_center(page):
    """Sayfadaki ilk görünür video elementinin merkezine mouse click gönder."""
    try:
        rect = await page.evaluate("""
            () => {
                var v = document.querySelector('video');
                if (!v) return null;
                var r = v.getBoundingClientRect();
                if (!r || r.width < 10 || r.height < 10) return null;
                return {x: r.left + r.width / 2, y: r.top + r.height / 2};
            }
        """)
        if rect and rect.get('x') and rect.get('y'):
            await page.mouse.click(rect['x'], rect['y'])
            return True
    except Exception:
        pass
    # Fallback: play buton seçicileri
    try:
        for sel in [
            '.jw-icon-display', '.jw-display-icon-container',
            '.vjs-big-play-button', '.play-btn', '.play-button',
            '[class*="play-button"]',
        ]:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.click()
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


async def ad_watcher_loop(page, found_streams, master_found_ref, duration=120):
    """
    Ana döngü: reklam atla, pop-up kapat, video başlat, stream yakala.
    found_streams: yakalanan stream URL listesi (list)
    master_found_ref: [False]  (pichive master.php bulundu mu)
    """
    log.info(f"Otonom döngü başlıyor ({duration}s) — reklam atlama + video başlatma")
    elapsed = 0
    step = 3
    ad_count = 0
    click_attempts = 0
    consecutive_close_clicks = 0  # "Close" butonuna ardışık tıklama sayısı

    while elapsed < duration:
        await asyncio.sleep(step)
        elapsed += step

        # Stream veya master.php yakalandıysa çık
        if found_streams:
            log.info(f"  ✓ Stream yakalandı ({elapsed}s'de)")
            return
        if master_found_ref[0]:
            log.info(f"  ✓ master.php yakalandı ({elapsed}s'de), variant bekleniyor...")
            # Variant URL'ler için 20s daha bekle
            for _ in range(10):
                await asyncio.sleep(2)
            return

        # Tüm frame'lerde reklam handler çalıştır
        try:
            for frame in page.frames:
                try:
                    result = await run_ad_handler(frame, f"f{elapsed}s")
                    await force_autoplay(frame, f"f{elapsed}s")
                    await extract_player_stream_candidates(frame, found_streams, f"f{elapsed}s")
                    if result and result.get("found"):
                        ad_count += 1
                        actions = result.get("actions", [])
                        # Sadece "Close/Kapat" tıklanıyorsa ve reklam sayısı artmıyorsa erken çık
                        if all("close" in a.lower() or "kapat" in a.lower() for a in actions if a):
                            consecutive_close_clicks += 1
                        else:
                            consecutive_close_clicks = 0
                        # Erken çıkış: 8+ ardışık close, 60s geçmiş, reklam sayısı 8'den fazla değil
                        if consecutive_close_clicks >= 8 and elapsed > 60 and ad_count <= 8:
                            log.warning(f"  [{elapsed}s] Sadece 'Close' tıklanıyor, stream yok — döngü sonlandırılıyor")
                            return
                        await asyncio.sleep(2)  # Aksiyon sonrası bekle
                        break
                except Exception:
                    pass
        except Exception:
            pass

        # Her 9 saniyede bir mouse click simülasyonu (autoplay policy bypass)
        if elapsed % 9 == 0 and click_attempts < 10:
            try:
                clicked = await _click_video_center(page)
                if clicked:
                    click_attempts += 1
                    log.debug(f"  [{elapsed}s] Video center click")
            except Exception:
                pass

        # Pop-up sayfaları kapat (yeni sekmeler)
        try:
            all_pages = page.context.pages
            if len(all_pages) > 2:  # Ana sayfa + en fazla 1 yardımcı
                for extra in all_pages[2:]:
                    try:
                        log.info(f"  Gereksiz sekme kapatıldı: {extra.url[:60]}")
                        await extra.close()
                    except Exception:
                        pass
        except Exception:
            pass

        if elapsed % 15 == 0:
            frame_count = len(page.frames)
            log.info(
                f"  [{elapsed}s/{duration}s] stream:{len(found_streams)} "
                f"reklam_atlatma:{ad_count} frame:{frame_count} click:{click_attempts}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#   nodriver YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════════════

async def get_embed_url_browser(main_url):
    """nodriver ile sayfayı aç ve embed URL tespit et."""
    if not HAS_NODRIVER:
        log.warning("nodriver yüklü değil, browser ile embed arama atlanıyor")
        return None
    assert uc is not None and cdp is not None

    log.info("nodriver ile embed URL aranıyor...")
    main_domain = main_url.split("/")[2]
    browser = None
    embed_url = None
    all_urls = []

    try:
        browser = await uc.start(headless=False)
        tab = browser.main_tab

        async def on_request(event):
            nonlocal embed_url
            try:
                url = event.request.url
                if not url.startswith("http"):
                    return
                if main_domain in url:
                    return
                if any(s in url.lower() for s in SKIP_DOMAINS):
                    return
                if any(url.lower().endswith(e) for e in SKIP_EXT):
                    return
                all_urls.append(url)
                if not embed_url:
                    embed_url = url
                    log.info(f"  Embed URL bulundu: {url}")
            except Exception:
                pass

        tab.add_handler(cdp.network.RequestWillBeSent, on_request)
        await tab.send(cdp.network.enable())
        await tab.get(main_url)
        # "Kaldığınız yerden devam" diyalogu çıkaran siteler için storage temizle
        _resume_sites = ["dizi54.life", "dizi54.ws", "dizi54.net"]
        if any(s in main_url.lower() for s in _resume_sites):
            try:
                await tab.evaluate("localStorage.clear(); sessionStorage.clear();")
                await tab.get(main_url)
            except Exception:
                pass
        await asyncio.sleep(8)

        if not embed_url and all_urls:
            log.debug("  Embed bulunamadı. Dış URL'ler:")
            for u in all_urls[:10]:
                log.debug(f"    {u[:100]}")
    except Exception as e:
        log.debug(f"  nodriver embed arama hatası: {e}")
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass
    return embed_url


async def capture_stream_nodriver(main_url, timeout=120):
    """nodriver ile stream yakala + reklam atla (fallback)."""
    if not HAS_NODRIVER:
        log.warning("nodriver yüklü değil")
        return None
    assert uc is not None and cdp is not None

    log.info("nodriver ile stream yakalanıyor (fallback)...")
    found = []

    browser = await uc.start(headless=False)
    tab = browser.main_tab

    async def on_request(event):
        try:
            url = event.request.url
            if any(ad in url.lower() for ad in AD_DOMAINS):
                return
            if any(ext in url for ext in STREAM_EXT):
                if url not in found:
                    found.append(url)
                    log.info(f"  ✓ STREAM yakalandı: {url}")
        except Exception:
            pass

    tab.add_handler(cdp.network.RequestWillBeSent, on_request)
    await tab.send(cdp.network.enable())

    try:
        await tab.get(main_url)
    except Exception:
        pass

    # nodriver'da JS ile reklam atlama
    ad_handler_nodriver = AD_HANDLER_JS.replace("var result", "let result")
    elapsed = 0
    ad_count = 0
    while elapsed < timeout:
        await asyncio.sleep(3)
        elapsed += 3
        if found:
            break

        try:
            result = await tab.evaluate(ad_handler_nodriver)
            if result and isinstance(result, dict) and result.get("found"):
                ad_count += 1
                for action in result.get("actions", []):
                    log.info(f"  [nodriver {elapsed}s] {action}")
                await asyncio.sleep(1)
        except Exception:
            pass

        if elapsed % 15 == 0:
            log.info(f"  [{elapsed}s/{timeout}s] stream:{len(found)} reklam:{ad_count}")

    try:
        browser.stop()
    except Exception:
        pass
    return found[0] if found else None


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYWRIGHT GENEL YAKALAMA (tüm siteler)
# ══════════════════════════════════════════════════════════════════════════════

async def capture_general_playwright(film_url, embed_url=None, use_persistent=False):
    """
    Playwright ile genel stream yakalama.
    use_persistent=True → Cloudflare bypass için kalıcı Chrome profili kullanır.
    """
    if not HAS_PLAYWRIGHT:
        log.warning("Playwright yüklü değil")
        return None, None
    assert async_playwright is not None

    found_streams = []
    cookie_file = None

    # LOCK dosyalarını temizle (persistent mod için)
    if use_persistent:
        try:
            for root, dirs, files in os.walk(PROFILE_DIR):
                for fname in files:
                    if fname == "LOCK":
                        try:
                            os.remove(os.path.join(root, fname))
                        except Exception:
                            pass
        except Exception:
            pass

    async with async_playwright() as p:
        if use_persistent:
            log.info("Playwright tarayıcı başlatılıyor (persistent CF bypass modu)...")
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=False,
                    viewport={"width": 1280, "height": 800},
                    user_agent=UA,
                    locale="tr-TR",
                    ignore_default_args=["--enable-automation"],
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
            except Exception:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=False,
                    channel="chrome",
                    viewport={"width": 1280, "height": 800},
                    user_agent=UA,
                    locale="tr-TR",
                    ignore_default_args=["--enable-automation"],
                    args=["--disable-blink-features=AutomationControlled"],
                )
        else:
            log.info("Playwright tarayıcı başlatılıyor (genel mod)...")
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                user_agent=UA,
                viewport={"width": 1280, "height": 800},
                locale="tr-TR",
            )
        await context.add_init_script(STEALTH_JS)

        page = await context.new_page()

        # Pop-up yakalayıcı: yeni sekmeler otomatik kapatılsın
        page.on("popup", lambda popup: asyncio.ensure_future(_close_popup(popup)))

        # Network intercept
        def on_request(request):
            url = request.url
            if any(ad in url.lower() for ad in AD_DOMAINS):
                return
            if looks_like_stream_candidate(url):
                if url not in found_streams:
                    found_streams.append(url)
                    log.info(f"  ✓ STREAM (network): {url}")

        async def on_response(response):
            try:
                rurl = response.url
                if any(ad in rurl.lower() for ad in AD_DOMAINS):
                    return
                # Yanıt URL'si zaten stream ise ekle
                if looks_like_stream_candidate(rurl) and rurl not in found_streams:
                    found_streams.append(rurl)
                    log.info(f"  ✓ STREAM (response-url): {rurl}")
                    return
                ctype = (response.headers.get("content-type", "") or "").lower()
                if "text/html" in ctype:
                    return
                if not any(k in ctype for k in ["json", "mpegurl", "dash+xml", "text/plain", "octet-stream"]):
                    return
                body = await response.text()
                for u in extract_stream_urls_from_text(body):
                    full = normalize_stream_candidate(u, rurl)
                    if looks_like_stream_candidate(full) and full not in found_streams:
                        found_streams.append(full)
                        log.info(f"  ✓ STREAM (response): {full}")
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", lambda r: asyncio.ensure_future(on_response(r)))

        # Sayfayı aç
        target_url = embed_url or film_url
        log.info(f"Sayfa açılıyor: {target_url[:100]}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            log.info("  Sayfa yüklendi")
            # "Kaldığınız yerden devam" diyalogu çıkaran siteler için storage temizle
            _resume_dialog_sites = ["dizi54.life", "dizi54.ws", "dizi54.net"]
            if any(s in (film_url or "").lower() for s in _resume_dialog_sites):
                try:
                    await page.evaluate("""
                        () => {
                            try { localStorage.clear(); } catch(e) {}
                            try { sessionStorage.clear(); } catch(e) {}
                        }
                    """)
                    await page.reload(wait_until="domcontentloaded", timeout=20000)
                    log.debug("  localStorage/sessionStorage temizlendi, sayfa yenilendi")
                except Exception:
                    pass
            await force_autoplay(page, "ilk_yukleme")
        except Exception as e:
            log.warning(f"  Sayfa yükleme hatası (devam ediliyor): {e}")

        # Eğer embed_url verilmişse, film sayfasında açmayı dene (iframe erişimi için)
        if embed_url and embed_url != film_url:
            try:
                page2 = await context.new_page()
                page2.on("request", on_request)
                page2.on("response", lambda r: asyncio.ensure_future(on_response(r)))
                page2.on("popup", lambda popup: asyncio.ensure_future(_close_popup(popup)))
                log.info(f"Film sayfası açılıyor: {film_url[:100]}")
                await page2.goto(film_url, wait_until="domcontentloaded", timeout=30000)
                # Ana sayfa sayfasını da izle
                await asyncio.sleep(3)
                await force_autoplay(page2, "film_sayfasi")
            except Exception:
                pass

        # Reklam atlama + video başlatma döngüsü
        master_found = [False]
        await ad_watcher_loop(page, found_streams, master_found, duration=120)

        # embed HTML'den de decode dene
        if not found_streams:
            try:
                html = await page.content()
                stream = extract_stream_url(html)
                if stream:
                    found_streams.append(stream)
            except Exception:
                pass

        # Cookie kaydet
        try:
            cookies = await context.cookies()
            with open(COOKIES_FILE, "w", encoding="utf-8") as cf:
                cf.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    secure = "TRUE" if c.get("secure") else "FALSE"
                    raw_exp = int(c.get("expires", 0)) if c.get("expires") else 0
                    expiry = raw_exp if raw_exp > 0 else 0
                    domain = c.get("domain", "")
                    incl_sub = "TRUE" if domain.startswith(".") else "FALSE"
                    cf.write(
                        f"{domain}\t{incl_sub}\t{c.get('path', '/')}\t{secure}\t"
                        f"{expiry}\t{c.get('name', '')}\t{c.get('value', '')}\n"
                    )
            cookie_file = COOKIES_FILE
            log.debug(f"  {len(cookies)} cookie kaydedildi")
        except Exception:
            pass

        await context.close()
        if not use_persistent:
            try:
                await browser.close()
            except Exception:
                pass

    best_stream = pick_best_stream_url(found_streams)
    return best_stream, cookie_file


async def _close_popup(popup):
    """Pop-up sayfalarını otomatik kapat."""
    try:
        await asyncio.sleep(1)
        log.info(f"  Pop-up kapatıldı: {popup.url[:60]}")
        await popup.close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#   PLAYWRIGHT PİCHİVE (Cloudflare bypass)
# ══════════════════════════════════════════════════════════════════════════════

async def capture_pichive_playwright(film_url, embed_url):
    """
    Playwright ile pichive.online stream yakalama.
    Kalıcı Chrome profili kullanır (Cloudflare bypass).
    """
    if not HAS_PLAYWRIGHT:
        log.warning("Playwright yüklü değil")
        return [], None, None, embed_url
    assert async_playwright is not None

    found_streams = []
    master_php_url = None
    master_m3u8_content = None
    variant_php_urls = []
    pichive_frame = None
    cookie_file = None
    embed_ref = embed_url
    pichive_host = urlparse(embed_url).netloc

    log.info("Playwright başlatılıyor (pichive CF bypass modu)...")

    # LOCK dosyalarını temizle
    try:
        for root, dirs, files in os.walk(PROFILE_DIR):
            for fname in files:
                if fname == "LOCK":
                    try:
                        os.remove(os.path.join(root, fname))
                    except Exception:
                        pass
    except Exception:
        pass

    async with async_playwright() as p:
        # Persistent context (CF cookie'leri saklamak için)
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                viewport={"width": 1280, "height": 800},
                user_agent=UA,
                locale="tr-TR",
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            log.info("  Chromium başlatıldı (persistent context)")
        except Exception:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                channel="chrome",
                viewport={"width": 1280, "height": 800},
                user_agent=UA,
                locale="tr-TR",
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled"],
            )
            log.info("  Gerçek Chrome başlatıldı (persistent context)")

        await context.add_init_script(STEALTH_JS)

        page = await context.new_page()
        page.on("popup", lambda popup: asyncio.ensure_future(_close_popup(popup)))

        # ── Network handler ──
        def on_request(request):
            nonlocal master_php_url
            url = request.url
            if any(ad in url.lower() for ad in AD_DOMAINS):
                return
            if "pichive" in url:
                log.debug(f"  [REQ] {url[:100]}")
            if any(ext in url for ext in STREAM_EXT):
                if url not in found_streams:
                    found_streams.append(url)
                    log.info(f"  ✓ STREAM (network): {url}")
            if "pichive" in url and "master.php" in url and not master_php_url:
                master_php_url = url
                log.info(f"  ✓ master.php yakalandı!")
                m = re.search(r"t=([A-Za-z0-9._-]+)", url)
                if m:
                    token = m.group(1)
                    cdn_candidates = decode_pichive_jwt_cdn_all(token)
                    stream = decode_pichive_jwt(token)
                    added = 0
                    for cdn in cdn_candidates:
                        if cdn and cdn not in found_streams:
                            found_streams.append(cdn)
                            log.info(f"  ✓ STREAM (JWT CDN): {cdn}")
                            added += 1
                    if stream and stream not in found_streams:
                        found_streams.append(stream)
                        log.info(f"  ✓ STREAM (JWT stream): {stream}")
                    if not cdn_candidates and not stream:
                        log.warning("  JWT decode başarısız, master.php URL kullanılacak")

        async def on_response(response):
            nonlocal master_m3u8_content
            url = response.url
            if "pichive" in url and ("master.php" in url or "variant.php" in url):
                php_type = "master" if "master.php" in url else "variant"
                try:
                    body = await response.body()
                    text = body.decode("utf-8", errors="replace")
                    log.debug(f"  {php_type}.php ({response.status}, {len(text)}b)")
                    if response.status == 200 and "#EXTM3U" in text:
                        if php_type == "master" and not master_m3u8_content:
                            master_m3u8_content = text
                            base = f"https://{pichive_host}"
                            for m in re.finditer(
                                r'URI="(/edge/variant\.php\?t=[A-Za-z0-9._-]+)"', text
                            ):
                                full = base + m.group(1)
                                if full not in variant_php_urls:
                                    variant_php_urls.append(full)
                                    log.info(f"  ✓ Variant URL bulundu: {full[:80]}")
                except Exception:
                    pass

        def on_frame_navigated(frame):
            nonlocal pichive_frame
            if "pichive" in frame.url:
                pichive_frame = frame
                log.info(f"  Pichive frame tespit edildi: {frame.url[:80]}")
                asyncio.ensure_future(_trigger_pichive_frame(frame))

        async def _trigger_pichive_frame(frame):
            await asyncio.sleep(3)
            if not master_php_url:
                await run_ad_handler(frame, "pichive_auto")

        page.on("request", on_request)
        page.on("response", lambda r: asyncio.ensure_future(on_response(r)))
        page.on("framenavigated", on_frame_navigated)

        # ── Film sayfasını aç ──
        log.info(f"Film sayfası açılıyor: {film_url}")
        try:
            await page.goto(film_url, wait_until="domcontentloaded", timeout=30000)
            log.info("  Sayfa yüklendi")
            await force_autoplay(page, "pichive_film")
        except Exception as e:
            log.warning(f"  Sayfa yükleme hatası (devam): {e}")

        # ── Otonom reklam atlama + video başlatma ──
        master_found_ref = [False]

        # master_php_url değişkenini referans olarak takip et
        class MasterRef:
            @property
            def value(self):
                return [bool(master_php_url)]

        elapsed = 0
        ad_count = 0
        # Pichive CDN subdomain fallback listesi
        _CDN_PREFIXES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
        _cdn_tried = set()
        _current_cdn = urlparse(embed_ref).hostname.split(".")[0] if embed_ref else ""
        _cdn_tried.add(_current_cdn)

        while elapsed < 120 and not master_php_url:
            await asyncio.sleep(3)
            elapsed += 3

            if found_streams:
                log.info(f"  ✓ Stream yakalandı ({elapsed}s)")
                break

            # Tüm frame'lerde reklam handler
            try:
                for frame in page.frames:
                    try:
                        result = await run_ad_handler(frame, f"p{elapsed}s")
                        await force_autoplay(frame, f"p{elapsed}s")
                        await extract_player_stream_candidates(frame, found_streams, f"p{elapsed}s")
                        if result and result.get("found"):
                            ad_count += 1
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            # Not: pichive CDN subdomain fallback kaldırıldı - one..ten.pichive.online domainleri DNS'de yok
            # Sadece four.pichive.online gerçek domain, CF challenge için beklemeye devam et

            # Pop-up kontrol
            try:
                if len(page.context.pages) > 2:
                    for extra in page.context.pages[2:]:
                        try:
                            await extra.close()
                            log.info("  Gereksiz sekme kapatıldı")
                        except Exception:
                            pass
            except Exception:
                pass

            if elapsed % 15 == 0:
                log.info(
                    f"  [{elapsed}s] master:{'evet' if master_php_url else 'yok'} "
                    f"stream:{len(found_streams)} reklam:{ad_count}"
                )

        # ── Strateji 2: iframe.php'yi yeni sayfada aç ──
        if not master_php_url and not found_streams:
            log.info("Strateji 2: iframe.php yeni sayfada açılıyor...")
            try:
                page2 = await context.new_page()
                page2.on("request", on_request)
                page2.on("response", lambda r: asyncio.ensure_future(on_response(r)))
                page2.on("framenavigated", on_frame_navigated)
                page2.on("popup", lambda popup: asyncio.ensure_future(_close_popup(popup)))

                # CDN subdomain listesini oluştur (mevcut + alternatifler)
                _strat2_cdn_order = [_current_cdn] + [
                    p for p in _CDN_PREFIXES if p != _current_cdn
                ]

                for cdn_prefix in _strat2_cdn_order:
                    if master_php_url or found_streams:
                        break
                    try_host = f"{cdn_prefix}.pichive.online"
                    try_embed = embed_ref.replace(
                        f"{urlparse(embed_ref).hostname}",
                        try_host,
                        1,
                    )

                    # CF challenge
                    log.info(f"  {try_host} root sayfasına gidiliyor (CF challenge)...")
                    _goto_failed = False
                    try:
                        await page2.goto(
                            f"https://{try_host}/",
                            wait_until="domcontentloaded",
                            timeout=20000,
                        )
                    except Exception as _eg:
                        if "ERR_NAME_NOT_RESOLVED" in str(_eg) or "ERR_CONNECTION_REFUSED" in str(_eg):
                            log.debug(f"  {try_host} DNS/bağlantı hatası, atlanıyor")
                            _goto_failed = True
                        # diğer hatalar için devam et

                    if _goto_failed:
                        continue

                    # CF challenge geçip geçmediğini kontrol et
                    cf_blocked = False
                    for i in range(15):
                        await asyncio.sleep(1)
                        try:
                            body = await page2.evaluate(
                                "() => document.body ? document.body.innerText.substring(0,120) : ''"
                            )
                            cur_url = page2.url
                            if "cf-no-screenshot-error" in await page2.content():
                                cf_blocked = True
                                break
                            if (
                                body
                                and "blocked" not in body.lower()
                                and "access denied" not in body.lower()
                                and "challenge" not in cur_url
                            ):
                                break
                        except Exception:
                            pass

                    if cf_blocked:
                        log.warning(f"  {try_host} CF tarafından engelleniyor, sonraki deneniyor...")
                        continue

                    # iframe.php'ye git
                    await page2.set_extra_http_headers({"Referer": film_url})
                    log.info(f"  iframe.php açılıyor: {try_embed[:80]}")
                    try:
                        await page2.goto(try_embed, wait_until="domcontentloaded", timeout=30000)
                        pichive_host = try_host
                    except Exception:
                        pass

                    elapsed2 = 0
                    while elapsed2 < 60 and not master_php_url:
                        await asyncio.sleep(3)
                        elapsed2 += 3
                        if master_php_url or found_streams:
                            log.info(f"  ✓ Stream yakalandı ({elapsed2}s) [{try_host}]")
                            break
                        try:
                            for frame in page2.frames:
                                await run_ad_handler(frame, f"p2-{elapsed2}s")
                                await force_autoplay(frame, f"p2-{elapsed2}s")
                                await extract_player_stream_candidates(frame, found_streams, f"p2-{elapsed2}s")
                        except Exception:
                            pass
                        if elapsed2 % 15 == 0:
                            log.info(
                                f"  [{elapsed2}s] master:{'evet' if master_php_url else 'yok'} "
                                f"frames:{len(page2.frames)}"
                            )

            except Exception as e:
                log.warning(f"  iframe.php hatası: {e}")

        if not master_php_url and not found_streams:
            log.warning("master.php yakalanamadı")

        # Variant bekleme
        if master_php_url:
            log.info("Variant URL'ler için bekleniyor...")
            # Player başlat
            for frame in page.frames:
                try:
                    await run_ad_handler(frame, "variant_wait")
                except Exception:
                    pass
            for _ in range(15):
                await asyncio.sleep(2)

        # Frame'den variant fetch
        if master_php_url and variant_php_urls:
            log.info("Frame'den variant.php fetch ediliyor...")
            active_frame = None
            for pg in page.context.pages:
                try:
                    for fr in pg.frames:
                        if pichive_host in fr.url:
                            active_frame = fr
                            break
                except Exception:
                    pass
                if active_frame:
                    break

            if active_frame:
                for vurl in variant_php_urls[:2]:
                    parsed = urlparse(vurl)
                    rel_path = parsed.path + "?" + parsed.query
                    try:
                        content = await active_frame.evaluate(
                            """async (path) => {
                            try { const r = await fetch(path); if(!r.ok) return null; return await r.text(); }
                            catch(e) { return null; }
                        }""",
                            rel_path,
                        )
                        if content and "#EXTM3U" in str(content):
                            out_path = os.path.join(
                                SCRIPT_DIR, f"_variant_{abs(hash(vurl)) % 10000}.m3u8"
                            )
                            with open(out_path, "w", encoding="utf-8") as vf:
                                vf.write(str(content))
                            log.info(f"  ✓ Variant m3u8 kaydedildi: {out_path}")
                    except Exception:
                        pass

        # Cookie kaydet
        try:
            cookies = await context.cookies()
            with open(COOKIES_FILE, "w", encoding="utf-8") as cf:
                cf.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    secure = "TRUE" if c.get("secure") else "FALSE"
                    raw_exp = int(c.get("expires", 0)) if c.get("expires") else 0
                    expiry = raw_exp if raw_exp > 0 else 0
                    domain = c.get("domain", "")
                    incl_sub = "TRUE" if domain.startswith(".") else "FALSE"
                    cf.write(
                        f"{domain}\t{incl_sub}\t{c.get('path', '/')}\t{secure}\t"
                        f"{expiry}\t{c.get('name', '')}\t{c.get('value', '')}\n"
                    )
            cookie_file = COOKIES_FILE
            log.info(f"  {len(cookies)} cookie kaydedildi")
        except Exception:
            pass

        await context.close()

    # master.m3u8 kaydet
    if master_m3u8_content:
        master_path = os.path.join(SCRIPT_DIR, "_master.m3u8")
        with open(master_path, "w", encoding="utf-8") as f:
            f.write(master_m3u8_content)
        log.info(f"  master.m3u8 kaydedildi: {master_path}")

    log.info(f"Toplam {len(found_streams)} stream URL yakalandı")
    for s in found_streams:
        log.info(f"  • {s}")

    ordered = sorted(found_streams, key=stream_score, reverse=True)
    return ordered, master_m3u8_content, cookie_file, embed_ref


# ══════════════════════════════════════════════════════════════════════════════
#   İNDİRME
# ══════════════════════════════════════════════════════════════════════════════

def download_stream(
    stream_url,
    referer,
    title: Optional[str] = "video",
    cookie_file=None,
    output_dir=".",
    snippet_seconds=0,
    source_url=None,
    embed_url=None,
):
    """Stream URL'sini en iyi kalitede indir."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title or "video")
    out_path = os.path.join(output_dir, safe_title + ".%(ext)s")
    out_file_mp4 = os.path.join(output_dir, safe_title + ".mp4")

    log.info(f"İndirme başlıyor: {safe_title}")
    log.info(f"  Stream: {stream_url[:100]}")

    if snippet_seconds > 0:
        log.info(f"  Test modu: Bu linkten ilk {snippet_seconds} saniye indirilecek")

    special_targets = resolve_special_stream_targets(stream_url, referer)
    if special_targets:
        log.info(f"  Özel site kuralı: {len(special_targets)} hedef denenecek")
        for method, target in special_targets:
            log.info(f"  Özel hedef ({method}): {target}")
            if method == "ffmpeg" and run_ffmpeg_direct(
                target,
                out_file_mp4,
                referer,
                snippet_seconds=snippet_seconds,
            ):
                log.info(f"  ✓ İndirme tamamlandı: {safe_title}")
                return True
            if method == "python_hls" and download_jpg_hls(
                target,
                out_file_mp4,
                referer,
                snippet_seconds=snippet_seconds,
            ):
                log.info(f"  ✓ İndirme tamamlandı: {safe_title}")
                return True

    formats_to_try = [
        "bestvideo+bestaudio/best",
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    ]

    success = False
    for fexpr in formats_to_try:
        log.info(f"  Format deneniyor: {fexpr}")
        success = _run_ytdlp_download(
            stream_url,
            out_path,
            referer,
            cookie_file=cookie_file,
            snippet_seconds=snippet_seconds,
            fmt=fexpr,
        )
        if success:
            break

    if not success:
        # Son şans: sayfa URL'si / embed URL'si üzerinden extractor ile indirme dene.
        fallback_targets = []
        for cand in [embed_url, source_url]:
            if cand and cand not in fallback_targets:
                fallback_targets.append(cand)
        if fallback_targets:
            log.warning("  Stream URL başarısız; sayfa tabanlı yt-dlp fallback deneniyor...")
            for ft in fallback_targets:
                log.info(f"  Fallback hedefi: {ft}")
                if _run_ytdlp_download(
                    ft,
                    out_path,
                    source_url or referer,
                    cookie_file=cookie_file,
                    snippet_seconds=snippet_seconds,
                    fmt="bestvideo+bestaudio/best",
                ):
                    success = True
                    break

    if success:
        log.info(f"  ✓ İndirme tamamlandı: {safe_title}")
    else:
        log.error("  ✗ İndirme hatası (tüm denemeler başarısız)")

    return success


# ══════════════════════════════════════════════════════════════════════════════
#   TEK URL İŞLEME
# ══════════════════════════════════════════════════════════════════════════════

async def process_url(url, output_dir=".", snippet_seconds=0):
    """
    Tek bir URL işle: site tipi tespit → stream bul → indir.
    Tamamen otonom çalışır.
    """
    log.info(f"URL tipi algılanıyor: {url}")

    rule_key, site_rule = match_site_rule(url)
    log_site_rule(url, rule_key, site_rule)

    # ── YouTube ──
    if is_youtube(url):
        return process_youtube(url, output_dir, snippet_seconds=snippet_seconds)

    # ── Film / Dizi siteleri ──
    log.info("Film/dizi sitesi — bilgiler alınıyor...")
    headers = {"User-Agent": UA}
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        main_html = resp.text
    except Exception as e:
        log.error(f"Ana sayfa alınamadı: {e}")
        return False

    # Film bilgileri
    title, poster = get_film_meta(url, main_html)
    log.info(f"Başlık: {title or 'bilinmiyor'}")
    if poster:
        log.debug(f"Poster: {poster}")

    # CF engeli kontrolü — başlık blocked_title_markers içindeyse HTML decode atla
    cf_blocked_html = is_cloudflare_blocked(main_html)
    if cf_blocked_html:
        log.warning("CF engeli tespit edildi — HTML decode atlanıyor, doğrudan tarayıcı kullanılacak")
        title = None  # CF başlığını dosya adı olarak kullanma
        main_html = ""

    stream_url = None
    referer = url
    cookie_file = None
    embed_rule_key = rule_key
    embed_rule = site_rule

    if not cf_blocked_html and site_rule.get("direct_html_first"):
        log.info("Site kuralı: Ana sayfa HTML decode öncelikli")
        stream_url = extract_stream_url(main_html)
        if stream_url:
            log.info(f"  ✓ Stream URL (ana HTML): {stream_url}")

    # ── Adım 1: Net-export log (komut satırı argümanı) ──
    # (parse_args'da işlenir)

    # ── Adım 2: Embed URL tespiti ──
    log.info("Embed URL aranıyor...")
    embed_url = None if cf_blocked_html else get_embed_url_from_html(url, main_html, site_rule)

    if not embed_url and site_rule.get("prefer_browser_embed"):
        log.info("Site kuralı: Tarayıcı ile embed arama öncelikli")
        try:
            embed_url = await get_embed_url_browser(url)
        except Exception as _e:
            log.debug(f"  Browser embed arama hatası: {_e}")

    if not embed_url:
        log.info("  HTML'den bulunamadı, tarayıcı ile aranıyor...")
        try:
            embed_url = await get_embed_url_browser(url)
        except Exception as _e:
            log.debug(f"  Browser embed arama hatası (2): {_e}")

    if embed_url:
        embed_rule_key, embed_rule = match_site_rule(embed_url)
        log_site_rule(embed_url, embed_rule_key, embed_rule)
        referer = embed_url
        log.info(f"Embed URL: {embed_url[:100]}")

        # ── Adım 3: pichive → Playwright CF bypass ──
        if is_pichive(embed_url):
            log.info("pichive.online tespit edildi — Cloudflare bypass deneniyor...")

            # Önce basit JWT decode (hızlı, tarayıcısız)
            try:
                embed_resp = requests.get(
                    embed_url,
                    headers={"Referer": url, "User-Agent": UA},
                    verify=False,
                    timeout=15,
                )
                if not is_cloudflare_blocked(embed_resp.text):
                    m = re.search(r"edge/master\.php\?t=([A-Za-z0-9._-]+)", embed_resp.text)
                    if m:
                        token = m.group(1)
                        stream_url = decode_pichive_jwt(token) or decode_pichive_jwt_cdn(token)
                        if stream_url:
                            log.info(f"  ✓ Stream URL (JWT direkt decode): {stream_url}")
            except Exception:
                pass

            # CF engeli varsa Playwright
            if not stream_url:
                found, master_content, cookie_file, embed_ref = await capture_pichive_playwright(
                    url, embed_url
                )
                referer = embed_ref or embed_url
                if found:
                    stream_url = pick_best_stream_url(found)
                if master_content:
                    # master.m3u8 dosyasını kaydettik (capture içinde)
                    pass

        # ── Adım 4: HTML decode (genel siteler) ──
        if not stream_url:
            log.info("Embed HTML decode deneniyor...")
            try:
                embed_resp = requests.get(
                    embed_url,
                    headers={
                        "Referer": url,
                        "Origin": "https://" + url.split("/")[2],
                        "User-Agent": UA,
                    },
                    verify=False,
                    timeout=15,
                )
                embed_html = embed_resp.text

                if is_cloudflare_blocked(embed_html):
                    log.info("  Cloudflare engeli — Playwright ile deneniyor...")
                    stream_url, cookie_file = await capture_general_playwright(url, embed_url)
                else:
                    stream_url = extract_stream_url(embed_html)
                    if stream_url:
                        log.info(f"  ✓ Stream URL (HTML decode): {stream_url}")
            except Exception as e:
                log.debug(f"  Embed fetch hatası: {e}")

    # ── Adım 5: Playwright genel yakalama ──
    if not stream_url and (site_rule.get("prefer_playwright") or embed_rule.get("prefer_playwright") or True):
        log.info("Playwright ile doğrudan yakalama deneniyor...")
        # CF engeli varsa kalıcı Chrome profili kullan (CF cookie'leri saklı)
        use_pers = cf_blocked_html and bool(site_rule.get("prefer_playwright"))
        stream_url, cookie_file = await capture_general_playwright(url, embed_url, use_persistent=use_pers)

    # ── Adım 6: nodriver fallback ──
    if not stream_url:
        use_nodriver = bool(site_rule.get("use_nodriver_fallback", True)) or bool(
            embed_rule.get("use_nodriver_fallback", True)
        )
        if use_nodriver:
            log.info("nodriver ile fallback deneniyor...")
            stream_url = await capture_stream_nodriver(url)
        else:
            log.info("Site kuralı: nodriver fallback pasif")

    # ── Sonuç ──
    if not stream_url:
        log.error("✗ Stream URL bulunamadı")
        log.info("Manuel yöntem:")
        log.info("  1. Chrome'da sayfayı aç, videoyu oynat")
        log.info("  2. chrome://net-export/ ile log al")
        log.info(f"  3. python videoflower.py --log LOG_DOSYASI {url}")
        return False

    log.info(f"✓ Stream URL bulundu: {stream_url}")

    # CF engeli nedeniyle başlık alınamadıysa URL'den türet
    if not title:
        slug = url.rstrip("/").split("/")[-1]
        title = re.sub(r"[-_]", " ", slug).title() or "video"
        log.info(f"  Başlık (URL'den): {title}")

    get_stream_info(stream_url, referer)
    return download_stream(
        stream_url,
        referer,
        title,
        cookie_file,
        output_dir,
        snippet_seconds=snippet_seconds,
        source_url=url,
        embed_url=embed_url,
    )


def write_run_report(results, output_dir, snippet_seconds=0, report_path=None):
    """Koşu sonu Türkçe markdown raporu üret."""
    if not report_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(SCRIPT_DIR, f"RAPOR_v1.0_{ts}.md")

    ok = sum(1 for _, s in results if s)
    fail = len(results) - ok
    lines = []
    lines.append("# VideoFlower v1.0 Çalışma Raporu")
    lines.append("")
    lines.append(f"- Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- Toplam URL: {len(results)}")
    lines.append(f"- Başarılı: {ok}")
    lines.append(f"- Başarısız: {fail}")
    lines.append(f"- Çıktı dizini: {os.path.abspath(output_dir)}")
    lines.append(f"- Log dosyası: {LOG_FILE}")
    lines.append(f"- Test kesiti: {snippet_seconds if snippet_seconds else 'tam video'}")
    lines.append("")
    lines.append("## URL Sonuçları")
    lines.append("")
    for i, (url, success) in enumerate(results, 1):
        durum = "BASARILI" if success else "BASARISIZ"
        lines.append(f"{i}. [{durum}] {url}")
    lines.append("")
    lines.append("## Otomasyon Kapsamı")
    lines.append("")
    lines.append("- Reklam metinleri (Skip, Reklam, Reklamı Geç) döngüsel olarak algılandı.")
    lines.append("- Reklam sonrası Videoyu Başlat/Oynat butonları otomatik tetiklendi.")
    lines.append("- Overlay/pop-up reklamları kapanacak şekilde akış yürütüldü.")
    lines.append("- YouTube playlist linklerinde sıralı indirme stratejisi uygulandı.")
    lines.append("- İndirme formatı en iyi kalite (bestvideo+bestaudio) olarak ayarlandı.")

    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write("\n".join(lines))

    log.info(f"Rapor üretildi: {report_path}")
    return report_path


# ══════════════════════════════════════════════════════════════════════════════
#   ANA GİRİŞ NOKTASI
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(
        description="VideoFlower v1.0 — Otonom Video İndirme Aracı",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python videoflower.py https://www.youtube.com/watch?v=XXXX
  python videoflower.py --output filmler https://site.com/film
  python videoflower.py url1 url2 url3
  python videoflower.py --log chrome_net.json https://site.com/film
        """,
    )
    parser.add_argument("urls", nargs="*", help="İndirilecek video URL'leri")
    parser.add_argument("-o", "--output", default=None, help="Çıktı dizini (varsayılan: ./indirilenler)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Detaylı log çıktısı")
    parser.add_argument("--log", help="Chrome net-export log dosyası (JSON)")
    parser.add_argument("--snippet-seconds", type=int, default=0, help="Test modu: sadece ilk N saniyeyi indir")
    parser.add_argument("--test-all-links", action="store_true", help="Dahili test linklerinin tamamını sırayla çalıştır")
    parser.add_argument("--report", default=None, help="Rapor dosya yolu (varsayılan: otomatik RAPOR_v1.0_*.md)")
    parser.add_argument("--version", action="version", version=f"VideoFlower v{__version__}")

    args = parser.parse_args()

    # Logging seviyesi
    if args.verbose:
        global log
        log = setup_logging(verbose=True)

    # Çıktı dizini
    output_dir = args.output or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # URL'ler
    urls = args.urls
    if args.test_all_links:
        urls = DEFAULT_TEST_URLS.copy()
        if args.snippet_seconds <= 0:
            args.snippet_seconds = 30
        log.info("Dahili kapsamlı test listesi aktif edildi")

    if not urls:
        url = input("\nVideo URL'sini girin (birden fazla için virgülle ayırın): ").strip()
        if url:
            urls = [u.strip() for u in url.split(",") if u.strip()]

    if not urls:
        log.error("URL belirtilmedi. Kullanım: python videoflower.py URL [URL2 ...]")
        return

    # Başlık
    log.info("=" * 60)
    log.info(f"  VideoFlower v{__version__} — Otonom Video İndirme Aracı")
    log.info(f"  Tarih  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"  Çıktı  : {os.path.abspath(output_dir)}")
    log.info(f"  URL    : {len(urls)} adet")
    if args.snippet_seconds > 0:
        log.info(f"  Mod    : Test (ilk {args.snippet_seconds} saniye)")
    else:
        log.info("  Mod    : Tam indirme")
    log.info("=" * 60)

    # Net-export log varsa önce onu dene
    if args.log and os.path.exists(args.log):
        log.info(f"\nNet-export log dosyası: {args.log}")
        stream_url, ref = parse_net_log(args.log)
        if stream_url:
            referer = ref or (urls[0] if urls else "")
            title = "net_log_video"
            download_stream(stream_url, referer, title, None, output_dir)
            return

    # Her URL'yi sırasıyla işle
    results = []
    for i, url in enumerate(urls, 1):
        log.info(f"\n{'━' * 60}")
        log.info(f"  [{i}/{len(urls)}] {url}")
        log.info(f"{'━' * 60}")
        try:
            success = await process_url(url, output_dir, snippet_seconds=args.snippet_seconds)
            results.append((url, success))
        except Exception as e:
            log.error(f"Beklenmeyen hata: {e}")
            results.append((url, False))

    # Özet
    log.info(f"\n{'═' * 60}")
    log.info("  SONUÇ ÖZETİ")
    log.info(f"{'═' * 60}")
    ok = sum(1 for _, s in results if s)
    fail = len(results) - ok
    for url, success in results:
        status = "✓" if success else "✗"
        log.info(f"  {status} {url[:70]}")
    log.info(f"\n  Toplam: {len(results)} | Başarılı: {ok} | Başarısız: {fail}")
    log.info(f"  Çıktı dizini: {os.path.abspath(output_dir)}")
    log.info(f"  Log dosyası : {LOG_FILE}")
    log.info(f"{'═' * 60}")

    write_run_report(results, output_dir, args.snippet_seconds, args.report)


if __name__ == "__main__":
    asyncio.run(main())
