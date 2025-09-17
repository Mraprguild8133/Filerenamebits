import os

class Config(object):
    # Get these values from my.telegram.org
    API_ID = int(os.environ.get("API_ID", 12345))
    API_HASH = os.environ.get("API_HASH", "")

    # Get this from @BotFather on Telegram
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # The Telegram user ID of the admin
    ADMIN = int(os.environ.get("ADMIN", 12345))

    # Directory for downloads
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads")
