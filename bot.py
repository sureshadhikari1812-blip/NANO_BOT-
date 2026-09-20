import os
import asyncio
import tempfile
import subprocess
import re
import json
import html as html_lib
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote, quote
from urllib.request import Request, urlopen

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = "NANO_BOT"
OWNER = "@Lightyagami_xx"

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".flac"}

# ===== NANO AI SUPER-RESOLUTION =====
MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_FILE = MODEL_DIR / "EDSR_x4.pb"
MODEL_URL = "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x4.pb"
_SR = None

def _load_sr():
    global _SR
    if cv2 is None:
        raise RuntimeError("Install opencv-contrib-python and numpy")
    if _SR is None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        if not MODEL_FILE.exists() or MODEL_FILE.stat().st_size < 5_000_000:
            req = Request(MODEL_URL, headers={"User-Agent": "NANO_BOT"})
            with urlopen(req, timeout=180) as r, open(MODEL_FILE, "wb") as f:
                while True:
                    b = r.read(1024 * 1024)
                    if not b:
                        break
                    f.write(b)
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(str(MODEL_FILE))
        sr.setModel("edsr", 4)
        _SR = sr
    return _SR

def ai_image(src, dst, fourk=False):
    if cv2 is None or np is None:
        raise RuntimeError("Install opencv-contrib-python and numpy")
    img = cv2.imread(src)
    if img is None:
        raise RuntimeError("Invalid image")
    out = _load_sr().upsample(img)
    if fourk:
        scale = min(3840/out.shape[1], 2160/out.shape[0])
        w, h = int(out.shape[1]*scale), int(out.shape[0]*scale)
        out = cv2.resize(out, (w, h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((2160, 3840, 3), dtype=np.uint8)
        x, y = (3840-w)//2, (2160-h)//2
        canvas[y:y+h, x:x+w] = out
        out = canvas
    elif max(out.shape[:2]) > 3840:
        scale = 3840/max(out.shape[:2])
        out = cv2.resize(out, (int(out.shape[1]*scale), int(out.shape[0]*scale)),
                         interpolation=cv2.INTER_AREA)
    cv2.imwrite(dst, out, [cv2.IMWRITE_JPEG_QUALITY, 96])

def ai_video(src, dst, fourk=False):
    if cv2 is None or np is None:
        raise RuntimeError("Install opencv-contrib-python and numpy")
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError("Could not open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ow, oh = W*4, H*4
    if fourk:
        scale = min(3840/ow, 2160/oh)
        ow, oh = int(ow*scale), int(oh*scale)
        canvas_mode = True
    else:
        scale = min(1, 3840/max(ow, oh))
        ow, oh = int(ow*scale), int(oh*scale)
        canvas_mode = False
    tmp = str(Path(dst).with_name("nano_ai_video.mp4"))
    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (ow, oh))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Could not create video")
    sr = _load_sr()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = sr.upsample(frame)
            frame = cv2.resize(frame, (ow, oh), interpolation=cv2.INTER_AREA)
            writer.write(frame)
    finally:
        cap.release()
        writer.release()
    run(["ffmpeg","-y","-i",tmp,"-i",src,"-map","0:v:0","-map","1:a?",
         "-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","192k","-movflags","+faststart",dst])
    Path(tmp).unlink(missing_ok=True)

ERROR = (
    "❌ <b>Could not process this URL.</b>\n\n"
    "Possible reasons:\n"
    "• URL is unavailable/private\n"
    "• Site is unsupported\n"
    "• Media is protected/login-required\n"
    "• Download or processing failed"
)

def is_url(text):
    try:
        p = urlparse(text.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def command_url(text):
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not is_url(parts[1]):
        return None
    return parts[1].strip()

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Media", callback_data="media"),
         InlineKeyboardButton("🖼️ Image", callback_data="image")],
        [InlineKeyboardButton("🎵 Audio", callback_data="audio"),
         InlineKeyboardButton("🤖 AI Enhance", callback_data="upscale")],
        [InlineKeyboardButton("💎 4K", callback_data="4k"),
         InlineKeyboardButton("🌐 Platforms", callback_data="platforms")],
        [InlineKeyboardButton("❓ Commands", callback_data="commands"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
    ])

def _safe_text(value, limit=900):
    value = "" if value is None else str(value)
    value = " ".join(value.split())
    if len(value) > limit:
        value = value[:limit - 3] + "..."
    return html_lib.escape(value)

def caption(info, mode):
    title = _safe_text(info.get("title") or "Unknown", 220)
    uploader = _safe_text(info.get("uploader") or info.get("channel") or "Unknown", 120)
    source = _safe_text(info.get("extractor_key") or info.get("extractor") or "Web", 80)
    description = _safe_text(
        info.get("description")
        or info.get("caption")
        or info.get("fulltitle")
        or "",
        1000
    )

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "        ⚡ <b>N A N O _ B O T</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"<blockquote>📦 <b>MEDIA INFO</b>\n\n"
        f"🎬 Type     : {mode}\n"
        f"📌 Title    : {title}\n"
        f"👤 Creator  : {uploader}\n"
        f"🌐 Source   : {source}"
    )

    # yt-dlp normally exposes Reel/Short/Post captions as `description`.
    # Include it when available, preserving line breaks in a compact form.
    if description:
        text += f"\n\n📝 <b>Caption / Description</b>\n{description}"

    text += "</blockquote>\n\n⚡ <b>NANO_BOT</b>\n👤 Owner: " + OWNER
    return text


def ytdlp(url, folder, mode):
    out = str(Path(folder) / "%(title).80s-%(id)s.%(ext)s")
    opts = {
        "outtmpl": out,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
    }
    if mode == "audio":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        opts.update({
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        })
    with yt_dlp.YoutubeDL(opts) as dl:
        info = dl.extract_info(url, download=True)
    files = [p for p in Path(folder).glob("*") if p.is_file()]
    allowed = VIDEO_EXT | IMAGE_EXT | AUDIO_EXT
    files = [p for p in files if p.suffix.lower() in allowed]
    if not files:
        raise FileNotFoundError("No media file")
    return str(max(files, key=lambda p: p.stat().st_size)), info

def _clean_url(value):
    """Clean URLs embedded in HTML/JSON."""
    value = html_lib.unescape(value)
    value = value.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    value = value.replace("\\u003A", ":").replace("\\u003a", ":")
    value = unquote(value)
    return value.strip().strip("\"'<>")

def direct_image(url, folder, referer=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer

    req = Request(url, headers=headers)
    with urlopen(req, timeout=30) as r:
        ct = (r.headers.get("Content-Type") or "").lower()
        final_url = r.geturl()
        data = r.read()

    # Some CDNs don't send a useful Content-Type. Detect common image signatures.
    if not ct.startswith("image/"):
        if data.startswith(b"\xff\xd8\xff"):
            ct = "image/jpeg"
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            ct = "image/png"
        elif data.startswith((b"GIF87a", b"GIF89a")):
            ct = "image/gif"
        elif data[:4] == b"RIFF" and b"WEBP" in data[:16]:
            ct = "image/webp"
        else:
            raise ValueError(f"Not a direct image: {ct or 'unknown content type'}")

    ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }.get(ct.split(";")[0], ".jpg")

    # Avoid overwriting another candidate.
    path = Path(folder) / ("image" + ext)
    if path.exists():
        path = Path(folder) / ("image_2" + ext)

    with open(path, "wb") as f:
        f.write(data)

    if path.stat().st_size < 512:
        path.unlink(missing_ok=True)
        raise ValueError("Downloaded image is empty or too small")

    return str(path), final_url

def pinterest_oembed_image(url, folder):
    """Use Pinterest's public oEmbed endpoint for a Pin thumbnail."""
    endpoint = (
        "https://www.pinterest.com/oembed.json?url="
        + quote(url, safe="")
    )
    req = Request(endpoint, headers={
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
    })
    with urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8", errors="ignore"))

    thumb = data.get("thumbnail_url")
    if not thumb:
        raise ValueError("Pinterest oEmbed returned no thumbnail")

    path, _ = direct_image(thumb, folder, referer=url)
    info = {
        "title": data.get("title") or "Pinterest Image",
        "uploader": data.get("author_name") or "Pinterest",
        "extractor_key": "Pinterest oEmbed",
    }
    return path, info

def _page_html(url):
    req = Request(url, headers={
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Mobile) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/139.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=30) as r:
        final_url = r.geturl()
        raw = r.read(8 * 1024 * 1024)
    return final_url, raw.decode("utf-8", errors="ignore")

def _image_candidates(html_text, base_url):
    s = html_lib.unescape(html_text)
    s = s.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")

    candidates = []

    # 1) Standard page metadata.
    meta_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
    ]
    for pattern in meta_patterns:
        for m in re.finditer(pattern, s, flags=re.I):
            candidates.append(_clean_url(urljoin(base_url, m.group(1))))

    # 2) Pinterest's CDN URLs embedded in page state / JSON.
    pin_patterns = [
        r'https?://i\.pinimg\.com/[^"\'<>\s\\]+',
        r'["\'](?:url|src)["\']\s*:\s*["\'](https?:\\?/\\?/i\.pinimg\.com/[^"\']+)',
    ]
    for pattern in pin_patterns:
        for m in re.finditer(pattern, s, flags=re.I):
            value = m.group(1) if m.lastindex else m.group(0)
            candidates.append(_clean_url(value))

    # 3) Common JSON fields for original/full-size images.
    json_patterns = [
        r'["\'](?:originals?|orig|original|image|image_url|imageUrl|src)["\']\s*:\s*["\'](https?[^"\']+)',
        r'"url"\s*:\s*"(https?[^"]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"]*)?)"',
    ]
    for pattern in json_patterns:
        for m in re.finditer(pattern, s, flags=re.I):
            candidates.append(_clean_url(m.group(1)))

    # 4) Generic image URLs in HTML/JSON.
    generic = r'https?://[^"\'<>\s\\]+?\.(?:jpg|jpeg|png|webp|gif)(?:\?[^"\'<>\s\\]*)?'
    for m in re.finditer(generic, s, flags=re.I):
        candidates.append(_clean_url(m.group(0)))

    # De-duplicate while preferring Pinterest originals/full-size paths.
    out = []
    seen = set()
    for c in candidates:
        if not c.startswith(("http://", "https://")):
            continue
        c = c.replace("&amp;", "&")
        if c in seen:
            continue
        seen.add(c)
        out.append(c)

    def score(u):
        low = u.lower()
        score = 0
        if "i.pinimg.com" in low:
            score += 100
        if "/originals/" in low:
            score += 80
        if "/736x/" in low:
            score += 60
        if "/564x/" in low:
            score += 50
        if "/474x/" in low:
            score += 40
        if "/236x/" in low:
            score += 10
        # Prefer normal raster images over tiny thumbnails.
        if any(x in low for x in ("sprite", "avatar", "profile", "logo", "favicon")):
            score -= 100
        return score

    return sorted(out, key=score, reverse=True)

def page_image(url, folder):
    """Extract and download a public webpage image; Pinterest gets special CDN parsing."""
    final_url, html_text = _page_html(url)
    candidates = _image_candidates(html_text, final_url)

    errors = []
    for image_url in candidates[:20]:
        try:
            path, _ = direct_image(image_url, folder, referer=final_url)
            return path
        except Exception as e:
            errors.append(str(e))

    raise ValueError("No downloadable page image found")

def ytdlp_thumbnail(url, folder):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 30,
    }
    with yt_dlp.YoutubeDL(opts) as dl:
        info = dl.extract_info(url, download=False)

    thumbs = info.get("thumbnails") or []
    thumb = info.get("thumbnail")
    if not thumb and thumbs:
        thumb = thumbs[-1].get("url")

    if not thumb:
        raise ValueError("No thumbnail found")

    path, _ = direct_image(thumb, folder, referer=url)
    return path, info

def image_from_url(url, folder):
    """Best-effort public image extraction with a dedicated Pinterest path."""
    # Direct image URL first.
    try:
        path, _ = direct_image(url, folder)
        return path, {"title": "Image", "uploader": "Unknown", "extractor_key": "Direct URL"}
    except Exception:
        pass

    # Pinterest's public oEmbed endpoint is the most reliable image fallback
    # for Pin URLs, including pin.it short links.
    host = (urlparse(url).hostname or "").lower()
    if host == "pin.it" or host.endswith(".pinterest.com"):
        try:
            return pinterest_oembed_image(url, folder)
        except Exception:
            pass

    # Generic public webpage image metadata.
    try:
        path = page_image(url, folder)
        return path, {"title": "Image", "uploader": "Unknown", "extractor_key": "Web Image"}
    except Exception:
        pass

    # Last fallback: yt-dlp thumbnail.
    path, info = ytdlp_thumbnail(url, folder)
    return path, info

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore")[-1500:])

def enhance_image(src, dst):
    try:
        ai_image(src, dst, False)
    except Exception as e:
        print("AI IMAGE FALLBACK:", repr(e))
        run(["ffmpeg","-y","-i",src,"-vf",
             "scale=iw*2:ih*2:flags=lanczos,unsharp=5:5:1.0",
             "-q:v","2",dst])

def enhance_video(src, dst):
    try:
        ai_video(src, dst, False)
    except Exception as e:
        print("AI VIDEO FALLBACK:", repr(e))
        run(["ffmpeg","-y","-i",src,"-vf",
             "scale=1920:1080:force_original_aspect_ratio=decrease,"
             "unsharp=5:5:1.0",
             "-c:v","libx264","-preset","medium","-crf","18",
             "-c:a","aac","-b:a","192k","-movflags","+faststart",dst])

def fourk_image(src, dst):
    try:
        ai_image(src, dst, True)
    except Exception as e:
        print("AI 4K IMAGE FALLBACK:", repr(e))
        run(["ffmpeg","-y","-i",src,"-vf",
             "scale=3840:2160:force_original_aspect_ratio=decrease,"
             "pad=3840:2160:(ow-iw)/2:(oh-ih)/2","-q:v","1",dst])

def fourk_video(src, dst):
    try:
        ai_video(src, dst, True)
    except Exception as e:
        print("AI 4K VIDEO FALLBACK:", repr(e))
        run(["ffmpeg","-y","-i",src,"-vf",
             "scale=3840:2160:force_original_aspect_ratio=decrease,"
             "pad=3840:2160:(ow-iw)/2:(oh-ih)/2",
             "-c:v","libx264","-preset","slow","-crf","18",
             "-c:a","aac","-b:a","256k","-movflags","+faststart",dst])

async def send_media(update, path, cap, kind):
    ext = Path(path).suffix.lower()
    with open(path, "rb") as f:
        if kind == "image":
            try:
                await update.message.reply_photo(f, caption=cap, parse_mode=ParseMode.HTML)
            except Exception:
                f.seek(0)
                await update.message.reply_document(f, caption=cap, parse_mode=ParseMode.HTML)
        elif kind == "audio":
            await update.message.reply_audio(f, caption=cap, parse_mode=ParseMode.HTML)
        elif ext in VIDEO_EXT:
            try:
                await update.message.reply_video(
                    f, caption=cap, parse_mode=ParseMode.HTML,
                    supports_streaming=True
                )
            except Exception:
                f.seek(0)
                await update.message.reply_document(f, caption=cap, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_document(f, caption=cap, parse_mode=ParseMode.HTML)

async def download_job(update, url, mode):
    status = await update.message.reply_text("🔎 Checking link...")
    try:
        with tempfile.TemporaryDirectory() as folder:
            await status.edit_text("📥 Downloading...")
            if mode == "image":
                path, info = await asyncio.to_thread(image_from_url, url, folder)
            else:
                path, info = await asyncio.to_thread(ytdlp, url, folder, mode)

            await status.edit_text("⬆️ Uploading...")
            await send_media(update, path, caption(info, mode.upper()), mode)
            await status.edit_text("✅ Completed.")
    except Exception as e:
        print("DOWNLOAD ERROR:", repr(e))
        await status.edit_text(ERROR, parse_mode=ParseMode.HTML)

async def start(update, context):
    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "        ⚡ <b>N A N O _ B O T</b>\n"
        "      MEDIA DOWNLOADER\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "Welcome! 👋\n\n"
        "Download publicly accessible media\n"
        "from supported platforms.\n\n"
        "╭─「 🌐 SUPPORTED PLATFORMS 」\n"
        "│ 🎬 YouTube   📸 Instagram\n"
        "│ 📘 Facebook  🎵 TikTok\n"
        "│ 🐦 X/Twitter 👽 Reddit\n"
        "│ 📌 Pinterest 🎧 SoundCloud\n"
        "╰────────────────────╯\n\n"
        "⚡ Fast • Clean • Simple"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=menu())

async def media_cmd(update, context):
    url = command_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ Usage: /media <URL>")
    await download_job(update, url, "media")

async def audio_cmd(update, context):
    url = command_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ Usage: /audio <URL>")
    await download_job(update, url, "audio")

async def image_cmd(update, context):
    url = command_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ Usage: /image <URL>")
    await download_job(update, url, "image")

async def upscale_cmd(update, context):
    url = command_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ Usage: /upscale <URL>")
    status = await update.message.reply_text("🤖 Enhancement starting...")
    try:
        with tempfile.TemporaryDirectory() as folder:
            try:
                src, info = await asyncio.to_thread(ytdlp, url, folder, "media")
            except Exception:
                # Image-page fallback: important for Pinterest image Pins.
                src, info = await asyncio.to_thread(image_from_url, url, folder)

            ext = Path(src).suffix.lower()
            await status.edit_text("✨ Enhancing...")
            if ext in IMAGE_EXT:
                out = str(Path(folder) / "NANO_ENHANCED.jpg")
                await asyncio.to_thread(enhance_image, src, out)
                kind = "image"
                mode = "ENHANCED IMAGE"
            else:
                out = str(Path(folder) / "NANO_ENHANCED.mp4")
                await asyncio.to_thread(enhance_video, src, out)
                kind = "media"
                mode = "ENHANCED VIDEO"
            await status.edit_text("⬆️ Uploading enhanced media...")
            await send_media(update, out, caption(info, mode), kind)
            await status.edit_text("✅ Enhancement completed.")
    except Exception as e:
        print("UPSCALE ERROR:", repr(e))
        await status.edit_text(ERROR, parse_mode=ParseMode.HTML)

async def fourk_cmd(update, context):
    url = command_url(update.message.text)
    if not url:
        return await update.message.reply_text("❌ Usage: /4k <URL>")
    status = await update.message.reply_text("💎 4K processing started...")
    try:
        with tempfile.TemporaryDirectory() as folder:
            try:
                src, info = await asyncio.to_thread(ytdlp, url, folder, "media")
            except Exception:
                # Image-page fallback: important for Pinterest image Pins.
                src, info = await asyncio.to_thread(image_from_url, url, folder)

            ext = Path(src).suffix.lower()
            await status.edit_text("💎 Creating 2160p output...")
            if ext in IMAGE_EXT:
                out = str(Path(folder) / "NANO_4K.jpg")
                await asyncio.to_thread(fourk_image, src, out)
                kind = "image"
                mode = "4K IMAGE"
            else:
                out = str(Path(folder) / "NANO_4K.mp4")
                await asyncio.to_thread(fourk_video, src, out)
                kind = "media"
                mode = "4K VIDEO"
            await status.edit_text("⬆️ Uploading 4K...")
            await send_media(update, out, caption(info, mode), kind)
            await status.edit_text("✅ 4K completed.")
    except Exception as e:
        print("4K ERROR:", repr(e))
        await status.edit_text(ERROR, parse_mode=ParseMode.HTML)

async def auto_url(update, context):
    text = update.message.text.strip()
    urls = [x for x in text.split() if is_url(x)]
    if not urls:
        return

    url = urls[0]

    # Pinterest image Pins are commonly image-only. Let the image extractor
    # handle them when a normal URL is pasted, instead of forcing video mode.
    host = (urlparse(url).hostname or "").lower()
    if host == "pin.it" or host.endswith(".pinterest.com"):
        try:
            with tempfile.TemporaryDirectory() as folder:
                path, info = await asyncio.to_thread(image_from_url, url, folder)
                await send_media(update, path, caption(info, "IMAGE"), "image")
                return
        except Exception as e:
            print("PINTEREST IMAGE ERROR:", repr(e))
            await update.message.reply_text(
                "❌ <b>Could not download this Pinterest image.</b>\n\n"
                "The Pin may be private, unavailable, or protected.",
                parse_mode=ParseMode.HTML
            )
            return

    await download_job(update, url, "media")

async def button(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "commands":
        text = (
            "📋 <b>COMMANDS</b>\n\n"
            "🎬 /media &lt;URL&gt; — highest available media\n"
            "🖼️ /image &lt;URL&gt; — image download\n"
            "🎵 /audio &lt;URL&gt; — MP3 extraction\n"
            "🤖 /upscale &lt;URL&gt; — enhancement\n"
            "💎 /4k &lt;URL&gt; — 2160p output\n"
            "🌐 /platforms — supported platforms\n"
            "❓ /help — commands"
        )
    elif q.data == "platforms":
        text = (
            "🌐 <b>SUPPORTED PLATFORMS</b>\n\n"
            "🎬 YouTube\n📸 Instagram\n📘 Facebook\n🎵 TikTok\n"
            "🐦 X/Twitter\n👽 Reddit\n📌 Pinterest\n🎧 SoundCloud\n\n"
            "Support depends on the site's current public access "
            "and yt-dlp support."
        )
    elif q.data == "about":
        text = (
            "ℹ️ <b>ABOUT NANO_BOT</b>\n\n"
            "Public-media downloader with quality, enhancement "
            "and 4K processing tools.\n\n"
            f"👤 Owner: {OWNER}"
        )
    else:
        text = "Use the command with a URL, for example:\n<code>/media https://...</code>"
    await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=menu())


def remove_watermark(src, dst, x, y, w, h):
    if cv2 is None or np is None:
        raise RuntimeError("Install opencv-contrib-python and numpy")
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError("Could not open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    x, y, w, h = max(0,int(x)), max(0,int(y)), int(w), int(h)
    if w < 4 or h < 4 or x+w > W or y+h > H:
        cap.release()
        raise ValueError("Watermark box is outside video")
    tmp = str(Path(dst).with_name("nano_wm.mp4"))
    writer = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W,H))
    ok, frame = cap.read()
    tracker = None
    if ok:
        if hasattr(cv2,"TrackerCSRT_create"):
            tracker = cv2.TrackerCSRT_create()
        elif hasattr(cv2,"legacy") and hasattr(cv2.legacy,"TrackerCSRT_create"):
            tracker = cv2.legacy.TrackerCSRT_create()
        if tracker:
            tracker.init(frame,(x,y,w,h))
    while ok:
        bx,by,bw,bh = x,y,w,h
        if tracker:
            good, box = tracker.update(frame)
            if good:
                bx,by,bw,bh = map(int,box)
        pad = max(2, int(min(bw,bh)*0.08))
        bx=max(0,bx-pad); by=max(0,by-pad)
        bw=min(W-bx,bw+2*pad); bh=min(H-by,bh+2*pad)
        mask=np.zeros((H,W),np.uint8)
        cv2.rectangle(mask,(bx,by),(bx+bw,by+bh),255,-1)
        writer.write(cv2.inpaint(frame,mask,3,cv2.INPAINT_TELEA))
        ok,frame=cap.read()
    cap.release(); writer.release()
    run(["ffmpeg","-y","-i",tmp,"-i",src,"-map","0:v:0","-map","1:a?",
         "-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
         "-c:a","aac","-b:a","192k","-movflags","+faststart",dst])
    Path(tmp).unlink(missing_ok=True)

async def watermark_cmd(update, context):
    parts = update.message.text.split()
    if len(parts) != 6:
        return await update.message.reply_text(
            "🧹 <b>Own/authorized video watermark remover</b>\n\n"
            "<code>/watermark URL x y w h</code>\n\n"
            "x y = top-left position, w h = box size (pixels).",
            parse_mode=ParseMode.HTML)
    url = parts[1]
    if not is_url(url):
        return await update.message.reply_text("❌ Invalid URL.")
    try:
        x,y,w,h=map(int,parts[2:6])
    except ValueError:
        return await update.message.reply_text("❌ x y w h must be numbers.")
    status=await update.message.reply_text("🧹 Downloading...")
    try:
        with tempfile.TemporaryDirectory() as folder:
            src,info=await asyncio.to_thread(ytdlp,url,folder,"media")
            out=str(Path(folder)/"NANO_WATERMARK_REMOVED.mp4")
            await status.edit_text("🧹 Tracking + cleaning watermark...")
            await asyncio.to_thread(remove_watermark,src,out,x,y,w,h)
            await status.edit_text("⬆️ Uploading...")
            await send_media(update,out,caption(info,"WATERMARK REMOVED"),"media")
            await status.edit_text("✅ Completed.")
    except Exception as e:
        print("WATERMARK ERROR:",repr(e))
        await status.edit_text(ERROR,parse_mode=ParseMode.HTML)


async def help_cmd(update, context):
    await update.message.reply_text(
        "📋 <b>Commands</b>\n\n"
        "🎬 /media &lt;URL&gt;\n"
        "🖼️ /image &lt;URL&gt;\n"
        "🎵 /audio &lt;URL&gt;\n"
        "🤖 /upscale &lt;URL&gt;\n"
        "💎 /4k &lt;URL&gt;\n"
        "🧹 /watermark URL x y w h\n"
        "🌐 /platforms\n"
        "❓ /help",
        parse_mode=ParseMode.HTML,
        reply_markup=menu()
    )

async def platforms_cmd(update, context):
    await update.message.reply_text(
        "🌐 <b>Platforms</b>\n\n"
        "🎬 YouTube\n📸 Instagram\n📘 Facebook\n🎵 TikTok\n"
        "🐦 X/Twitter\n👽 Reddit\n📌 Pinterest\n🎧 SoundCloud",
        parse_mode=ParseMode.HTML,
        reply_markup=menu()
    )

def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Put your BotFather token in BOT_TOKEN first.")

    print("🤖 NANO_BOT AI v9 is running...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("platforms", platforms_cmd))
    app.add_handler(CommandHandler("media", media_cmd))
    app.add_handler(CommandHandler("audio", audio_cmd))
    app.add_handler(CommandHandler("image", image_cmd))
    app.add_handler(CommandHandler("upscale", upscale_cmd))
    app.add_handler(CommandHandler("4k", fourk_cmd))
    app.add_handler(CommandHandler("watermark", watermark_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, auto_url)
    )

    app.run_polling()

if __name__ == "__main__":
    main()
