import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9242935334:AAGJPMmjUYJfVYocxHFoJ9E2n0fN9j416qg")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8338661047").split("8804568121")]
PORT = int(os.environ.get("PORT", "8080"))
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://numbot:2dMPBmnNjdqDFO2SxtqdxoykwGAbQA8M@dpg-dc3i34e7bikc73d7k9tg-a:5432/numbot")
