import os
import time
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import MessageNotModified

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Bot Initialization
app = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Simple state management
USER_STATES = {}

# Helper function to convert bytes to human readable format
def humanbytes(size):
    if not size:
        return "0B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

async def progress_callback(current, total, message, start_time, action):
    try:
        now = time.time()
        diff = now - start_time
        
        if round(diff % 5.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff if diff > 0 else 0
            elapsed_time = round(diff)
            eta = round((total - current) / speed) if speed > 0 else 0
            
            filled_length = int(20 * percentage / 100)
            progress_bar = '█' * filled_length + ' ' * (20 - filled_length)
            
            progress_str = (
                f"**{action} Progress**\n"
                f"`[{progress_bar}] {percentage:.2f}%`\n\n"
                f"**Done:** `{humanbytes(current)}` of `{humanbytes(total)}`\n"
                f"**Speed:** `{humanbytes(speed)}/s`\n"
                f"**ETA:** `{time.strftime('%H:%M:%S', time.gmtime(eta))}`"
            )
            
            try:
                await message.edit_text(progress_str)
            except MessageNotModified:
                pass
    except Exception as e:
        print(f"Progress error: {e}")

# Command handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply_text(
        "👋 **Hello! I am your File Manager Bot.**\n\n"
        "Send me any file, and I will help you manage it.\n"
        "I can rename files and apply custom thumbnails to videos.\n\n"
        "Use /cancel at any time to cancel the current operation.",
        quote=True
    )
    USER_STATES.pop(message.from_user.id, None)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message):
    user_id = message.from_user.id
    if user_id in USER_STATES:
        USER_STATES.pop(user_id)
        await message.reply_text("✅ Operation cancelled.", quote=True)
    else:
        await message.reply_text("🤔 Nothing to cancel.", quote=True)

# File handler
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
    user_id = message.from_user.id
    
    USER_STATES[user_id] = {
        'file_message_id': message.id,
        'chat_id': message.chat.id,
        'is_video': bool(message.video)
    }
    
    buttons = [
        [InlineKeyboardButton("📝 Rename File", callback_data="rename")],
    ]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        "**What would you like to do with this file?**\n\n"
        "Select an option below:",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

# Callback query handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in USER_STATES:
        await callback_query.answer("Session expired. Send file again.", show_alert=True)
        return
    
    if data == "rename":
        USER_STATES[user_id]['action'] = 'rename'
        await callback_query.message.edit_text("✍️ Send me the new file name with extension.\n\nExample: `my_file.mp4`")
    
    elif data == "set_thumbnail":
        USER_STATES[user_id]['action'] = 'thumbnail'
        await callback_query.message.edit_text("🖼️ Send me the photo for thumbnail.")
    
    await callback_query.answer()

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in USER_STATES or USER_STATES[user_id].get('action') != 'rename':
        return
    
    new_filename = message.text
    user_data = USER_STATES[user_id]
    
    status_msg = await message.reply_text("🔄 Processing...")
    
    try:
        # Get original file message
        original_msg = await client.get_messages(user_data['chat_id'], user_data['file_message_id'])
        
        if not original_msg:
            await status_msg.edit_text("❌ File not found.")
            return
        
        # Download file
        start_time = time.time()
        file_path = await original_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time, "Downloading")
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Download failed.")
            return
        
        # Upload with new name
        await status_msg.edit_text("⬆️ Uploading...")
        start_time_upload = time.time()
        
        if user_data['is_video']:
            await client.send_video(
                chat_id=user_id,
                video=file_path,
                file_name=new_filename,
                caption=f"**Renamed:** `{new_filename}`",
                progress=progress_callback,
                progress_args=(status_msg, start_time_upload, "Uploading")
            )
        else:
            await client.send_document(
                chat_id=user_id,
                document=file_path,
                file_name=new_filename,
                caption=f"**Renamed:** `{new_filename}`",
                progress=progress_callback,
                progress_args=(status_msg, start_time_upload, "Uploading")
            )
        
        await status_msg.delete()
        if os.path.exists(file_path):
            os.remove(file_path)
        
        USER_STATES.pop(user_id, None)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        USER_STATES.pop(user_id, None)

# Photo handler for thumbnails
@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in USER_STATES or USER_STATES[user_id].get('action') != 'thumbnail':
        return
    
    if not USER_STATES[user_id]['is_video']:
        await message.reply_text("❌ Thumbnails only work for videos.")
        USER_STATES.pop(user_id, None)
        return
    
    user_data = USER_STATES[user_id]
    status_msg = await message.reply_text("🔄 Processing...")
    
    try:
        # Download thumbnail
        thumb_path = await message.download(f"{user_id}_thumb.jpg")
        
        # Get original video
        original_msg = await client.get_messages(user_data['chat_id'], user_data['file_message_id'])
        
        if not original_msg or not original_msg.video:
            await status_msg.edit_text("❌ Video not found.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Download video
        start_time = time.time()
        video_path = await original_msg.download(
            progress=progress_callback,
            progress_args=(status_msg, start_time, "Downloading")
        )
        
        # Upload with new thumbnail
        await status_msg.edit_text("⬆️ Uploading with thumbnail...")
        start_time_upload = time.time()
        
        await client.send_video(
            chat_id=user_id,
            video=video_path,
            thumb=thumb_path,
            caption="✅ Thumbnail applied!",
            progress=progress_callback,
            progress_args=(status_msg, start_time_upload, "Uploading")
        )
        
        await status_msg.delete()
        
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        USER_STATES.pop(user_id, None)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        USER_STATES.pop(user_id, None)

# Cleanup function
async def cleanup_states():
    while True:
        await asyncio.sleep(60)
        current_time = time.time()
        # Simple cleanup - remove states older than 10 minutes
        for user_id in list(USER_STATES.keys()):
            if 'timestamp' in USER_STATES[user_id]:
                if current_time - USER_STATES[user_id]['timestamp'] > 600:
                    USER_STATES.pop(user_id, None)

# Main function
async def main():
    async with app:
        # Start cleanup task
        asyncio.create_task(cleanup_states())
        print("Bot started successfully!")
        # Keep the bot running
        await asyncio.Event().wait()

if __name__ == "__main__":
    print("Starting bot...")
    try:
        app.run()
    except Exception as e:
        print(f"Error: {e}")
