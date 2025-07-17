import json
import asyncio
import os
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
from clone_worker import clone_worker  # <- Import clone logic

# Load token
with open("bot.json") as f:
    bot_data = json.load(f)
BOT_TOKEN = bot_data["bot_token"]
CONFIG_FILE = "config.json"

# Flags
is_cloning = False

# Save channel ID
def save_channel_id(key, chat_id):
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    config[key] = chat_id
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# Show Start Mission Menu
async def show_start_mission_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_clone = KeyboardButton("🌀 Full Clone")
    range_clone = KeyboardButton("🔢 Range Clone")
    stop_btn = KeyboardButton("⛔ Stop Clone")
    keyboard = [[full_clone], [range_clone], [stop_btn]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("📦 Choose Clone Option:", reply_markup=markup)

# Handle /panel or /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    source_btn = KeyboardButton(
        text="Select Source Channel",
        request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True)
    )
    target_btn = KeyboardButton(
        text="Select Target Channel",
        request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=True)
    )
    keyboard = [[source_btn], [target_btn], [KeyboardButton("🚀 Start Mission")]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("⚙️ Configure Source/Target:", reply_markup=markup)

# Handle shared channel selection
async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared
    if not shared:
        return
    if shared.request_id == 1:
        save_channel_id("source_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Source channel saved:\n`{shared.chat_id}`", parse_mode="Markdown")
    elif shared.request_id == 2:
        save_channel_id("target_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Target channel saved:\n`{shared.chat_id}`", parse_mode="Markdown")

# Handle button presses (Clone actions)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_cloning
    text = update.message.text

    if text == "🚀 Start Mission":
        await show_start_mission_menu(update, context)

    elif text == "🌀 Full Clone":
        if is_cloning:
            await update.message.reply_text("⏳ A clone is already in progress.")
            return
        await update.message.reply_text("🔄 Starting Full Clone...")
        is_cloning = True
        asyncio.create_task(run_clone(update))

    elif text == "🔢 Range Clone":
        await update.message.reply_text("✏️ Send range like:\n`start_id end_id`\nExample: `100 200`", parse_mode="Markdown")

    elif text == "⛔ Stop Clone":
        with open("stop.flag", "w") as f:
            f.write("stop")
        await update.message.reply_text("🛑 Clone stop requested.")

    elif " " in text and all(x.isdigit() for x in text.split()) and len(text.split()) == 2:
        start_id, end_id = map(int, text.split())
        if is_cloning:
            await update.message.reply_text("⏳ A clone is already in progress.")
            return
        await update.message.reply_text(f"🔄 Starting Range Clone from {start_id} to {end_id}...")
        is_cloning = True
        asyncio.create_task(run_clone(update, start_id, end_id))

async def run_clone(update: Update, start_id=None, end_id=None):
    global is_cloning
    try:
        await clone_messages(update=update, range_start=start_id, range_end=end_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Clone failed: {e}")
    is_cloning = False

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("panel", start))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, chat_shared_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
