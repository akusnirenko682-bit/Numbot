import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
raw_ids = os.environ.get("ADMIN_IDS", "0")
ADMIN_IDS = [int(x.strip()) for x in raw_ids.split(",") if x.strip()]
PORT = int(os.environ.get("PORT", "8080"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
