import os, io, time, uuid, re, socket, ipaddress, json, subprocess, shutil, tempfile
from urllib.parse import urlparse
import requests
from flask import Flask, request, jsonify, Response, abort, send_file
from yt_dlp import YoutubeDL
from PIL import Image

app = Flask(__name__, static_folder="static", static_url_path="")
CACHE = {}
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"
PHOTO_EXT = ("jpg", "jpeg", "png", "webp")


def host_ok(url):
    # Semua situs boleh, kecuali alamat lokal/jaringan privat (keamanan server).
    h = urlparse(url).hostname
    if not h:
        return False
    try:
        for fam, _, _, _, addr in socket.getaddrinfo(h, None):
            ip = ipaddress.ip_address(addr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
    except Exception:
        return False
    return True


def from_direct(url):  # tautan langsung ke gambar / video
    r = requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=20)
    ct = r.headers.get("content-type", "").split(";")[0]
    r.close()
    if ct.startswith("image/"):
        kind = "photo"
    elif ct.startswith("video/") or ct.startswith("audio/"):
        kind = "video"
    else:
        raise ValueError("Situs ini tidak punya media yang bisa diambil")
    name = urlparse(url).path.rsplit("/", 1)[-1] or "media"
    ext = name.rsplit(".", 1)[-1] if "." in name else None
    return {"title": name, "items": [item(1, kind, url, ext=ext)]}


def put(**data):
    now = time.time()
    for k in [k for k, v in CACHE.items() if now - v["ts"] > 3600]:
        old = CACHE.pop(k, {})
        if old.get("path"):
            try:
                os.remove(old["path"])
            except OSError:
                pass
    t = uuid.uuid4().hex
    CACHE[t] = {"ts": now, **data}
    return t


def item(n, kind, url, headers=None, ext=None):
    ext = ext or ("jpg" if kind == "photo" else "mp4")
    t = put(url=url, headers=headers or {"User-Agent": UA}, name=f"kae-{n}.{ext}")
    return {"kind": kind, "src": f"/api/file/{t}", "dl": f"/api/file/{t}?dl=1", "token": t}


def from_ytdlp(url):
    opts = {"quiet": True, "noplaylist": True, "skip_download": True,
            "format": "best[ext=mp4]/best"}
    if os.path.exists("cookies.txt"):  # opsional, untuk Instagram / konten login
        opts["cookiefile"] = "cookies.txt"
    if shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
    with YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
    entries = info.get("entries") or [info]
    items = []
    for i, e in enumerate(entries, 1):
        if not e or not e.get("url"):
            continue
        ext = e.get("ext") or "mp4"
        kind = "photo" if ext in PHOTO_EXT else "video"
        items.append(item(i, kind, e["url"], e.get("http_headers"), ext))
    if not items:
        raise ValueError("Media tidak ditemukan")
    return {"title": info.get("title") or "Tanpa judul", "items": items}


DL_DIR = os.path.join(tempfile.gettempdir(), "kae_dl")


def from_youtube(url):
    """MP4 kualitas lebih tinggi: unduh video+audio lalu gabung dengan ffmpeg."""
    if not shutil.which("ffmpeg"):
        return from_ytdlp(url)  # tanpa ffmpeg: hanya format progresif
    os.makedirs(DL_DIR, exist_ok=True)
    h = int(os.environ.get("YT_MAX_HEIGHT", "720"))
    uid = uuid.uuid4().hex
    opts = {"quiet": True, "noplaylist": True, "merge_output_format": "mp4",
            "outtmpl": os.path.join(DL_DIR, uid + ".%(ext)s"),
            "format": f"bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}][ext=mp4]/b[height<={h}]/b"}
    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"
    if shutil.which("node"):
        opts["js_runtimes"] = {"node": {}}
    with YoutubeDL(opts) as y:
        info = y.extract_info(url, download=True)
    path = os.path.join(DL_DIR, uid + ".mp4")
    if not os.path.exists(path):
        found = [f for f in os.listdir(DL_DIR) if f.startswith(uid)]
        if not found:
            raise ValueError("Gagal menyiapkan video")
        path = os.path.join(DL_DIR, found[0])
    t = put(path=path, name="kae-youtube.mp4")
    return {"title": info.get("title") or "YouTube",
            "items": [{"kind": "video", "src": f"/api/local/{t}", "dl": f"/api/local/{t}?dl=1"}]}


@app.get("/api/local/<t>")
def local_file(t):
    c = CACHE.get(t)
    if not c or "path" not in c:
        abort(404)
    return send_file(c["path"], mimetype="video/mp4", conditional=True,
                     as_attachment=bool(request.args.get("dl")), download_name=c["name"])


def from_scrapr(url):  # butuh Node.js + `npm install` di folder scrapr/
    here = os.path.dirname(os.path.abspath(__file__))
    p = subprocess.run(["node", "scrapr_bridge.js", url], cwd=here,
                       capture_output=True, text=True, timeout=90)
    d = json.loads(p.stdout or "{}")
    if not d.get("status"):
        raise ValueError(d.get("message") or p.stderr[-120:] or "scrapr gagal")
    r = d["result"]
    items = [item(i, it["kind"], it["url"]) for i, it in enumerate(r["items"], 1)]
    return {"title": r.get("title") or "Tanpa judul", "items": items}


def resolve(url):
    host = (urlparse(url).hostname or "").lower()
    if "spotify.com" in host:
        return from_spotify(url)
    if "youtube.com" in host or "youtu.be" in host:
        chain = [from_youtube]
    elif "tiktok" in host or host == "tt.site":
        chain = [from_scrapr, from_ytdlp, from_tikwm]
    else:
        chain = [from_scrapr, from_ytdlp, from_direct]
    err = None
    for f in chain:
        try:
            return f(url)
        except Exception as e:
            err = e
    raise err


def from_tikwm(url):  # cadangan untuk slideshow foto TikTok
    d = requests.get("https://www.tikwm.com/api/", params={"url": url, "hd": 1},
                     timeout=25).json().get("data")
    if not d:
        raise ValueError("Konten TikTok tidak ditemukan")
    if d.get("images"):
        items = [item(i, "photo", u) for i, u in enumerate(d["images"], 1)]
    else:
        items = [item(1, "video", d.get("hdplay") or d["play"])]
    return {"title": d.get("title") or "TikTok", "items": items}


def from_spotify(url):
    # Audio Spotify dilindungi DRM, jadi hanya sampul + judul.
    d = requests.get("https://open.spotify.com/oembed", params={"url": url}, timeout=15).json()
    cover = d.get("thumbnail_url")
    if not cover:
        raise ValueError("Tautan Spotify tidak valid")
    return {"title": d.get("title", "Spotify"), "items": [item(1, "photo", cover)],
            "note": "Audio Spotify dilindungi DRM, jadi hanya sampul yang bisa diunduh."}


@app.post("/api/analyze")
def analyze():
    url = ((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not re.match(r"^https?://", url) or not host_ok(url):
        return jsonify(error="Tautan tidak valid. Tempel alamat lengkap yang diawali http:// atau https://"), 400
    try:
        res = resolve(url)
    except Exception as e:
        return jsonify(error=f"Gagal mengambil konten: {str(e)[:160]}"), 400
    photos = [i["token"] for i in res["items"] if i["kind"] == "photo"]
    if len(photos) > 1:
        res["pdf"] = f"/api/pdf/{put(group=photos)}"
    for i in res["items"]:
        i.pop("token", None)
    return jsonify(res)


@app.get("/api/file/<t>")
def file(t):
    c = CACHE.get(t)
    if not c or "url" not in c:
        abort(404)
    h = dict(c["headers"])
    if request.headers.get("Range"):
        h["Range"] = request.headers["Range"]
    r = requests.get(c["url"], headers=h, stream=True, timeout=30)
    keep = ("content-type", "content-length", "content-range", "accept-ranges")
    out = {k: v for k, v in r.headers.items() if k.lower() in keep}
    if request.args.get("dl"):
        out["Content-Disposition"] = f'attachment; filename="{c["name"]}"'
    return Response(r.iter_content(65536), status=r.status_code, headers=out)


@app.get("/api/pdf/<t>")
def pdf(t):
    c = CACHE.get(t)
    if not c or "group" not in c:
        abort(404)
    pages = []
    for tok in c["group"]:
        f = CACHE[tok]
        img = Image.open(io.BytesIO(requests.get(f["url"], headers=f["headers"], timeout=30).content))
        pages.append(img.convert("RGB"))
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])
    return Response(buf.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="kae-galeri.pdf"'})


@app.get("/")
def home():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
