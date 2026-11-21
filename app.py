from flask import Flask, request, jsonify
from urllib.parse import urlparse
import ipaddress

app = Flask(__name__)

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

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return jsonify({"error": "সঠিক ভিডিও URL দাও"}), 400

    host = parsed.hostname.lower()

    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        return jsonify({"error": "এই হোস্ট অনুমোদিত নয়"}), 400

    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            return jsonify({"error": "এই IP অনুমোদিত নয়"}), 400
    except ValueError:
        pass

    ext = parsed.path.lower()
    if not ext.endswith((".mp4", ".webm", ".mov")):
        return jsonify({
            "error": "সরাসরি MP4, WEBM বা MOV ভিডিও লিংক ব্যবহার করো"
        }), 400

    # Return the validated direct link.
    return jsonify({"download_url": url})

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
