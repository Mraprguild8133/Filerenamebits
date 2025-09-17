import os
import time
import asyncio
from datetime import datetime
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
PORT = int(os.environ.get("PORT", 5000))

# Verify credentials
if not all([API_ID, API_HASH, BOT_TOKEN]):
    print("❌ Error: Missing environment variables")
    exit(1)

# Bot initialization with optimized settings
app = Client(
    "power_speed_bot", 
    api_id=int(API_ID), 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN,
    workers=50,
    max_concurrent_transmissions=20
)

# Global variables
user_data = {}
bot_start_time = time.time()
transfer_stats = {
    'total_downloaded': 0,
    'total_uploaded': 0,
    'max_download_speed': 0,
    'max_upload_speed': 0
}

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

def create_progress_bar(percentage, length=20):
    """Create a visual progress bar"""
    filled = int(length * percentage / 100)
    empty = length - filled
    return f"█" * filled + f"░" * empty

async def update_progress(message, current, total, start_time, action):
    """Update progress with speed and ETA"""
    elapsed = time.time() - start_time
    speed = current / elapsed if elapsed > 0 else 0
    percentage = (current / total) * 100
    
    # Update stats
    if action == "Downloading":
        transfer_stats['total_downloaded'] += current
        transfer_stats['max_download_speed'] = max(transfer_stats['max_download_speed'], speed)
    else:
        transfer_stats['total_uploaded'] += current
        transfer_stats['max_upload_speed'] = max(transfer_stats['max_upload_speed'], speed)
    
    eta = (total - current) / speed if speed > 0 else 0
    
    progress_bar = create_progress_bar(percentage)
    
    progress_text = (
        f"🚀 **{action}** 🚀\n\n"
        f"`{progress_bar}` **{percentage:.1f}%**\n\n"
        f"⚡ **Speed:** `{humanbytes(speed)}/s`\n"
        f"📦 **Progress:** `{humanbytes(current)}` / `{humanbytes(total)}`\n"
        f"⏱️ **ETA:** `{time.strftime('%M:%S', time.gmtime(eta))}`\n"
        f"🕒 **Elapsed:** `{time.strftime('%M:%S', time.gmtime(elapsed))}`"
    )
    
    try:
        await message.edit_text(progress_text)
    except MessageNotModified:
        pass
    
    return speed

# Command handlers
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    uptime = time.time() - bot_start_time
    await message.reply_text(
        f"⚡ **POWER SPEED BOT** ⚡\n\n"
        f"✅ **Status:** Online\n"
        f"🕒 **Uptime:** `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"🌐 **Port:** `{PORT}`\n\n"
        f"**Features:**\n"
        f"• Lightning fast transfers\n"
        f"• Real-time speed metrics\n"
        f"• Custom file renaming\n"
        f"• Video thumbnail support\n\n"
        f"Send any file to experience extreme speed!",
        quote=True
    )

@app.on_message(filters.command("status") & filters.private)
async def status_handler(client, message):
    uptime = time.time() - bot_start_time
    await message.reply_text(
        f"📊 **BOT STATUS** 📊\n\n"
        f"✅ **Online:** Yes\n"
        f"🕒 **Uptime:** `{time.strftime('%H:%M:%S', time.gmtime(uptime))}`\n"
        f"🌐 **Port:** `{PORT}`\n"
        f"👥 **Active Users:** `{len(user_data)}`\n\n"
        f"📈 **Transfer Statistics:**\n"
        f"⬇️ **Total Downloaded:** `{humanbytes(transfer_stats['total_downloaded'])}`\n"
        f"⬆️ **Total Uploaded:** `{humanbytes(transfer_stats['total_uploaded'])}`\n"
        f"⚡ **Max Download Speed:** `{humanbytes(transfer_stats['max_download_speed'])}/s`\n"
        f"🚀 **Max Upload Speed:** `{humanbytes(transfer_stats['max_upload_speed'])}/s`"
    )

@app.on_message(filters.command("ping") & filters.private)
async def ping_handler(client, message):
    start_time = time.time()
    ping_msg = await message.reply_text("🏓 Pinging...")
    end_time = time.time()
    ping_time = (end_time - start_time) * 1000  # Convert to milliseconds
    
    await ping_msg.edit_text(
        f"🏓 **PONG!**\n"
        f"⏱️ **Response Time:** `{ping_time:.2f}ms`\n"
        f"✅ **Status:** Connected\n"
        f"🕒 **Server Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )

@app.on_message(filters.command("speedtest") & filters.private)
async def speedtest_handler(client, message):
    test_msg = await message.reply_text("🚀 Starting speed test...")
    
    # Create a test file
    test_size = 5 * 1024 * 1024  # 5MB test file
    test_content = os.urandom(test_size)
    
    with open("test_file.bin", "wb") as f:
        f.write(test_content)
    
    # Test upload speed
    start_time = time.time()
    await client.send_document(
        message.chat.id,
        "test_file.bin",
        caption="⚡ Speed Test File"
    )
    upload_time = time.time() - start_time
    upload_speed = test_size / upload_time
    
    # Test download speed
    start_time = time.time()
    await client.download_media(test_msg.document.file_id)
    download_time = time.time() - start_time
    download_speed = test_size / download_time
    
    # Cleanup
    if os.path.exists("test_file.bin"):
        os.remove("test_file.bin")
    
    await test_msg.edit_text(
        f"📊 **SPEED TEST RESULTS** 📊\n\n"
        f"⬆️ **Upload Speed:** `{humanbytes(upload_speed)}/s`\n"
        f"⬇️ **Download Speed:** `{humanbytes(download_speed)}/s`\n"
        f"⏱️ **Upload Time:** `{upload_time:.2f}s`\n"
        f"⏱️ **Download Time:** `{download_time:.2f}s`\n\n"
        f"✅ **Connection Quality:** Excellent"
    )

# File handler
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
    user_id = message.from_user.id
    
    file = message.video or message.document or message.audio
    file_size = file.file_size
    
    user_data[user_id] = {
        'message_id': message.id,
        'chat_id': message.chat.id,
        'file_type': 'video' if message.video else 'document',
        'file_size': file_size,
        'file_name': getattr(file, 'file_name', 'file'),
        'timestamp': time.time()
    }
    
    buttons = [
        [InlineKeyboardButton("⚡ Rename File", callback_data="rename")],
        [InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")] if message.video else []
    ]
    
    await message.reply_text(
        f"📁 **File Received** 📁\n\n"
        f"**Name:** `{user_data[user_id]['file_name']}`\n"
        f"**Size:** `{humanbytes(file_size)}`\n"
        f"**Type:** {'Video' if message.video else 'File'}\n\n"
        f"⚡ **Estimated Transfer Time:** `{time.strftime('%M:%S', time.gmtime(file_size / (10 * 1024 * 1024)))}`\n\n"
        "**Select action:**",
        reply_markup=InlineKeyboardMarkup(buttons),
        quote=True
    )

# Callback handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in user_data:
        await callback_query.answer("❌ Session expired. Send file again.", show_alert=True)
        return
    
    if data == "rename":
        user_data[user_id]['action'] = 'rename'
        await callback_query.message.edit_text("✍️ **Send new filename with extension:**\n\nExample: `my_file.mp4`")
    
    elif data == "set_thumbnail":
        user_data[user_id]['action'] = 'thumbnail'
        await callback_query.message.edit_text("🖼️ **Send photo for thumbnail:**")
    
    await callback_query.answer()

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('action') != 'rename':
        return
    
    new_filename = message.text.strip()
    user_info = user_data[user_id]
    
    status_msg = await message.reply_text("🚀 **Starting ultra-fast transfer...**")
    start_time = time.time()
    
    try:
        # Download with progress
        file_path = await client.download_media(
            message=await client.get_messages(user_info['chat_id'], user_info['message_id']),
            progress=update_progress,
            progress_args=(status_msg, 0, user_info['file_size'], start_time, "Downloading")
        )
        
        # Upload with progress
        if user_info['file_type'] == 'video':
            await client.send_video(
                chat_id=user_id,
                video=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                progress=update_progress,
                progress_args=(status_msg, 0, user_info['file_size'], start_time, "Uploading")
            )
        else:
            await client.send_document(
                chat_id=user_id,
                document=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                progress=update_progress,
                progress_args=(status_msg, 0, user_info['file_size'], start_time, "Uploading")
            )
        
        total_time = time.time() - start_time
        avg_speed = user_info['file_size'] / total_time
        
        await status_msg.edit_text(
            f"✅ **Transfer Complete!** ✅\n\n"
            f"📁 **File:** `{new_filename}`\n"
            f"⚡ **Average Speed:** `{humanbytes(avg_speed)}/s`\n"
            f"⏱️ **Total Time:** `{time.strftime('%M:%S', time.gmtime(total_time))}`\n"
            f"📦 **Size:** `{humanbytes(user_info['file_size'])}`"
        )
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
        del user_data[user_id]
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        if user_id in user_data:
            del user_data[user_id]

# Photo handler
@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_data or user_data[user_id].get('action') != 'thumbnail':
        return
    
    user_info = user_data[user_id]
    
    if user_info['file_type'] != 'video':
        await message.reply_text("❌ Thumbnails only for videos")
        return
    
    status_msg = await message.reply_text("🚀 **Processing thumbnail...**")
    
    try:
        thumb_path = await message.download()
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        
        # Download video
        video_path = await client.download_media(original_msg)
        
        # Upload with thumbnail
        await client.send_video(
            chat_id=user_id,
            video=video_path,
            thumb=thumb_path,
            caption="✅ **Custom thumbnail applied!**"
        )
        
        await status_msg.edit_text("✅ **Thumbnail applied successfully!**")
        
        # Cleanup
        for path in [video_path, thumb_path]:
            if os.path.exists(path):
                os.remove(path)
        del user_data[user_id]
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")
        if user_id in user_data:
            del user_data[user_id]

# Main execution
if __name__ == "__main__":
    print("🚀 Starting Power Speed Bot...")
    print(f"🌐 Running on port: {PORT}")
    print(f"✅ API ID: {API_ID}")
    print(f"✅ API HASH: {API_HASH}")
    print(f"✅ BOT TOKEN: {BOT_TOKEN[:15]}...")
    
    try:
        app.run()
        print("✅ Bot running successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")
