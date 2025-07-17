import os
import json
import asyncio
import subprocess
from datetime import datetime
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

# Configuration
CONFIG_FILE = "config.json"
BOT_FILE = "bot.json"
SESSION_FILE = "anon.session"
STATE_FILE = "clone_state.json"
PROGRESS_FILE = "clone_progress.json"

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

def get_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {"status": "inactive", "progress": 0, "total": 0, "current_file": ""}

# ---------------------- KEYBOARDS ----------------------
def main_menu(show_status=False):
    buttons = [
        ["User Config", "Source/Target"],
        ["Start Mission"]
    ]
    if show_status:
        buttons.insert(1, ["Cloning Status"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

def user_config_menu():
    return ReplyKeyboardMarkup([
        ["Api ID", "Api Hash", "Phone No."],
        ["Login", "Logout", "Show Config"],
        ["⬅ Back", "skip"]
    ], resize_keyboard=True)

def source_target_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Select Source Channel", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))],
        [KeyboardButton("Select Target Channel", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=True))],
        ["⬅ Back"]
    ], resize_keyboard=True)

def mission_menu(show_resume=False):
    buttons = [
        ["Full Clone", "Range Clone"],
        ["Stop", "⬅ Back", "skip"]
    ]
    if show_resume:
        buttons.insert(1, ["Resume Clone"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

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

# ---------------------- CLONE MANAGEMENT ----------------------
clone_process = None

async def start_clone(chat_id, start_id=None, end_id=None):
    global clone_process
    args = ['python', 'clone_worker.py', '--chat_id', str(chat_id)]
    if start_id:
        args.extend(['--start', str(start_id)])
    if end_id:
        args.extend(['--end', str(end_id)])
    
    clone_process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

async def stop_clone_handler():
    global clone_process
    if clone_process:
        clone_process.terminate()
        try:
            await asyncio.wait_for(clone_process.wait(), timeout=5)
        except asyncio.TimeoutError:
            clone_process.kill()
        clone_process = None

# ---------------------- HANDLERS ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    show_status = get_progress()["status"] == "active"
    await update.message.reply_text("Main Menu", reply_markup=main_menu(show_status))
    return MAIN_MENU

async def clone_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    progress = get_progress()
    if progress["status"] == "active":
        message = (
            f"🔄 Clone Status\n"
            f"Progress: {progress['progress']}/{progress['total']}\n"
            f"Current: {progress['current_file']}\n"
            f"{(progress['progress']/progress['total'])*100:.1f}% complete"
        )
    else:
        message = "✅ No active clone operations"
    await update.message.reply_text(message)

async def full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Starting full clone...")
    await start_clone(update.effective_chat.id)
    return MAIN_MENU

async def set_range_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_id = context.user_data["range_start"]
        end_id = int(update.message.text)
        await update.message.reply_text(f"🚀 Cloning {start_id} to {end_id}...")
        await start_clone(update.effective_chat.id, start_id, end_id)
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text("❌ Must be a number. Try again:")
        return WAITING_FOR_RANGE_END

async def stop_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await stop_clone_handler()
    await update.message.reply_text("⏸ Clone stopped", reply_markup=main_menu())
    return MAIN_MENU

# ... [other handlers remain the same] ...

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Add status polling task
    async def status_poller(context: ContextTypes.DEFAULT_TYPE):
        while True:
            progress = get_progress()
            if progress["status"] == "active":
                await context.bot.send_message(
                    chat_id=progress["chat_id"],
                    text=f"Progress: {progress['progress']}/{progress['total']}",
                    reply_markup=main_menu(show_status=True)
                )
            await asyncio.sleep(30)

    app.job_queue.run_repeating(status_poller, interval=30.0)

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^Cloning Status$"), clone_status),
                # ... [other handlers] ...
            ],
            # ... [other states] ...
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
