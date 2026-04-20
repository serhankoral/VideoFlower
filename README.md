# VideoFlower

Otonom video indirme aracı. Film ve dizi sitelerindeki videoları otomatik olarak bulur, reklamları atlar ve en iyi kalitede indirir.

## Özellikler

- **YouTube** — tek video ve playlist indirme
- **Çoklu Türk site desteği** — hdfilmcehennemi, hdfilmizle, dizi54, jetfilmizle, izleplus, zeusdizi, dizibox ve genel siteler
- **Otonom reklam atlama** — "Reklamı Geç", "Skip Ad", overlay reklamlar otomatik kapatılır
- **Otomatik video başlatma** — JWPlayer, Video.js ve HTML5 player API desteği
- **Cloudflare bypass** — persistent Chrome profili ile CF korumalı sitelere erişim
- **HLS indirme** — uzantısız/özel segment içeren stream'ler için Python tabanlı HLS downloader
- **Pop-up engelleme** — yeni sekme açan reklamlar otomatik kapatılır
- **Türkçe log** — konsol ve dosyaya detaylı kayıt

## Kurulum

### Gereksinimler

- Python 3.10+
- Google Chrome (sisteme kurulu)
- ffmpeg

### 1. Bağımlılıkları kur

```bash
pip install -r requirements.txt
```

### 2. Playwright Chromium kur

```bash
playwright install chromium
```

### 3. yt-dlp ve ffmpeg kur

Windows:
```bash
winget install yt-dlp
winget install Gyan.FFmpeg
```

Linux/macOS:
```bash
pip install yt-dlp
# ffmpeg: sudo apt install ffmpeg  /  brew install ffmpeg
```

## Kullanım

### Tek video

```bash
python videoflower.py https://www.youtube.com/watch?v=XXXX
```

### Birden fazla URL

```bash
python videoflower.py url1 url2 url3
```

### YouTube playlist

```bash
python videoflower.py "https://www.youtube.com/playlist?list=XXXX"
```

### Çıktı dizini belirt

```bash
python videoflower.py -o filmler https://site.com/film
```

### Detaylı log

```bash
python videoflower.py -v https://site.com/film
```

### Tüm test URL'lerini çalıştır

```bash
python videoflower.py --test
```

### Test + ilk N saniyeyi indir (hızlı test)

```bash
python videoflower.py --test --snippet 30
```

### Net-export log ile (Chrome network log dosyası)

```bash
python videoflower.py --log chrome_net.json https://site.com/film
```

## Seçenekler

| Parametre | Açıklama |
|-----------|----------|
| `URL [URL ...]` | İndirilecek bir veya birden fazla URL |
| `-o, --output DIR` | Çıktı dizini (varsayılan: `indirilenler/`) |
| `-v, --verbose` | Detaylı debug logu |
| `--log DOSYA` | Chrome net-export JSON log dosyası |
| `--test` | Varsayılan test URL listesini çalıştır |
| `--snippet N` | Test modunda her videodan ilk N saniyeyi indir |

## Desteklenen Siteler

| Site | Tür | Yöntem |
|------|-----|--------|
| youtube.com / youtu.be | Video / Playlist | yt-dlp |
| hdfilmcehennemi.llc / .nl | Film / Dizi | Playwright + JWT decode |
| hdfilmizle.so | Film | HTML decode + Python HLS |
| dizi54.life | Dizi | Playwright + Python HLS |
| jetfilmizle.net | Dizi | Playwright |
| izleplus.com | Film | Playwright + Python HLS |
| zeusdizi31.com | Film | Playwright |
| dizibox.live | Dizi | Playwright + nodriver |
| Genel siteler | Otomatik | Playwright + nodriver fallback |

## Nasıl Çalışır

```
URL geldi
  │
  ├─ YouTube? → yt-dlp ile direkt indir
  │
  └─ Film/Dizi sitesi?
       │
       ├─ HTML'den embed URL çıkar
       │
       ├─ Playwright ile sayfayı aç
       │    ├─ Ağ trafiğini izle (.m3u8, .mp4, .mpd)
       │    ├─ Her 3s: reklam atla, player API tetikle
       │    └─ Stream URL yakalandı mı?
       │
       ├─ Evet → Özel CDN? → Python HLS ile indir
       │                   → yt-dlp ile indir
       │
       └─ Hayır → nodriver (undetected Chrome) ile tekrar dene
```

### Reklam Atlama Sistemi

1. **ADIM 0** — "Baştan başla / Start over" diyalogları (izleme geçmişi)
2. **ADIM 1** — Reklam atlama butonları: "Reklamı Geç", "Skip Ad", "Atla"
3. **ADIM 2** — Overlay/pop-up kapatma (yüksek z-index katmanlar)
4. **ADIM 3** — "Videoyu Başlat / Oynat" butonları
5. **ADIM 4** — Player API: `jwplayer().play()`, `videojs().play()`, HTML5 autoplay
6. **ADIM 5** — CSS selector fallback: `.jw-icon-display`, `.vjs-big-play-button`

## Proje Yapısı

```
videoflower.py      — Ana script (~2800 satır)
requirements.txt    — Python bağımlılıkları
LICENSE             — MIT Lisans
indirilenler/       — İndirilen videolar (otomatik oluşturulur)
videoflower.log     — Log dosyası (otomatik oluşturulur)
_chrome_profile/    — Cloudflare bypass için kalıcı Chrome profili
```

## Gereksinimler (Detaylı)

```
requests>=2.31.0
urllib3>=2.0.0
playwright>=1.40.0
nodriver>=0.38
```

## Lisans

MIT License — detaylar için [LICENSE](LICENSE) dosyasına bakın.
