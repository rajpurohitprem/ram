# bot.py

import json
from telethon import TelegramClient, events, Button
import os


# ---------- Utility Functions ----------
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def cleanup_journals():
    for file in glob.glob("*journal"):
        try:
            os.remove(file)
        except Exception as e:
            print(f"Could not delete {file}: {e}")

# ---------- Load Configuration ----------
bot_config = load_json("bot.json")       # Contains bot_token and allowed_users
main_config = load_json("config.json")   # Contains api_id, api_hash, phone, etc.

bot_token = bot_config["bot_token"]
allowed_users = bot_config["allowed_users"]

api_id = main_config["api_id"]
api_hash = main_config["api_hash"]
phone = main_config.get("phone", "")

BOT = "bot"
ANON = "anon"

# Create bot client
#bot = TelegramClient("bot", api_id, api_hash).start(bot_token=bot_token)

# ✅ User check
def is_authorized(event):
    return event.sender_id in allowed_users

# 📌 Start command - shows 3 main options
@bot.on(events.NewMessage(pattern="/start"))
async def start_handler(event):
    if not is_authorized(event):
        return await event.reply("🚫 Not authorized.")

    keyboard = [
        [Button.inline("👤 User Config", b"user_config")],
        [Button.inline("🔁 Source/Target", b"source_target")],
        [Button.inline("🚀 Start Mission", b"start_mission")]
    ]
    await event.respond("🔘 *Main Menu*", buttons=keyboard, parse_mode="markdown")

# 📌 Start command - shows 3 main options
@bot.on(events.NewMessage(pattern="👤 User Config"))
async def start_handler(event):
    if not is_authorized(event):
        return await event.reply("🚫 Not authorized.")

    keyboard = [
        [Button.inline("API ID", b"API_ID")],
        [Button.inline("API Hash", b"API_Hash")],
        [Button.inline("Phone No.", b"Phone_No.")]
    ]
    await event.respond("🔘 *Main Menu*", buttons=keyboard, parse_mode="markdown")


























print("🤖 Bot is running...")
bot.run_until_disconnected()

