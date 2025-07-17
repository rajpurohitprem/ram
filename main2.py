import json
import subprocess
import glob
import os
from telethon import TelegramClient, events

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

# ---------- Initialize Clients ----------
bot = TelegramClient(BOT, api_id, api_hash).start(bot_token=bot_token)
anon = TelegramClient(ANON, api_id, api_hash)

# ---------- Authorization Check ----------
def is_authorized(event):
    return event.sender_id in allowed_users

# ---------- Command Handlers ----------

@bot.on(events.NewMessage)
async def handler(event):
    if not is_authorized(event):
        await event.reply("🚫 You are not authorized to use this bot.")
        return

    message = event.raw_text.strip()

    # Start / Help
    if message.startswith("/start") or message.startswith("/help"):
        await event.reply(
            "🤖 *Telegram Clone Bot*\n\n"
            "/login – Request OTP to login\n"
            "/code `1 2 3 4 5` – Submit the OTP code\n"
            "/logout – Logout anon session\n"
            "/api `<new_api_id>` – Update API ID\n"
            "/hash `<new_api_hash>` – Update API Hash\n"
            "/set_source `-100xxxxxxxxx` – Set source channel\n"
            "/set_target `-100yyyyyyyyy` – Set target channel\n"
            "/run_clone – Run the cloner script\n\n"
            "_Only authorized users can use these commands._",
            parse_mode="markdown"
        )

    # Login
    elif message.startswith("/login"):
        try:
            await anon.connect()
            if await anon.is_user_authorized():
                return await event.reply("✅ Already logged in.")
            await anon.send_code_request(phone)
            await event.reply("📨 OTP sent. Use `/code 1 2 3 4 5` to complete login.")
        except Exception as e:
            await event.reply(f"❌ Error: {e}")

    # Submit Code
    elif message.startswith("/code"):
        try:
            digits = "".join(filter(str.isdigit, message))
            if len(digits) != 5:
                return await event.reply("❌ Invalid format. Send exactly 5 digits.")
            await anon.sign_in(phone, digits)
            await event.reply("✅ Logged in. `anon.session` saved.")
        except Exception as e:
            await event.reply(f"❌ Login failed: {e}")
            cleanup_journals()

    # Logout
    elif message.startswith("/logout"):
        try:
            await anon.log_out()
            await event.reply("✅ Logged out.")
        except Exception as e:
            await event.reply(f"❌ Logout error: {e}")
        cleanup_journals()
        for ext in ["anon.session", "anon.session-journal"]:
            if os.path.exists(ext):
                os.remove(ext)

    # Update API ID
    elif message.startswith("/api"):
        try:
            new_api_id = int(message.split(" ")[1])
            main_config["api_id"] = new_api_id
            save_json("config.json", main_config)
            await event.reply(f"✅ API ID updated to `{new_api_id}`")
        except Exception as e:
            await event.reply(f"⚠️ Failed to update API ID: {str(e)}")

    # Update API Hash
    elif message.startswith("/hash"):
        try:
            new_api_hash = message.split(" ")[1]
            main_config["api_hash"] = new_api_hash
            save_json("config.json", main_config)
            await event.reply(f"✅ API Hash updated to `{new_api_hash}`")
        except Exception as e:
            await event.reply(f"⚠️ Failed to update API Hash: {str(e)}")

    # Set Source Channel
    elif message.startswith("/set_source"):
        try:
            source_id = message.split(" ")[1].replace("-100", "")
            main_config["source_channel_id"] = int(source_id)
            save_json("config.json", main_config)
            await event.reply(f"✅ Source channel set to: `{source_id}`")
        except Exception as e:
            await event.reply(f"⚠️ Error: {str(e)}")

    # Set Target Channel
    elif message.startswith("/set_target"):
        try:
            target_id = message.split(" ")[1].replace("-100", "")
            main_config["target_channel_id"] = int(target_id)
            save_json("config.json", main_config)
            await event.reply(f"✅ Target channel set to: `{target_id}`")
        except Exception as e:
            await event.reply(f"⚠️ Error: {str(e)}")

    # Run Cloner Script
    elif message.startswith("/run_clone"):
        await event.reply("▶️ Starting clone.py...")
        try:
            subprocess.Popen(["python", "clone.py"])
        except Exception as e:
            await event.reply(f"❌ Failed to run clone.py: {str(e)}")

# ---------- Final Cleanup ----------
if os.path.exists("anon.session_journal"):
    os.remove("anon.session_journal")
if os.path.exists("bot.session_journal"):
    os.remove("bot.session_journal")

print("🤖 Bot is running...")
bot.run_until_disconnected()
