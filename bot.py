import os
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import MessageNotModified

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Verify credentials
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("Missing environment variables")
    exit(1)

# Initialize bot
app = Client("file_bot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# User state management
user_states = {}

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size or size == 0:
        return "0B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}"

# Command handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        await message.reply_text(
            "🤖 **File Manager Bot**\n\n"
            "Send me any file to:\n"
            "• Rename files\n"
            "• Set custom thumbnails for videos\n\n"
            "Use /cancel to stop any operation.",
            quote=True
        )
        user_id = message.from_user.id
        if user_id in user_states:
            del user_states[user_id]
    except Exception as e:
        logger.error(f"Start handler error: {e}")

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message):
    try:
        user_id = message.from_user.id
        if user_id in user_states:
            del user_states[user_id]
            await message.reply_text("✅ Operation cancelled.", quote=True)
        else:
            await message.reply_text("🤔 Nothing to cancel.", quote=True)
    except Exception as e:
        logger.error(f"Cancel handler error: {e}")

@app.on_message(filters.command("status") & filters.private)
async def status_handler(client, message):
    try:
        await message.reply_text(
            "✅ **Bot Status:** Online\n"
            "🚀 **Ready to process files**\n"
            "📁 Send any file to get started!",
            quote=True
        )
    except Exception as e:
        logger.error(f"Status handler error: {e}")

# File handler
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
    try:
        user_id = message.from_user.id
        
        # Get file info
        if message.video:
            file = message.video
            file_type = "video"
        elif message.document:
            file = message.document
            file_type = "document"
        elif message.audio:
            file = message.audio
            file_type = "audio"
        else:
            return
        
        user_states[user_id] = {
            'message_id': message.id,
            'chat_id': message.chat.id,
            'file_type': file_type,
            'file_size': file.file_size,
            'file_name': getattr(file, 'file_name', 'file')
        }
        
        # Create buttons
        buttons = [[InlineKeyboardButton("📝 Rename File", callback_data="rename")]]
        if file_type == "video":
            buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])
        
        await message.reply_text(
            f"📁 **File Received**\n\n"
            f"**Name:** `{user_states[user_id]['file_name']}`\n"
            f"**Size:** `{humanbytes(file.file_size)}`\n"
            f"**Type:** {file_type.title()}\n\n"
            "What would you like to do?",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
        
    except Exception as e:
        logger.error(f"File handler error: {e}")
        await message.reply_text("❌ Error processing file. Please try again.")

# Callback handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    try:
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        if user_id not in user_states:
            await callback_query.answer("❌ Session expired. Send file again.", show_alert=True)
            return
        
        if data == "rename":
            user_states[user_id]['action'] = 'rename'
            await callback_query.message.edit_text(
                "✍️ Please send me the new file name (with extension):\n\n"
                "Example: `my_file.mp4`\n"
                "Use /cancel to stop."
            )
        
        elif data == "set_thumbnail":
            user_states[user_id]['action'] = 'thumbnail'
            await callback_query.message.edit_text(
                "🖼️ Please send me a photo to use as thumbnail\n"
                "Use /cancel to stop."
            )
        
        await callback_query.answer()
        
    except Exception as e:
        logger.error(f"Callback handler error: {e}")
        await callback_query.answer("❌ Error processing request", show_alert=True)

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_states or user_states[user_id].get('action') != 'rename':
            return
        
        new_filename = message.text.strip()
        if not new_filename:
            await message.reply_text("❌ Please provide a valid filename")
            return
            
        user_info = user_states[user_id]
        status_msg = await message.reply_text("⏳ Processing your file...")
        
        # Get original message
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        if not original_msg:
            await status_msg.edit_text("❌ Original file not found.")
            return
        
        # Download file
        await status_msg.edit_text("📥 Downloading file...")
        file_path = await original_msg.download()
        
        if not file_path:
            await status_msg.edit_text("❌ Failed to download file.")
            return
        
        # Upload with new name
        await status_msg.edit_text("📤 Uploading with new name...")
        
        if user_info['file_type'] == 'video':
            await client.send_video(
                chat_id=user_id,
                video=file_path,
                file_name=new_filename,
                caption=f"📁 **Renamed to:** `{new_filename}`"
            )
        else:
            await client.send_document(
                chat_id=user_id,
                document=file_path,
                file_name=new_filename,
                caption=f"📁 **Renamed to:** `{new_filename}`"
            )
        
        await status_msg.edit_text("✅ File renamed successfully!")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        del user_states[user_id]
        
    except Exception as e:
        logger.error(f"Text handler error: {e}")
        try:
            await message.reply_text("❌ Error during file processing. Please try again.")
        except:
            pass
        if user_id in user_states:
            del user_states[user_id]

# Photo handler for thumbnails
@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_states or user_states[user_id].get('action') != 'thumbnail':
            return
        
        user_info = user_states[user_id]
        
        if user_info['file_type'] != 'video':
            await message.reply_text("❌ Thumbnails can only be set for videos.")
            del user_states[user_id]
            return
        
        status_msg = await message.reply_text("⏳ Processing thumbnail...")
        
        # Download thumbnail
        thumb_path = await message.download()
        if not thumb_path:
            await status_msg.edit_text("❌ Failed to download thumbnail.")
            return
        
        # Get original video
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        if not original_msg or not hasattr(original_msg, 'video'):
            await status_msg.edit_text("❌ Original video not found.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Download video
        await status_msg.edit_text("📥 Downloading video...")
        video_path = await original_msg.download()
        if not video_path:
            await status_msg.edit_text("❌ Failed to download video.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Upload with thumbnail
        await status_msg.edit_text("📤 Uploading with thumbnail...")
        await client.send_video(
            chat_id=user_id,
            video=video_path,
            thumb=thumb_path,
            caption="✅ Custom thumbnail applied!"
        )
        
        await status_msg.edit_text("✅ Thumbnail applied successfully!")
        
        # Cleanup
        for path in [video_path, thumb_path]:
            if os.path.exists(path):
                os.remove(path)
        del user_states[user_id]
        
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        try:
            await message.reply_text("❌ Error processing thumbnail. Please try again.")
        except:
            pass
        if user_id in user_states:
            del user_states[user_id]

# Error handler for unhandled exceptions
@app.on_errors()
async def error_handler(client, error):
    logger.error(f"Unhandled error: {error}")

# Main execution
if __name__ == "__main__":
    print("🤖 Starting File Manager Bot...")
    print("✅ Checking environment variables...")
    
    try:
        print("🚀 Starting bot...")
        app.run()
        print("✅ Bot started successfully!")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        print("💡 Troubleshooting tips:")
        print("1. Check your API_ID, API_HASH, and BOT_TOKEN")
        print("2. Make sure your bot token is valid")
        print("3. Check your internet connection")
    finally:
        print("🛑 Bot stopped")
