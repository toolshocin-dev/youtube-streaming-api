import os
import subprocess
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)


@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "youtube-streaming-api"
    })


@app.get("/info")
def info():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing url"}), 400

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--dump-single-json",
                "--skip-download",
                url
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return jsonify({"error": result.stderr[-2000:]}), 500

        return Response(result.stdout, mimetype="application/json")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing url"}), 400

    command = [
    "yt-dlp",
    "--no-playlist",
    "--no-part",
    "--extractor-args",
    "youtube:player_client=mweb",
    "-f",
        "best[ext=mp4]/best",
        "-o",
        "-",
        url
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=None,
        bufsize=0
    )

    def generate():
        try:
            while True:
                chunk = process.stdout.read(1024 * 256)

                if not chunk:
                    break

                yield chunk
        finally:
            if process.poll() is None:
                process.kill()

    response = Response(
        stream_with_context(generate()),
        mimetype="video/mp4"
    )

    response.headers["Content-Disposition"] = (
        'attachment; filename="youtube-video.mp4"'
    )

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
