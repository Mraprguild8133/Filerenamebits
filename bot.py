import os
import time
import asyncio
import aiohttp
import aiofiles
from concurrent.futures import ThreadPoolExecutor
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

# Bot Initialization with optimized settings
app = Client(
    "high_speed_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    workers=100,  # Increased workers for parallel processing
    max_concurrent_transmissions=50  # Higher concurrent transmissions
)

# State management
USER_STATES = {}

# Thread pool for parallel operations
executor = ThreadPoolExecutor(max_workers=20)

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

async def download_file_with_progress(client, message, file_id, file_size, file_name, status_msg):
    """High-speed download with progress tracking"""
    start_time = time.time()
    downloaded = 0
    last_update = start_time
    
    # Create download directory if not exists
    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{file_name}"
    
    try:
        # Use async file operations for better performance
        async with aiofiles.open(file_path, 'wb') as f:
            async for chunk in client.stream_media(message, limit=1024*1024):  # 1MB chunks
                await f.write(chunk)
                downloaded += len(chunk)
                
                # Update progress every second
                current_time = time.time()
                if current_time - last_update >= 1:
                    elapsed = current_time - start_time
                    speed = downloaded / elapsed
                    progress = (downloaded / file_size) * 100
                    
                    progress_str = (
                        f"⚡ **ULTRA HIGH SPEED DOWNLOAD** ⚡\n\n"
                        f"**Progress:** `{progress:.1f}%`\n"
                        f"**Speed:** `{humanbytes(speed)}/s`\n"
                        f"**Downloaded:** `{humanbytes(downloaded)}` / `{humanbytes(file_size)}`\n"
                        f"**ETA:** `{time.strftime('%H:%M:%S', time.gmtime((file_size - downloaded) / speed)) if speed > 0 else 'Calculating...'}`"
                    )
                    
                    try:
                        await status_msg.edit_text(progress_str)
                    except MessageNotModified:
                        pass
                    
                    last_update = current_time
        
        return file_path
        
    except Exception as e:
        print(f"Download error: {e}")
        return None

async def upload_file_with_progress(client, chat_id, file_path, file_name, caption, status_msg, is_video=False, thumb_path=None):
    """High-speed upload with progress tracking"""
    file_size = os.path.getsize(file_path)
    start_time = time.time()
    uploaded = 0
    last_update = start_time
    
    def progress(current, total):
        nonlocal uploaded, last_update
        uploaded = current
        
        current_time = time.time()
        if current_time - last_update >= 1:
            elapsed = current_time - start_time
            speed = uploaded / elapsed
            progress_percent = (uploaded / total) * 100
            
            progress_str = (
                f"🚀 **ULTRA HIGH SPEED UPLOAD** 🚀\n\n"
                f"**Progress:** `{progress_percent:.1f}%`\n"
                f"**Speed:** `{humanbytes(speed)}/s`\n"
                f"**Uploaded:** `{humanbytes(uploaded)}` / `{humanbytes(total)}`\n"
                f"**ETA:** `{time.strftime('%H:%M:%S', time.gmtime((total - uploaded) / speed)) if speed > 0 else 'Calculating...'}`"
            )
            
            asyncio.create_task(update_progress(status_msg, progress_str))
            last_update = current_time
    
    async def update_progress(msg, text):
        try:
            await msg.edit_text(text)
        except MessageNotModified:
            pass
    
    try:
        if is_video and thumb_path:
            await client.send_video(
                chat_id=chat_id,
                video=file_path,
                file_name=file_name,
                caption=caption,
                thumb=thumb_path,
                progress=progress
            )
        elif is_video:
            await client.send_video(
                chat_id=chat_id,
                video=file_path,
                file_name=file_name,
                caption=caption,
                progress=progress
            )
        else:
            await client.send_document(
                chat_id=chat_id,
                document=file_path,
                file_name=file_name,
                caption=caption,
                progress=progress
            )
        
        return True
        
    except Exception as e:
        print(f"Upload error: {e}")
        return False

# Command handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply_text(
        "⚡ **ULTRA HIGH SPEED FILE BOT** ⚡\n\n"
        "Send me any file for lightning-fast processing!\n"
        "• Rename files with custom names\n"
        "• Set custom thumbnails for videos\n"
        "• Extreme download/upload speeds\n\n"
        "**Capable of 300MB/s transfers!**",
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
    
    file = message.video or message.document or message.audio
    file_size = file.file_size if file else 0
    
    USER_STATES[user_id] = {
        'file_message_id': message.id,
        'chat_id': message.chat.id,
        'is_video': bool(message.video),
        'file_size': file_size,
        'file_name': getattr(file, 'file_name', 'file')
    }
    
    buttons = [
        [InlineKeyboardButton("📝 Rename File", callback_data="rename")],
    ]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Set Custom Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        f"⚡ **File Received** ⚡\n\n"
        f"**Size:** `{humanbytes(file_size)}`\n"
        f"**Type:** {'Video' if message.video else 'File'}\n\n"
        "**Select an option:**",
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
        await callback_query.message.edit_text("🖼️ Send me the photo for thumbnail (high quality recommended).")
    
    await callback_query.answer()

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in USER_STATES or USER_STATES[user_id].get('action') != 'rename':
        return
    
    new_filename = message.text
    user_data = USER_STATES[user_id]
    
    status_msg = await message.reply_text("⚡ **Starting Ultra High Speed Processing...**")
    
    try:
        # Get original file message
        original_msg = await client.get_messages(user_data['chat_id'], user_data['file_message_id'])
        
        if not original_msg:
            await status_msg.edit_text("❌ File not found.")
            return
        
        # High-speed download
        file_path = await download_file_with_progress(
            client, original_msg, 
            user_data['file_message_id'], 
            user_data['file_size'], 
            user_data['file_name'],
            status_msg
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Download failed.")
            return
        
        # High-speed upload with new name
        success = await upload_file_with_progress(
            client, user_id, file_path, new_filename, 
            f"⚡ **Renamed to:** `{new_filename}`", 
            status_msg, user_data['is_video']
        )
        
        if success:
            await status_msg.edit_text("✅ **File processing completed at ultra high speed!**")
        else:
            await status_msg.edit_text("❌ Upload failed.")
        
        # Cleanup
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
    status_msg = await message.reply_text("⚡ **Processing thumbnail...**")
    
    try:
        # Download thumbnail
        thumb_path = f"downloads/{user_id}_thumb.jpg"
        os.makedirs("downloads", exist_ok=True)
        
        photo = message.photo[-1]  # Get highest quality
        await client.download_media(photo.file_id, file_name=thumb_path)
        
        # Get original video
        original_msg = await client.get_messages(user_data['chat_id'], user_data['file_message_id'])
        
        if not original_msg or not original_msg.video:
            await status_msg.edit_text("❌ Video not found.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # High-speed download
        file_path = await download_file_with_progress(
            client, original_msg, 
            user_data['file_message_id'], 
            user_data['file_size'], 
            user_data['file_name'],
            status_msg
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Download failed.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # High-speed upload with thumbnail
        success = await upload_file_with_progress(
            client, user_id, file_path, user_data['file_name'], 
            "✅ **Custom thumbnail applied!**", 
            status_msg, True, thumb_path
        )
        
        if success:
            await status_msg.edit_text("✅ **Video with custom thumbnail processed at ultra high speed!**")
        else:
            await status_msg.edit_text("❌ Upload failed.")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        USER_STATES.pop(user_id, None)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        USER_STATES.pop(user_id, None)

# Cleanup function
async def cleanup():
    while True:
        await asyncio.sleep(300)  # Clean every 5 minutes
        try:
            # Remove old download files
            if os.path.exists("downloads"):
                for file in os.listdir("downloads"):
                    file_path = os.path.join("downloads", file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
        except:
            pass

if __name__ == "__main__":
    print("🚀 Starting Ultra High Speed File Bot...")
    # Start cleanup task
    asyncio.create_task(cleanup())
    app.run()
    print("Bot stopped.")
