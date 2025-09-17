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

# Bot initialization
app = Client(
    "power_speed_bot", 
    api_id=int(API_ID), 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN
)

# Global variables
user_data = {}
bot_start_time = time.time()
transfer_stats = {
    'total_downloaded': 0,
    'total_uploaded': 0,
    'max_download_speed': 0,
    'max_upload_speed': 0,
    'transfers_completed': 0
}

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

def create_progress_bar(percentage, length=20):
    """Create a visual progress bar"""
    filled = min(int(length * percentage / 100), length)
    empty = length - filled
    return f"█" * filled + f"░" * empty

async def update_progress(current, total, message, start_time, action):
    """Update progress with speed and ETA"""
    try:
        elapsed = time.time() - start_time
        speed = current / elapsed if elapsed > 0 else 0
        percentage = (current / total) * 100 if total > 0 else 0
        
        # Update stats
        if action == "Downloading":
            transfer_stats['max_download_speed'] = max(transfer_stats['max_download_speed'], speed)
        else:
            transfer_stats['max_upload_speed'] = max(transfer_stats['max_upload_speed'], speed)
        
        eta = (total - current) / speed if speed > 0 and total > current else 0
        
        progress_bar = create_progress_bar(percentage)
        
        progress_text = (
            f"🚀 **{action}** 🚀\n\n"
            f"`{progress_bar}` **{percentage:.1f}%**\n\n"
            f"⚡ **Speed:** `{humanbytes(speed)}/s`\n"
            f"📦 **Progress:** `{humanbytes(current)}` / `{humanbytes(total)}`\n"
            f"⏱️ **ETA:** `{time.strftime('%M:%S', time.gmtime(eta)) if eta > 0 else '00:00'}`\n"
            f"🕒 **Elapsed:** `{time.strftime('%M:%S', time.gmtime(elapsed))}`"
        )
        
        try:
            await message.edit_text(progress_text)
        except MessageNotModified:
            pass
        
        return speed
    except Exception as e:
        print(f"Progress error: {e}")
        return 0

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
        f"👥 **Active Users:** `{len(user_data)}`\n"
        f"📤 **Transfers Completed:** `{transfer_stats['transfers_completed']}`\n\n"
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
    ping_time = (end_time - start_time) * 1000
    
    await ping_msg.edit_text(
        f"🏓 **PONG!**\n"
        f"⏱️ **Response Time:** `{ping_time:.2f}ms`\n"
        f"✅ **Status:** Connected\n"
        f"🕒 **Server Time:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`"
    )

@app.on_message(filters.command("clean") & filters.private)
async def clean_handler(client, message):
    """Clean temporary files"""
    cleaned = 0
    if os.path.exists("downloads"):
        for file in os.listdir("downloads"):
            try:
                os.remove(os.path.join("downloads", file))
                cleaned += 1
            except:
                pass
    await message.reply_text(f"🧹 Cleaned {cleaned} temporary files")

# File handler
@app.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def file_handler(client, message):
    try:
        user_id = message.from_user.id
        
        file = message.video or message.document or message.audio
        if not file:
            return
            
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
        ]
        if message.video:
            buttons.append([InlineKeyboardButton("🖼️ Set Thumbnail", callback_data="set_thumbnail")])
        
        await message.reply_text(
            f"📁 **File Received** 📁\n\n"
            f"**Name:** `{user_data[user_id]['file_name']}`\n"
            f"**Size:** `{humanbytes(file_size)}`\n"
            f"**Type:** {'Video' if message.video else 'File'}\n\n"
            "**Select action:**",
            reply_markup=InlineKeyboardMarkup(buttons),
            quote=True
        )
    except Exception as e:
        print(f"File handler error: {e}")
        await message.reply_text("❌ Error processing file")

# Callback handler
@app.on_callback_query()
async def callback_handler(client, callback_query):
    try:
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
    except Exception as e:
        print(f"Callback error: {e}")
        await callback_query.answer("❌ Error processing request", show_alert=True)

# Text handler for rename
@app.on_message(filters.text & filters.private)
async def text_handler(client, message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_data or user_data[user_id].get('action') != 'rename':
            return
        
        new_filename = message.text.strip()
        if not new_filename:
            await message.reply_text("❌ Please provide a valid filename")
            return
            
        user_info = user_data[user_id]
        
        status_msg = await message.reply_text("🚀 **Starting transfer...**")
        start_time = time.time()
        
        # Get original message
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        if not original_msg:
            await status_msg.edit_text("❌ Original file not found.")
            return
        
        # Create downloads directory
        os.makedirs("downloads", exist_ok=True)
        download_path = f"downloads/{user_id}_{int(time.time())}"
        
        # Download file
        file_path = await client.download_media(
            message=original_msg,
            file_name=download_path,
            progress=lambda current, total: asyncio.create_task(
                update_progress(current, total, status_msg, start_time, "Downloading")
            )
        )
        
        if not file_path or not os.path.exists(file_path):
            await status_msg.edit_text("❌ Download failed.")
            return
        
        transfer_stats['total_downloaded'] += user_info['file_size']
        
        # Upload file
        if user_info['file_type'] == 'video':
            await client.send_video(
                chat_id=user_id,
                video=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                progress=lambda current, total: asyncio.create_task(
                    update_progress(current, total, status_msg, start_time, "Uploading")
                )
            )
        else:
            await client.send_document(
                chat_id=user_id,
                document=file_path,
                file_name=new_filename,
                caption=f"✅ **Renamed:** `{new_filename}`",
                progress=lambda current, total: asyncio.create_task(
                    update_progress(current, total, status_msg, start_time, "Uploading")
                )
            )
        
        transfer_stats['total_uploaded'] += user_info['file_size']
        transfer_stats['transfers_completed'] += 1
        
        total_time = time.time() - start_time
        avg_speed = user_info['file_size'] / total_time if total_time > 0 else 0
        
        await status_msg.edit_text(
            f"✅ **Transfer Complete!** ✅\n\n"
            f"📁 **File:** `{new_filename}`\n"
            f"⚡ **Average Speed:** `{humanbytes(avg_speed)}/s`\n"
            f"⏱️ **Total Time:** `{time.strftime('%M:%S', time.gmtime(total_time))}`\n"
            f"📦 **Size:** `{humanbytes(user_info['file_size'])}`"
        )
        
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
            
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        print(f"Text handler error: {e}")
        try:
            await message.reply_text("❌ Error during file processing")
        except:
            pass
        if user_id in user_data:
            del user_data[user_id]

# Photo handler
@app.on_message(filters.photo & filters.private)
async def photo_handler(client, message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_data or user_data[user_id].get('action') != 'thumbnail':
            return
        
        user_info = user_data[user_id]
        
        if user_info['file_type'] != 'video':
            await message.reply_text("❌ Thumbnails only for videos")
            return
        
        status_msg = await message.reply_text("🚀 **Processing thumbnail...**")
        
        # Download thumbnail
        os.makedirs("downloads", exist_ok=True)
        thumb_path = f"downloads/thumb_{user_id}_{int(time.time())}.jpg"
        await message.download(file_name=thumb_path)
        
        if not os.path.exists(thumb_path):
            await status_msg.edit_text("❌ Failed to download thumbnail")
            return
        
        # Get original video
        original_msg = await client.get_messages(user_info['chat_id'], user_info['message_id'])
        if not original_msg:
            await status_msg.edit_text("❌ Original video not found")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Download video
        video_path = f"downloads/video_{user_id}_{int(time.time())}"
        await original_msg.download(file_name=video_path)
        
        if not os.path.exists(video_path):
            await status_msg.edit_text("❌ Failed to download video")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
            return
        
        # Upload with thumbnail
        await client.send_video(
            chat_id=user_id,
            video=video_path,
            thumb=thumb_path,
            caption="✅ **Custom thumbnail applied!**"
        )
        
        transfer_stats['transfers_completed'] += 1
        await status_msg.edit_text("✅ **Thumbnail applied successfully!**")
        
        # Cleanup
        for path in [video_path, thumb_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
                
        if user_id in user_data:
            del user_data[user_id]
            
    except Exception as e:
        print(f"Photo handler error: {e}")
        try:
            await message.reply_text("❌ Error processing thumbnail")
        except:
            pass
        if user_id in user_data:
            del user_data[user_id]

# Main execution
if __name__ == "__main__":
    print("🚀 Starting Power Speed Bot...")
    print(f"🌐 Running on port: {PORT}")
    
    # Create downloads directory
    os.makedirs("downloads", exist_ok=True)
    
    try:
        app.run()
        print("✅ Bot running successfully!")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
    finally:
        print("🛑 Bot stopped")
