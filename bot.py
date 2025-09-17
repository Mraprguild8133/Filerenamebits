import os
import time
import math
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# --- Bot Initialization ---
# Use a file-based session to persist data across restarts
app = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- State Management ---
# A simple dictionary to hold user states and data in memory.
# For a production bot, consider using a database like SQLite or Redis.
USER_DATA = {}

# --- Helper Functions ---
def humanbytes(size):
    """Converts bytes to a human-readable format."""
    if not size:
        return ""
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

async def progress_callback(current, total, message, start_time, action):
    """
    Updates the message with the current progress of the upload/download.
    """
    now = time.time()
    diff = now - start_time
    if round(diff % 5.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff)
        eta = round((total - current) / speed) if speed > 0 else 0
        
        progress_str = (
            f"**{action} Progress**\n"
            f"[{'█' * int(percentage / 5)}{' ' * (20 - int(percentage / 5))}] {percentage:.2f}%\n"
            f"**Done:** {humanbytes(current)} of {humanbytes(total)}\n"
            f"**Speed:** {humanbytes(speed)}/s\n"
            f"**ETA:** {time.strftime('%H:%M:%S', time.gmtime(eta))}\n"
            f"**Elapsed:** {time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}"
        )
        
        try:
            await message.edit_text(progress_str)
        except Exception:
            pass # Ignore errors if message is not editable

# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    """Handles the /start command."""
    await message.reply_text(
        "👋 **Hello! I am your File Manager Bot.**\n\n"
        "Send me any file, and I will help you manage it.\n"
        "I can rename files and apply custom thumbnails to videos.\n\n"
        "Created with ❤️ by Pyrogram.",
        quote=True
    )
    USER_DATA.pop(message.from_user.id, None)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message: Message):
    """Handles the /cancel command to reset the user's state."""
    user_id = message.from_user.id
    if user_id in USER_DATA:
        USER_DATA.pop(user_id, None)
        await message.reply_text("✅ Operation cancelled successfully.", quote=True)
    else:
        await message.reply_text("🤔 Nothing to cancel.", quote=True)

# --- Message Handlers for File Processing ---
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message: Message):
    """Handles incoming files and presents action buttons."""
    user_id = message.from_user.id
    
    # Store the message object for later use
    file_type = "video" if message.video else "document"
    
    USER_DATA[user_id] = {
        'file_message_id': message.id,
        'file_type': file_type
    }
    
    buttons = [
        [InlineKeyboardButton("📝 Rename File", callback_data="rename")],
    ]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Custom Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        "**What would you like to do with this file?**\n\n"
        "Select an option below. You can use /cancel at any time to stop.",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

@app.on_callback_query()
async def button_handler(client, callback_query: CallbackQuery):
    """Handles button presses for rename and thumbnail actions."""
    user_id = callback_query.from_user.id
    action = callback_query.data

    if user_id not in USER_DATA:
        await callback_query.answer("⚠️ This is an old message. Please send the file again.", show_alert=True)
        return

    if action == "rename":
        USER_DATA[user_id]['state'] = 'awaiting_rename'
        await callback_query.message.edit_text("✍️ **Send me the new file name, including the extension.**\n\nExample: `My Awesome Video.mp4`")
    
    elif action == "set_thumbnail":
        USER_DATA[user_id]['state'] = 'awaiting_thumbnail'
        await callback_query.message.edit_text("🖼️ **Please send me the photo you want to use as a thumbnail.**")
    
    await callback_query.answer()


@app.on_message(filters.text & filters.private)
async def text_handler(client, message: Message):
    """Handles text input for renaming files."""
    user_id = message.from_user.id
    if USER_DATA.get(user_id, {}).get('state') == 'awaiting_rename':
        
        new_filename = message.text
        status_msg = await message.reply_text("Processing...", quote=True)

        # Retrieve the original file message
        original_file_msg = await client.get_messages(user_id, USER_DATA[user_id]['file_message_id'])
        
        # Download the file
        start_time = time.time()
        file_path = await original_file_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time, "Downloading")
        )
        
        # Upload the file with the new name
        await status_msg.edit_text("⬆️ **Uploading file with new name...**")
        start_time_upload = time.time()

        # Choose the correct method to send based on file type
        if USER_DATA[user_id]['file_type'] == 'video' and original_file_msg.video:
            await client.send_video(
                chat_id=user_id,
                video=file_path,
                file_name=new_filename,
                caption=f"**Renamed to:** `{new_filename}`",
                progress=progress_callback,
                progress_args=(status_msg, start_time_upload, "Uploading")
            )
        else:
            await client.send_document(
                chat_id=user_id,
                document=file_path,
                file_name=new_filename,
                caption=f"**Renamed to:** `{new_filename}`",
                force_document=True,
                progress=progress_callback,
                progress_args=(status_msg, start_time_upload, "Uploading")
            )

        await status_msg.delete()
        os.remove(file_path)
        USER_DATA.pop(user_id, None)

@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message: Message):
    """Handles photo input for setting thumbnails."""
    user_id = message.from_user.id
    if USER_DATA.get(user_id, {}).get('state') == 'awaiting_thumbnail':
        
        status_msg = await message.reply_text("Processing...", quote=True)
        
        # Download the thumbnail
        thumbnail_path = await message.download(file_name=f"{user_id}_thumb.jpg")
        
        # Retrieve the original video message
        original_video_msg = await client.get_messages(user_id, USER_DATA[user_id]['file_message_id'])
        
        # Download the video
        await status_msg.edit_text("📥 **Downloading video...**")
        start_time_dl = time.time()
        video_path = await original_video_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time_dl, "Downloading")
        )
        
        # Upload with new thumbnail
        await status_msg.edit_text("⬆️ **Uploading with new thumbnail...**")
        start_time_ul = time.time()
        
        await client.send_video(
            chat_id=user_id,
            video=video_path,
            thumb=thumbnail_path,
            caption="✅ **Thumbnail applied successfully!**",
            progress=progress_callback,
            progress_args=(status_msg, start_time_ul, "Uploading")
        )
        
        await status_msg.delete()
        os.remove(video_path)
        os.remove(thumbnail_path)
        USER_DATA.pop(user_id, None)


# --- Main execution ---
if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
    print("Bot has stopped.")
