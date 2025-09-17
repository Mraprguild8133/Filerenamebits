import os
import time
import asyncio
import shutil
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, ForceReply
from pyrogram.errors import BadRequest, FloodWait
from flask import Flask
from threading import Thread
import math

# --- Load Environment Variables ---
load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
PORT = int(os.environ.get("PORT", 5000))

# --- Bot Initialization ---
if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    raise ValueError("Missing one or more required environment variables: API_ID, API_HASH, BOT_TOKEN, ADMIN_ID")

try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("ADMIN_ID must be a valid integer.")

app = Client(
    "file_renamer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Flask Web Server for Render ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is running successfully! 🚀"

@web_app.route('/status')
def status():
    return {
        "status": "online",
        "port": PORT,
        "bot_connected": True,
        "active_tasks": len(user_tasks)
    }

def run_web_server():
    web_app.run(host='0.0.0.0', port=PORT)

# --- In-memory storage for user states ---
user_tasks = {}
progress_data = {}  # Store progress data for each user

# --- Helper Functions ---
def humanbytes(size):
    """Converts bytes to a human-readable format (e.g., KB, MB, GB)."""
    if not size or size == 0:
        return "0 B"
    power = 1024
    t_n = 0
    power_dict = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}
    while size > power:
        size /= power
        t_n += 1
    return f"{size:.2f} {power_dict[t_n]}"

def format_time(seconds):
    """Format seconds into HH:MM:SS or MM:SS"""
    if seconds < 0:
        return "00:00"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def create_progress_bar(percentage, bar_length=20):
    """Create a visual progress bar"""
    completed = math.floor(percentage / 100 * bar_length)
    remaining = bar_length - completed
    return "█" * completed + "░" * remaining

async def safe_edit_message(message, text):
    """Safely edit a message with flood wait handling."""
    try:
        await message.edit_text(text=text)
    except FloodWait as e:
        # If we hit a flood wait, just wait it out
        print(f"Flood wait: Waiting {e.value} seconds")
        await asyncio.sleep(e.value)
    except Exception:
        # Ignore other errors (message might be deleted)
        pass

async def progress_callback(current, total, user_id, action):
    """Real-time progress callback with all metrics"""
    if user_id not in progress_data:
        return
    
    # Update progress data
    progress_data[user_id].update({
        'current': current,
        'total': total,
        'last_update': time.time()
    })
    
    # Calculate metrics
    data = progress_data[user_id]
    elapsed = time.time() - data['start_time']
    
    if elapsed > 0 and current > 0:
        speed = current / elapsed
        if total > current and speed > 0:
            eta = (total - current) / speed
        else:
            eta = 0
    else:
        speed = 0
        eta = 0
    
    percentage = (current / total) * 100 if total > 0 else 0
    
    # Only update display every 1 second to avoid rate limiting
    if time.time() - data.get('last_display_update', 0) < 1 and current != total:
        return
    
    progress_data[user_id]['last_display_update'] = time.time()
    
    # Create progress display
    progress_bar = create_progress_bar(percentage)
    
    progress_text = (
        f"**{action}**\n\n"
        f"`{progress_bar}` **{percentage:.1f}%**\n\n"
        f"📊 **Progress:** {humanbytes(current)} / {humanbytes(total)}\n"
        f"🚀 **Speed:** {humanbytes(speed)}/s\n"
        f"⏱️ **Elapsed:** {format_time(elapsed)}\n"
        f"⏳ **ETA:** {format_time(eta)}\n"
    )
    
    try:
        await safe_edit_message(data['status_message'], progress_text)
    except Exception:
        pass

# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handles the /start command."""
    await message.reply_text(
        "**Hello! I am a File Renamer Bot.**\n\n"
        "Send me any file and I will help you rename it. I can also add custom thumbnails to video files.\n\n"
        "To get started, simply send me a file.",
        quote=True
    )

@app.on_message(filters.command("status") & filters.private)
async def status_handler(client: Client, message: Message):
    """Handles the /status command to check bot status."""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.reply_text("Sorry, this command is for admin only.", quote=True)
        return
        
    status_text = (
        "🤖 **Bot Status**\n"
        f"• **Running on:** Render (Port {PORT})\n"
        f"• **Active tasks:** {len(user_tasks)}\n"
        f"• **Bot connected:** ✅\n"
        f"• **Web server:** ✅\n"
        "• **Support:** Contact admin for assistance"
    )
    await message.reply_text(status_text, quote=True)

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client: Client, message: Message):
    """Handles the /cancel command to clear a user's current task."""
    user_id = message.from_user.id
    if user_id in user_tasks:
        del user_tasks[user_id]
    if user_id in progress_data:
        del progress_data[user_id]
    await message.reply_text("Your current task has been cancelled.", quote=True)

# --- Main Logic Handlers ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_handler(client: Client, message: Message):
    """Handles incoming files and starts the renaming process."""
    user_id = message.from_user.id

    # Check if the user is the admin
    if user_id != ADMIN_ID:
        await message.reply_text("Sorry, this bot is for the admin's use only.", quote=True)
        return

    file_type = None
    file = None
    if message.document:
        file_type = "document"
        file = message.document
    elif message.video:
        file_type = "video"
        file = message.video
    elif message.audio:
        file_type = "audio"
        file = message.audio
        
    if not file:
        return

    # Store the file information and ask for the new name
    user_tasks[user_id] = {
        "file_id": file.file_id,
        "file_type": file_type,
        "message_id": message.id,
        "file_size": file.file_size
    }
    
    await message.reply_text(
        "📁 File received. Now, please send me the new file name, including the extension.",
        reply_to_message_id=message.id,
        reply_markup=ForceReply(selective=True)
    )

@app.on_message(filters.private & filters.text)
async def name_and_thumbnail_handler(client: Client, message: Message):
    """Handles the new filename and potential custom thumbnail."""
    user_id = message.from_user.id

    # Check if the user has an active task
    if user_id not in user_tasks:
        return
        
    task = user_tasks[user_id]

    # Handle the skip command
    if message.text == "/skip" and task["file_type"] == "video":
        task["thumbnail_id"] = None
        await process_file(client, message)
        return

    # This part handles the new file name
    if "new_name" not in task:
        # Validate filename
        if not message.text.strip() or any(c in message.text for c in '<>:"/\\|?*'):
            await message.reply_text(
                "❌ Invalid file name. Please provide a valid file name without special characters.",
                quote=True
            )
            return
            
        task["new_name"] = message.text.strip()
        
        # If it's a video, ask for a thumbnail
        if task["file_type"] == "video":
            await message.reply_text(
                "📸 Great! Now, send a photo to set it as a custom thumbnail, or send /skip to use the default thumbnail.",
                reply_to_message_id=message.id,
                reply_markup=ForceReply(selective=True)
            )
        else:
            # If not a video, start processing immediately
            await process_file(client, message)

@app.on_message(filters.private & filters.photo)
async def thumbnail_handler(client: Client, message: Message):
    """Handles the custom thumbnail photo."""
    user_id = message.from_user.id
    if (user_id in user_tasks and 
        "new_name" in user_tasks[user_id] and 
        user_tasks[user_id]["file_type"] == "video"):
        user_tasks[user_id]["thumbnail_id"] = message.photo.file_id
        await process_file(client, message)

async def process_file(client: Client, message: Message):
    """The main function to download, rename, and upload the file."""
    user_id = message.from_user.id
    task = user_tasks.get(user_id)

    if not task or "new_name" not in task:
        return

    status_message = await message.reply_text("⏳ Initializing...", quote=True)
    
    # Initialize progress data
    progress_data[user_id] = {
        'status_message': status_message,
        'start_time': time.time(),
        'current': 0,
        'total': task.get('file_size', 0),
        'last_update': time.time(),
        'last_display_update': 0
    }
    
    original_file_path = None
    thumbnail_path = None
    new_file_path = None
    
    try:
        # 1. Download the file with progress tracking
        await safe_edit_message(status_message, "📥 Starting download...")
        
        # Create custom progress callback
        def download_progress(current, total):
            asyncio.create_task(progress_callback(current, total, user_id, "📥 Downloading"))
        
        original_file_path = await client.download_media(
            message=task["file_id"],
            progress=download_progress
        )
        
        if not original_file_path or not os.path.exists(original_file_path):
            await safe_edit_message(status_message, "❌ Failed to download the file.")
            return
        
        # 2. Download thumbnail if provided
        if task.get("thumbnail_id"):
            thumbnail_path = await client.download_media(task["thumbnail_id"])

        await safe_edit_message(status_message, "✅ Download complete. Preparing to upload...")
        
        # 3. Prepare for upload
        new_file_path = os.path.join(os.path.dirname(original_file_path), task["new_name"])
        
        # Use shutil.move instead of os.rename for cross-filesystem compatibility
        shutil.move(original_file_path, new_file_path)

        # 4. Upload the file with progress tracking
        caption = f"📁 Renamed to: `{task['new_name']}`"
        file_type = task["file_type"]
        
        # Reset progress for upload
        progress_data[user_id].update({
            'start_time': time.time(),
            'current': 0,
            'total': os.path.getsize(new_file_path),
            'last_update': time.time(),
            'last_display_update': 0
        })
        
        # Create custom progress callback for upload
        def upload_progress(current, total):
            asyncio.create_task(progress_callback(current, total, user_id, "📤 Uploading"))
        
        if file_type == "document":
            await client.send_document(
                chat_id=user_id,
                document=new_file_path,
                thumb=thumbnail_path,
                caption=caption,
                progress=upload_progress
            )
        elif file_type == "video":
            # Get video properties to maintain them
            media = await client.get_messages(user_id, task["message_id"])
            video_meta = media.video
            await client.send_video(
                chat_id=user_id,
                video=new_file_path,
                thumb=thumbnail_path,
                caption=caption,
                duration=video_meta.duration,
                width=video_meta.width,
                height=video_meta.height,
                progress=upload_progress
            )
        elif file_type == "audio":
            await client.send_audio(
                chat_id=user_id,
                audio=new_file_path,
                thumb=thumbnail_path,
                caption=caption,
                progress=upload_progress
            )

        await safe_edit_message(status_message, "✅ Task completed successfully! File has been renamed and sent.")

    except FloodWait as e:
        await safe_edit_message(status_message, f"⏳ Please wait {e.value} seconds due to rate limits...")
        await asyncio.sleep(e.value)
    except Exception as e:
        await safe_edit_message(status_message, f"❌ An error occurred: {str(e)}")
        print(f"Error: {e}")
    finally:
        # Clean up files and task data
        try:
            if original_file_path and os.path.exists(original_file_path):
                os.remove(original_file_path)
            if new_file_path and os.path.exists(new_file_path):
                os.remove(new_file_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception as e:
            print(f"Error cleaning up files: {e}")
        
        # Clean up progress data
        if user_id in progress_data:
            del progress_data[user_id]
        if user_id in user_tasks:
            del user_tasks[user_id]

# --- Start the bot and web server ---
if __name__ == "__main__":
    print(f"🤖 Bot is starting on port {PORT}...")
    
    # Start Flask web server in a separate thread
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    print("🌐 Web server started")
    print("🔌 Connecting Telegram bot...")
    
    # Run the Pyrogram bot
    app.run()
    
    print("Bot has stopped.")
