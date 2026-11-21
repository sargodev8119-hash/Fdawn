
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse
import subprocess
import tempfile
import os
import glob
import shutil
import json

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

ALLOWED_ORIGIN = "https://sargodev8119-hash.github.io"

CORS(app, resources={
    r"/*": {
        "origins": [ALLOWED_ORIGIN],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Facebook URL validation
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


# Run yt-dlp
def run_ytdlp(args, timeout=180):
    return subprocess.run(
        ["python", "-m", "yt_dlp"] + args,
        capture_output=True,
        text=True,
        timeout=timeout
    )


@app.get("/")
def home():
    return "FDown server is running!"


# VIDEO INFO API
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
            return jsonify({
                "error": "ভিডিওর তথ্য পাওয়া যায়নি। ভিডিওটি পাবলিক কিনা পরীক্ষা করো।"
            }), 400

        info = json.loads(result.stdout)

        formats = info.get("formats") or []
        heights = sorted({
            f.get("height")
            for f in formats
            if f.get("height") and f.get("vcodec") != "none"
        })

        fps_values = sorted({
            round(f.get("fps"))
            for f in formats
            if f.get("fps") and f.get("vcodec") != "none"
        })

        return jsonify({
            "title": info.get("title") or "Facebook Video",
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "qualities": heights,
            "fps_options": fps_values
        })

    except subprocess.TimeoutExpired:
        return jsonify({"error": "ভিডিও তথ্য পেতে সময় বেশি লাগছে"}), 408

    except Exception:
        return jsonify({"error": "সার্ভারে সমস্যা হয়েছে"}), 500


# VIDEO DOWNLOAD API
@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    # User choices
    quality = str(data.get("quality", "best")).strip().lower()
    fps = str(data.get("fps", "original")).strip().lower()

    if not url:
        return jsonify({"error": "ভিডিও লিংক দাও"}), 400

    if not is_valid_facebook_url(url):
        return jsonify({"error": "সঠিক Facebook ভিডিও লিংক দাও"}), 400

    # Allowed quality values
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
        return jsonify({"error": "সঠিক ভিডিও Quality নির্বাচন করো"}), 400

    if fps not in ("original", "24", "30", "50", "60"):
        return jsonify({"error": "সঠিক FPS নির্বাচন করো"}), 400

    max_height = allowed_qualities[quality]

    # Build format filters
    height_filter = ""
    if max_height:
        height_filter = f"[height<={max_height}]"

    fps_filter = ""
    if fps != "original":
        fps_filter = f"[fps<={fps}]"

    # H.264 preference for playback compatibility
    video_filter = height_filter + fps_filter

    if video_filter:
        video_format = (
            f"bestvideo[vcodec^=avc1]{video_filter}"
            f"/bestvideo{video_filter}"
        )
        combined_format = f"best{height_filter}{fps_filter}"
        format_selector = f"{video_format}+bestaudio/{combined_format}"
    else:
        format_selector = (
            "bestvideo[vcodec^=avc1]+bestaudio"
            "/bestvideo+bestaudio/best"
        )

    temp_dir = tempfile.mkdtemp(prefix="fdown_")
    output_template = os.path.join(temp_dir, "video.%(ext)s")

    command = [
        "--no-playlist",
        "--no-warnings",
        "--socket-timeout", "30",
        "--retries", "2",
        "--fragment-retries", "2",
        "--max-filesize", "100M",
        "-f", format_selector,
        "--merge-output-format", "mp4",
        "--postprocessor-args", "ffmpeg:-movflags +faststart",
        "-o", output_template,
        url
    ]

    try:
        result = run_ytdlp(command, timeout=240)

        files = glob.glob(os.path.join(temp_dir, "video.*"))
        files = [
            f for f in files
            if os.path.isfile(f) and not f.endswith(".part")
        ]

        if result.returncode != 0 or not files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({
                "error": "ডাউনলোড ব্যর্থ। ভিডিওটি পাবলিক কিনা বা FFmpeg ইনস্টল আছে কিনা পরীক্ষা করো।"
            }), 400

        video_path = files[0]

        response = send_file(
            video_path,
            as_attachment=True,
            download_name="FDown_video.mp4",
            mimetype="video/mp4"
        )

        response.call_on_close(
            lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )

        return response

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "ডাউনলোডে বেশি সময় লাগছে। আবার চেষ্টা করো।"}), 408

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "সার্ভারে সমস্যা হয়েছে"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
