import json
import asyncio
import os
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
from clone_worker import clone_worker, clone_worker
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

# ---------------------- REPLY KEYBOARDS ----------------------

def main_menu():
    return ReplyKeyboardMarkup([
        ["User Config", "Source/Target"],
        ["Start Mission"]
    ], resize_keyboard=True)

def user_config_menu():
    return ReplyKeyboardMarkup([
        ["Api ID", "Api Hash", "Phone No."],
        ["Login", "Logout"],
        ["⬅ Back","skip"]
    ], resize_keyboard=True)

def source_target_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Select Source Channel", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))],
        [KeyboardButton("Select Target Channel", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=True))],
        ["⬅ Back"]
    ], resize_keyboard=True)

def mission_menu():
    return ReplyKeyboardMarkup([
        ["Full Clone", "Range Clone"],
        ["Stop", "⬅ Back","skip"]
    ], resize_keyboard=True)


# ---------------------- STATES ----------------------
(
    WAITING_FOR_API_ID,
    WAITING_FOR_API_HASH,
    WAITING_FOR_PHONE,
    WAITING_FOR_RANGE_START,
    WAITING_FOR_RANGE_END
) = range(5)

# ---------------------- HANDLERS ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Use buttons to configure and start cloning.", reply_markup=main_menu())

# USER CONFIG

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "User Config":
        await update.message.reply_text("User Config:", reply_markup=user_config_menu())

    elif text == "Api ID":
        await update.message.reply_text("Please send your API ID:")
        return WAITING_FOR_API_ID

    elif text == "Api Hash":
        await update.message.reply_text("Please send your API Hash:")
        return WAITING_FOR_API_HASH

    elif text == "Phone No.":
        config = load_config()
        current = config.get("phone", "Not Set")
        await update.message.reply_text(f"Current number: `{current}`\nSend new phone number or type 'skip' to keep.", parse_mode="Markdown")
        return WAITING_FOR_PHONE

    elif text == "Login":
        config = load_config()
        if not all(k in config for k in ("api_id", "api_hash", "phone")):
            await update.message.reply_text("Please configure API ID, Hash, and Phone first.")
            return
        client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(config["phone"])
            await update.message.reply_text("📲 Code sent. Please reply with the code:")
            context.user_data["client"] = client
            return ConversationHandler.END
        await update.message.reply_text("✅ Already logged in.")
        await client.disconnect()

    elif text == "Logout":
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
            await update.message.reply_text("🔒 Logged out and session removed.")
        else:
            await update.message.reply_text("No session to remove.")

    elif text == "Source/Target":
        await update.message.reply_text("Select source or target channel.", reply_markup=source_target_menu())

    elif text == "Start Mission":
        await update.message.reply_text("Choose clone mode:", reply_markup=mission_menu())

    elif text == "Full Clone":
        await update.message.reply_text("🚀 Starting full clone...")
        asyncio.create_task(clone_worker())
        await update.message.reply_text("📥 Cloning started...")

    elif text == "Range Clone":
        await update.message.reply_text("Send start message ID:")
        return WAITING_FOR_RANGE_START

    elif text == "Stop":
        with open(STOP_FLAG, "w") as f:
            f.write("stop")
        await update.message.reply_text("⛔ Clone stopped.")

    elif text == "⬅ Back":
        await update.message.reply_text("Main Menu:", reply_markup=main_menu())

# SET RANGE

async def set_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["range_start"] = int(update.message.text)
    await update.message.reply_text("Now send end message ID:")
    return WAITING_FOR_RANGE_END

async def set_range_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = context.user_data["range_start"]
    end = int(update.message.text)
    await update.message.reply_text(f"🚀 Starting clone for messages {start} to {end}...")
    asyncio.create_task(clone_worker_range(start, end))
    await update.message.reply_text("📥 Range clone started.")
    return ConversationHandler.END

# CONFIG SETTERS

async def save_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_config_key("api_id", int(update.message.text))
    await update.message.reply_text("✅ API ID saved.", reply_markup=user_config_menu())
    return ConversationHandler.END

async def save_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hash = update.message.text
    if phone.lower() != "skip":
        ensure_config_key("api_hash", update.message.text)
        await update.message.reply_text("✅ API Hash saved.", reply_markup=user_config_menu())
        return ConversationHandler.END
    else:
        await update.message.reply_text("No changes made.")
    return ConversationHandler.END
  

async def save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if phone.lower() != "skip":
        ensure_config_key("phone", phone)
        await update.message.reply_text("✅ Phone number updated.")
    else:
        await update.message.reply_text("No changes made.")
    return ConversationHandler.END

# CHANNEL HANDLER
async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared
    if not shared:
        return
    if shared.request_id == 1:
        ensure_config_key("source_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Source channel set: `{shared.chat_id}`", parse_mode="Markdown")
    elif shared.request_id == 2:
        ensure_config_key("target_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Target channel set: `{shared.chat_id}`", parse_mode="Markdown")

# Track clone state
user_states = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "Start Mission":
        # Show cloning mode options
        user_states[chat_id] = "awaiting_clone_type"
        keyboard = [
            [KeyboardButton("Full Clone")],
            [KeyboardButton("Range Clone")],
        ]
        markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("🛰 Choose Clone Type:", reply_markup=markup)

    elif text == "Full Clone" and user_states.get(chat_id) == "awaiting_clone_type":
        await update.message.reply_text("🟢 Starting full clone...")
        user_states.pop(chat_id)

        # Launch clone_worker in full mode
        from clone_worker import start_clone
        await start_clone()  # assumes no args runs full clone

    elif text == "Range Clone" and user_states.get(chat_id) == "awaiting_clone_type":
        await update.message.reply_text("📩 Please enter range (e.g., `100 500`):", parse_mode="Markdown")
        user_states[chat_id] = "awaiting_range_input"

    elif user_states.get(chat_id) == "awaiting_range_input":
        try:
            start_id, end_id = map(int, text.strip().split())
            user_states.pop(chat_id)
            await update.message.reply_text(f"🚀 Cloning messages from ID {start_id} to {end_id}...")

            # Call clone_worker with range
            from clone_worker import start_clone
            await start_clone(start_id=start_id, end_id=end_id)

        except Exception:
            await update.message.reply_text("❌ Invalid range. Please send like: `100 500`", parse_mode="Markdown")

# ---------------------- MAIN ----------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text)],
        states={
            WAITING_FOR_API_ID: [MessageHandler(filters.TEXT, save_api_id)],
            WAITING_FOR_API_HASH: [MessageHandler(filters.TEXT, save_api_hash)],
            WAITING_FOR_PHONE: [MessageHandler(filters.TEXT, save_phone)],
            WAITING_FOR_RANGE_START: [MessageHandler(filters.TEXT, set_range_start)],
            WAITING_FOR_RANGE_END: [MessageHandler(filters.TEXT, set_range_end)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, chat_shared_handler))
    app.add_handler(conv)

    app.run_polling()

if __name__ == "__main__":
    main()
