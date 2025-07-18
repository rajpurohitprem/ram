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
START_FLAG = "start.flag"



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
        ["Mission Status"]
    ], resize_keyboard=True)

def user_config_menu():
    return ReplyKeyboardMarkup([
        ["Api ID", "Api Hash", "Phone No."],
        ["Login", "Logout","Show Config"],
        ["⬅ Back", "skip"]
    ], resize_keyboard=True)

def source_target_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Select Source Channel", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))],
        [KeyboardButton("Select Target Channel", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=True))],
        ["⬅ Back"]
    ], resize_keyboard=True)

#def mission_menu():
#    return ReplyKeyboardMarkup([
#        ["Full Clone", "Range Clone"],
#        [ "Stop""⬅ Back", "skip"]
#    ], resize_keyboard=True)
def mission_menu():
    return ReplyKeyboardMarkup([
        ["Full Clone", "Range Clone"],
        ["Resume Clone"],
        ["Stop", "⬅ Back", "skip"]
    ], resize_keyboard=True)

    
# Add to your utils section
def save_clone_state(start_id=None, end_id=None):
    state = {
        'last_start': start_id,
        'last_end': end_id,
        'timestamp': datetime.now().isoformat()
    }
    with open('clone_state.json', 'w') as f:
        json.dump(state, f)

def load_clone_state():
    try:
        with open('clone_state.json') as f:
            return json.load(f)
    except:
        return None

def clear_clone_state():
    if os.path.exists('clone_state.json'):
        os.remove('clone_state.json')
        
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

# ---------------------- HANDLERS ----------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Welcome! Use buttons to configure and start cloning.", reply_markup=main_menu())
    return MAIN_MENU

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Main Menu:", reply_markup=main_menu())
    return MAIN_MENU

async def check_start_command(update: Update, text: str):
    if text.lower() == "/start":
        await start(update, ContextTypes.DEFAULT_TYPE)
        return True
    return False
    
async def user_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("User Config:", reply_markup=user_config_menu())
    return USER_CONFIG

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        config = load_config()
        
        # Hide sensitive info
        safe_config = config.copy()
        if 'api_hash' in safe_config:
            safe_config['api_hash'] = f"{safe_config['api_hash'][:4]}...{safe_config['api_hash'][-4:]}"
        if 'phone' in safe_config:
            safe_config['phone'] = f"{safe_config['phone'][:3]}...{safe_config['phone'][-2:]}"
        
        formatted_config = json.dumps(safe_config, indent=2)
        
        await update.message.reply_text(
            f"<b>Current Configuration:</b>\n"
            f"<pre>{formatted_config}</pre>\n"
            f"<i>Sensitive fields are partially hidden</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=user_config_menu()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error loading config: {str(e)}",
            reply_markup=user_config_menu()
        )
    return USER_CONFIG
    
async def source_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("Select source or target channel.", reply_markup=source_target_menu())
    return SOURCE_TARGET

async def start_mission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("Choose clone mode:", reply_markup=mission_menu())
    return MISSION

async def request_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("Please send your API ID:")
    return WAITING_FOR_API_ID

async def request_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("Please send your API Hash:")
    return WAITING_FOR_API_HASH

async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    config = load_config()
    current = config.get("phone", "Not Set")
    await update.message.reply_text(f"Current number: `{current}`\nSend new phone number or type 'skip' to keep.", parse_mode="Markdown")
    return WAITING_FOR_PHONE

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    config = load_config()
    if not all(k in config for k in ("api_id", "api_hash", "phone")):
        await update.message.reply_text("Please configure API ID, Hash, and Phone first.")
        return USER_CONFIG
    
    try:
        client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
        await client.connect()
        
        if not await client.is_user_authorized():
            sent_code = await client.send_code_request(config["phone"])
            context.user_data["client"] = client
            context.user_data["phone"] = config["phone"]
            context.user_data["phone_code_hash"] = sent_code.phone_code_hash
            
            await update.message.reply_text(
                "📲 Code sent. Please reply with the code in format: 1 2 3 4 5\n"
                "(Enter the numbers separated by spaces)"
            )
            return WAITING_FOR_CODE
        
        await update.message.reply_text("✅ Already logged in.", reply_markup=main_menu())
        await client.disconnect()
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(f"❌ Login failed: {str(e)}")
        return USER_CONFIG   
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.connect()
    
    if not await client.is_user_authorized():
        await client.send_code_request(config["phone"])
        await update.message.reply_text("📲 Code sent. Please reply with the code:")
        context.user_data["client"] = client
        return USER_CONFIG
    
    await update.message.reply_text("✅ Already logged in.")
    await client.disconnect()
    return USER_CONFIG

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    code = update.message.text.replace(" ", "")  # Remove spaces from "1 2 3 4 5" format
    if not code.isdigit() or len(code) != 5:
        await update.message.reply_text("❌ Invalid code format. Please send 5 digits (e.g., '1 2 3 4 5')")
        return WAITING_FOR_CODE
    
    try:
        client = context.user_data["client"]
        await client.sign_in(
            phone=context.user_data["phone"],
            code=code,
            phone_code_hash=context.user_data["phone_code_hash"]
        )
        await update.message.reply_text("✅ Login successful!", reply_markup=main_menu())
        await client.disconnect()
        return MAIN_MENU
    except Exception as e:
        await update.message.reply_text(f"❌ Verification failed: {str(e)}\nPlease try again:")
        return WAITING_FOR_CODE
        
async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)
        await update.message.reply_text("🔒 Logged out and session removed.")
    else:
        await update.message.reply_text("No session to remove.")
    return USER_CONFIG

async def save_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=user_config_menu())
        return USER_CONFIG
    
    try:
        if await check_start_command(update, update.message.text):
            return await start(update, context)
        ensure_config_key("api_id", int(text))
        await update.message.reply_text("✅ API ID saved.", reply_markup=user_config_menu())
        return USER_CONFIG
    except ValueError:
        await update.message.reply_text("❌ Invalid API ID. Must be a number.")
        return WAITING_FOR_API_ID

async def save_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=user_config_menu())
        return USER_CONFIG
    
    
    if len(text) == 32 and all(c in '0123456789abcdef' for c in text.lower()):
        ensure_config_key("api_hash", text)
        await update.message.reply_text("✅ API Hash saved!", reply_markup=main_menu())
        return MAIN_MENU
    else:
        await update.message.reply_text(
            "❌ Invalid API Hash!\n"
            "Must be 32-character hexadecimal string\n"
            "Example: 1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p",
            reply_markup=user_config_menu()
        )
        return WAITING_FOR_API_HASH

async def save_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=user_config_menu())
        return USER_CONFIG
    
     # Validation (basic international phone format)
    if text.startswith('+') and text[1:].isdigit() and len(text) >= 8:
        ensure_config_key("phone", text)
        await update.message.reply_text("✅ Phone number saved!", reply_markup=main_menu())
        return USER_CONFIG
    else:
        await update.message.reply_text(
            "❌ Invalid phone number!\n"
            "Must be in international format with country code\n"
            "Example: +123456789012",
            reply_markup=user_config_menu()
        )
        return WAITING_FOR_PHONE

async def request_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    await update.message.reply_text("Send start message ID:")
    return WAITING_FOR_RANGE_START

async def set_range_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=mission_menu())
        return MISSION
    
    try:
        context.user_data["range_start"] = int(text)
        await update.message.reply_text("Now send end message ID:")
        return WAITING_FOR_RANGE_END
    except ValueError:
        await update.message.reply_text("❌ Invalid message ID. Must be a number.")
        return WAITING_FOR_RANGE_START

async def set_range_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    text = update.message.text
    if text.lower() == "skip":
        await update.message.reply_text("No changes made.", reply_markup=mission_menu())
        return MISSION
    
    try:
        start_id = context.user_data["range_start"]
        end_id = int(text)
        await update.message.reply_text(f"🚀 Starting clone for messages {start_id} to {end_id}...")
        if not os.path.exists(START_FLAG):
            with open(START_FLAG, 'w') as f:
                pass  # Creates empty file
        asyncio.create_task(clone_worker(start_id=start_id, end_id=end_id))
        await update.message.reply_text("📥 Range clone started.", reply_markup=mission_menu())
        return MISSION
    except ValueError:
        await update.message.reply_text("❌ Invalid message ID. Must be a number.")
        return WAITING_FOR_RANGE_END

async def full_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU


    if not os.path.exists(START_FLAG):
        with open(START_FLAG, 'w') as f:
            pass  # Creates empty file
    
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
        
    await update.message.reply_text("🚀 Starting full clone...")
    asyncio.create_task(clone_worker())
    await update.message.reply_text("📥 Cloning started...", reply_markup=mission_menu())
    return MISSION
    
    
async def mission_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU

    await update.message.reply_text("🚀 Mission Status...")
    asyncio.create_task(live_updates())
    return MISSION

    

async def stop_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU

    if os.path.exists(START_FLAG):
        os.remove(START_FLAG)

    with open(STOP_FLAG, "w") as f:
        f.write("stop")
    await update.message.reply_text("⛔ Clone stopped.", reply_markup=mission_menu())
    return MISSION
    
async def resume_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_clone_state()
    if not os.path.exists(STOP_FLAG):
        await update.message.reply_text("⚠️ No previous clone operation to resume", reply_markup=mission_menu())
        return MISSION
    
    try:
        start_id = state.get('last_start')
        end_id = state.get('last_end')
        
        await update.message.reply_text(
            f"🔄 Resuming clone from {start_id or 'start'} to {end_id or 'end'}...",
            reply_markup=mission_menu()
        )

        if not os.path.exists(START_FLAG):
            with open(START_FLAG, 'w') as f:
                pass
        if os.path.exists(STOP_FLAG):
            os.remove(STOP_FLAG)
        
        # Start the clone worker with previous parameters
        asyncio.create_task(clone_worker(
            start_id=start_id,
            end_id=end_id
        ))
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to resume: {str(e)}", reply_markup=mission_menu())
    
    return MISSION
    
async def chat_shared_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_start_command(update, update.message.text):
        return MAIN_MENU
    shared = update.message.chat_shared
    if not shared:
        return SOURCE_TARGET
    
    if shared.request_id == 1:
        ensure_config_key("source_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Source channel set: `{shared.chat_id}`", parse_mode="Markdown")
    elif shared.request_id == 2:
        ensure_config_key("target_channel_id", shared.chat_id)
        await update.message.reply_text(f"✅ Target channel set: `{shared.chat_id}`", parse_mode="Markdown")
    
    return SOURCE_TARGET

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    print(f"Error: {error}")
    if update and update.message:
        await update.message.reply_text(f"⚠️ Error occurred: {error}")

# ---------------------- MAIN ----------------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    
    # Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^User Config$"), user_config),
            MessageHandler(filters.Regex("^Source/Target$"), source_target),
            MessageHandler(filters.Regex("^Start Mission$"), start_mission),
            MessageHandler(filters.Regex("^Mission Status$"), mission_updates),
            CommandHandler("start", start),
        ],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex("^User Config$"), user_config),
                MessageHandler(filters.Regex("^Source/Target$"), source_target),
                MessageHandler(filters.Regex("^Start Mission$"), start_mission),
                MessageHandler(filters.Regex("^Mission Status$"), mission_status),
                CommandHandler("start", start),
            ],
            
            USER_CONFIG: [
                MessageHandler(filters.Regex("^Api ID$"), request_api_id),
                MessageHandler(filters.Regex("^Api Hash$"), request_api_hash),
                MessageHandler(filters.Regex("^Phone No\.$"), request_phone),
                MessageHandler(filters.Regex("^Login$"), login),
                MessageHandler(filters.Regex("^Logout$"), logout),
                MessageHandler(filters.Regex("^Show Config$"), show_config),  # Added
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
                CommandHandler("start", start),
            ],
            WAITING_FOR_API_ID: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_api_id),
            ],
            WAITING_FOR_API_HASH: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_api_hash),
            ],
            WAITING_FOR_PHONE: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_phone),
            ],
            WAITING_FOR_CODE: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code),
            ],
            SOURCE_TARGET: [
                CommandHandler("start", start),
                MessageHandler(filters.StatusUpdate.CHAT_SHARED, chat_shared_handler),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            ],
            MISSION: [
                MessageHandler(filters.Regex("^Full Clone$"), full_clone),
                MessageHandler(filters.Regex("^Range Clone$"), request_range_start),
                MessageHandler(filters.Regex("^Resume Clone$"), resume_clone),  # New handler
                MessageHandler(filters.Regex("^Stop$"), stop_clone),
                MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
                CommandHandler("start", start),
            ],
            WAITING_FOR_RANGE_START: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_range_start),
            ],
            WAITING_FOR_RANGE_END: [
                CommandHandler("start", start),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_range_end),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^⬅ Back$"), back_to_main),
            MessageHandler(filters.Regex("^skip$"), back_to_main),
        ],
    )

    app.add_handler(conv_handler)
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Startup message
    print("🤖 Bot is running and ready")
    app.run_polling()
if __name__ == "__main__":
    asyncio.run(main())
