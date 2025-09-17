import os
import time
import math
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, PeerIdInvalid

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- Bot Initialization ---
app = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- State Management ---
# Dictionary to hold user states and data with timestamp for cleanup
USER_DATA: Dict[int, Dict[str, Any]] = {}
STATE_TIMEOUT = 300  # 5 minutes

# --- Helper Functions ---
def humanbytes(size: int) -> str:
    """Converts bytes to a human-readable format."""
    if not size or size == 0:
        return "0B"
    
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
        
    return f"{size:.2f} {power_labels[n]}"

async def progress_callback(current: int, total: int, message: Message, start_time: float, action: str):
    """
    Updates the message with the current progress of the upload/download.
    """
    try:
        now = time.time()
        diff = now - start_time
        
        # Update every 5 seconds or when completed
        if round(diff % 5.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff if diff > 0 else 0
            elapsed_time = round(diff)
            eta = round((total - current) / speed) if speed > 0 else 0
            
            # Create progress bar
            filled_length = int(20 * percentage / 100)
            progress_bar = '█' * filled_length + ' ' * (20 - filled_length)
            
            progress_str = (
                f"**{action} Progress**\n"
                f"`[{progress_bar}] {percentage:.2f}%`\n\n"
                f"**Done:** `{humanbytes(current)}` of `{humanbytes(total)}`\n"
                f"**Speed:** `{humanbytes(speed)}/s`\n"
                f"**ETA:** `{time.strftime('%H:%M:%S', time.gmtime(eta))}`\n"
                f"**Elapsed:** `{time.strftime('%H:%M:%S', time.gmtime(elapsed_time))}`"
            )
            
            try:
                await message.edit_text(progress_str)
            except MessageNotModified:
                pass  # Ignore if message wasn't modified
    except Exception as e:
        print(f"Error in progress callback: {e}")

async def cleanup_states():
    """Periodically clean up expired user states"""
    while True:
        await asyncio.sleep(60)  # Run every minute
        current_time = time.time()
        expired_users = [
            user_id for user_id, data in USER_DATA.items() 
            if current_time - data.get('timestamp', 0) > STATE_TIMEOUT
        ]
        
        for user_id in expired_users:
            USER_DATA.pop(user_id, None)

def get_user_state(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user state with timestamp check"""
    if user_id in USER_DATA:
        # Check if state is expired
        if time.time() - USER_DATA[user_id].get('timestamp', 0) > STATE_TIMEOUT:
            USER_DATA.pop(user_id, None)
            return None
        return USER_DATA[user_id]
    return None

def set_user_state(user_id: int, state_data: Dict[str, Any]):
    """Set user state with current timestamp"""
    state_data['timestamp'] = time.time()
    USER_DATA[user_id] = state_data

# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handles the /start command."""
    await message.reply_text(
        "👋 **Hello! I am your File Manager Bot.**\n\n"
        "Send me any file, and I will help you manage it.\n"
        "I can rename files and apply custom thumbnails to videos.\n\n"
        "Use /cancel at any time to cancel the current operation.\n\n"
        "Created with ❤️ by Pyrogram.",
        quote=True
    )
    USER_DATA.pop(message.from_user.id, None)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client: Client, message: Message):
    """Handles the /cancel command to reset the user's state."""
    user_id = message.from_user.id
    if user_id in USER_DATA:
        USER_DATA.pop(user_id, None)
        await message.reply_text("✅ Operation cancelled successfully.", quote=True)
    else:
        await message.reply_text("🤔 Nothing to cancel.", quote=True)

# --- Message Handlers for File Processing ---
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client: Client, message: Message):
    """Handles incoming files and presents action buttons."""
    user_id = message.from_user.id
    
    # Store the message object for later use
    file_type = "video" if message.video else "document"
    
    set_user_state(user_id, {
        'file_message_id': message.id,
        'file_type': file_type,
        'chat_id': message.chat.id
    })
    
    buttons = [
        [InlineKeyboardButton("📝 Rename File", callback_data="rename")],
    ]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Custom Thumbnail", callback_data="set_thumbnail")])

    try:
        await message.reply_text(
            "**What would you like to do with this file?**\n\n"
            "Select an option below. You can use /cancel at any time to stop.",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    except Exception as e:
        print(f"Error in file handler: {e}")

@app.on_callback_query()
async def button_handler(client: Client, callback_query: CallbackQuery):
    """Handles button presses for rename and thumbnail actions."""
    user_id = callback_query.from_user.id
    action = callback_query.data

    user_state = get_user_state(user_id)
    if not user_state:
        await callback_query.answer("⚠️ This is an old message. Please send the file again.", show_alert=True)
        return

    try:
        if action == "rename":
            set_user_state(user_id, {**user_state, 'state': 'awaiting_rename'})
            await callback_query.message.edit_text("✍️ **Send me the new file name, including the extension.**\n\nExample: `My Awesome Video.mp4`")
        
        elif action == "set_thumbnail":
            set_user_state(user_id, {**user_state, 'state': 'awaiting_thumbnail'})
            await callback_query.message.edit_text("🖼️ **Please send me the photo you want to use as a thumbnail.**")
        
        await callback_query.answer()
    except Exception as e:
        print(f"Error in button handler: {e}")
        await callback_query.answer("❌ An error occurred. Please try again.", show_alert=True)

@app.on_message(filters.text & filters.private)
async def text_handler(client: Client, message: Message):
    """Handles text input for renaming files."""
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state or user_state.get('state') != 'awaiting_rename':
        # Not in rename state, ignore
        return
        
    new_filename = message.text
    status_msg = await message.reply_text("Processing...", quote=True)

    try:
        # Retrieve the original file message
        original_file_msg = await client.get_messages(user_state['chat_id'], user_state['file_message_id'])
        
        if not original_file_msg:
            await status_msg.edit_text("❌ Original file message not found. Please send the file again.")
            USER_DATA.pop(user_id, None)
            return
        
        # Download the file
        start_time = time.time()
        file_path = await original_file_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time, "Downloading")
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Failed to download the file.")
            USER_DATA.pop(user_id, None)
            return
        
        # Upload the file with the new name
        await status_msg.edit_text("⬆️ **Uploading file with new name...**")
        start_time_upload = time.time()

        # Choose the correct method to send based on file type
        if user_state['file_type'] == 'video' and original_file_msg.video:
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
        if os.path.exists(file_path):
            os.remove(file_path)
        USER_DATA.pop(user_id, None)
        
    except Exception as e:
        print(f"Error in text handler: {e}")
        await status_msg.edit_text("❌ An error occurred during processing. Please try again.")
        USER_DATA.pop(user_id, None)

@app.on_message(filters.photo & filters.private)
async def photo_handler(client: Client, message: Message):
    """Handles photo input for setting thumbnails."""
    user_id = message.from_user.id
    user_state = get_user_state(user_id)
    
    if not user_state or user_state.get('state') != 'awaiting_thumbnail':
        # Not in thumbnail state, ignore
        return
        
    status_msg = await message.reply_text("Processing...", quote=True)

    try:
        # Download the thumbnail
        thumbnail_path = await message.download(file_name=f"{user_id}_thumb.jpg")
        
        if not thumbnail_path:
            await status_msg.edit_text("❌ Failed to download the thumbnail.")
            USER_DATA.pop(user_id, None)
            return
        
        # Retrieve the original video message
        original_video_msg = await client.get_messages(user_state['chat_id'], user_state['file_message_id'])
        
        if not original_video_msg or not original_video_msg.video:
            await status_msg.edit_text("❌ Original video message not found or invalid.")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            USER_DATA.pop(user_id, None)
            return
        
        # Download the video
        await status_msg.edit_text("📥 **Downloading video...**")
        start_time_dl = time.time()
        video_path = await original_video_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time_dl, "Downloading")
        )
        
        if not video_path:
            await status_msg.edit_text("❌ Failed to download the video.")
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            USER_DATA.pop(user_id, None)
            return
        
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
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
        USER_DATA.pop(user_id, None)
        
    except Exception as e:
        print(f"Error in photo handler: {e}")
        await status_msg.edit_text("❌ An error occurred during processing. Please try again.")
        USER_DATA.pop(user_id, None)

# --- Startup and Shutdown ---
@app.on_start()
async def on_start(client: Client):
    """Run when the bot starts"""
    print("Bot is starting...")
    # Start the cleanup task
    asyncio.create_task(cleanup_states())

@app.on_stop()
async def on_stop(client: Client):
    """Run when the bot stops"""
    print("Bot has stopped.")

# --- Main execution ---
if __name__ == "__main__":
    try:
        print("Starting bot...")
        app.run()
    except Exception as e:
        print(f"Error running bot: {e}")
