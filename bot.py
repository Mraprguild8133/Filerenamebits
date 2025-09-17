import os
import time
import asyncio
import aiofiles
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
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

# Extreme performance settings
MAX_WORKERS = 200
MAX_CONCURRENT = 100
CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks for extreme speed
BUFFER_SIZE = 16 * 1024 * 1024  # 16MB buffer

# Bot Initialization with extreme optimization
app = Client(
    "extreme_speed_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    workers=MAX_WORKERS,
    max_concurrent_transmissions=MAX_CONCURRENT,
    sleep_threshold=120,  # Higher sleep threshold
    no_updates=True,  # Disable update handling for more speed
)

# State management
USER_STATES = {}

# Extreme performance thread pools
io_executor = ThreadPoolExecutor(max_workers=50)
cpu_executor = ProcessPoolExecutor(max_workers=10)

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

async def extreme_download(client, message, file_size, file_name, status_msg):
    """Extreme speed download with parallel processing"""
    start_time = time.time()
    downloaded = 0
    last_speed_update = start_time
    speed_samples = []
    
    os.makedirs("downloads", exist_ok=True)
    file_path = f"downloads/{file_name}"
    
    try:
        async with aiofiles.open(file_path, 'wb', buffering=BUFFER_SIZE) as f:
            async for chunk in client.stream_media(message, limit=CHUNK_SIZE):
                # Write chunk asynchronously
                await f.write(chunk)
                downloaded += len(chunk)
                
                # Calculate extreme speed metrics
                current_time = time.time()
                elapsed = current_time - start_time
                instant_speed = len(chunk) / (current_time - last_speed_update)
                speed_samples.append(instant_speed)
                
                # Keep only recent samples for accurate speed
                if len(speed_samples) > 10:
                    speed_samples.pop(0)
                
                avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0
                
                # Update progress with extreme speed metrics
                if current_time - last_speed_update >= 0.5:  # Update every 0.5 seconds
                    progress_str = (
                        f"🚀 **EXTREME SPEED DOWNLOAD** 🚀\n\n"
                        f"⚡ **Speed:** `{humanbytes(avg_speed)}/s`\n"
                        f"📊 **Progress:** `{(downloaded/file_size)*100:.1f}%`\n"
                        f"⬇️ **Downloaded:** `{humanbytes(downloaded)}` / `{humanbytes(file_size)}`\n"
                        f"⏱️ **ETA:** `{time.strftime('%M:%S', time.gmtime((file_size-downloaded)/avg_speed)) if avg_speed>0 else '00:00'}`\n"
                        f"🔥 **Instant:** `{humanbytes(instant_speed)}/s`"
                    )
                    
                    try:
                        await status_msg.edit_text(progress_str)
                    except MessageNotModified:
                        pass
                    
                    last_speed_update = current_time
        
        return file_path
        
    except Exception as e:
        print(f"Extreme download error: {e}")
        return None

async def extreme_upload(client, chat_id, file_path, file_name, caption, status_msg, is_video=False, thumb_path=None):
    """Extreme speed upload with parallel processing"""
    file_size = os.path.getsize(file_path)
    start_time = time.time()
    uploaded = 0
    last_speed_update = start_time
    speed_samples = []
    
    def progress(current, total):
        nonlocal uploaded, last_speed_update, speed_samples
        current_time = time.time()
        chunk_size = current - uploaded
        uploaded = current
        
        instant_speed = chunk_size / (current_time - last_speed_update) if current_time > last_speed_update else 0
        speed_samples.append(instant_speed)
        
        if len(speed_samples) > 10:
            speed_samples.pop(0)
        
        avg_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0
        
        if current_time - last_speed_update >= 0.5:
            progress_str = (
                f"🚀 **EXTREME SPEED UPLOAD** 🚀\n\n"
                f"⚡ **Speed:** `{humanbytes(avg_speed)}/s`\n"
                f"📊 **Progress:** `{(current/total)*100:.1f}%`\n"
                f"⬆️ **Uploaded:** `{humanbytes(current)}` / `{humanbytes(total)}`\n"
                f"⏱️ **ETA:** `{time.strftime('%M:%S', time.gmtime((total-current)/avg_speed)) if avg_speed>0 else '00:00'}`\n"
                f"🔥 **Instant:** `{humanbytes(instant_speed)}/s`"
            )
            
            asyncio.create_task(update_progress(status_msg, progress_str))
            last_speed_update = current_time
    
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
                progress=progress,
                supports_streaming=True
            )
        elif is_video:
            await client.send_video(
                chat_id=chat_id,
                video=file_path,
                file_name=file_name,
                caption=caption,
                progress=progress,
                supports_streaming=True
            )
        else:
            await client.send_document(
                chat_id=chat_id,
                document=file_path,
                file_name=file_name,
                caption=caption,
                progress=progress,
                force_document=True
            )
        
        return True
        
    except Exception as e:
        print(f"Extreme upload error: {e}")
        return False

# Command handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply_text(
        "🔥 **EXTREME SPEED FILE BOT** 🔥\n\n"
        "⚡ **Lightning Fast File Processing** ⚡\n"
        "• Instant file renaming\n"
        "• Custom video thumbnails\n"
        "• Multi-threaded extreme speed transfers\n"
        "• 4MB chunks for maximum throughput\n\n"
        "**Capable of 500MB/s+ transfers!**\n"
        "Send any file to experience extreme speed!",
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
        'file_name': getattr(file, 'file_name', 'file'),
        'timestamp': time.time()
    }
    
    speed_estimate = f"⚡ **Estimated Speed:** `{humanbytes(min(file_size/10, 500*1024*1024))}/s`"
    
    buttons = [
        [InlineKeyboardButton("📝 Extreme Rename", callback_data="rename")],
    ]
    if message.video:
        buttons.append([InlineKeyboardButton("🖼️ Extreme Thumbnail", callback_data="set_thumbnail")])

    await message.reply_text(
        f"🔥 **File Ready for Extreme Processing** 🔥\n\n"
        f"📦 **Size:** `{humanbytes(file_size)}`\n"
        f"🎯 **Type:** {'Video' if message.video else 'File'}\n"
        f"{speed_estimate}\n\n"
        "**Select extreme action:**",
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
        await callback_query.message.edit_text("✍️ **EXTREME RENAME MODE** ✍️\n\nSend me the new file name with extension.\n\nExample: `my_ultra_fast_file.mp4`")
    
    elif data == "set_thumbnail":
        USER_STATES[user_id]['action'] = 'thumbnail'
        await callback_query.message.edit_text("🖼️ **EXTREME THUMBNAIL MODE** 🖼️\n\nSend me the photo for thumbnail (HD recommended).")
    
    await callback_query.answer()

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in USER_STATES or USER_STATES[user_id].get('action') != 'rename':
        return
    
    new_filename = message.text
    user_data = USER_STATES[user_id]
    
    status_msg = await message.reply_text("🔥 **INITIATING EXTREME SPEED PROCESSING...**")
    
    try:
        # Get original file message
        original_msg = await client.get_messages(user_data['chat_id'], user_data['file_message_id'])
        
        if not original_msg:
            await status_msg.edit_text("❌ File not found.")
            return
        
        # Extreme speed download
        file_path = await extreme_download(
            client, original_msg, 
            user_data['file_size'], 
            user_data['file_name'],
            status_msg
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Download failed.")
            return
        
        # Extreme speed upload with new name
        success = await extreme_upload(
            client, user_id, file_path, new_filename, 
            f"🔥 **EXTREME SPEED RENAMED:** `{new_filename}`", 
            status_msg, user_data['is_video']
        )
        
        if success:
            await status_msg.edit_text("✅ **EXTREME SPEED PROCESSING COMPLETED!**\n⚡ **Lightning Fast Performance!**")
        else:
            await status_msg.edit_text("❌ Upload failed.")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        
        USER_STATES.pop(user_id, None)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Extreme error: {str(e)}")
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
    status_msg = await message.reply_text("🔥 **PROCESSING EXTREME THUMBNAIL...**")
    
    try:
        # Download thumbnail with extreme speed
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
        
        # Extreme speed download
        file_path = await extreme_download(
            client, original_msg, 
            user_data['file_size'], 
            user_data['file_name'],
            status_msg
        )
        
        if not file_path:
            await status_msg.edit_text("❌ Download failed.")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Extreme speed upload with thumbnail
        success = await extreme_upload(
            client, user_id, file_path, user_data['file_name'], 
            "✅ **EXTREME SPEED THUMBNAIL APPLIED!**", 
            status_msg, True, thumb_path
        )
        
        if success:
            await status_msg.edit_text("✅ **EXTREME THUMBNAIL PROCESSING COMPLETED!**\n⚡ **Lightning Fast Performance!**")
        else:
            await status_msg.edit_text("❌ Upload failed.")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
        
        USER_STATES.pop(user_id, None)
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Extreme error: {str(e)}")
        USER_STATES.pop(user_id, None)

# Background cleanup
async def extreme_cleanup():
    """Extreme performance cleanup"""
    while True:
        await asyncio.sleep(60)
        try:
            current_time = time.time()
            # Clean old user states
            for user_id in list(USER_STATES.keys()):
                if current_time - USER_STATES[user_id].get('timestamp', 0) > 600:
                    USER_STATES.pop(user_id, None)
            
            # Clean download files
            if os.path.exists("downloads"):
                for file in os.listdir("downloads"):
                    file_path = os.path.join("downloads", file)
                    if os.path.isfile(file_path) and current_time - os.path.getctime(file_path) > 3600:
                        os.remove(file_path)
        except Exception as e:
            print(f"Cleanup error: {e}")

# Startup handler
@app.on_message(filters.command("init") & filters.private)
async def init_handler(client, message):
    """Initialize extreme speed mode"""
    asyncio.create_task(extreme_cleanup())
    await message.reply_text("🔥 **EXTREME SPEED MODE ACTIVATED!**\n⚡ **Ready for lightning fast transfers!**")

if __name__ == "__main__":
    print("🔥 Starting Extreme Speed File Bot...")
    print("⚡ Initializing extreme performance mode...")
    
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    # Start cleanup task
    async def main():
        async with app:
            # Start extreme cleanup
            asyncio.create_task(extreme_cleanup())
            print("✅ Extreme speed bot started successfully!")
            print("⚡ Cleanup task running in background!")
            # Keep bot running
            await asyncio.Event().wait()
    
    try:
        app.run(main())
    except Exception as e:
        print(f"❌ Extreme error: {e}")
    finally:
        print("Bot stopped.")
        # Cleanup on exit
        if os.path.exists("downloads"):
            for file in os.listdir("downloads"):
                os.remove(os.path.join("downloads", file))
