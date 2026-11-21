
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from urllib.parse import urlparse
import subprocess
import tempfile
import os
import glob
import shutil

app = Flask(__name__)

CORS(app, resources={
    r"/download": {
        "origins": ["https://sargodev8119-hash.github.io"]
    }
})

@app.get("/")
def home():
    return "FDown server is running!"

@app.post("/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "ভিডিও লিংক দাও"}), 400

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    # Facebook domain check
    allowed = (
        host == "facebook.com"
        or host.endswith(".facebook.com")
        or host == "fb.watch"
        or host.endswith(".fb.watch")
    )

    if parsed.scheme not in ("http", "https") or not allowed:
        return jsonify({"error": "শুধু Facebook ভিডিও লিংক দাও"}), 400

    temp_dir = tempfile.mkdtemp(prefix="fdown_")
    output_template = os.path.join(temp_dir, "video.%(ext)s")

    try:
        command = [
            "python", "-m", "yt_dlp",
            "--no-playlist",
            "--no-warnings",
            "--socket-timeout", "30",
            "--retries", "1",
            "--fragment-retries", "1",
            "--max-filesize", "100M",
            "-f", "best[ext=mp4]/best",
            "-o", output_template,
            url
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180
        )

        files = glob.glob(os.path.join(temp_dir, "video.*"))

        if result.returncode != 0 or not files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify({
                "error": "ভিডিও ডাউনলোড করা যায়নি। ভিডিওটি পাবলিক কিনা পরীক্ষা করো।"
            }), 400

        video_path = files[0]

        response = send_file(
            video_path,
            as_attachment=True,
            download_name="video.mp4"
        )

        response.call_on_close(
            lambda: shutil.rmtree(temp_dir, ignore_errors=True)
        )

        return response

    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "ডাউনলোড করতে সময় বেশি লাগছে"}), 408

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({"error": "সার্ভারে সমস্যা হয়েছে"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
