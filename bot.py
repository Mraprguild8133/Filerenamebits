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

# -----------------------
# Config & logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "5000"))

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Missing API_ID / API_HASH / BOT_TOKEN in environment")
    raise SystemExit("Missing env vars")

# -----------------------
# Globals
# -----------------------
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

# -----------------------
# Helpers
# -----------------------
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

def safe_filename(name: str) -> str:
    if not name:
        return "file"
    return re.sub(r'[<>:"/\\|?*]', "_", name).strip()

def create_progress_bar(percent: float, length: int = 20) -> str:
    filled = min(int(length * percent / 100), length)
    return "█" * filled + "░" * (length - filled)

async def update_progress(current, total, message, start_time, action, user_id):
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

        text = (
            f"🚀 **{action}** 🚀\n\n"
            f"`{create_progress_bar(percent)}` **{percent:.1f}%**\n\n"
            f"⚡ Speed: `{humanbytes(speed)}/s`\n"
            f"📦 Progress: `{humanbytes(current)}` / `{humanbytes(total)}`\n"
            f"⏱️ ETA: `{time.strftime('%M:%S', time.gmtime(eta)) if eta > 0 else '00:00'}`\n"
            f"🕒 Elapsed: `{time.strftime('%M:%S', time.gmtime(elapsed))}`"
        )

        try:
            await message.edit_text(text)
        except MessageNotModified:
            pass
    except Exception as e:
        logger.exception("Progress update failed")

async def safe_send(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        logger.warning(f"FloodWait: sleeping for {e.value}s")
        await asyncio.sleep(e.value)
        return await safe_send(func, *args, **kwargs)

# -----------------------
# File processing
# -----------------------
async def handle_file_processing(app, trigger_message, user_info, new_filename):
    """
    - app: Client instance
    - trigger_message: message that triggered the processing (used to reply/status)
    - user_info: dict saved previously with message ids, file info, etc.
    - new_filename: sanitized filename string for upload
    """
    status_msg = None
    file_path = None
    try:
        status_msg = await trigger_message.reply_text("🚀 **Starting transfer...**")
        start_time = time.time()

        # --- fetch original message ---
        try:
            original_msg = await app.get_messages(user_info["chat_id"], user_info["message_id"])
        except Exception as e:
            original_msg = None
            logger.exception("get_messages failed")

        if not original_msg:
            await status_msg.edit_text("❌ Original file not found (may be deleted or expired).")
            logger.error("Original message not found for user_info=%s", user_info)
            return

        # --- check that original_msg actually contains media ---
        media = original_msg.video or original_msg.document or original_msg.audio
        if not media:
            await status_msg.edit_text("❌ No downloadable media found in the original message.")
            logger.error("No media in original message: %s", original_msg)
            return

        if getattr(media, "file_id", None) is None:
            await status_msg.edit_text("❌ Media has no file_id; cannot download.")
            logger.error("Media has no file_id: %s", media)
            return

        # --- prepare download path ---
        base_dir = "downloads"
        os.makedirs(base_dir, exist_ok=True)
        download_dir = os.path.join(base_dir, f"{user_info['user_id']}_{int(time.time())}")
        os.makedirs(download_dir, exist_ok=True)

        safe_name = safe_filename(user_info.get("file_name") or media.file_name or "file")
        download_path = os.path.join(download_dir, safe_name)

        if not isinstance(download_path, str) or download_path.strip() == "":
            await status_msg.edit_text("❌ Invalid download path.")
            logger.error("Invalid download path: %r", download_path)
            return

        logger.info("⬇️ Downloading media to %s", download_path)

        # --- download ---
        file_path = await app.download_media(
            message=original_msg,
            file_name=download_path,
            progress=lambda cur, tot: asyncio.create_task(
                update_progress(cur, tot, status_msg, start_time, "Downloading", user_info["user_id"])
            )
        )

        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Download failed (file not saved).")
            logger.error("download_media returned invalid path: %r", file_path)
            return

        logger.info("✅ Download finished: %s", file_path)
        transfer_stats["total_downloaded"] += int(user_info.get("file_size", 0) or 0)

        # --- validate thumbnail if present ---
        thumb_path = user_info.get("thumbnail")
        if thumb_path:
            if not isinstance(thumb_path, str) or not os.path.exists(thumb_path):
                logger.warning("Thumbnail invalid or missing, ignoring thumb: %s", thumb_path)
                thumb_path = None

        # --- upload back to user with new filename ---
        logger.info("⬆️ Uploading to user %s as %s (type=%s)", user_info["user_id"], new_filename, user_info["file_type"])
        if user_info.get("file_type") == "video":
            await safe_send(
                app.send_video,
                chat_id=user_info["user_id"],
                video=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                thumb=thumb_path,
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

        transfer_stats["total_uploaded"] += int(user_info.get("file_size", 0) or 0)
        transfer_stats["transfers_completed"] += 1

        total_time = time.time() - start_time
        avg_speed = (user_info.get("file_size") or 0) / total_time if total_time > 0 else 0

        await status_msg.edit_text(
            f"✅ **Transfer Complete!** ✅\n\n"
            f"📁 **File:** `{new_filename}`\n"
            f"⚡ **Average Speed:** `{humanbytes(avg_speed)}/s`\n"
            f"⏱️ **Total Time:** `{time.strftime('%M:%S', time.gmtime(total_time))}`\n"
            f"📦 **Size:** `{humanbytes(user_info.get('file_size', 0))}`"
        )

    except AuthBytesInvalid:
        logger.exception("AuthBytesInvalid - session issue")
        if status_msg:
            await status_msg.edit_text("🔁 **Session expired. Please restart the bot.**")
    except Exception as exc:
        logger.exception("❌ File processing error")
        if status_msg:
            # show a short error to user, log full stack
            await status_msg.edit_text("❌ Error during processing. Check bot logs for details.")
    finally:
        # cleanup downloaded file and thumbnail if it was downloaded by bot (not the user's original)
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                # remove parent dir if empty
                parent = os.path.dirname(file_path)
                if os.path.exists(parent) and not os.listdir(parent):
                    os.rmdir(parent)
        except Exception as cleanup_err:
            logger.warning("Cleanup error: %s", cleanup_err)

# -----------------------
# Bot (client & handlers)
# -----------------------
app = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, workers=20)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    uptime = time.time() - bot_start_time
    await message.reply_text(
        f"⚡ **POWER SPEED BOT** ⚡\n\n"
        f"✅ **Status:** Online\n"
        f"🕒 **Uptime:** `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"🌐 **Port:** `{PORT}`\n\n"
        f"Send any file to rename and transfer with speed tracking!",
        quote=True
    )
    user_data.pop(message.from_user.id, None)

@app.on_message(filters.command(["status", "stats"]) & filters.private)
async def stats_handler(client, message):
    uptime = time.time() - bot_start_time
    await message.reply_text(
        f"📊 **BOT STATUS** 📊\n\n"
        f"🕒 **Uptime:** `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"👥 **Active Users:** `{len(user_data)}`\n"
        f"📤 **Transfers Completed:** `{transfer_stats['transfers_completed']}`\n\n"
        f"⬇️ **Total Downloaded:** `{humanbytes(transfer_stats['total_downloaded'])}`\n"
        f"⬆️ **Total Uploaded:** `{humanbytes(transfer_stats['total_uploaded'])}`\n"
        f"⚡ **Max Download Speed:** `{humanbytes(transfer_stats['max_download_speed'])}/s`\n"
        f"🚀 **Max Upload Speed:** `{humanbytes(transfer_stats['max_upload_speed'])}/s`"
    )

@app.on_message(filters.command("ping") & filters.private)
async def ping_handler(client, message):
    start = time.time()
    ping_msg = await message.reply_text("🏓 Pinging...")
    end = time.time()
    await ping_msg.edit_text(
        f"🏓 **PONG!** `{(end - start) * 1000:.2f}ms`\n"
        f"🕒 **Server Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )

@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
    file = message.video or message.document or message.audio
    if not file:
        return

    uid = message.from_user.id
    user_data[uid] = {
        "user_id": uid,
        "message_id": message.id,
        "chat_id": message.chat.id,
        "file_type": "video" if message.video else "document",
        "file_size": getattr(file, "file_size", 0),
        "file_name": getattr(file, "file_name", None) or getattr(file, "file_name", "file"),
        "timestamp": time.time(),
        # "thumbnail" will be set if user uploads a photo afterwards
    }

    buttons = [[InlineKeyboardButton("⚡ Rename File", callback_data="rename")]]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        f"📁 **File Received** 📁\n\n"
        f"**Name:** `{user_data[uid]['file_name']}`\n"
        f"**Size:** `{humanbytes(user_data[uid]['file_size'])}`\n\n"
        f"**Select action:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

@app.on_callback_query()
async def callback_handler(client, cq):
    uid = cq.from_user.id
    if uid not in user_data:
        await cq.answer("❌ Session expired. Send file again.", show_alert=True)
        return

    if cq.data == "rename":
        user_data[uid]["action"] = "rename"
        await cq.message.edit_text("✍️ Send new filename with extension (e.g., `movie.mp4`)")
    elif cq.data == "set_thumbnail":
        user_data[uid]["action"] = "thumbnail"
        await cq.message.edit_text("🖼️ Send a photo to set as thumbnail.")
    await cq.answer()

@app.on_message(filters.photo & filters.private)
async def thumbnail_handler(client, message):
    uid = message.from_user.id
    if uid in user_data and user_data[uid].get("action") == "thumbnail":
        try:
            photo_path = await message.download()
            if photo_path and os.path.exists(photo_path):
                user_data[uid]["thumbnail"] = photo_path
                user_data[uid]["action"] = None
                await message.reply_text("✅ Thumbnail saved. Now press Rename File to continue.")
            else:
                await message.reply_text("❌ Failed to save thumbnail.")
        except Exception:
            logger.exception("Failed to download thumbnail")
            await message.reply_text("❌ Error while saving thumbnail. See logs.")

@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    uid = message.from_user.id
    if uid not in user_data or user_data[uid].get("action") != "rename":
        return

    new_filename = safe_filename(message.text.strip())
    if not new_filename:
        await message.reply_text("❌ Invalid filename.")
        return

    user_info = user_data[uid]
    # start processing in background, pass the trigger message for status replies
    asyncio.create_task(handle_file_processing(app, message, user_info, new_filename))
    # remove user data to avoid reuse; thumbnail path (if any) remains in filesystem until cleaned
    user_data.pop(uid, None)

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    logger.info("🚀 Starting bot...")
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        
