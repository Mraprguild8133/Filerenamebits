import os
import time
import math
import mimetypes
from PIL import Image
from pyrogram.types import Message
import ffmpeg


# Get media from message
def get_media_from_message(message: Message):
    media_types = ("audio", "document", "photo", "sticker", "animation", "video", "voice", "video_note")
    for attr in media_types:
        if hasattr(message, attr):
            return getattr(message, attr)


# Get media info (thumbnail, duration, etc.)
def get_media_info(path):
    info = {
        "thumbnail": None,
        "duration": 0,
        "width": 0,
        "height": 0,
        "artist": None,
        "title": None
    }
    try:
        metadata = ffmpeg.probe(path)["format"]
        if "tags" in metadata:
            if "artist" in metadata["tags"]:
                info["artist"] = metadata["tags"]["artist"]
            if "title" in metadata["tags"]:
                info["title"] = metadata["tags"]["title"]

        video_stream = next((s for s in ffmpeg.probe(path)["streams"] if s["codec_type"] == "video"), None)
        if video_stream:
            info["duration"] = int(float(video_stream["duration"]))
            info["width"] = int(video_stream["width"])
            info["height"] = int(video_stream["height"])
            
            # Generate thumbnail
            thumb_path = f"thumbnails/{os.path.basename(path)}.jpg"
            ffmpeg.input(path, ss=info["duration"] / 2).filter('scale', 320, -1).output(thumb_path, vframes=1).run(overwrite_output=True)
            info["thumbnail"] = thumb_path
    except:
        pass
    return info

# Convert bytes to a human-readable format
def humanbytes(size):
    if not size:
        return ""
    power = 2 ** 10
    n = 0
    Dic_powerN = {0: " ", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + "B"

# Format time
def get_time(seconds):
    seconds = int(seconds/1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f'{hours}h {minutes}m {seconds}s'
    elif minutes > 0:
        return f'{minutes}m {seconds}s'
    else:
        return f'{seconds}s'
