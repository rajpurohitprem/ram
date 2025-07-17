import os
import json
import asyncio
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
STOP_FILE = "stop.flag"

# Load bot token
with open(BOT_FILE) as f:
    BOT_TOKEN = json.load(f)["bot_token"]

# ---------------------- UTILS ----------------------
def log_error(msg):
    with open("errors.txt", "a") as f:
        f.write(f"{datetime.now()}: {msg}\n")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def save_clone_state(start_id=None, end_id=None):
    state = {
        'last_start': start_id,
        'last_end': end_id,
        'timestamp': datetime.now().isoformat()
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def load_clone_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return None

def clear_clone_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)

# ---------------------- KEYBOARDS ----------------------
def main_menu():
    return ReplyKeyboardMarkup([
        ["User Config", "Source/Target"],
        ["Start Mission"]
    ], resize_keyboard=True)

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

# ---------------------- HANDLERS ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Main Menu", reply_markup=main_menu())
    return MAIN_MENU

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)

async def user_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("User Config", reply_markup=user_config_menu())
    return USER_CONFIG

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    safe_config = config.copy()
    if 'api_hash' in safe_config:
        safe_config['api_hash'] = f"{safe_config['api_hash'][:4]}...{safe_config['api_hash'][-4:]}"
    if 'phone' in safe_config:
        safe_config['phone'] = f"{safe_config['phone'][:3]}...{safe_config['phone'][-2:]}"
    
    await update.message.reply_text(
        f"<pre>{json.dumps(safe_config, indent=2)}</pre>",
        parse_mode="HTML",
        reply_markup=user_config_menu()
    )
    return USER_CONFIG

async def request_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter API ID (number):")
    return WAITING_FOR_API_ID

async def save_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/start":
        return await start(update, context)
    if text.lower() == "skip":
        await update.message.reply_text("Skipped", reply_markup=user_config_menu())
        return USER_CONFIG
    
    try:
        api_id = int(text)
        ensure_config_key("api_id", api_id)
        await update.message.reply_text("✅ API ID saved!", reply_markup=main_menu())
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text("❌ Must be a number. Try again:")
        return WAITING_FOR_API_ID

async def request_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter API Hash (32 chars):")
    return WAITING_FOR_API_HASH

async def save_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/start":
        return await start(update, context)
    if text.lower() == "skip":
        await update.message.reply_text("Skipped", reply_markup=user_config_menu())
        return USER_CONFIG
    
    if len(text) == 32 and all(c in '0123456789abcdef' for c in text.lower()):
        ensure_config_key("api_hash", text)
        await update.message.reply_text("✅ API Hash saved!", reply_markup=main_menu())
        return MAIN_MENU
    else:
        await update.message.reply_text("❌ Must be 32-char hex string. Try again:")
        return WAITING_FOR_API_HASH

async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter phone (with country code):")
    return WAITING_FOR_PHONE

async def save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() == "/start":
        return await start(update, context)
    if text.lower() == "skip":
        await update.message.reply_text("Skipped", reply_markup=user_config_menu())
        return USER_CONFIG
    
    if text.startswith('+') and text[1:].isdigit() and len(text) >= 8:
        ensure_config_key("phone", text)
        await update.message.reply_text("✅ Phone saved!", reply_markup=main_menu())
        return MAIN_MENU
    else:
        await update.message.reply_text("❌ Invalid format. Try again:")
        return WAITING_FOR_PHONE

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    try:
        client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
        await client.connect()
        
        if not await client.is_user_authorized():
            sent_code = await client.send_code_request(config["phone"])
            context.user_data["client"] = client
            context.user_data["phone_code_hash"] = sent_code.phone_code_hash
            await update.message.reply_text("📲 Enter the 5-digit code:")
            return WAITING_FOR_CODE
        else:
            await update.message.reply_text("✅ Already logged in!", reply_markup=main_menu())
            return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {str(e)}")
        return USER_CONFIG

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.replace(" ", "")
    try:
        client = context.user_data["client"]
        await client.sign_in(
            phone=load_config()["phone"],
            code=code,
            phone_code_hash=context.user_data["phone_code_hash"]
        )
        await update.message.reply_text("✅ Login successful!", reply_markup=main_menu())
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)}\nTry /login again")
        return USER_CONFIG

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    await update.message.reply_text("✅ Logged out", reply_markup=main_menu())
    return MAIN_MENU

async def source_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Select channels:", reply_markup=source_target_menu())
    return SOURCE_TARGET

async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared
    if shared.request_id == 1:
        ensure_config_key("source_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Source set: {shared.chat_id}")
    elif shared.request_id == 2:
        ensure_config_key("target_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Target set: {shared.chat_id}")
    return SOURCE_TARGET

async def start_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    show_resume = os.path.exists(STATE_FILE)
    await update.message.reply_text(
        "Mission Control", 
        reply_markup=mission_menu(show_resume=show_resume)
    )
    return MISSION

async def full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Starting full clone...")
    os.system(f"python clone_worker.py --chat_id {update.effective_chat.id} &")
    return MAIN_MENU

async def request_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enter start message ID:")
    return WAITING_FOR_RANGE_START

async def set_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["range_start"] = int(update.message.text)
        await update.message.reply_text("Enter end message ID:")
        return WAITING_FOR_RANGE_END
    except ValueError:
        await update.message.reply_text("❌ Must be a number. Try again:")
        return WAITING_FOR_RANGE_START

async def set_range_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        start_id = context.user_data["range_start"]
        end_id = int(update.message.text)
        await update.message.reply_text(f"🚀 Cloning {start_id} to {end_id}...")
        os.system(f"python clone_worker.py --chat_id {update.effective_chat.id} --start {start_id} --end {end_id} &")
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text("❌ Must be a number. Try again:")
        return WAITING_FOR_RANGE_END

async def resume_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_clone_state()
    if state:
        await update.message.reply_text(f"🔄 Resuming from {state['last_start']}...")
        os.system(
            f"python clone_worker.py --chat_id {update.effective_chat.id} "
            f"--start {state['last_start']} --end {state['last_end']} &"
        )
    else:
        await update.message.reply_text("⚠️ No clone to resume")
    return MAIN_MENU

async def stop_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(STOP_FILE, "w") as f:
        f.write("stop")
    save_clone_state(
        context.user_data.get("range_start"),
        context.user_data.get("range_end")
    )
    await update.message.reply_text(
        "⏸ Clone paused",
        reply_markup=mission_menu(show_resume=True)
    )
    return MISSION

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    print(f"Error: {error}")
    if update and update.message:
        await update.message.reply_text(f"⚠️ Error: {str(error)[:200]}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Global commands
    #app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", lambda u,c: u.message.reply_text(
        "Help:\n"
        "/start - Main menu\n"
        "/help - This message\n"
        "Use buttons to navigate"
    )))

    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^User Config$"), user_config),
            MessageHandler(filters.Regex("^Source/Target$"), source_target),
            MessageHandler(filters.Regex("^Start Mission$"), start_mission),
        ],
        states={
            MAIN_MENU: [
                CommandHandler("start", start),
                MessageHandler(filters.Regex("^User Config$"), user_config),
                MessageHandler(filters.Regex("^Source/Target$"), source_target),
                MessageHandler(filters.Regex("^Start Mission$"), start_mission),
            ],
            USER_CONFIG: [
                CommandHandler("start", start),
                MessageHandler(filters.Regex("^Api ID$"), request_api_id),
                MessageHandler(filters.Regex("^Api Hash$"), request_api_hash),
                MessageHandler(filters.Regex("^Phone No\.$"), request_phone),
                MessageHandler(filters.Regex("^Login$"), login),
                MessageHandler(filters.Regex("^Logout$"), logout),
                MessageHandler(filters.Regex("^Show Config$"), show_config),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            ],
            WAITING_FOR_API_ID: [CommandHandler("start", start),
                                 MessageHandler(filters.TEXT, save_api_id)],
            WAITING_FOR_API_HASH: [CommandHandler("start", start),
                                   MessageHandler(filters.TEXT, save_api_hash)],
            WAITING_FOR_PHONE: [CommandHandler("start", start),
                                MessageHandler(filters.TEXT, save_phone)],
            WAITING_FOR_CODE: [CommandHandler("start", start),
                               MessageHandler(filters.TEXT, verify_code)],
            SOURCE_TARGET: [
                CommandHandler("start", start),
                MessageHandler(filters.StatusUpdate.CHAT_SHARED, chat_shared_handler),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            ],
            MISSION: [
                CommandHandler("start", start),
                MessageHandler(filters.Regex("^Full Clone$"), full_clone),
                MessageHandler(filters.Regex("^Range Clone$"), request_range_start),
                MessageHandler(filters.Regex("^Resume Clone$"), resume_clone),
                MessageHandler(filters.Regex("^Stop$"), stop_clone),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            ],
            WAITING_FOR_RANGE_START: [CommandHandler("start", start),
                                      MessageHandler(filters.TEXT, set_range_start)],
            WAITING_FOR_RANGE_END: [CommandHandler("start", start),
                                    MessageHandler(filters.TEXT, set_range_end)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
