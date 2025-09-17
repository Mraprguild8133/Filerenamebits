import os

# Get these values from my.telegram.org
API_ID = int(os.environ.get("API_ID", "123456")) # Your API_ID
API_HASH = os.environ.get("API_HASH", "your_api_hash") # Your API_HASH

# Get this from @BotFather on Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token") # Your Bot Token

# List of user IDs who are authorized to use the bot.
# Separate multiple IDs with a space.
AUTH_USERS = set(int(x) for x in os.environ.get("AUTH_USERS", "123456789").split())

# Directory to save downloaded files temporarily.
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads/")
