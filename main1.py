import os
import json
import asyncio
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButtonRequestChat,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from clone_worker import clone_worker

CONFIG_FILE = "config.json"
BOT_TOKEN = json.load(open("bot.json"))["bot_token"]

# Helpers
def save_channel_id(key, chat_id):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    config[key] = chat_id
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_user_cfg = KeyboardButton("User Config")
    btn_src_tgt = KeyboardButton("Source/Target")
    btn_start_msn = KeyboardButton("Start Mission")
    keyboard = [[btn_user_cfg], [btn_src_tgt], [btn_start_msn]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Select an option:", reply_markup=markup)

# /start_mission → Show full or range
async def handle_start_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    btn_full = KeyboardButton("Full Clone")
    btn_range = KeyboardButton("Range Clone")
    markup = ReplyKeyboardMarkup([[btn_full], [btn_range]], resize_keyboard=True)
    await update.message.reply_text("Choose clone type:", reply_markup=markup)

# Full Clone
async def handle_full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Starting full clone...")
    await clone_worker()

# Handle shared channels
async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.chat_shared:
        return
    shared = update.message.chat_shared
    if shared.request_id == 1:
        save_channel_id("source_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Source set: `{shared.chat_id}`", parse_mode="Markdown")
    elif shared.request_id == 2:
        save_channel_id("target_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Target set: `{shared.chat_id}`", parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("User Config"), handle_start_mission))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Start Mission"), handle_start_mission))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Full Clone"), handle_full_clone))
    app.add_handler(MessageHandler(filters.ALL, chat_shared_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
