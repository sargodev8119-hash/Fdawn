from flask import Flask, request, jsonify, Response
import requests
from urllib.parse import urlparse
import ipaddress
import socket

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
        return jsonify({"error": "সঠিক URL দাও"}), 400

    host = parsed.hostname.lower()

    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        return jsonify({"error": "এই URL অনুমোদিত নয়"}), 400

    try:
        addresses = socket.getaddrinfo(host, None)
        for addr in addresses:
            ip = ipaddress.ip_address(addr[4][0])
            if not ip.is_global:
                return jsonify({"error": "এই ঠিকানা অনুমোদিত নয়"}), 400
    except Exception:
        return jsonify({"error": "হোস্ট যাচাই করা যায়নি"}), 400

    try:
        r = requests.get(
            url,
            stream=True,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=False
        )

        if r.status_code != 200:
            r.close()
            return jsonify({"error": "ভিডিও পাওয়া যায়নি"}), 400

        content_type = r.headers.get("Content-Type", "")

        if not content_type.startswith("video/"):
            r.close()
            return jsonify({"error": "এটি সরাসরি ভিডিও ফাইলের লিংক নয়"}), 400

        return Response(
            r.iter_content(chunk_size=8192),
            headers={
                "Content-Type": content_type,
                "Content-Disposition": 'attachment; filename="video.mp4"'
            }
        )

    except requests.RequestException:
        return jsonify({"error": "ভিডিও ডাউনলোড করা যায়নি"}), 400

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
