import os
import time
import asyncio
import json
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, ForceReply

# --- Load Environment Variables ---
load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# --- Bot Initialization ---
if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    raise ValueError("Missing one or more required environment variables")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID must be a valid integer.")

app = Client(
    "file_renamer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- In-memory storage & Config File ---
user_tasks = {}
CONFIG_FILE = "config.json"

# --- Configuration Helpers ---
def load_config():
    """Loads configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Saves configuration to JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# --- Helper Functions ---
def humanbytes(size):
    """Converts bytes to a human-readable format."""
    if not size:
        return "0 B"
    power = 1024
    t_n = 0
    power_dict = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size >= power:
        size /= power
        t_n += 1
    return f"{size:.2f} {power_dict[t_n]}"

async def progress_callback(current, total, message, start_time, action):
    """Updates the message with upload/download progress."""
    now = time.time()
    diff = now - start_time
    if diff == 0: diff = 0.001

    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff)
    eta = round((total - current) / speed) if speed > 0 else 0
    
    progress_bar = "[{0}{1}]".format('█' * int(percentage / 5), ' ' * (20 - int(percentage / 5)))
    
    progress_text = (
        f"**{action}**\n"
        f"{progress_bar} {percentage:.2f}%\n"
        f"**Done:** {humanbytes(current)}\n"
        f"**Total:** {humanbytes(total)}\n"
        f"**Speed:** {humanbytes(speed)}/s\n"
        f"**ETA:** {time.strftime('%Hh %Mm %Ss', time.gmtime(eta))}\n"
    )
    
    try:
        await message.edit_text(text=progress_text)
    except Exception:
        pass

# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply_text(
        "**Hello! I am a File Renamer Bot.**\n\n"
        "**Features:**\n"
        "- Rename any file.\n"
        "- Add custom thumbnails to videos.\n"
        "- Set a permanent thumbnail with `/set_thumbnail`.\n"
        "- Remove the permanent thumbnail with `/del_thumbnail`.\n"
        "- Add a filename prefix with `/prefix`.\n"
        "- Add a filename suffix with `/suffix`.\n\n"
        "Send me a file to get started!",
        quote=True
    )

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client: Client, message: Message):
    if message.from_user.id in user_tasks:
        del user_tasks[message.from_user.id]
        await message.reply_text("Your current task has been cancelled.", quote=True)
    else:
        await message.reply_text("You have no active tasks to cancel.", quote=True)

@app.on_message(filters.command("set_thumbnail") & filters.private)
async def set_thumbnail_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    user_tasks[message.from_user.id] = {"action": "set_thumbnail"}
    await message.reply_text("Please send me the photo you want to set as the permanent thumbnail.", quote=True)

@app.on_message(filters.command("del_thumbnail") & filters.private)
async def del_thumbnail_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    config = load_config()
    if "custom_thumbnail" in config:
        del config["custom_thumbnail"]
        save_config(config)
        await message.reply_text("Permanent thumbnail has been deleted.", quote=True)
    else:
        await message.reply_text("No permanent thumbnail was set.", quote=True)

@app.on_message(filters.command("prefix") & filters.private)
async def prefix_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    config = load_config()
    parts = message.text.split(" ", 1)
    if len(parts) > 1:
        prefix = parts[1]
        config["prefix"] = prefix
        save_config(config)
        await message.reply_text(f"Prefix successfully set to: `{prefix}`", quote=True)
    else:
        if "prefix" in config:
            del config["prefix"]
            save_config(config)
            await message.reply_text("Prefix has been removed.", quote=True)
        else:
            await message.reply_text("Usage: `/prefix your_prefix_here`. To remove, just send `/prefix`.", quote=True)

@app.on_message(filters.command("suffix") & filters.private)
async def suffix_handler(client: Client, message: Message):
    if message.from_user.id != ADMIN_ID: return
    config = load_config()
    parts = message.text.split(" ", 1)
    if len(parts) > 1:
        suffix = parts[1]
        config["suffix"] = suffix
        save_config(config)
        await message.reply_text(f"Suffix successfully set to: `{suffix}`", quote=True)
    else:
        if "suffix" in config:
            del config["suffix"]
            save_config(config)
            await message.reply_text("Suffix has been removed.", quote=True)
        else:
            await message.reply_text("Usage: `/suffix your_suffix_here`. To remove, just send `/suffix`.", quote=True)

# --- Main Logic Handlers ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.reply_text("Sorry, this bot is for the admin's use only.", quote=True)
        return
    if user_id in user_tasks:
        await message.reply_text("You have an active task. Please complete or /cancel it.", quote=True)
        return

    file_type = "document" if message.document else "video" if message.video else "audio"
    file = message.document or message.video or message.audio
    
    user_tasks[user_id] = {
        "action": "rename",
        "file_id": file.file_id,
        "file_type": file_type,
        "message_id": message.id
    }
    await message.reply_text(
        "File received. Send me the new file name (with extension).",
        reply_to_message_id=message.id,
        reply_markup=ForceReply(selective=True)
    )

@app.on_message(filters.private & filters.text)
async def name_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_tasks: return

    task = user_tasks[user_id]
    if task.get("action") != "rename" or "new_name" in task: return

    sanitized_name = message.text.replace("/", "_").replace("\\", "_")
    task["new_name"] = sanitized_name
    
    if task["file_type"] == "video":
        await message.reply_text(
            "Great. Now, send a photo for a one-time thumbnail, or /skip to use the default or permanent thumbnail.",
            reply_to_message_id=message.id,
            reply_markup=ForceReply(selective=True)
        )
    else:
        await process_file(client, message)

@app.on_message(filters.private & filters.photo)
async def thumbnail_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id not in user_tasks: return
    
    task = user_tasks[user_id]
    action = task.get("action")

    if action == "set_thumbnail":
        config = load_config()
        config["custom_thumbnail"] = message.photo.file_id
        save_config(config)
        await message.reply_text("Permanent thumbnail has been saved successfully!", quote=True)
        del user_tasks[user_id]
        
    elif action == "rename" and task["file_type"] == "video" and "new_name" in task:
        task["thumbnail_id"] = message.photo.file_id
        await process_file(client, message)

@app.on_message(filters.command("skip"))
async def skip_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_tasks and user_tasks[user_id].get("action") == "rename":
        user_tasks[user_id]["thumbnail_id"] = None
        await process_file(client, message)

async def process_file(client: Client, message: Message):
    user_id = message.from_user.id
    task = user_tasks.get(user_id)

    if not task or task.get("action") != "rename" or "new_name" not in task:
        return

    status_message = await message.reply_text("Processing...", quote=True)
    
    original_file_path = None
    new_file_path = None
    thumbnail_path = None
    
    try:
        # 1. Download the file
        start_time = time.time()
        original_file_path = await client.download_media(
            message=task["file_id"],
            progress=progress_callback,
            progress_args=(status_message, start_time, "Downloading...")
        )
        
        # 2. Handle Thumbnail
        config = load_config()
        thumb_id = task.get("thumbnail_id") or config.get("custom_thumbnail")
        if thumb_id:
            thumbnail_path = await client.download_media(thumb_id)

        # 3. Construct New Filename with Prefix/Suffix
        new_name = task["new_name"]
        prefix = config.get("prefix", "")
        suffix = config.get("suffix", "")
        
        base, ext = os.path.splitext(new_name)
        final_name = f"{prefix}{base}{suffix}{ext}"
        
        new_file_path = os.path.join(os.path.dirname(original_file_path), final_name)
        os.rename(original_file_path, new_file_path)

        # 4. Upload the file
        await status_message.edit_text("Uploading...")
        caption = f"`{final_name}`"
        file_type = task["file_type"]
        start_time = time.time()
        
        if file_type == "document":
            await client.send_document(
                user_id, document=new_file_path, thumb=thumbnail_path, caption=caption,
                progress=progress_callback, progress_args=(status_message, start_time, "Uploading...")
            )
        elif file_type == "video":
            media = await client.get_messages(user_id, task["message_id"])
            video_meta = media.video
            await client.send_video(
                user_id, video=new_file_path, thumb=thumbnail_path, caption=caption,
                duration=video_meta.duration, width=video_meta.width, height=video_meta.height,
                progress=progress_callback, progress_args=(status_message, start_time, "Uploading...")
            )
        elif file_type == "audio":
            await client.send_audio(
                user_id, audio=new_file_path, thumb=thumbnail_path, caption=caption,
                progress=progress_callback, progress_args=(status_message, start_time, "Uploading...")
            )

        await status_message.delete()
        await message.reply_text("Task completed successfully!", quote=True)

    except Exception as e:
        await status_message.edit_text(f"An error occurred: {e}")
        print(e)
    finally:
        # Clean up files and task data
        if new_file_path and os.path.exists(new_file_path): os.remove(new_file_path)
        elif original_file_path and os.path.exists(original_file_path): os.remove(original_file_path)
        if thumbnail_path and os.path.exists(thumbnail_path): os.remove(thumbnail_path)
        if user_id in user_tasks: del user_tasks[user_id]

# --- Start the bot ---
if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    print("Bot has stopped.")
