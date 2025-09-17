# (c) @MrMKN
# (c) @LazyDeveloperr
import os
import time
import json
import psutil
import shutil
import string
import random
import asyncio
from PIL import Image
from pyrogram import Client, filters
from datetime import datetime
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    MessageNotModified,
    FloodWait,
    InputUserDeactivated,
    UserIsBlocked,
    PeerIdInvalid,
)

from configs import Config
from helper_fns import (
    humanbytes,
    get_time,
    get_media_info,
    get_media_from_message,
)

# Initialize the Pyrogram client
bot = Client(
    "Simple-Rename-Bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)

# Start command handler
@bot.on_message(filters.command("start"))
async def start_handler(c: Client, m: Message):
    await m.reply_text(
        "**Hello, I am a simple file rename bot.**\n\nI can rename any file, video, or audio you send me. Just send me the file and I'll do the rest!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Developer", url="https://t.me/MrMKN"),
                    InlineKeyboardButton(
                        "Source Code", url="https://github.com/MrMKN/Simple-Rename-Bot"
                    ),
                ]
            ]
        ),
    )


# Help command handler
@bot.on_message(filters.command("help"))
async def help_handler(c: Client, m: Message):
    await m.reply_text(
        "**How to use me:**\n\n1. Send me any file, video, or audio.\n2. Reply to the file with the new name (including the extension).\n3. I will rename it and send it back to you.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Developer", url="https://t.me/MrMKN"),
                    InlineKeyboardButton(
                        "Source Code", url="https://github.com/MrMKN/Simple-Rename-Bot"
                    ),
                ]
            ]
        ),
    )


# Status command handler
@bot.on_message(filters.command("status"))
async def status_handler(c: Client, m: Message):
    # Get server status
    total, used, free = shutil.disk_usage(".")
    total = humanbytes(total)
    used = humanbytes(used)
    free = humanbytes(free)
    cpu_usage = psutil.cpu_percent()
    ram_usage = psutil.virtual_memory().percent
    disk_usage = psutil.disk_usage("/").percent
    body = (
        f"**Disk Space:**\n**Total:** {total}\n**Used:** {used}\n**Free:** {free}\n\n"
        f"**CPU Usage:** {cpu_usage}%\n"
        f"**RAM Usage:** {ram_usage}%\n"
        f"**Disk Usage:** {disk_usage}%"
    )
    await m.reply_text(body)


# Generic message handler for renaming
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def rename_handler(c: Client, m: Message):
    media = get_media_from_message(m)
    if media is None:
        await m.reply_text("Unsupported file type.")
        return

    # Ask for the new name
    ask_for_name = await c.ask(
        chat_id=m.chat.id,
        text="Please send me the new name for the file (including the extension):",
        reply_to_message_id=m.message_id,
    )

    new_name = ask_for_name.text
    if not new_name:
        await ask_for_name.reply_text("Name cannot be empty.")
        return

    # Download the file
    download_start_time = time.time()
    status_msg = await m.reply_text("Downloading file...")

    file_path = await c.download_media(
        message=m,
        file_name=f"downloads/{new_name}",
        progress=progress_bar,
        progress_args=("Downloading", status_msg, download_start_time),
    )

    if not file_path:
        await status_msg.edit("Failed to download the file.")
        return

    await status_msg.edit("Download complete. Now uploading...")

    # Upload the file with the new name
    upload_start_time = time.time()
    media_info = get_media_info(file_path)

    if m.video and media_info["thumbnail"]:
        await c.send_video(
            chat_id=m.chat.id,
            video=file_path,
            caption=f"**New Name:** `{new_name}`",
            thumb=media_info["thumbnail"],
            duration=media_info["duration"],
            width=media_info["width"],
            height=media_info["height"],
            progress=progress_bar,
            progress_args=("Uploading", status_msg, upload_start_time),
        )
    elif m.audio:
        await c.send_audio(
            chat_id=m.chat.id,
            audio=file_path,
            caption=f"**New Name:** `{new_name}`",
            thumb=media_info["thumbnail"],
            duration=media_info["duration"],
            performer=media_info["artist"],
            title=media_info["title"],
            progress=progress_bar,
            progress_args=("Uploading", status_msg, upload_start_time),
        )
    else:
        await c.send_document(
            chat_id=m.chat.id,
            document=file_path,
            caption=f"**New Name:** `{new_name}`",
            thumb=media_info["thumbnail"],
            progress=progress_bar,
            progress_args=("Uploading", status_msg, upload_start_time),
        )

    # Clean up
    await status_msg.delete()
    os.remove(file_path)
    if media_info["thumbnail"]:
        os.remove(media_info["thumbnail"])


# Progress bar function
async def progress_bar(current, total,- text, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion
        elapsed_time = get_time(elapsed_time)
        estimated_total_time = get_time(estimated_total_time)
        progress = "[{0}{1}] \n**Percentage:** {2}%\n".format(
            "".join(["●" for i in range(math.floor(percentage / 5))]),
            "".join(["○" for i in range(20 - math.floor(percentage / 5))]),
            round(percentage, 2),
        )
        tmp = progress + "**Total:** {0}\n**Completed:** {1}\n**Speed:** {2}/s\n**ETA:** {3}\n".format(
            humanbytes(total),
            humanbytes(current),
            humanbytes(speed),
            estimated_total_time if estimated_total_time != "" else "0 s",
        )
        try:
            await message.edit(text="{}\n {}".format(text, tmp))
        except:
            pass

# Start the bot
print("Bot is starting...")
bot.run()
