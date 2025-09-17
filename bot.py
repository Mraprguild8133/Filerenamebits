import os
import time
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

# Load environment variables
load_dotenv()

# Configuration
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Verify credentials
if not all([API_ID, API_HASH, BOT_TOKEN]):
    print("❌ Error: Missing environment variables. Please check your .env file")
    print(f"API_ID: {API_ID}")
    print(f"API_HASH: {API_HASH}")
    print(f"BOT_TOKEN: {BOT_TOKEN}")
    exit(1)

# Simple bot initialization
app = Client("file_bot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

# User state management
user_data = {}

def humanbytes(size):
    """Convert bytes to human readable format"""
    if not size:
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
    await message.reply_text(
        "🤖 **File Manager Bot**\n\n"
        "Send me any file and I can:\n"
        "• Rename files\n"
        "• Set custom thumbnails for videos\n\n"
        "Use /cancel to stop any operation.",
        quote=True
    )
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client, message):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.reply_text("✅ Operation cancelled.", quote=True)
    else:
        await message.reply_text("🤔 Nothing to cancel.", quote=True)

@app.on_message(filters.command("status") & filters.private)
async def status_handler(client, message):
    await message.reply_text("✅ Bot is running and ready!", quote=True)

# File handler
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
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
    
    user_data[user_id] = {
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
        f"**Name:** `{user_data[user_id]['file_name']}`\n"
        f"**Size:** `{humanbytes(file.file_size)}`\n"
        f"**Type:** {file_type.title()}\n\n"
        "What would you like to do?",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

# Callback handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in user_data:
        await callback_query.answer("❌ Session expired. Send the file again.", show_alert=True)
        return
    
    if data == "rename":
        user_data[user_id]['action'] = 'rename'
        await callback_query.message.edit_text("✍️ Please send me the new file name (with extension):\n\nExample: `my_file.mp4`")
    
    elif data == "set_thumbnail":
        user_data[user_id]['action'] = 'thumbnail'
        await callback_query.message.edit_text("🖼️ Please send me a photo to use as thumbnail")
    
    await callback_query.answer()

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('action') != 'rename':
        return
    
    new_filename = message.text.strip()
    user_info = user_data[user_id]
    
    status_msg = await message.reply_text("⏳ Downloading file...")
    
    try:
        # Get original message
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        if not original_msg:
            await status_msg.edit_text("❌ Original file not found.")
            return
        
        # Download file
        file_path = await original_msg.download()
        if not file_path:
            await status_msg.edit_text("❌ Failed to download file.")
            return
        
        await status_msg.edit_text("⏳ Uploading with new name...")
        
        # Upload with new name
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
        del user_data[user_id]
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        if user_id in user_data:
            del user_data[user_id]

# Photo handler for thumbnails
@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('action') != 'thumbnail':
        return
    
    user_info = user_data[user_id]
    
    if user_info['file_type'] != 'video':
        await message.reply_text("❌ Thumbnails can only be set for videos.")
        if user_id in user_data:
            del user_data[user_id]
        return
    
    status_msg = await message.reply_text("⏳ Processing thumbnail...")
    
    try:
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
        video_path = await original_msg.download()
        if not video_path:
            await status_msg.edit_text("❌ Failed to download video.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        await status_msg.edit_text("⏳ Uploading with new thumbnail...")
        
        # Upload with thumbnail
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
        if user_id in user_data:
            del user_data[user_id]
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        if user_id in user_data:
            del user_data[user_id]

# Main execution
if __name__ == "__main__":
    print("🤖 Starting File Manager Bot...")
    print("✅ Checking environment variables...")
    print(f"📋 API_ID: {API_ID}")
    print(f"📋 API_HASH: {API_HASH}")
    print(f"📋 BOT_TOKEN: {BOT_TOKEN[:10]}...")  # Show only first 10 chars of token for security
    
    try:
        print("🚀 Starting bot...")
        app.run()
        print("✅ Bot started successfully!")
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        print("💡 Troubleshooting tips:")
        print("1. Check if your API_ID, API_HASH, and BOT_TOKEN are correct")
        print("2. Make sure your bot token is valid and you've started the bot with @BotFather")
        print("3. Check your internet connection")
        print("4. Verify that pyrogram is installed: pip install pyrogram")
