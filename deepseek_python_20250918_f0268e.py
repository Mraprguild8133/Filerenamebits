import os
import time
import asyncio
import shutil
import json
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
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

# Simple configuration - remove advanced options that might cause issues
app = Client(
    "file_renamer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Simple Flask Web Server ---
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
    try:
        web_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Web server error: {e}")

# --- In-memory storage for user states ---
user_tasks = {}
progress_data = {}
thumbnail_requests = {}

# --- Thumbnail Storage ---
THUMBNAIL_FILE = "permanent_thumbnail.json"

def load_thumbnail():
    if os.path.exists(THUMBNAIL_FILE):
        try:
            with open(THUMBNAIL_FILE, 'r') as f:
                return json.load(f)
        except:
            return None
    return None

def save_thumbnail(thumbnail_id):
    with open(THUMBNAIL_FILE, 'w') as f:
        json.dump({"thumbnail_id": thumbnail_id}, f)

def delete_thumbnail():
    if os.path.exists(THUMBNAIL_FILE):
        os.remove(THUMBNAIL_FILE)

# Load permanent thumbnail
permanent_thumbnail = load_thumbnail()

# --- Helper Functions ---
def humanbytes(size):
    """Convert bytes to human readable format"""
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

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename.strip()

def extract_extension(filename):
    """Extract file extension from filename"""
    if '.' in filename:
        return '.' + filename.split('.')[-1].lower()
    return ''

def build_final_filename(original_name, user_input, prefix="", suffix=""):
    """Build the final filename with prefix and suffix"""
    extension = extract_extension(original_name)
    base_name = original_name.replace(extension, '') if extension else original_name
    
    if user_input:
        if '.' in user_input:
            user_extension = extract_extension(user_input)
            user_base = user_input.replace(user_extension, '')
            final_name = f"{prefix}{user_base}{suffix}{user_extension}"
        else:
            final_name = f"{prefix}{user_input}{suffix}{extension}"
    else:
        final_name = f"{prefix}{base_name}{suffix}{extension}"
    
    return sanitize_filename(final_name)

async def safe_edit_message(message, text):
    """Safely edit a message with flood wait handling."""
    try:
        await message.edit_text(text=text)
    except FloodWait as e:
        print(f"Flood wait: Waiting {e.value} seconds")
        await asyncio.sleep(e.value)
    except Exception:
        pass

async def update_progress_display(user_id, action):
    """Update the progress display for a user"""
    if user_id not in progress_data:
        return
    
    data = progress_data[user_id]
    current = data.get('current', 0)
    total = data.get('total', 1)
    start_time = data.get('start_time', time.time())
    last_current = data.get('last_current', 0)
    last_time = data.get('last_time', start_time)
    
    current_time = time.time()
    elapsed = current_time - start_time
    
    # Calculate instant speed (bytes per second)
    time_diff = current_time - last_time
    if time_diff > 0:
        instant_speed = (current - last_current) / time_diff
    else:
        instant_speed = 0
    
    # Update last values for next calculation
    progress_data[user_id]['last_current'] = current
    progress_data[user_id]['last_time'] = current_time
    
    if instant_speed > 0 and total > current:
        eta = (total - current) / instant_speed
    else:
        eta = 0
    
    percentage = (current / total) * 100 if total > 0 else 0
    
    # Create progress display
    progress_bar = create_progress_bar(percentage)
    
    progress_text = (
        f"**{action}**\n\n"
        f"`{progress_bar}` **{percentage:.1f}%**\n\n"
        f"📊 **Progress:** {humanbytes(current)} / {humanbytes(total)}\n"
        f"🚀 **Speed:** {humanbytes(instant_speed)}/s\n"
        f"⏱️ **Elapsed:** {format_time(elapsed)}\n"
        f"⏳ **ETA:** {format_time(eta)}\n"
    )
    
    try:
        await safe_edit_message(data['status_message'], progress_text)
    except Exception:
        pass

def create_progress_callback(user_id, action):
    """Create a progress callback function that updates progress_data"""
    def callback(current, total):
        if user_id not in progress_data:
            return
            
        progress_data[user_id].update({
            'current': current,
            'total': total if total > 0 else progress_data[user_id].get('total', 1),
            'last_update': time.time()
        })
        
        current_time = time.time()
        if (current_time - progress_data[user_id].get('last_display_update', 0) >= 1 or 
            current == total):
            
            progress_data[user_id]['last_display_update'] = current_time
            
            if hasattr(app, 'loop'):
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        update_progress_display(user_id, action), 
                        app.loop
                    )
                except:
                    pass
    return callback

def parse_filename_input(user_input, original_filename):
    """Parse user input for prefix, suffix, and filename"""
    prefix = ""
    suffix = ""
    filename = ""
    
    if not user_input:
        return prefix, suffix, original_filename
    
    if 'prefix:' in user_input or 'suffix:' in user_input:
        parts = user_input.split('|')
        for part in parts:
            part = part.strip()
            if part.startswith('prefix:'):
                prefix = part.replace('prefix:', '').strip()
            elif part.startswith('suffix:'):
                suffix = part.replace('suffix:', '').strip()
            else:
                filename = part
    else:
        filename = user_input
    
    return prefix, suffix, filename

# --- Command Handlers ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    """Handles the /start command."""
    await message.reply_text(
        "**Hello! I am a File Renamer Bot.**\n\n"
        "Send me any file and I will help you rename it with prefix/suffix support!\n\n"
        "**Features:**\n"
        "• Custom filenames\n"
        "• Prefix & Suffix support\n"
        "• Permanent thumbnails\n"
        "• Real-time progress tracking\n\n"
        "To get started, simply send me a file!",
        quote=True
    )

@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    """Shows help information."""
    help_text = (
        "**📖 Prefix & Suffix Guide**\n\n"
        "**Format:**\n"
        "`prefix:text|suffix:text|filename`\n\n"
        "**Examples:**\n"
        "• `prefix:NEW_|myfile` → `NEW_myfile.ext`\n"
        "• `suffix:_2024|document` → `document_2024.ext`\n"
        "• `myfile` → `myfile.ext` (normal rename)\n\n"
        "Send me a file to get started!"
    )
    await message.reply_text(help_text, quote=True)

@app.on_message(filters.command("status") & filters.private)
async def status_handler(client: Client, message: Message):
    """Handles the /status command to check bot status."""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.reply_text("Sorry, this command is for admin only.", quote=True)
        return
        
    thumbnail_status = "✅ Set" if permanent_thumbnail else "❌ Not set"
    
    status_text = (
        "🤖 **Bot Status**\n"
        f"• **Running on:** Port {PORT}\n"
        f"• **Active tasks:** {len(user_tasks)}\n"
        f"• **Permanent Thumbnail:** {thumbnail_status}\n"
        f"• **Bot connected:** ✅\n"
        f"• **Web server:** ✅\n"
    )
    await message.reply_text(status_text, quote=True)

@app.on_message(filters.command("thumbnail") & filters.private)
async def thumbnail_command_handler(client: Client, message: Message):
    """Handle thumbnail management commands"""
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.reply_text("Sorry, this command is for admin only.", quote=True)
        return
    
    if len(message.command) > 1:
        action = message.command[1].lower()
        if action == "set":
            await message.reply_text(
                "Please send a photo to set as permanent thumbnail.",
                quote=True
            )
        elif action == "remove":
            delete_thumbnail()
            global permanent_thumbnail
            permanent_thumbnail = None
            await message.reply_text(
                "✅ Permanent thumbnail has been removed.",
                quote=True
            )
        elif action == "view":
            if permanent_thumbnail:
                try:
                    await client.send_photo(
                        chat_id=user_id,
                        photo=permanent_thumbnail['thumbnail_id'],
                        caption="📸 Current permanent thumbnail"
                    )
                except Exception:
                    await message.reply_text(
                        "❌ Could not load thumbnail. It may have been deleted.",
                        quote=True
                    )
            else:
                await message.reply_text(
                    "No permanent thumbnail is set.",
                    quote=True
                )
        else:
            await message.reply_text(
                "Invalid command. Use /thumbnail set, /thumbnail remove, or /thumbnail view",
                quote=True
            )
    else:
        await message.reply_text(
            "**Thumbnail Management**\n\n"
            "Use:\n"
            "/thumbnail set - Set permanent thumbnail\n"
            "/thumbnail remove - Remove permanent thumbnail\n"
            "/thumbnail view - View current thumbnail",
            quote=True
        )

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_handler(client: Client, message: Message):
    """Handles the /cancel command to clear a user's current task."""
    user_id = message.from_user.id
    if user_id in user_tasks:
        del user_tasks[user_id]
    if user_id in progress_data:
        del progress_data[user_id]
    if user_id in thumbnail_requests:
        del thumbnail_requests[user_id]
    await message.reply_text("Your current task has been cancelled.", quote=True)

# --- Main Logic Handlers ---
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_handler(client: Client, message: Message):
    """Handles incoming files and starts the renaming process."""
    user_id = message.from_user.id

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

    # Get original filename
    original_filename = ""
    if hasattr(file, 'file_name') and file.file_name:
        original_filename = file.file_name
    else:
        ext = ".bin"
        if file_type == "video":
            ext = ".mp4"
        elif file_type == "audio":
            ext = ".mp3"
        elif file_type == "document":
            ext = ".pdf"
        original_filename = f"file_{int(time.time())}{ext}"

    user_tasks[user_id] = {
        "file_id": file.file_id,
        "file_type": file_type,
        "message_id": message.id,
        "file_size": file.file_size,
        "original_filename": original_filename
    }
    
    await message.reply_text(
        f"📁 **File Received:** `{original_filename}`\n"
        f"📊 **Size:** {humanbytes(file.file_size)}\n\n"
        "Now, please send me the new filename or prefix/suffix format:",
        reply_to_message_id=message.id,
        reply_markup=ForceReply(selective=True)
    )

@app.on_message(filters.private & filters.text)
async def name_and_thumbnail_handler(client: Client, message: Message):
    """Handles the new filename and potential custom thumbnail."""
    user_id = message.from_user.id

    if user_id not in user_tasks:
        return
        
    task = user_tasks[user_id]

    if message.text == "/skip" and task["file_type"] == "video":
        task["thumbnail_id"] = None
        await process_file(client, message)
        return

    if message.text == "/help":
        await help_handler(client, message)
        return

    if "new_name" not in task:
        user_input = message.text.strip()
        
        if not user_input:
            await message.reply_text(
                "Please provide a filename or use /cancel to stop.",
                quote=True
            )
            return
        
        prefix, suffix, filename = parse_filename_input(user_input, task["original_filename"])
        
        if filename and any(c in filename for c in '<>:"/\\|?*'):
            await message.reply_text(
                "❌ Invalid filename. Please provide a valid filename without special characters.",
                quote=True
            )
            return
        
        final_filename = build_final_filename(
            task["original_filename"], 
            filename, 
            prefix, 
            suffix
        )
        
        task["new_name"] = final_filename
        task["prefix"] = prefix
        task["suffix"] = suffix
        task["base_filename"] = filename
        
        confirmation_text = f"✅ **Filename configured:**\n\n"
        if prefix:
            confirmation_text += f"• **Prefix:** `{prefix}`\n"
        if suffix:
            confirmation_text += f"• **Suffix:** `{suffix}`\n"
        if filename:
            confirmation_text += f"• **Filename:** `{filename}`\n"
        confirmation_text += f"• **Final name:** `{final_filename}`\n\n"
        
        if task["file_type"] == "video":
            thumbnail_requests[user_id] = True
            confirmation_text += "📸 Now, send a photo for custom thumbnail or /skip for default:"
            await message.reply_text(
                confirmation_text,
                reply_to_message_id=message.id,
                reply_markup=ForceReply(selective=True)
            )
        else:
            confirmation_text += "Starting processing..."
            await message.reply_text(confirmation_text, quote=True)
            await process_file(client, message)

@app.on_message(filters.private & filters.photo)
async def thumbnail_handler(client: Client, message: Message):
    """Handles the custom thumbnail photo."""
    user_id = message.from_user.id
    
    if (user_id == ADMIN_ID and 
        not message.reply_to_message and 
        user_id not in thumbnail_requests):
        save_thumbnail(message.photo.file_id)
        global permanent_thumbnail
        permanent_thumbnail = {"thumbnail_id": message.photo.file_id}
        await message.reply_text(
            "✅ Permanent thumbnail has been set! It will be used for all future uploads.",
            quote=True
        )
        return
    
    if (user_id in thumbnail_requests and 
        user_id in user_tasks and 
        "new_name" in user_tasks[user_id] and 
        user_tasks[user_id]["file_type"] == "video"):
        
        user_tasks[user_id]["thumbnail_id"] = message.photo.file_id
        del thumbnail_requests[user_id]
        await process_file(client, message)
        return
    
    await message.reply_text(
        "I received your photo, but I'm not sure what to do with it. "
        "Please send a file first or use /thumbnail command for permanent thumbnails.",
        quote=True
    )

async def process_file(client: Client, message: Message):
    """The main function to download, rename, and upload the file."""
    user_id = message.from_user.id
    task = user_tasks.get(user_id)

    if not task or "new_name" not in task:
        return

    status_message = await message.reply_text("Starting processing...", quote=True)
    
    progress_data[user_id] = {
        'status_message': status_message,
        'start_time': time.time(),
        'current': 0,
        'total': task.get('file_size', 1),
        'last_update': time.time(),
        'last_display_update': 0,
        'last_current': 0,
        'last_time': time.time()
    }
    
    original_file_path = None
    thumbnail_path = None
    new_file_path = None
    
    try:
        await safe_edit_message(status_message, "Downloading...")
        
        download_callback = create_progress_callback(user_id, "Downloading")
        
        download_path = f"downloads/{user_id}_{int(time.time())}"
        os.makedirs("downloads", exist_ok=True)
        
        original_file_path = await client.download_media(
            message=task["file_id"],
            file_name=download_path,
            progress=download_callback
        )
        
        if not os.path.exists(download_path):
            await safe_edit_message(status_message, "❌ Failed to download the file.")
            return

        # Download thumbnail if provided
        if task.get("thumbnail_id"):
            thumbnail_path = await client.download_media(task["thumbnail_id"])
        elif permanent_thumbnail:
            thumbnail_path = await client.download_media(permanent_thumbnail['thumbnail_id'])

        await safe_edit_message(status_message, "✅ Download complete. Preparing to upload...")
        
        new_file_path = os.path.join(os.path.dirname(download_path), task["new_name"])
        shutil.move(download_path, new_file_path)

        # Create caption
        caption_parts = []
        if task.get("prefix"):
            caption_parts.append(f"**Prefix:** `{task['prefix']}`")
        if task.get("suffix"):
            caption_parts.append(f"**Suffix:** `{task['suffix']}`")
        if task.get("base_filename"):
            caption_parts.append(f"**Filename:** `{task['base_filename']}`")
        
        caption = f"📁 **Renamed to:** `{task['new_name']}`"
        if caption_parts:
            caption += "\n" + " | ".join(caption_parts)
        
        file_type = task["file_type"]
        
        file_size = os.path.getsize(new_file_path)
        progress_data[user_id].update({
            'start_time': time.time(),
            'current': 0,
            'total': file_size,
            'last_update': time.time(),
            'last_display_update': 0,
            'last_current': 0,
            'last_time': time.time()
        })
        
        upload_callback = create_progress_callback(user_id, "Uploading")
        
        upload_params = {
            'chat_id': user_id,
            'caption': caption,
            'progress': upload_callback,
            'thumb': thumbnail_path,
        }
        
        if file_type == "document":
            await client.send_document(
                document=new_file_path,
                **upload_params
            )
        elif file_type == "video":
            media = await client.get_messages(user_id, task["message_id"])
            video_meta = media.video
            await client.send_video(
                video=new_file_path,
                duration=video_meta.duration,
                width=video_meta.width,
                height=video_meta.height,
                **upload_params
            )
        elif file_type == "audio":
            await client.send_audio(
                audio=new_file_path,
                **upload_params
            )

        await safe_edit_message(status_message, "✅ Task completed successfully!")

    except FloodWait as e:
        await safe_edit_message(status_message, f"⏳ Please wait {e.value} seconds due to rate limits...")
        await asyncio.sleep(e.value)
    except Exception as e:
        await safe_edit_message(status_message, f"❌ An error occurred: {str(e)}")
        print(f"Error: {e}")
    finally:
        try:
            if original_file_path and os.path.exists(original_file_path):
                os.remove(original_file_path)
            if new_file_path and os.path.exists(new_file_path):
                os.remove(new_file_path)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
        except Exception as e:
            print(f"Error cleaning up files: {e}")
        
        if user_id in progress_data:
            del progress_data[user_id]
        if user_id in user_tasks:
            del user_tasks[user_id]
        if user_id in thumbnail_requests:
            del thumbnail_requests[user_id]

# --- Start the bot and web server ---
if __name__ == "__main__":
    print(f"🤖 Bot is starting on port {PORT}...")
    
    # Create necessary directories
    os.makedirs("downloads", exist_ok=True)
    
    # Start Flask web server in a separate thread
    try:
        web_thread = Thread(target=run_web_server)
        web_thread.daemon = True
        web_thread.start()
        print("🌐 Web server started")
    except Exception as e:
        print(f"❌ Web server failed to start: {e}")
    
    print("🔌 Connecting Telegram bot...")
    
    # Run the Pyrogram bot
    try:
        app.run()
        print("✅ Bot is running successfully!")
    except Exception as e:
        print(f"❌ Bot failed to start: {e}")
    
    print("Bot has stopped.")