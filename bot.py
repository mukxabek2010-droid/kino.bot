BOT_TOKEN   = os.getenv("BOT_TOKEN", "")
ADMIN_IDS   = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_1   = os.getenv("CHANNEL_1", "@kanal1")
CHANNEL_2   = os.getenv("CHANNEL_2", "@kanal2")
WEBHOOK_URL=https://sizning-app.onrender.com
PORT=8000
