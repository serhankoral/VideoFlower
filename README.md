# VideoFlower 🌸

**Otonom Video İndirme Aracı v1.0**

Film, dizi ve YouTube videolarını otomatik olarak bulup en iyi kalitede indiren araç.

## Özellikler

- 🎬 **YouTube desteği** — Tek video + playlist (sıralı indirme)
- 🛡️ **Otomatik reklam atlama** — "Reklamı Geç", "Skip", "Atla" gibi butonları otomatik tıklar
- 🎮 **Otomatik video başlatma** — JWPlayer, Video.js ve HTML5 player desteği
- 🔒 **Cloudflare bypass** — Persistent Chrome profili ile CF korumalı sitelere erişim
- 📺 **Çoklu site desteği** — hdfilmcehennemi, hdfilmizle, dizi54, jetfilmizle, izleplus, dizibox ve daha fazlası
- 🚫 **Pop-up engelleme** — Overlay reklamlar ve gereksiz sekmeler otomatik kapatılır
- 📝 **Detaylı Türkçe log** — Konsol + dosya loglama
- 🎯 **En iyi kalite** — bestvideo+bestaudio formatında indirme

## Kurulum

### Gereksinimler

- Python 3.10+
- Google Chrome (Playwright Chromium veya sistem Chrome)
- yt-dlp (komut satırı)
- ffmpeg (birleştirme için)

### Python bağımlılıkları

```bash
pip install -r requirements.txt
```

### Playwright kurulumu

```bash
playwright install chromium
```

### yt-dlp ve ffmpeg

```bash
pip install yt-dlp
# veya
winget install yt-dlp
winget install ffmpeg
```

## Kullanım

### Tek video indirme

```bash
python videoflower.py https://www.youtube.com/watch?v=XXXX
```

### Birden fazla URL

```bash
python videoflower.py url1 url2 url3
```

### YouTube playlist

```bash
python videoflower.py "https://www.youtube.com/watch?v=XXXX&list=PLAYLIST_ID"
```

### Çıktı dizini belirtme

```bash
python videoflower.py -o filmler https://site.com/film
```

### Net-export log ile

```bash
python videoflower.py --log chrome_net.json https://site.com/film
```

### Detaylı log

```bash
python videoflower.py -v url1
```

## Desteklenen Siteler

| Site | Tür | Yöntem |
|------|-----|--------|
| YouTube | Video/Playlist | yt-dlp direkt |
| hdfilmcehennemi.llc/.nl | Film/Dizi | Playwright + JWT decode |
| hdfilmizle.so | Film | HTML decode + Playwright |
| dizi54.life | Dizi | Playwright |
| jetfilmizle.net | Dizi | Playwright |
| izleplus.com | Film | Playwright |
| zeusdizi31.com | Film | Playwright |
| dizibox.live | Dizi | Playwright |
| pichive.online embed | Player | CF bypass + JWT |
| Genel siteler | Otomatik | Playwright + nodriver fallback |

## Reklam Atlama Sistemi

VideoFlower, metin tabanlı (text-based) reklam tespiti kullanır:

1. **Reklam atlama butonları**: "Reklamı Geç", "Skip Ad", "Atla", "Close Ad"
2. **Pop-up/overlay kapatma**: Yüksek z-index'li katmanlar tespit edilip kapatılır
3. **Post-reklam butonları**: "Videoyu Başlat", "Oynat", "İzle"
4. **Player API**: JWPlayer, Video.js, HTML5 video otomatik oynatma
5. **CSS fallback**: Bilinen player butonları için selector tabanlı tıklama

## Proje Yapısı

```
videoflower.py      — Ana script
requirements.txt    — Python bağımlılıkları
README.md           — Bu dosya
LICENSE             — MIT Lisans
indirilenler/       — İndirilen videolar (otomatik oluşturulur)
videoflower.log     — Log dosyası (otomatik oluşturulur)
```

## Lisans

MIT License — detaylar için [LICENSE](LICENSE) dosyasına bakın.

## Yazar

VideoFlower v1.0 — 2025
