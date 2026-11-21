
from flask import Flask, request, jsonify, send_file
from yt_dlp import YoutubeDL
import tempfile
import os
import shutil
import threading
from urllib.parse import urlparse

app = Flask(__name__)

ALLOWED_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "fb.watch"
}

def valid_url(url):
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        return (
            p.scheme == "https"
            and host in ALLOWED_HOSTS
        )
    except Exception:
        return False

@app.get("/")
def home():
    return "FDown backend is running!"

@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not valid_url(url):
        return jsonify(error="সঠিক Facebook লিংক দিন।"), 400

    folder = tempfile.mkdtemp()

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(folder, "video.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "max_filesize": 80 * 1024 * 1024,
    }

    try:
        with YoutubeDL(options) as ydl:
            ydl.download([url])

        files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
        ]

        if not files:
            shutil.rmtree(folder, ignore_errors=True)
            return jsonify(error="ভিডিও পাওয়া যায়নি।"), 404

        response = send_file(
            files[0],
            as_attachment=True,
            download_name="FDown_video.mp4"
        )

        response.call_on_close(
            lambda: shutil.rmtree(folder, ignore_errors=True)
        )
        return response

    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        return jsonify(
            error="ভিডিও ডাউনলোড করা যায়নি। ভিডিওটি public কি না পরীক্ষা করো।"
        ), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
