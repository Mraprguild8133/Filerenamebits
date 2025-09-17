import os

# Get these values from my.telegram.org
API_ID = int(os.environ.get("API_ID", "123456")) # Your API_ID
API_HASH = os.environ.get("API_HASH", "your_api_hash") # Your API_HASH

# Get this from @BotFather on Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token") # Your Bot Token

Replace 123456789 with your actual Telegram User ID from @userinfobot.
# If you have multiple users, separate the numbers with commas inside the curly braces.
# For example: AUTH_USERS = {123456789, 987654321}
AUTH_USERS = {6300568870}
# Directory to save downloaded files temporarily.
DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "./downloads/")
