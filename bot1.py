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
PROGRESS_FILE = "clone_progress.json"
STOP_FILE = "stop.flag"
SENT_LOG = "sent_ids.txt"

# Ensure required files exist
for f in [CONFIG_FILE, BOT_FILE]:
    if not os.path.exists(f):
        open(f, 'w').close()

# Load bot token
try:
    with open(BOT_FILE) as f:
        BOT_TOKEN = json.load(f).get("bot_token", "")
except:
    BOT_TOKEN = ""

# ---------------------- UTILS ----------------------
def log_error(msg):
    with open("errors.log", "a") as f:
        f.write(f"{datetime.now()}: {msg}\n")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def ensure_config_key(key, value):
    config = load_config()
    config[key] = value
    save_config(config)

def get_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {"status": "inactive", "progress": 0, "total": 0, "current": "", "chat_id": None}

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
    for f in [STATE_FILE, PROGRESS_FILE, STOP_FILE]:
        if os.path.exists(f):
            os.remove(f)

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

async def run_worker(chat_id, start_id=None, end_id=None):
    """Run the clone worker in a subprocess"""
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
    return clone_process

async def stop_clone_handler():
    """Gracefully stop the clone process"""
    global clone_process
    if clone_process:
        clone_process.terminate()
        try:
            await asyncio.wait_for(clone_process.wait(), timeout=5)
        except asyncio.TimeoutError:
            clone_process.kill()
        clone_process = None
    clear_clone_state()

# ---------------------- HANDLERS ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler - main entry point"""
    context.user_data.clear()
    show_status = get_progress()["status"] == "active"
    await update.message.reply_text(
        "🤖 Telegram Cloner Bot\n\n"
        "Main Menu Options:\n"
        "• User Config - Setup API credentials\n"
        "• Source/Target - Configure channels\n"
        "• Start Mission - Begin cloning\n"
        "• Cloning Status - View current progress",
        reply_markup=main_menu(show_status)
    )
    return MAIN_MENU

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    return await start(update, context)

async def clone_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current cloning progress"""
    progress = get_progress()
    if progress["status"] == "active":
        percent = (progress["progress"]/progress["total"])*100 if progress["total"] > 0 else 0
        await update.message.reply_text(
            f"🔄 Clone Status\n\n"
            f"📊 Progress: {progress['progress']}/{progress['total']} ({percent:.1f}%)\n"
            f"📄 Current: {progress['current']}\n"
            f"⏱ Last Update: {progress.get('timestamp', 'Just now')}",
            reply_markup=main_menu(show_status=True)
        )
    else:
        await update.message.reply_text(
            "✅ No active clone operations",
            reply_markup=main_menu()
        )

async def user_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User configuration menu"""
    if get_progress()["status"] == "active":
        await update.message.reply_text(
            "⚠️ Please stop any active clone operations first",
            reply_markup=main_menu(show_status=True)
        )
        return MAIN_MENU
    await update.message.reply_text(
        "⚙️ User Configuration\n\n"
        "Configure your Telegram API credentials:",
        reply_markup=user_config_menu()
    )
    return USER_CONFIG

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current configuration"""
    config = load_config()
    safe_config = config.copy()
    if 'api_hash' in safe_config:
        safe_config['api_hash'] = f"{safe_config['api_hash'][:4]}...{safe_config['api_hash'][-4:]}"
    if 'phone' in safe_config:
        safe_config['phone'] = f"{safe_config['phone'][:3]}...{safe_config['phone'][-2:]}"
    
    await update.message.reply_text(
        f"📋 Current Configuration:\n<pre>{json.dumps(safe_config, indent=2)}</pre>\n"
        "🔒 Sensitive values are partially hidden",
        parse_mode="HTML",
        reply_markup=user_config_menu()
    )
    return USER_CONFIG

async def request_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request API ID input"""
    await update.message.reply_text(
        "🔢 Please enter your Telegram API ID (numeric):\n"
        "Type /start to cancel",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )
    return WAITING_FOR_API_ID

async def save_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save API ID to config"""
    text = update.message.text.strip()
    if text.lower() == "/start":
        return await start(update, context)
    if text.lower() == "skip":
        await update.message.reply_text("↩️ API ID remains unchanged", reply_markup=user_config_menu())
        return USER_CONFIG
    
    try:
        api_id = int(text)
        if api_id <= 0:
            raise ValueError
        ensure_config_key("api_id", api_id)
        await update.message.reply_text(
            "✅ API ID saved successfully!",
            reply_markup=main_menu()
        )
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid API ID. Must be a positive number.\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_API_ID

async def request_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request API Hash input"""
    await update.message.reply_text(
        "🔑 Please enter your Telegram API Hash (32-character hexadecimal):\n"
        "Type /start to cancel",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )
    return WAITING_FOR_API_HASH

async def save_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save API Hash to config"""
    text = update.message.text.strip().lower()
    if text == "/start":
        return await start(update, context)
    if text == "skip":
        await update.message.reply_text("↩️ API Hash remains unchanged", reply_markup=user_config_menu())
        return USER_CONFIG
    
    if len(text) == 32 and all(c in '0123456789abcdef' for c in text):
        ensure_config_key("api_hash", text)
        await update.message.reply_text(
            "✅ API Hash saved successfully!",
            reply_markup=main_menu()
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "❌ Invalid API Hash. Must be 32-character hexadecimal.\n"
            "Example: 1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_API_HASH

async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request phone number input"""
    await update.message.reply_text(
        "📱 Please enter your phone number with country code:\n"
        "Example: +1234567890\n"
        "Type /start to cancel",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )
    return WAITING_FOR_PHONE

async def save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save phone number to config"""
    text = update.message.text.strip()
    if text.lower() == "/start":
        return await start(update, context)
    if text.lower() == "skip":
        await update.message.reply_text("↩️ Phone number remains unchanged", reply_markup=user_config_menu())
        return USER_CONFIG
    
    if text.startswith('+') and text[1:].isdigit() and len(text) >= 8:
        ensure_config_key("phone", text)
        await update.message.reply_text(
            "✅ Phone number saved successfully!",
            reply_markup=main_menu()
        )
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "❌ Invalid phone format. Must be international format with country code.\n"
            "Example: +1234567890\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_PHONE

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiate Telegram login"""
    config = load_config()
    if not all(k in config for k in ("api_id", "api_hash", "phone")):
        await update.message.reply_text(
            "⚠️ Please configure API ID, Hash, and Phone first",
            reply_markup=user_config_menu()
        )
        return USER_CONFIG
    
    try:
        from telethon import TelegramClient
        client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
        await client.connect()
        
        if not await client.is_user_authorized():
            sent_code = await client.send_code_request(config["phone"])
            context.user_data["client"] = client
            context.user_data["phone_code_hash"] = sent_code.phone_code_hash
            await update.message.reply_text(
                "📲 Verification code sent!\n"
                "Please enter the 5-digit code in format: 1 2 3 4 5\n"
                "Type /start to cancel"
            )
            return WAITING_FOR_CODE
        
        await update.message.reply_text(
            "✅ Already logged in!",
            reply_markup=main_menu()
        )
        await client.disconnect()
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(
            f"❌ Login failed: {str(e)}\n"
            "Please check your credentials and try again",
            reply_markup=user_config_menu()
        )
        return USER_CONFIG

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify Telegram login code"""
    code = update.message.text.replace(" ", "")
    if not code.isdigit() or len(code) != 5:
        await update.message.reply_text(
            "❌ Invalid code format. Must be 5 digits.\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_CODE
    
    try:
        client = context.user_data["client"]
        await client.sign_in(
            phone=load_config()["phone"],
            code=code,
            phone_code_hash=context.user_data["phone_code_hash"]
        )
        await update.message.reply_text(
            "✅ Login successful!",
            reply_markup=main_menu()
        )
        await client.disconnect()
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(
            f"❌ Verification failed: {str(e)}\n"
            "Please try /login again",
            reply_markup=user_config_menu()
        )
        return USER_CONFIG

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Logout and clear session"""
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
    await update.message.reply_text(
        "✅ Logged out successfully",
        reply_markup=main_menu()
    )
    return MAIN_MENU

async def source_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Source/Target channel configuration"""
    if get_progress()["status"] == "active":
        await update.message.reply_text(
            "⚠️ Cannot change channels during active clone operation",
            reply_markup=main_menu(show_status=True)
        )
        return MAIN_MENU
    
    await update.message.reply_text(
        "📡 Channel Configuration\n\n"
        "Select source and target channels:",
        reply_markup=source_target_menu()
    )
    return SOURCE_TARGET

async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel selection"""
    shared = update.message.chat_shared
    if not shared:
        return SOURCE_TARGET
    
    if shared.request_id == 1:
        ensure_config_key("source_channel_id", shared.chat_id)
        await update.message.reply_text(
            f"✅ Source channel set: {shared.chat_id}",
            reply_markup=source_target_menu()
        )
    elif shared.request_id == 2:
        ensure_config_key("target_channel_id", shared.chat_id)
        await update.message.reply_text(
            f"✅ Target channel set: {shared.chat_id}",
            reply_markup=source_target_menu()
        )
    return SOURCE_TARGET

async def start_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mission control menu"""
    config = load_config()
    if not all(k in config for k in ("source_channel_id", "target_channel_id")):
        await update.message.reply_text(
            "⚠️ Please configure source and target channels first",
            reply_markup=main_menu()
        )
        return MAIN_MENU
    
    show_resume = os.path.exists(STATE_FILE)
    await update.message.reply_text(
        "🚀 Mission Control\n\n"
        "Choose cloning mode:",
        reply_markup=mission_menu(show_resume=show_resume)
    )
    return MISSION

async def full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start full clone operation"""
    await update.message.reply_text(
        "🔄 Starting full channel clone...",
        reply_markup=main_menu(show_status=True)
    )
    await run_worker(update.effective_chat.id)
    return MAIN_MENU

async def request_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request start of range clone"""
    await update.message.reply_text(
        "🔢 Enter starting message ID:\n"
        "Type /start to cancel",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )
    return WAITING_FOR_RANGE_START

async def set_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set range start ID"""
    try:
        start_id = int(update.message.text)
        context.user_data["range_start"] = start_id
        await update.message.reply_text(
            "🔢 Enter ending message ID:\n"
            "Type /start to cancel",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return WAITING_FOR_RANGE_END
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid message ID. Must be a number.\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_RANGE_START

async def set_range_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set range end ID and start clone"""
    try:
        end_id = int(update.message.text)
        start_id = context.user_data["range_start"]
        await update.message.reply_text(
            f"🔄 Cloning messages {start_id} to {end_id}...",
            reply_markup=main_menu(show_status=True)
        )
        await run_worker(update.effective_chat.id, start_id, end_id)
        return MAIN_MENU
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid message ID. Must be a number.\n"
            "Please try again or type /start to cancel"
        )
        return WAITING_FOR_RANGE_END

async def resume_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume paused clone operation"""
    state = load_clone_state()
    if state:
        await update.message.reply_text(
            f"🔄 Resuming clone from message {state['last_start']}...",
            reply_markup=main_menu(show_status=True)
        )
        await run_worker(update.effective_chat.id, state["last_start"], state["last_end"])
    else:
        await update.message.reply_text(
            "⚠️ No paused clone operation found",
            reply_markup=mission_menu()
        )
        return MISSION
    return MAIN_MENU

async def stop_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current clone operation"""
    with open(STOP_FILE, "w") as f:
        f.write("stop")
    
    if "range_start" in context.user_data:
        save_clone_state(
            context.user_data["range_start"],
            context.user_data.get("range_end")
        )
    
    await update.message.reply_text(
        "⏸ Clone operation paused",
        reply_markup=mission_menu(show_resume=True)
    )
    return MISSION

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in telegram bot"""
    error = context.error
    print(f"Error: {error}")
    
    if update and update.message:
        await update.message.reply_text(
            f"⚠️ An error occurred: {str(error)[:200]}",
            reply_markup=main_menu()
        )

# ---------------------- MAIN ----------------------
def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ Error: No bot token found in bot.json")
        return
    
    # Create required files if they don't exist
    for f in [SENT_LOG, PROGRESS_FILE]:
        if not os.path.exists(f):
            open(f, 'w').close()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add global commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", lambda u,c: u.message.reply_text(
        "🤖 Telegram Cloner Bot Help\n\n"
        "Available commands:\n"
        "/start - Return to main menu\n"
        "/help - Show this message\n\n"
        "Use the interactive buttons to navigate through the bot",
        reply_markup=main_menu()
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
                MessageHandler(filters.Regex("^User Config$"), user_config),
                MessageHandler(filters.Regex("^Source/Target$"), source_target),
                MessageHandler(filters.Regex("^Start Mission$"), start_mission),
                MessageHandler(filters.Regex("^Cloning Status$"), clone_status),
            ],
            USER_CONFIG: [
                MessageHandler(filters.Regex("^Api ID$"), request_api_id),
                MessageHandler(filters.Regex("^Api Hash$"), request_api_hash),
                MessageHandler(filters.Regex("^Phone No\.$"), request_phone),
                MessageHandler(filters.Regex("^Login$"), login),
                MessageHandler(filters.Regex("^Logout$"), logout),
                MessageHandler(filters.Regex("^Show Config$"), show_config),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
                CommandHandler("start", start),
            ],
            WAITING_FOR_API_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_api_id),
                CommandHandler("start", start),
            ],
            WAITING_FOR_API_HASH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_api_hash),
                CommandHandler("start", start),
            ],
            WAITING_FOR_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_phone),
                CommandHandler("start", start),
            ],
            WAITING_FOR_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code),
                CommandHandler("start", start),
            ],
            SOURCE_TARGET: [
                MessageHandler(filters.StatusUpdate.CHAT_SHARED, chat_shared_handler),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
                CommandHandler("start", start),
            ],
            MISSION: [
                MessageHandler(filters.Regex("^Full Clone$"), full_clone),
                MessageHandler(filters.Regex("^Range Clone$"), request_range_start),
                MessageHandler(filters.Regex("^Resume Clone$"), resume_clone),
                MessageHandler(filters.Regex("^Stop$"), stop_clone),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
                CommandHandler("start", start),
            ],
            WAITING_FOR_RANGE_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_range_start),
                CommandHandler("start", start),
            ],
            WAITING_FOR_RANGE_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_range_end),
                CommandHandler("start", start),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)

    # Start the bot
    print("🤖 Bot starting...")
    try:
        app.run_polling()
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
    finally:
        print("🛑 Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
