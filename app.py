
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

# Maximum upload size: 50 MB
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

@app.get("/")
def home():
    return "FDown server is running!"

@app.post("/download")
def download():
    if "video" not in request.files:
        return jsonify({"error": "ভিডিও ফাইল নির্বাচন করো"}), 400

    video = request.files["video"]

    if not video.filename:
        return jsonify({"error": "ফাইলের নাম নেই"}), 400

    filename = secure_filename(video.filename)

    allowed = {".mp4", ".mov", ".webm"}
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed:
        return jsonify({"error": "অনুমোদিত ভিডিও ফাইল নয়"}), 400

    return send_file(
        video,
        as_attachment=True,
        download_name=filename
    )

@app.errorhandler(413)
def too_large(error):
    return jsonify({"error": "ফাইল ৫০ MB-এর বেশি"}), 413

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
