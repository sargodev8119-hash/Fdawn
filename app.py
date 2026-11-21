
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse
import subprocess
import tempfile
import os
import glob
import shutil
import json
import logging

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

logging.basicConfig(level=logging.INFO)

ALLOWED_ORIGIN = "https://sargodev8119-hash.github.io"

CORS(app, resources={
    r"/*": {
        "origins": [ALLOWED_ORIGIN],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})


# ==============================
# FACEBOOK URL VALIDATION
# ==============================

def is_valid_facebook_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        allowed = (
            host == "facebook.com"
            or host.endswith(".facebook.com")
            or host == "fb.watch"
            or host.endswith(".fb.watch")
        )

        return parsed.scheme in ("http", "https") and allowed

    except Exception:
        return False


# ==============================
# RUN YT-DLP
# ==============================

def run_ytdlp(args, timeout=180):
    return subprocess.run(
        ["python", "-m", "yt_dlp"] + args,
        capture_output=True,
        text=True,
        timeout=timeout
    )


# ==============================
# HOME
# ==============================

@app.get("/")
def home():
    return "FDown server is running!"


# ==============================
# VIDEO INFO API
# ==============================

@app.post("/info")
def video_info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "ভিডিও লিংক দাও"}), 400

    if not is_valid_facebook_url(url):
        return jsonify({"error": "সঠিক Facebook ভিডিও লিংক দাও"}), 400

    try:
        result = run_ytdlp([
            "--no-playlist",
            "--no-warnings",
            "--skip-download",
            "--dump-single-json",
            "--socket-timeout", "25",
            "--retries", "1",
            url
        ], timeout=60)

        if result.returncode != 0:
            logging.error("INFO yt-dlp error: %s", result.stderr[-1500:])

            return jsonify({
                "error": "ভিডিওর তথ্য পাওয়া যায়নি। ভিডিওটি পাবলিক কিনা পরীক্ষা করো।"
            }), 400

        info = json.loads(result.stdout)

        formats = info.get("formats") or []

        heights = sorted({
            int(f["height"])
            for f in formats
            if f.get("height")
            and f.get("vcodec") != "none"
        }, reverse=True)

        fps_values = sorted({
            int(round(f["fps"]))
            for f in formats
            if f.get("fps")
            and f.get("vcodec") != "none"
        }, reverse=True)

        return jsonify({
            "title": info.get("title") or "Facebook Video",
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "qualities": heights,
            "fps_options": fps_values
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "ভিডিও তথ্য পেতে সময় বেশি লাগছে"
        }), 408

    except Exception:
        logging.exception("Video info error")

        return jsonify({
            "error": "সার্ভারে সমস্যা হয়েছে"
        }), 500


# ==============================
# VIDEO DOWNLOAD API
# ==============================

@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}

    url = (data.get("url") or "").strip()
    quality = str(data.get("quality", "best")).strip().lower()
    fps = str(data.get("fps", "original")).strip().lower()

    if not url:
        return jsonify({"error": "ভিডিও লিংক দাও"}), 400

    if not is_valid_facebook_url(url):
        return jsonify({"error": "সঠিক Facebook ভিডিও লিংক দাও"}), 400


    # ==============================
    # QUALITY SETTINGS
    # ==============================

    allowed_qualities = {
        "best": None,
        "144": 144,
        "240": 240,
        "360": 360,
        "480": 480,
        "720": 720,
        "1080": 1080,
        "1440": 1440
    }

    if quality not in allowed_qualities:
        return jsonify({
            "error": "সঠিক ভিডিও Quality নির্বাচন করো"
        }), 400

    if fps not in ("original", "24", "30", "50", "60"):
        return jsonify({
            "error": "সঠিক FPS নির্বাচন করো"
        }), 400


    max_height = allowed_qualities[quality]


    # ==============================
    # BUILD VIDEO FILTERS
    # ==============================

    filters = ""

    if max_height:
        filters += f"[height<={max_height}]"

    if fps != "original":
        filters += f"[fps<={fps}]"


    # ==============================
    # VIDEO + AUDIO FORMAT
    # ==============================

    # প্রথমে H.264 ভিডিও নেওয়ার চেষ্টা করবে
    # এরপর অন্য ভিডিও codec fallback হিসেবে নেবে
    # অডিও আলাদাভাবে নিয়ে FFmpeg দিয়ে merge করবে

    if filters:
        format_selector = (
            f"bestvideo[vcodec^=avc1]{filters}+bestaudio/"
            f"bestvideo{filters}+bestaudio/"
            f"best{filters}"
        )
    else:
        format_selector = (
            "bestvideo[vcodec^=avc1]+bestaudio/"
            "bestvideo+bestaudio/"
            "best"
        )


    # ==============================
    # TEMPORARY DIRECTORY
    # ==============================

    temp_dir = tempfile.mkdtemp(prefix="fdown_")

    output_template = os.path.join(
        temp_dir,
        "video.%(ext)s"
    )


    # ==============================
    # YT-DLP COMMAND
    # ==============================

    command = [
        "--no-playlist",
        "--no-warnings",
        "--socket-timeout", "30",
        "--retries", "3",
        "--fragment-retries", "3",
        "--max-filesize", "100M",

        "-f", format_selector,

        # ভিডিও ও অডিও Merge করে MP4 তৈরি
        "--merge-output-format", "mp4",

        # MP4 দ্রুত চালু হওয়ার জন্য
        "--postprocessor-args", "ffmpeg:-movflags +faststart",

        "-o", output_template,
        url
    ]


    # ==============================
    # DOWNLOAD
    # ==============================

    try:
        result = run_ytdlp(command, timeout=240)

        # তৈরি হওয়া ফাইল খুঁজবে
        files = glob.glob(
            os.path.join(temp_dir, "video.*")
        )

        files = [
            f for f in files
            if os.path.isfile(f)
            and not f.endswith(".part")
            and not f.endswith(".ytdl")
        ]

        if result.returncode != 0 or not files:

            logging.error(
                "DOWNLOAD yt-dlp error: %s",
                result.stderr[-2500:]
            )

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error": (
                    "ডাউনলোড ব্যর্থ। ভিডিওটি পাবলিক কিনা, "
                    "FFmpeg ইনস্টল আছে কিনা এবং ভিডিওর "
                    "Quality/FPS উপলব্ধ কিনা পরীক্ষা করো।"
                )
            }), 400


        # MP4 ফাইল খুঁজে অগ্রাধিকার
        mp4_files = [
            f for f in files
            if f.lower().endswith(".mp4")
        ]

        video_path = mp4_files[0] if mp4_files else files[0]


        # ==============================
        # SEND FILE
        # ==============================

        response = send_file(
            video_path,
            as_attachment=True,
            download_name="FDown_video.mp4",
            mimetype="video/mp4"
        )

        # Download শেষ হলে temporary files মুছে ফেলবে
        response.call_on_close(
            lambda: shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )
        )

        return response


    # ==============================
    # ERROR HANDLING
    # ==============================

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "error": "ডাউনলোডে বেশি সময় লাগছে। আবার চেষ্টা করো।"
        }), 408

    except Exception:
        logging.exception("Download error")

        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            "error": "সার্ভারে সমস্যা হয়েছে"
        }), 500


# ==============================
# START SERVER
# ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port
    )
