import os
import re
import time
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not all([API_ID, API_HASH, BOT_TOKEN]):
    raise SystemExit("❌ Missing API_ID, API_HASH, or BOT_TOKEN in environment")

# Globals
user_data = {}
last_update_time = {}
transfer_stats = {"total_downloaded": 0, "total_uploaded": 0}

# Utility functions
def humanbytes(size: int) -> str:
    if not size:
        return "0B"
    power = 1024
    n = 0
    dic = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {dic[n]}"

def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)

def create_progress_bar(percentage, length=20):
    filled = int(length * percentage / 100)
    return f"{'█' * filled}{'░' * (length - filled)}"

async def update_progress(current, total, message, start, action, uid):
    now = time.time()
    if uid in last_update_time and now - last_update_time[uid] < 1:
        return
    last_update_time[uid] = now
    percent = current * 100 / total if total else 0
    bar = create_progress_bar(percent)
    speed = current / (now - start + 1e-9)
    eta = (total - current) / speed if speed > 0 else 0
    try:
        await message.edit_text(
            f"{action}...\n"
            f"{bar} {percent:.1f}%\n"
            f"📥 {humanbytes(current)} of {humanbytes(total)}\n"
            f"⚡ {humanbytes(speed)}/s | ⏳ {int(eta)}s left"
        )
    except Exception:
        pass

# Bot init
app = Client("rename-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    await message.reply_text(
        "👋 Send me any **photo, video, document, or audio** and I’ll let you rename it."
    )

@app.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.voice | filters.photo | filters.animation))
async def save_file(client, message: Message):
    file = message.document or message.video or message.audio or message.voice or message.photo or message.animation
    if not file:
        return await message.reply_text("❌ Unsupported file type.")

    # Default filename handling
    file_name = getattr(file, "file_name", None)
    if not file_name:
        ext = ".jpg" if message.photo else ".ogg" if message.voice else ".bin"
        file_name = f"file_{int(time.time())}{ext}"

    user_data[message.from_user.id] = {
        "chat_id": message.chat.id,
        "msg_id": message.id,
        "file_name": file_name,
        "file_size": getattr(file, "file_size", 0),
    }

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Rename", callback_data="rename")]])
    await message.reply_text(f"📂 File received: **{file_name}**", reply_markup=kb)

@app.on_callback_query(filters.regex("rename"))
async def ask_new_name(client, query):
    uid = query.from_user.id
    if uid not in user_data:
        return await query.message.edit_text("❌ Session expired. Send file again.")
    await query.message.edit_text("✏️ Send me the new filename (with extension).")

@app.on_message(filters.private & filters.text)
async def rename_handler(client, message: Message):
    uid = message.from_user.id
    if uid not in user_data:
        return

    new_name = safe_filename(message.text.strip())
    info = user_data[uid]

    status = await message.reply_text("🚀 Processing...")

    try:
        # Fetch original message
        original_msg = await client.get_messages(info["chat_id"], info["msg_id"])
        if not original_msg:
            return await status.edit_text("❌ Could not retrieve original file.")

        # Download
        start = time.time()
        os.makedirs("downloads", exist_ok=True)
        dl_path = await client.download_media(
            original_msg,
            file_name=os.path.join("downloads", new_name),
            progress=lambda cur, tot: asyncio.create_task(
                update_progress(cur, tot, status, start, "Downloading", uid)
            )
        )
        if not dl_path:
            return await status.edit_text("❌ Download failed.")
        transfer_stats["total_downloaded"] += info["file_size"]

        # Upload
        start = time.time()
        await client.send_document(
            uid,
            dl_path,
            file_name=new_name,
            caption=f"✅ Renamed to `{new_name}`",
            progress=lambda cur, tot: asyncio.create_task(
                update_progress(cur, tot, status, start, "Uploading", uid)
            )
        )
        transfer_stats["total_uploaded"] += info["file_size"]
        await status.edit_text("✅ Done!")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await rename_handler(client, message)

    except Exception as e:
        err_text = f"❌ Error during processing:\n`{type(e).__name__}: {e}`"
        logger.error(f"❌ Processing error for user {uid}: {e}", exc_info=True)
        await status.edit_text(err_text)

    finally:
        user_data.pop(uid, None)

if __name__ == "__main__":
    logger.info("🚀 Bot started")
    app.run()
    
