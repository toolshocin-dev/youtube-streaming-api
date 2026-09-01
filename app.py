import os
import shutil
import subprocess
import tempfile

from flask import Flask, request, jsonify, Response, send_file


app = Flask(__name__)


YT_PROXY = os.environ.get("YT_PROXY", "").strip()

POT_SERVER = (
    "https://cobalt-pot-provider.onrender.com"
)


def youtube_base_args():
    return [
        "yt-dlp",
        "--no-playlist",

        "--extractor-args",
        "youtube:player_client=mweb",

        "--remote-components",
        "ejs:github",

        "--extractor-args",
        f"youtubepot-bgutilhttp:base_url={POT_SERVER}",
    ]


def is_youtube_block(error_text):
    text = (error_text or "").lower()

    block_messages = [
        "http error 429",
        "http error 403",
        "too many requests",
        "sign in to confirm",
        "not a bot",
        "confirm you’re not a bot",
        "confirm you're not a bot",
    ]

    return any(
        message in text
        for message in block_messages
    )


def run_command(command, timeout):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout
    )

    if result.stdout:
        print(result.stdout, flush=True)

    if result.stderr:
        print(result.stderr, flush=True)

    return result


@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "service": "youtube-streaming-api",
        "proxy_fallback": bool(YT_PROXY)
    })


@app.get("/info")
def info():
    url = request.args.get(
        "url",
        ""
    ).strip()

    if not url:
        return jsonify({
            "error": "Missing url"
        }), 400

    direct_command = [
        *youtube_base_args(),

        "--dump-single-json",
        "--skip-download",

        url
    ]

    try:
        # FIRST: try YouTube directly.
        result = run_command(
            direct_command,
            60
        )

        # ONLY retry through IPRoyal if
        # YouTube actually blocked Render.
        if (
            result.returncode != 0
            and is_youtube_block(result.stderr)
            and YT_PROXY
        ):
            print(
                "[proxy-fallback] "
                "Direct YouTube request blocked. "
                "Retrying metadata through YT_PROXY.",
                flush=True
            )

            proxy_command = [
                *youtube_base_args(),

                "--proxy",
                YT_PROXY,

                "--dump-single-json",
                "--skip-download",

                url
            ]

            result = run_command(
                proxy_command,
                60
            )

        if result.returncode != 0:
            return jsonify({
                "error":
                    result.stderr[-2000:]
                    if result.stderr
                    else "yt-dlp metadata request failed."
            }), 500

        return Response(
            result.stdout,
            mimetype="application/json"
        )

    except subprocess.TimeoutExpired:
        return jsonify({
            "error": "Metadata request timed out."
        }), 504

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


@app.get("/download")
def download():
    url = request.args.get(
        "url",
        ""
    ).strip()

    if not url:
        return jsonify({
            "error": "Missing url"
        }), 400

    temp_dir = tempfile.mkdtemp(
        prefix="youtube_"
    )

    output_template = os.path.join(
        temp_dir,
        "youtube-video.%(ext)s"
    )

    def make_download_command(proxy=None):
        command = [
            *youtube_base_args(),

            "--no-part",

            "--downloader",
            "native",

            "-f",
            "best[ext=mp4]/best",

            "--merge-output-format",
            "mp4",

            "-o",
            output_template,
        ]

        if proxy:
            command.extend([
                "--proxy",
                proxy
            ])

        command.append(url)

        return command

    try:
        # FIRST:
        # Try the download without IPRoyal.
        print(
            "[download] Trying direct YouTube connection.",
            flush=True
        )

        result = run_command(
            make_download_command(),
            540
        )

        # If a partial file was created during
        # the failed direct attempt, remove it.
        if (
            result.returncode != 0
            and is_youtube_block(result.stderr)
            and YT_PROXY
        ):
            print(
                "[proxy-fallback] "
                "YouTube blocked direct Render connection. "
                "Retrying through YT_PROXY.",
                flush=True
            )

            for filename in os.listdir(
                temp_dir
            ):
                file_path = os.path.join(
                    temp_dir,
                    filename
                )

                try:
                    os.remove(file_path)
                except OSError:
                    pass

            # SECOND:
            # Only now use IPRoyal.
            result = run_command(
                make_download_command(
                    proxy=YT_PROXY
                ),
                540
            )

        if result.returncode != 0:
            error_message = (
                result.stderr[-3000:]
                if result.stderr
                else
                "yt-dlp download failed."
            )

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error": error_message
            }), 500

        files = os.listdir(
            temp_dir
        )

        video_files = [
            filename
            for filename in files
            if filename
            .lower()
            .endswith(".mp4")
        ]

        if not video_files:
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error":
                    "yt-dlp finished but "
                    "no MP4 file was created."
            }), 500

        video_path = os.path.join(
            temp_dir,
            video_files[0]
        )

        if (
            not os.path.exists(video_path)
            or os.path.getsize(
                video_path
            ) == 0
        ):
            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )

            return jsonify({
                "error":
                    "Downloaded video file is empty."
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
            "error":
                "Video download timed out."
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
