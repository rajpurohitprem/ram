import json
import asyncio
import os
import re
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from clone_worker import clone_worker
from telethon.sync import TelegramClient

CONFIG_FILE = "config.json"
BOT_FILE = "bot.json"
STOP_FLAG = "stop.flag"
SESSION_FILE = "anon.session"

# Load bot token
with open(BOT_FILE) as f:
    BOT_TOKEN = json.load(f)["bot_token"]

# ---------------------- UTILS ----------------------

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def ensure_config_key(key, value):
    config = load_config()
    config[key] = value
    save_config(config)

# ---------------------- STATES ----------------------
(
    MAIN_MENU,
    USER_CONFIG,
    WAITING_FOR_API_ID,
    WAITING_FOR_API_HASH,
    WAITING_FOR_PHONE,
    WAITING_FOR_CODE,  # New state for OTP code
    SOURCE_TARGET,
    MISSION,
    WAITING_FOR_RANGE_START,
    WAITING_FOR_RANGE_END
) = range(10)

# ---------------------- HANDLERS ----------------------

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not all(k in config for k in ("api_id", "api_hash", "phone")):
        await update.message.reply_text("Please configure API ID, Hash, and Phone first.")
        return USER_CONFIG
    
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.connect()
    
    if not await client.is_user_authorized():
        # Store client in context for later use
        context.user_data["client"] = client
        
        # Send code request
        sent_code = await client.send_code_request(config["phone"])
        context.user_data["phone_code_hash"] = sent_code.phone_code_hash
        
        await update.message.reply_text("📲 Code sent. Please reply with the code:")
        return WAITING_FOR_CODE
    
    await update.message.reply_text("✅ Already logged in.", reply_markup=main_menu())
    await client.disconnect()
    return MAIN_MENU

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Extract digits from message (handles formats like "12345", "1 2 3 4 5", "1-2-3-4-5")
    code = re.sub(r'[^0-9]', '', update.message.text)
    
    if not code or len(code) < 5:
        await update.message.reply_text("❌ Invalid code format. Please enter the 5-digit code:")
        return WAITING_FOR_CODE
    
    try:
        client = context.user_data["client"]
        phone_code_hash = context.user_data["phone_code_hash"]
        phone = load_config()["phone"]
        
        # Sign in with the code
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash
        )
        
        await update.message.reply_text("✅ Successfully logged in!", reply_markup=main_menu())
        
        # Clean up
        del context.user_data["client"]
        del context.user_data["phone_code_hash"]
        
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {str(e)}\nPlease try again or check your code.")
        return WAITING_FOR_CODE

# Update the ConversationHandler states to include WAITING_FOR_CODE
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            # ... (other states remain the same) ...
            WAITING_FOR_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            MessageHandler(filters.Regex("^skip$"), back_to_main),
        ],
    )

    app.add_handler(conv_handler)
    app.run_polling()
    
if __name__ == "__main__":
    main()
