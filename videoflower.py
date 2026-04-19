#!/usr/bin/env python3
"""
VideoFlower v1.0 — Otonom Video İndirme Aracı
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Desteklenen siteler:
  • YouTube (tek video + playlist)
  • hdfilmcehennemi (.llc / .nl)
  • hdfilmizle.so
  • dizi54.life
  • jetfilmizle.net / izleplus.com / zeusdizi31.com / dizibox.live
  • pichive.online embed (Cloudflare bypass)
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
from urllib.parse import urlparse, urljoin

import requests
import urllib3
urllib3.disable_warnings()

# Opsiyonel bağımlılıklar
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

try:
    import nodriver as uc
    from nodriver import cdp
    HAS_NODRIVER = True
except ImportError:
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

AD_DOMAINS = [
    "cvt-s2", "agl005", ".xml", "vast", "doubleclick",
    "googlesyndication", "adserver", "adsystem", "pagead",
    "securepubads", "moatads", "adnxs", "advertising",
    "tpc.googlesyndication",
]

SKIP_DOMAINS = [
    "google", "gtag", "analytics", "facebook", "twitter",
    "cloudflare", "jquery", "bootstrap", "gstatic",
    "doubleclick", "googleapis", "fontawesome", "recaptcha",
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

    // ADIM 1: Reklam atlama butonları
    if (findByText([
        'reklamı geç', 'reklam geç', 'reklamı kapat', 'reklamı atla',
        'skip ad', 'skip ads', 'skip', 'atla', 'geç',
        'reklam', 'close ad'
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
    if (findByText(['videoyu başlat', 'başlat', 'oynat', 'izle', 'play video', 'watch now'])) {
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


def decode_pichive_jwt_cdn(token):
    """pichive JWT → CDN domain URL."""
    parts = token.split(".")
    payload = parts[0] if len(parts) == 2 else (parts[1] if len(parts) >= 3 else None)
    if not payload:
        return None
    payload += "=" * (4 - len(payload) % 4)
    try:
        data = json.loads(base64.b64decode(payload).decode("utf-8")).get("data", {})
        raw_url = data.get("u", "")
        domains = data.get("domains", [])
        if domains and raw_url:
            d = domains[0]
            parsed = urlparse(raw_url)
            return f"https://{d['d_name']}/{d['d_url_prefix']}{parsed.path}"
    except Exception:
        pass
    return None


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


def is_cloudflare_blocked(html):
    lower = html.lower()
    return (
        "cloudflare" in lower
        or "attention required" in lower
        or "sorry, you have been blocked" in lower
        or (len(html) < 500 and ("just a moment" in lower or "challenge" in lower))
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


def get_embed_url_from_html(main_url, html):
    """Ana sayfa HTML'inden embed iframe URL'sini çıkar."""
    main_domain = main_url.split("/")[2]

    for url in re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I):
        url = fix_url(url, main_url)
        if main_domain in url:
            continue
        if any(s in url.lower() for s in SKIP_DOMAINS):
            continue
        if any(url.lower().endswith(e) for e in SKIP_EXT):
            continue
        log.info(f"  Embed URL (iframe): {url}")
        return url

    for pat in [
        r'(https?://[^"\'\s]+/(?:embed|iframe|player|v|vod|video)/[^"\'\s]+)',
        r'src=["\']([^"\']*(?:embed|iframe|player)[^"\']*)["\']',
    ]:
        for url in re.findall(pat, html, re.I):
            url = fix_url(url, main_url)
            if main_domain in url:
                continue
            if any(s in url.lower() for s in SKIP_DOMAINS):
                continue
            log.info(f"  Embed URL (pattern): {url}")
            return url

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


# ══════════════════════════════════════════════════════════════════════════════
#   YOUTUBE HANDLER
# ══════════════════════════════════════════════════════════════════════════════

def process_youtube(url, output_dir):
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
                    if result and result.get("found"):
                        ad_count += 1
                        await asyncio.sleep(2)  # Aksiyon sonrası bekle
                        break
                except Exception:
                    pass
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
                f"reklam_atlatma:{ad_count} frame:{frame_count}"
            )


# ══════════════════════════════════════════════════════════════════════════════
#   nodriver YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════════════

async def get_embed_url_browser(main_url):
    """nodriver ile sayfayı aç ve embed URL tespit et."""
    if not HAS_NODRIVER:
        log.warning("nodriver yüklü değil, browser ile embed arama atlanıyor")
        return None

    log.info("nodriver ile embed URL aranıyor...")
    main_domain = main_url.split("/")[2]
    browser = await uc.start(headless=False)
    tab = browser.main_tab
    embed_url = None
    all_urls = []

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
    await asyncio.sleep(8)

    if not embed_url and all_urls:
        log.debug("  Embed bulunamadı. Dış URL'ler:")
        for u in all_urls[:10]:
            log.debug(f"    {u[:100]}")

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

async def capture_general_playwright(film_url, embed_url=None):
    """
    Playwright ile genel stream yakalama.
    Pichive OLMAYAN siteler için — standart tarayıcı, reklam atlama, network intercept.
    """
    if not HAS_PLAYWRIGHT:
        log.warning("Playwright yüklü değil")
        return None, None

    found_streams = []
    cookie_file = None

    async with async_playwright() as p:
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
            if any(ext in url for ext in STREAM_EXT):
                if url not in found_streams:
                    found_streams.append(url)
                    log.info(f"  ✓ STREAM (network): {url}")

        page.on("request", on_request)

        # Sayfayı aç
        target_url = embed_url or film_url
        log.info(f"Sayfa açılıyor: {target_url[:100]}")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            log.info("  Sayfa yüklendi")
        except Exception as e:
            log.warning(f"  Sayfa yükleme hatası (devam ediliyor): {e}")

        # Eğer embed_url verilmişse, film sayfasında açmayı dene (iframe erişimi için)
        if embed_url and embed_url != film_url:
            try:
                page2 = await context.new_page()
                page2.on("request", on_request)
                page2.on("popup", lambda popup: asyncio.ensure_future(_close_popup(popup)))
                log.info(f"Film sayfası açılıyor: {film_url[:100]}")
                await page2.goto(film_url, wait_until="domcontentloaded", timeout=30000)
                # Ana sayfa sayfasını da izle
                await asyncio.sleep(3)
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
                    expiry = int(c.get("expires", 0)) if c.get("expires") else 0
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
        await browser.close()

    return found_streams[0] if found_streams else None, cookie_file


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
                    cdn = decode_pichive_jwt_cdn(token)
                    stream = decode_pichive_jwt(token)
                    target = cdn or stream
                    if target and target not in found_streams:
                        found_streams.append(target)
                        log.info(f"  ✓ STREAM (JWT decode): {target}")

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
                        if result and result.get("found"):
                            ad_count += 1
                            await asyncio.sleep(2)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

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

                # CF challenge
                log.info(f"  {pichive_host} root sayfasına gidiliyor (CF challenge)...")
                try:
                    await page2.goto(
                        f"https://{pichive_host}/",
                        wait_until="domcontentloaded",
                        timeout=20000,
                    )
                except Exception:
                    pass

                for i in range(30):
                    await asyncio.sleep(1)
                    try:
                        body = await page2.evaluate(
                            "() => document.body ? document.body.innerText.substring(0,80) : ''"
                        )
                        if (
                            body
                            and "blocked" not in body.lower()
                            and "challenge" not in page2.url
                        ):
                            break
                    except Exception:
                        pass

                # iframe.php'ye git
                await page2.set_extra_http_headers({"Referer": film_url})
                log.info(f"  iframe.php açılıyor: {embed_ref[:80]}")
                await page2.goto(embed_ref, wait_until="domcontentloaded", timeout=30000)

                elapsed2 = 0
                while elapsed2 < 120 and not master_php_url:
                    await asyncio.sleep(3)
                    elapsed2 += 3
                    if master_php_url:
                        log.info(f"  ✓ master.php yakalandı ({elapsed2}s)")
                        break
                    try:
                        for frame in page2.frames:
                            await run_ad_handler(frame, f"p2-{elapsed2}s")
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
                    expiry = int(c.get("expires", 0)) if c.get("expires") else 0
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

    return found_streams, master_m3u8_content, cookie_file, embed_ref


# ══════════════════════════════════════════════════════════════════════════════
#   İNDİRME
# ══════════════════════════════════════════════════════════════════════════════

def download_stream(stream_url, referer, title="video", cookie_file=None, output_dir="."):
    """Stream URL'sini en iyi kalitede indir."""
    os.makedirs(output_dir, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title or "video")
    out_path = os.path.join(output_dir, safe_title + ".%(ext)s")

    log.info(f"İndirme başlıyor: {safe_title}")
    log.info(f"  Stream: {stream_url[:100]}")

    # referer'dan origin çıkar
    try:
        ref_origin = f"https://{referer.split('/')[2]}"
    except Exception:
        ref_origin = referer

    cmd = [
        "yt-dlp",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--referer", referer,
        "--add-header", f"Origin:{ref_origin}",
        "--no-check-certificate",
        "--downloader", "native",
        "--concurrent-fragments", "4",
        "--no-warnings",
        "--newline",
        "-o", out_path,
    ]
    if cookie_file and os.path.exists(cookie_file):
        cmd += ["--cookies", cookie_file]
    cmd.append(stream_url)

    log.debug(f"  Komut: {' '.join(cmd[:8])}...")
    result = subprocess.run(cmd, encoding="utf-8", errors="replace")

    if result.returncode != 0:
        log.warning("  native downloader başarısız, ffmpeg deneniyor...")
        cmd2 = [c for c in cmd if c not in ["--downloader", "native"]]
        idx = None
        for ci, cv in enumerate(cmd2):
            if cv == "native" and ci > 0 and cmd2[ci - 1] == "--downloader":
                cmd2[ci] = "ffmpeg"
                break
        else:
            cmd2 += ["--downloader", "ffmpeg"]
        cmd2 += ["--hls-use-mpegts"]
        result = subprocess.run(cmd2, encoding="utf-8", errors="replace")

    if result.returncode == 0:
        log.info(f"  ✓ İndirme tamamlandı: {safe_title}")
    else:
        log.error(f"  ✗ İndirme hatası (kod: {result.returncode})")

    return result.returncode == 0


# ══════════════════════════════════════════════════════════════════════════════
#   TEK URL İŞLEME
# ══════════════════════════════════════════════════════════════════════════════

async def process_url(url, output_dir="."):
    """
    Tek bir URL işle: site tipi tespit → stream bul → indir.
    Tamamen otonom çalışır.
    """
    log.info(f"URL tipi algılanıyor: {url}")

    # ── YouTube ──
    if is_youtube(url):
        return process_youtube(url, output_dir)

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

    stream_url = None
    referer = url
    cookie_file = None

    # ── Adım 1: Net-export log (komut satırı argümanı) ──
    # (parse_args'da işlenir)

    # ── Adım 2: Embed URL tespiti ──
    log.info("Embed URL aranıyor...")
    embed_url = get_embed_url_from_html(url, main_html)

    if not embed_url:
        log.info("  HTML'den bulunamadı, tarayıcı ile aranıyor...")
        embed_url = await get_embed_url_browser(url)

    if embed_url:
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
                    stream_url = found[0]
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
    if not stream_url:
        log.info("Playwright ile doğrudan yakalama deneniyor...")
        stream_url, cookie_file = await capture_general_playwright(url, embed_url)

    # ── Adım 6: nodriver fallback ──
    if not stream_url:
        log.info("nodriver ile fallback deneniyor...")
        stream_url = await capture_stream_nodriver(url)

    # ── Sonuç ──
    if not stream_url:
        log.error("✗ Stream URL bulunamadı")
        log.info("Manuel yöntem:")
        log.info("  1. Chrome'da sayfayı aç, videoyu oynat")
        log.info("  2. chrome://net-export/ ile log al")
        log.info(f"  3. python videoflower.py --log LOG_DOSYASI {url}")
        return False

    log.info(f"✓ Stream URL bulundu: {stream_url}")
    get_stream_info(stream_url, referer)
    return download_stream(stream_url, referer, title, cookie_file, output_dir)


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
            success = await process_url(url, output_dir)
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


if __name__ == "__main__":
    asyncio.run(main())
