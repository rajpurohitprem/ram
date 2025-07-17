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
from clone_worker import clone_worker
from telethon.sync import TelegramClient
from telegram.constants import ParseMode

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
        ["⬅ Back", "skip"]
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
        ["Stop", "⬅ Back", "skip"]
    ], resize_keyboard=True)

# ---------------------- STATES ----------------------
(
    MAIN_MENU,
    USER_CONFIG,
    WAITING_FOR_API_ID,
    WAITING_FOR_API_HASH,
    WAITING_FOR_PHONE,
    WAITING_FOR_CODE,
    SOURCE_TARGET,
    MISSION,
    WAITING_FOR_RANGE_START,
    WAITING_FOR_RANGE_END
) = range(10)

# ---------------------- HANDLERS ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Main Menu", reply_markup=main_menu())
    return MAIN_MENU

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def check_start_command(update: Update, text: str):
    if text.lower() == "/start":
        await start(update, ContextTypes.DEFAULT_TYPE)
        return True
    return False

# Modified handlers with start command check
async def user_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
            break
        return MAIN_MENU
    await update.message.reply_text("User Config:", reply_markup=user_config_menu())
    return USER_CONFIG

async def source_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        break
        return MAIN_MENU
    await update.message.reply_text("Select source or target channel.", reply_markup=source_target_menu())
    return SOURCE_TARGET

async def start_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        break
        return MAIN_MENU
    await update.message.reply_text("Choose clone mode:", reply_markup=mission_menu())
    return MISSION

async def request_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        break
        return MAIN_MENU
    await update.message.reply_text("Please send your API ID:")
    return WAITING_FOR_API_ID

async def save_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        break
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=user_config_menu())
        return USER_CONFIG
    try:
        ensure_config_key("api_id", int(text))
        await update.message.reply_text("✅ API ID saved.", reply_markup=main_menu())
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text("❌ Invalid API ID. Must be a number.")
        return WAITING_FOR_API_ID

# ... [similar modifications for all other handlers] ...

async def full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("🚀 Starting full clone...")
    asyncio.create_task(clone_worker())
    await update.message.reply_text("📥 Cloning started...", reply_markup=main_menu())
    return MAIN_MENU

# ---------------------- MAIN ----------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Add global /start command
    app.add_handler(CommandHandler("start", start))
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^User Config$"), user_config),
            MessageHandler(filters.Regex("^Source/Target$"), source_target),
            MessageHandler(filters.Regex("^Start Mission$"), start_mission),
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^User Config$"), user_config),
                MessageHandler(filters.Regex("^Source/Target$"), source_target),
                MessageHandler(filters.Regex("^Start Mission$"), start_mission),
            ],
            # ... [other states with CommandHandler('start', start) added] ...
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            MessageHandler(filters.Regex("^skip$"), back_to_main),
        ],
    )

    app.add_handler(conv_handler)
    print("🤖 Bot Is Running")
    app.run_polling()

if __name__ == "__main__":
    main()
