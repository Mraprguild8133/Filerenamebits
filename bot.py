import os
import re
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import MessageNotModified, AuthBytesInvalid, FloodWait

# ✅ TgCrypto is used automatically if installed alongside Pyrogram
# Install with: pip install -U pyrogram tgcrypto

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Env
load_dotenv()
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 5000))

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Missing API_ID / API_HASH / BOT_TOKEN")
    exit(1)

# Globals
user_data = {}
transfer_stats = {
    "total_downloaded": 0,
    "total_uploaded": 0,
    "max_download_speed": 0,
    "max_upload_speed": 0,
    "transfers_completed": 0,
}
bot_start_time = time.time()
last_update_time = {}


# Helpers
def humanbytes(size: int) -> str:
    if not size or size == 0:
        return "0B"
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size >= power and n < len(units) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {units[n]}"


def create_progress_bar(percent: float, length: int = 20) -> str:
    filled = min(int(length * percent / 100), length)
    return "█" * filled + "░" * (length - filled)


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)


async def update_progress(current, total, message, start_time, action, user_id):
    """Throttled progress updates"""
    try:
        now = time.time()
        if user_id in last_update_time and now - last_update_time[user_id] < 1:
            return
        last_update_time[user_id] = now

        elapsed = now - start_time
        speed = current / elapsed if elapsed > 0 else 0
        percent = (current / total) * 100 if total > 0 else 0
        eta = (total - current) / speed if speed > 0 and total > current else 0

        if action == "Downloading":
            transfer_stats["max_download_speed"] = max(transfer_stats["max_download_speed"], speed)
        else:
            transfer_stats["max_upload_speed"] = max(transfer_stats["max_upload_speed"], speed)

        progress_text = (
            f"🚀 **{action}** 🚀\n\n"
            f"`{create_progress_bar(percent)}` **{percent:.1f}%**\n\n"
            f"⚡ Speed: `{humanbytes(speed)}/s`\n"
            f"📦 Progress: `{humanbytes(current)}` / `{humanbytes(total)}`\n"
            f"⏱️ ETA: `{time.strftime('%M:%S', time.gmtime(eta)) if eta > 0 else '00:00'}`\n"
            f"🕒 Elapsed: `{time.strftime('%M:%S', time.gmtime(elapsed))}`"
        )
        try:
            await message.edit_text(progress_text)
        except MessageNotModified:
            pass
    except Exception as e:
        logger.error(f"Progress error: {e}")


async def safe_send(func, *args, **kwargs):
    """Retry on FloodWait"""
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await safe_send(func, *args, **kwargs)


# Pyrogram client
app = Client(
    "bot_session",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=20
)


# Handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(_, msg):
    uid = msg.from_user.id
    uptime = time.time() - bot_start_time
    await msg.reply_text(
        f"⚡ **POWER SPEED BOT** ⚡\n\n"
        f"✅ Status: Online\n"
        f"🕒 Uptime: `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"🌐 Port: `{PORT}`\n\n"
        f"**Features:**\n"
        f"• Lightning transfers\n"
        f"• Real-time speed\n"
        f"• File renaming\n"
        f"• Video thumbnails\n\n"
        f"Send me a file!"
    )
    if uid in user_data:
        del user_data[uid]


@app.on_message(filters.command(["status", "stats"]) & filters.private)
async def stats_handler(_, msg):
    uptime = time.time() - bot_start_time
    await msg.reply_text(
        f"📊 **BOT STATUS** 📊\n\n"
        f"🕒 Uptime: `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"👥 Active Users: `{len(user_data)}`\n"
        f"📤 Completed: `{transfer_stats['transfers_completed']}`\n\n"
        f"⬇️ Downloaded: `{humanbytes(transfer_stats['total_downloaded'])}`\n"
        f"⬆️ Uploaded: `{humanbytes(transfer_stats['total_uploaded'])}`\n"
        f"⚡ Max DL Speed: `{humanbytes(transfer_stats['max_download_speed'])}/s`\n"
        f"🚀 Max UL Speed: `{humanbytes(transfer_stats['max_upload_speed'])}/s`"
    )


@app.on_message(filters.command("ping") & filters.private)
async def ping_handler(_, msg):
    start = time.time()
    pong = await msg.reply_text("🏓 Pinging...")
    delay = (time.time() - start) * 1000
    await pong.edit_text(
        f"🏓 **PONG!**\n⏱️ {delay:.2f} ms\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(_, msg):
    uid = msg.from_user.id
    file = msg.video or msg.document or msg.audio
    if not file:
        return
    user_data[uid] = {
        "user_id": uid,
        "message_id": msg.id,
        "chat_id": msg.chat.id,
        "file_type": "video" if msg.video else "document",
        "file_size": file.file_size,
        "file_name": getattr(file, "file_name", "file"),
        "timestamp": time.time(),
    }
    buttons = [[InlineKeyboardButton("⚡ Rename", callback_data="rename")]]
    if msg.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])
    await msg.reply_text(
        f"📁 **File Received** 📁\n\n"
        f"Name: `{file.file_name}`\n"
        f"Size: `{humanbytes(file.file_size)}`\n"
        f"Type: {'Video' if msg.video else 'File'}\n\n"
        f"Choose action:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query()
async def cb_handler(_, cq):
    uid = cq.from_user.id
    if uid not in user_data:
        await cq.answer("❌ Session expired. Send file again.", show_alert=True)
        return
    if cq.data == "rename":
        user_data[uid]["action"] = "rename"
        await cq.message.edit_text("✍️ Send new filename with extension:\nExample: `movie.mp4`")
    elif cq.data == "set_thumbnail":
        user_data[uid]["action"] = "thumbnail"
        await cq.message.edit_text("🖼️ Send photo for thumbnail.")
    await cq.answer()


@app.on_message(filters.photo & filters.private)
async def thumb_handler(_, msg):
    uid = msg.from_user.id
    if uid in user_data and user_data[uid].get("action") == "thumbnail":
        thumb_path = await msg.download()
        user_data[uid]["thumbnail"] = thumb_path
        del user_data[uid]["action"]
        await msg.reply_text("✅ Thumbnail saved.")


@app.on_message(filters.text & filters.private)
async def text_handler(_, msg):
    uid = msg.from_user.id
    if uid not in user_data or user_data[uid].get("action") != "rename":
        return
    new_name = safe_filename(msg.text.strip())
    if not new_name:
        await msg.reply_text("❌ Invalid filename")
        return

    # Kick off background processing
    asyncio.create_task(handle_file_processing(app, msg, user_data[uid], new_name))
    del user_data[uid]


# File processing function
async def handle_file_processing(app, message, user_info, new_filename):
    status_msg = None
    file_path = None
    try:
        status_msg = await message.reply_text("🚀 **Starting transfer...**")
        start_time = time.time()

        # Download
        original_msg = await app.get_messages(user_info["chat_id"], user_info["message_id"])
        if not original_msg:
            await status_msg.edit_text("❌ Original file not found.")
            return

        base_dir = "downloads"
        os.makedirs(base_dir, exist_ok=True)
        download_dir = os.path.join(base_dir, f"{user_info['user_id']}_{int(time.time())}")
        os.makedirs(download_dir, exist_ok=True)
        download_path = os.path.join(download_dir, safe_filename(user_info["file_name"]))

        file_path = await app.download_media(
            message=original_msg,
            file_name=download_path,
            progress=lambda cur, tot: asyncio.create_task(
                update_progress(cur, tot, status_msg, start_time, "Downloading", user_info["user_id"])
            )
        )
        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Download failed.")
            return

        transfer_stats["total_downloaded"] += user_info["file_size"]

        # Upload
        if user_info["file_type"] == "video":
            await safe_send(
                app.send_video,
                chat_id=user_info["user_id"],
                video=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                thumb=user_info.get("thumbnail"),
                progress=lambda cur, tot: asyncio.create_task(
                    update_progress(cur, tot, status_msg, start_time, "Uploading", user_info["user_id"])
                )
            )
        else:
            await safe_send(
                app.send_document,
                chat_id=user_info["user_id"],
                document=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                progress=lambda cur, tot: asyncio.create_task(
                    update_progress(cur, tot, status_msg, start_time, "Uploading", user_info["user_id"])
                )
            )

        transfer_stats["total_uploaded"] += user_info["file_size"]
        transfer_stats["transfers_completed"] += 1

        total_time = time.time() - start_time
        avg_speed = user_info["file_size"] / total_time if total_time > 0 else 0

        await status_msg.edit_text(
            f"✅ **Transfer Complete!** ✅\n\n"
            f"📁 File: `{new_filename}`\n"
            f"⚡ Avg Speed: `{humanbytes(avg_speed)}/s`\n"
            f"⏱️ Total Time: `{time.strftime('%M:%S', time.gmtime(total_time))}`\n"
            f"📦 Size: `{humanbytes(user_info['file_size'])}`"
        )
    except AuthBytesInvalid:
        logger.error("Auth bytes invalid")
        if status_msg:
            await status_msg.edit_text("🔁 **Session expired. Restart bot.**")
    except Exception as e:
        logger.error(f"Processing error: {e}")
        if status_msg:
            await status_msg.edit_text("❌ Error during processing.")
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                d = os.path.dirname(file_path)
                if os.path.exists(d) and not os.listdir(d):
                    os.rmdir(d)
            except:
                pass


# Run bot
if __name__ == "__main__":
    try:
        logger.info("🚀 Starting bot...")
        app.run()  # ✅ No asyncio.run(), avoids loop error
    except KeyboardInterrupt:
        print("🛑 Bot stopped by user")
    
