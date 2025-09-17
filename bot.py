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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "5000"))

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Missing environment variables")
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

# ---------- Helpers ----------
def humanbytes(size: int) -> str:
    if not size or size == 0:
        return "0B"
    power = 1024
    n = 0
    labels = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size >= power and n < len(labels) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {labels[n]}"


def create_progress_bar(percentage, length=20):
    filled = min(int(length * percentage / 100), length)
    return "█" * filled + "░" * (length - filled)


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)


async def update_progress(current, total, message, start_time, action, user_id):
    try:
        now = time.time()
        if user_id in last_update_time and now - last_update_time[user_id] < 1:
            return
        last_update_time[user_id] = now

        elapsed = now - start_time
        speed = current / elapsed if elapsed > 0 else 0
        percentage = (current / total) * 100 if total > 0 else 0
        eta = (total - current) / speed if speed > 0 and total > current else 0

        if action == "Downloading":
            transfer_stats["max_download_speed"] = max(
                transfer_stats["max_download_speed"], speed
            )
        else:
            transfer_stats["max_upload_speed"] = max(
                transfer_stats["max_upload_speed"], speed
            )

        bar = create_progress_bar(percentage)
        text = (
            f"🚀 **{action}** 🚀\n\n"
            f"`{bar}` **{percentage:.1f}%**\n\n"
            f"⚡ **Speed:** `{humanbytes(speed)}/s`\n"
            f"📦 **Progress:** `{humanbytes(current)}` / `{humanbytes(total)}`\n"
            f"⏱️ **ETA:** `{time.strftime('%M:%S', time.gmtime(eta)) if eta > 0 else '00:00'}`\n"
            f"🕒 **Elapsed:** `{time.strftime('%M:%S', time.gmtime(elapsed))}`"
        )
        try:
            await message.edit_text(text)
        except MessageNotModified:
            pass
    except Exception as e:
        logger.error(f"Progress error: {e}")


async def safe_send(func, *args, **kwargs):
    """Handle FloodWait automatically"""
    try:
        return await func(*args, **kwargs)
    except FloodWait as e:
        logger.warning(f"FloodWait: sleeping {e.value}s")
        await asyncio.sleep(e.value)
        return await safe_send(func, *args, **kwargs)


# ---------- File Processing ----------
async def handle_file_processing(app, message, user_info, new_filename):
    status_msg, file_path = None, None
    try:
        status_msg = await message.reply_text("🚀 **Starting transfer...**")
        start_time = time.time()

        # Get original file
        original_msg = await app.get_messages(user_info["chat_id"], user_info["message_id"])
        if not original_msg:
            await status_msg.edit_text("❌ Original file not found.")
            return

        # Download dir
        base_dir = "downloads"
        os.makedirs(base_dir, exist_ok=True)
        download_dir = os.path.join(base_dir, f"{user_info['user_id']}_{int(time.time())}")
        os.makedirs(download_dir, exist_ok=True)
        download_path = os.path.join(download_dir, safe_filename(user_info["file_name"]))

        # Download file
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
                ),
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
                ),
            )

        transfer_stats["total_uploaded"] += user_info["file_size"]
        transfer_stats["transfers_completed"] += 1

        total_time = time.time() - start_time
        avg_speed = user_info["file_size"] / total_time if total_time > 0 else 0

        await status_msg.edit_text(
            f"✅ **Transfer Complete!** ✅\n\n"
            f"📁 **File:** `{new_filename}`\n"
            f"⚡ **Average Speed:** `{humanbytes(avg_speed)}/s`\n"
            f"⏱️ **Total Time:** `{time.strftime('%M:%S', time.gmtime(total_time))}`\n"
            f"📦 **Size:** `{humanbytes(user_info['file_size'])}`"
        )

    except Exception as e:
        logger.error(f"❌ File processing error: {e}")
        if status_msg:
            await status_msg.edit_text("❌ Error during processing. Check logs.")
    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                d = os.path.dirname(file_path)
                if os.path.exists(d) and not os.listdir(d):
                    os.rmdir(d)
            except Exception as cleanup_err:
                logger.warning(f"Cleanup error: {cleanup_err}")


# ---------- Bot ----------
app = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=20
)


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
async def status_handler(client, message):
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

    user_data[message.from_user.id] = {
        "user_id": message.from_user.id,
        "message_id": message.id,
        "chat_id": message.chat.id,
        "file_type": "video" if message.video else "document",
        "file_size": file.file_size,
        "file_name": getattr(file, "file_name", "file"),
        "timestamp": time.time()
    }

    buttons = [[InlineKeyboardButton("⚡ Rename File", callback_data="rename")]]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        f"📁 **File Received** 📁\n\n"
        f"**Name:** `{user_data[message.from_user.id]['file_name']}`\n"
        f"**Size:** `{humanbytes(file.file_size)}`\n\n"
        f"**Select action:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )


@app.on_callback_query()
async def callback_handler(client, callback_query):
    uid = callback_query.from_user.id
    if uid not in user_data:
        await callback_query.answer("❌ Session expired. Send file again.", show_alert=True)
        return

    if callback_query.data == "rename":
        user_data[uid]["action"] = "rename"
        await callback_query.message.edit_text("✍️ Send new filename with extension (e.g., `movie.mp4`)")
    elif callback_query.data == "set_thumbnail":
        user_data[uid]["action"] = "thumbnail"
        await callback_query.message.edit_text("🖼️ Send a photo to set as thumbnail.")

    await callback_query.answer()


@app.on_message(filters.photo & filters.private)
async def thumbnail_handler(client, message):
    uid = message.from_user.id
    if uid in user_data and user_data[uid].get("action") == "thumbnail":
        photo_path = await message.download()
        user_data[uid]["thumbnail"] = photo_path
        user_data[uid]["action"] = None
        await message.reply_text("✅ Thumbnail saved. Now press **Rename File** to continue.")


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
    asyncio.create_task(handle_file_processing(app, message, user_info, new_filename))
    user_data.pop(uid, None)


# ---------- Run ----------
if __name__ == "__main__":
    logger.info("🚀 Starting bot...")
    app.run()
                          
