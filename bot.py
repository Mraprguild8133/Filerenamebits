# (c) @No-OnE-Kn0wS-Me
# Credits: @PredatorHackerzZ, @anasty17

import os
import time
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from config import API_ID, API_HASH, BOT_TOKEN, AUTH_USERS, DOWNLOAD_DIR

# --- Basic Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)

# --- Bot Initialization ---
bot = Client(
    "FileRenameBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- In-memory storage for user states ---
user_states = {}

# --- Helper Functions & Progress Bar ---
def humanbytes(size):
    """Converts bytes to a human-readable format."""
    if not size:
        return ""
    power = 1024
    t_n = 0
    power_dict = {0: " B", 1: " KB", 2: " MB", 3: " GB", 4: " TB"}
    while size > power:
        size /= power
        t_n += 1
    return f"{size:.2f}{power_dict[t_n]}"

def time_formatter(seconds: int) -> str:
    """Formats seconds into a human-readable time string."""
    result = ""
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f"{days}d "
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f"{hours}h "
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f"{minutes}m "
    seconds = int(seconds)
    result += f"{seconds}s "
    return result.strip()

def progress_bar(current, total, ud_type, message, start):
    """Generates a progress bar string."""
    now = time.time()
    diff = now - start
    if diff == 0:
        diff = 0.01

    percentage = current * 100 / total
    speed = current / diff
    elapsed_time = round(diff)
    time_to_completion = round((total - current) / speed) if speed > 0 else 0
    
    total_size = humanbytes(total)
    current_size = humanbytes(current)

    progress_str = (
        f"**╭ {ud_type}**\n"
        f"**├ Progress: **{percentage:.2f}%\n"
        f"**├ {current_size} of {total_size}**\n"
        f"**├ Speed: **{humanbytes(speed)}/s\n"
        f"**╰ ETA: **{time_formatter(time_to_completion)}"
    )
    
    try:
        if message.text != progress_str:
            message.edit_text(text=progress_str)
    except FloodWait as e:
        time.sleep(e.x)
    except Exception as e:
        LOGGER.error(f"Error updating progress bar: {e}")


# --- Command Handlers ---

def authorized_users_only(func):
    """Decorator to check if the user is authorized."""
    async def wrapper(client, message):
        if message.from_user.id in AUTH_USERS:
            await func(client, message)
        else:
            await message.reply_text("Sorry, you are not authorized to use this bot.")
    return wrapper

@bot.on_message(filters.command("start") & filters.private)
@authorized_users_only
async def start_command(client, message):
    """Handler for the /start command."""
    await message.reply_text(
        "**Hello! I am a File Rename Bot.**\n\n"
        "I can rename any file you send me. Just send a file and then reply with the new name. Use /help for more information.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Developer", url="https://github.com/No-OnE-Kn0wS-Me")]]
        )
    )

@bot.on_message(filters.command("help") & filters.private)
@authorized_users_only
async def help_command(client, message):
    """Handler for the /help command."""
    await message.reply_text(
        "**How to use me:**\n\n"
        "1. Send me any file (document, video, audio, etc.).\n"
        "2. I will ask for the new file name.\n"
        "3. Reply to my message with the desired file name (including the extension, e.g., `MyVideo.mkv`).\n\n"
        "That's it! I will then rename and upload the file for you."
    )

# --- File Handling Logic ---

@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
@authorized_users_only
async def handle_file(client, message: Message):
    """Handles incoming files and asks for the new name."""
    if not os.path.isdir(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    user_states[message.from_user.id] = message.id
    
    await message.reply_text(
        "File received! Now, please reply to this message with the **new file name** (including the extension).",
        reply_to_message_id=message.id
    )

@bot.on_message(filters.private & filters.text & ~filters.command(["start", "help"]))
@authorized_users_only
async def rename_file(client, message: Message):
    """Renames the file based on the user's text reply."""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        await message.reply_text("Please send a file first before providing a new name.")
        return

    # Check if this is a reply to the bot's message asking for filename
    if not message.reply_to_message:
        await message.reply_text("Please reply to my message where I asked for the new filename.")
        return
        
    original_file_message_id = user_states.pop(user_id)
    try:
        original_file_message = await client.get_messages(user_id, original_file_message_id)
    except Exception as e:
        LOGGER.error(f"Could not get original message: {e}")
        await message.reply_text("I couldn't find the original file. Please send it again.")
        return

    if not (original_file_message and (original_file_message.document or original_file_message.video or original_file_message.audio)):
        await message.reply_text("Something went wrong. It seems the original message was not a file. Please try again.")
        return
        
    status_message = await message.reply_text("Downloading file...", quote=True)
    
    file_path = None
    try:
        start_time = time.time()
        file_path = await original_file_message.download(
            file_name=DOWNLOAD_DIR,
            progress=progress_bar,
            progress_args=("Downloading...", status_message, start_time)
        )
    except Exception as e:
        LOGGER.error(f"Error downloading file: {e}")
        await status_message.edit(f"Failed to download file. Error: {e}")
        return

    if not file_path or not os.path.exists(file_path):
        await status_message.edit("Download failed. File path not found.")
        return

    new_file_name = message.text
    directory, old_file_name = os.path.split(file_path)
    new_path = os.path.join(directory, new_file_name)

    try:
        os.rename(file_path, new_path)
    except Exception as e:
        LOGGER.error(f"Error renaming file: {e}")
        await status_message.edit(f"Failed to rename file. Error: {e}")
        if os.path.exists(file_path): 
            os.remove(file_path)
        return

    await status_message.edit("Uploading renamed file...")
    
    # Determine the appropriate send method and parameters
    try:
        upload_start_time = time.time()
        
        if original_file_message.document:
            await client.send_document(
                chat_id=message.chat.id,
                document=new_path,
                file_name=new_file_name,
                progress=progress_bar,
                progress_args=("Uploading...", status_message, upload_start_time),
                reply_to_message_id=message.id
            )
        elif original_file_message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=new_path,
                file_name=new_file_name,
                progress=progress_bar,
                progress_args=("Uploading...", status_message, upload_start_time),
                reply_to_message_id=message.id
            )
        elif original_file_message.audio:
            await client.send_audio(
                chat_id=message.chat.id,
                audio=new_path,
                file_name=new_file_name,
                progress=progress_bar,
                progress_args=("Uploading...", status_message, upload_start_time),
                reply_to_message_id=message.id
            )
    except FloodWait as fw:
        LOGGER.warning(f"FloodWait: Sleeping for {fw.x} seconds.")
        await asyncio.sleep(fw.x)
        # Retry the upload after waiting
        if original_file_message.document:
            await client.send_document(
                chat_id=message.chat.id,
                document=new_path,
                file_name=new_file_name,
                reply_to_message_id=message.id
            )
        elif original_file_message.video:
            await client.send_video(
                chat_id=message.chat.id,
                video=new_path,
                file_name=new_file_name,
                reply_to_message_id=message.id
            )
        elif original_file_message.audio:
            await client.send_audio(
                chat_id=message.chat.id,
                audio=new_path,
                file_name=new_file_name,
                reply_to_message_id=message.id
            )
    except Exception as e:
        LOGGER.error(f"Error uploading file: {e}")
        await status_message.edit(f"Failed to upload file. Error: {e}")
        if os.path.exists(new_path):
            os.remove(new_path)
        return

    await status_message.delete()
    if os.path.exists(new_path):
        os.remove(new_path)


# --- Start the Bot ---
if __name__ == "__main__":
    LOGGER.info("Bot is starting...")
    bot.run()
    LOGGER.info("Bot has stopped.")
