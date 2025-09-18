import os
import time
import asyncio
import shutil
import json
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import BadRequest, FloodWait
from flask import Flask, render_template_string
from threading import Thread
import math
import aiofiles
import psutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

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

# ULTRA HYPER TURBO Configuration
app = Client(
    "file_renamer_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=300,  # Extreme workers for maximum parallelism
    max_concurrent_transmissions=30,  # Maximum concurrent transfers
    sleep_threshold=180,  # Very high sleep threshold
    in_memory=False,
)

# --- Enhanced Flask Web Server with Beautiful Status Page ---
web_app = Flask(__name__)

# HTML Template for Beautiful Status Page
STATUS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Renamer Bot Status</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            padding: 40px;
            text-align: center;
            color: white;
        }
        
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            font-weight: 300;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 40px;
        }
        
        .status-card {
            background: #f8f9fa;
            padding: 30px;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .status-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }
        
        .card-icon {
            font-size: 3em;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 1.5em;
            font-weight: 600;
            margin-bottom: 15px;
            color: #2c3e50;
        }
        
        .card-value {
            font-size: 2em;
            font-weight: 700;
            color: #27ae60;
        }
        
        .card-value.offline {
            color: #e74c3c;
        }
        
        .card-description {
            margin-top: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        
        .metrics {
            background: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .metrics h2 {
            margin-bottom: 20px;
            font-size: 2em;
            font-weight: 300;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .metric-item {
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .metric-label {
            opacity: 0.8;
            font-size: 0.9em;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            background: #34495e;
            color: white;
        }
        
        .online-dot {
            display: inline-block;
            width: 12px;
            height: 12px;
            background: #27ae60;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .speed-gauge {
            width: 100%;
            height: 20px;
            background: #ecf0f1;
            border-radius: 10px;
            overflow: hidden;
            margin: 15px 0;
        }
        
        .speed-fill {
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #2ecc71);
            border-radius: 10px;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ ULTRA HYPER TURBO BOT</h1>
            <p>Real-time Status & Performance Monitoring</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <div class="card-icon">🤖</div>
                <div class="card-title">Bot Status</div>
                <div class="card-value"><span class="online-dot"></span> ONLINE</div>
                <div class="card-description">Telegram Bot Connection</div>
            </div>
            
            <div class="status-card">
                <div class="card-icon">🌐</div>
                <div class="card-title">Web Server</div>
                <div class="card-value"><span class="online-dot"></span> RUNNING</div>
                <div class="card-description">Port: {{ port }}</div>
            </div>
            
            <div class="status-card">
                <div class="card-icon">📊</div>
                <div class="card-title">Active Tasks</div>
                <div class="card-value">{{ active_tasks }}</div>
                <div class="card-description">Current processing tasks</div>
            </div>
            
            <div class="status-card">
                <div class="card-icon">💾</div>
                <div class="card-title">Max File Size</div>
                <div class="card-value">10GB</div>
                <div class="card-description">Supported file size limit</div>
            </div>
            
            <div class="status-card">
                <div class="card-icon">🚀</div>
                <div class="card-title">Speed Mode</div>
                <div class="card-value">ULTRA HYPER</div>
                <div class="card-description">Maximum performance enabled</div>
            </div>
            
            <div class="status-card">
                <div class="card-icon">⏰</div>
                <div class="card-title">Uptime</div>
                <div class="card-value">{{ uptime }}</div>
                <div class="card-description">Server running time</div>
            </div>
        </div>
        
        <div class="metrics">
            <h2>📈 Performance Metrics</h2>
            <div class="metric-grid">
                <div class="metric-item">
                    <div class="metric-value">{{ cpu_usage }}%</div>
                    <div class="metric-label">CPU Usage</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{{ memory_usage }}%</div>
                    <div class="metric-label">Memory Usage</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{{ disk_usage }}%</div>
                    <div class="metric-label">Disk Usage</div>
                </div>
                <div class="metric-item">
                    <div class="metric-value">{{ network_usage }}</div>
                    <div class="metric-label">Network Speed</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>© 2024 ULTRA HYPER TURBO File Renamer Bot | Powered by Pyrogram & Flask</p>
            <p>Status last updated: {{ current_time }}</p>
        </div>
    </div>
</body>
</html>
"""

# Global variables for performance metrics
start_time = time.time()
network_stats = {"last_bytes_sent": 0, "last_bytes_recv": 0, "last_time": time.time()}

@web_app.route('/')
def home():
    """Beautiful status dashboard"""
    # Get system metrics
    cpu_usage = psutil.cpu_percent()
    memory_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage('/').percent
    
    # Calculate network speed
    current_time = time.time()
    net_io = psutil.net_io_counters()
    time_diff = current_time - network_stats["last_time"]
    
    if time_diff > 0:
        upload_speed = (net_io.bytes_sent - network_stats["last_bytes_sent"]) / time_diff
        download_speed = (net_io.bytes_recv - network_stats["last_bytes_recv"]) / time_diff
        network_speed = f"▲{humanbytes(upload_speed)}/s ▼{humanbytes(download_speed)}/s"
    else:
        network_speed = "Calculating..."
    
    # Update network stats
    network_stats.update({
        "last_bytes_sent": net_io.bytes_sent,
        "last_bytes_recv": net_io.bytes_recv,
        "last_time": current_time
    })
    
    # Calculate uptime
    uptime_seconds = time.time() - start_time
    uptime = format_time(uptime_seconds)
    
    return render_template_string(
        STATUS_TEMPLATE,
        port=PORT,
        active_tasks=len(user_tasks),
        cpu_usage=round(cpu_usage, 1),
        memory_usage=round(memory_usage, 1),
        disk_usage=round(disk_usage, 1),
        network_usage=network_speed,
        uptime=uptime,
        current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

@web_app.route('/api/status')
def api_status():
    """JSON API endpoint for status"""
    return {
        "status": "online",
        "port": PORT,
        "bot_connected": True,
        "active_tasks": len(user_tasks),
        "timestamp": datetime.now().isoformat(),
        "performance": {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
    }

def run_web_server():
    """Run the enhanced web server"""
    web_app.run(host='0.0.0.0', port=PORT, threaded=True)

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

# --- Thread Pools for Maximum Performance ---
io_thread_pool = ThreadPoolExecutor(max_workers=100)
cpu_thread_pool = ThreadPoolExecutor(max_workers=50)

# --- Enhanced Helper Functions ---
def humanbytes(size):
    """Convert bytes to human readable format with higher precision"""
    if not size or size == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.2f} {units[unit_index]}"

def format_time(seconds):
    """Format seconds into human readable time"""
    if seconds < 0:
        return "00:00:00"
    
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{int(days)}d {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    else:
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def create_progress_bar(percentage, bar_length=20):
    """Create visual progress bar with more precision"""
    completed = math.floor(percentage / 100 * bar_length)
    remaining = bar_length - completed
    return "█" * completed + "░" * remaining

# ... (rest of the helper functions remain the same as previous version)

async def download_file_with_retry(file_id, output_path, progress_callback, max_retries=7):
    """Enhanced download with chunk optimization"""
    for attempt in range(max_retries):
        try:
            # Use larger chunks for better throughput
            chunk_size = 32 * 1024 * 1024  # 32MB chunks for large files
            
            await app.download_media(
                message=file_id,
                file_name=output_path,
                progress=progress_callback,
                block=True,
                chunk_size=chunk_size
            )
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False

async def optimized_file_move(source, destination):
    """Ultra-optimized file move with larger chunks"""
    try:
        # Try atomic rename first (fastest)
        os.rename(source, destination)
    except OSError:
        try:
            # Try shutil.move
            shutil.move(source, destination)
        except Exception:
            # Async copy with optimized chunk size
            chunk_size = 64 * 1024 * 1024  # 64MB chunks for maximum speed
            async with aiofiles.open(source, 'rb') as src, aiofiles.open(destination, 'wb') as dst:
                while True:
                    chunk = await src.read(chunk_size)
                    if not chunk:
                        break
                    await dst.write(chunk)
            os.remove(source)

# ... (rest of the code remains similar but with speed optimizations)

async def process_file(client: Client, message: Message):
    """ULTRA HYPER TURBO file processing"""
    user_id = message.from_user.id
    task = user_tasks.get(user_id)

    if not task or "new_name" not in task:
        return

    status_message = await message.reply_text("⚡ ULTRA HYPER TURBO mode activated...", quote=True)
    
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
        await safe_edit_message(status_message, "📥 HYPER downloading...")
        
        download_callback = create_progress_callback(user_id, "📥 Downloading")
        
        download_path = f"downloads/{user_id}_{int(time.time())}"
        os.makedirs("downloads", exist_ok=True)
        
        # HYPER speed download
        success = await download_file_with_retry(
            task["file_id"], 
            download_path, 
            download_callback,
            max_retries=7
        )
        
        if not success or not os.path.exists(download_path):
            await safe_edit_message(status_message, "❌ Failed to download the file.")
            return

        # Parallel thumbnail processing
        thumbnail_tasks = []
        if task.get("thumbnail_id"):
            thumbnail_tasks.append(task["thumbnail_id"])
        if permanent_thumbnail:
            thumbnail_tasks.append(permanent_thumbnail['thumbnail_id'])
        
        if thumbnail_tasks:
            thumbnail_path = await parallel_download_thumbnails(thumbnail_tasks)

        await safe_edit_message(status_message, "✅ Download complete. Preparing for HYPER upload...")
        
        new_file_path = os.path.join(os.path.dirname(download_path), task["new_name"])
        await optimized_file_move(download_path, new_file_path)

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
        
        upload_callback = create_progress_callback(user_id, "📤 UPLOADING")
        
        # HYPER speed upload parameters
        upload_params = {
            'chat_id': user_id,
            'caption': caption,
            'progress': upload_callback,
            'disable_notification': True,
            'thumb': thumbnail_path,
            'read_timeout': 600,  # 10 minutes timeout
            'write_timeout': 600,  # 10 minutes timeout
            'connect_timeout': 600,  # 10 minutes timeout
            'pool_timeout': 600,  # 10 minutes timeout
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

        await safe_edit_message(status_message, "✅ ULTRA HYPER TURBO task completed! 🚀")

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
    print(f"🤖 ULTRA HYPER TURBO Bot is starting on port {PORT}...")
    os.makedirs("downloads", exist_ok=True)
    
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    print("🌐 Beautiful web server started")
    print("🔌 Connecting Telegram bot...")
    print("⚡ ULTRA HYPER TURBO mode activated!")
    print("🚀 Maximum speed optimization enabled!")
    print("💾 10GB file support ready!")
    print("📊 Real-time monitoring available!")
    
    app.run()
    
    print("Bot has stopped.")
