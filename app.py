import os
import shutil
import subprocess
import tempfile

from flask import Flask, request, jsonify, Response, send_file


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
                "--extractor-args",
                "youtube:player_client=mweb",
                "--remote-components",
                "ejs:github",
                "--extractor-args",
                "youtubepot-bgutilhttp:base_url=https://cobalt-pot-provider.onrender.com",
                url
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            return jsonify({
                "error": result.stderr[-2000:]
            }), 500

        return Response(
            result.stdout,
            mimetype="application/json"
        )

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()

    if not url:
        return jsonify({"error": "Missing url"}), 400

    temp_dir = tempfile.mkdtemp(
        prefix="youtube_"
    )

    output_template = os.path.join(
        temp_dir,
        "youtube-video.%(ext)s"
    )

    command = [
        "yt-dlp",

        "--no-playlist",

        "--no-part",

        "--extractor-args",
        "youtube:player_client=mweb",

        "--remote-components",
        "ejs:github",

        "--extractor-args",
        "youtubepot-bgutilhttp:base_url=https://cobalt-pot-provider.onrender.com",

        "--downloader",
        "native",

        "-f",
        (
            "bestvideo[height<=1080][ext=mp4]"
            "+bestaudio[ext=m4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/best[height<=1080][ext=mp4]"
            "/best[height<=1080]"
        ),

        "--merge-output-format",
        "mp4",

        "-o",
        output_template,

        url
    ]

    try:
        result = subprocess.run(
            command,
            stdout=None,
            stderr=None,
            text=True,
            timeout=540
        )

        if result.returncode != 0:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error": "yt-dlp download failed. Check Render logs for details."
            }), 500

        files = os.listdir(temp_dir)

        video_files = [
            filename
            for filename in files
            if filename.lower().endswith(".mp4")
        ]

        if not video_files:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error": "yt-dlp finished but no MP4 file was created."
            }), 500

        video_path = os.path.join(
            temp_dir,
            video_files[0]
        )

        if os.path.getsize(video_path) == 0:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error": "Downloaded video file is empty."
            }), 500

        response = send_file(
            video_path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name="youtube-video.mp4"
        )

        response.call_on_close(
            lambda: shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )
        )

        return response

    except subprocess.TimeoutExpired:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return jsonify({
            "error": "Video download timed out."
        }), 504

    except Exception as e:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True
        )

        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
