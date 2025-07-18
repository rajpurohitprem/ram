import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm
from datetime import datetime

# Config files
CONFIG_FILE = "config.json"
BOT_FILE = "bot.json"
SESSION_FILE = "anon.session"
SENT_LOG = "sent_ids.txt"
ERROR_LOG = "errors.txt"
STOP_FILE = "stop.flag"

# Initialize files
open(SENT_LOG, 'a').close()
open(ERROR_LOG, 'a').close()

def log_error(msg):
    with open(ERROR_LOG, 'a') as f:
        f.write(f"{datetime.now()}: {msg}\n")

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

class CloneBot:
    def __init__(self):
        self.bot_client = None
        self.active_chats = set()
        self.is_cloning = False
        self.progress_message_id = None
        self.progress_chat_id = None
        self.allowed_users = set()
        self.current_status = "Idle"
        self.last_update = None

    async def start_bot(self):
        bot_config = load_json(BOT_FILE)
        if not bot_config.get("bot_token"):
            return

        self.allowed_users = set(bot_config.get("allowed_users", []))
        
        self.bot_client = TelegramClient(
            'bot_session',
            load_json(CONFIG_FILE)["api_id"],
            load_json(CONFIG_FILE)["api_hash"]
        )

        @self.bot_client.on(events.NewMessage())
        async def message_handler(event):
            

            if event.text == '/start':
                self.active_chats.add(event.chat_id)
                await event.reply("🤖 Clone Bot Activated\n"
                               "Send /status for current progress\n"
                               "Send /stop to cancel operation")
            elif event.text == '/status':
                await self.send_status(event.chat_id)
            elif event.text == '/stop':
                open(STOP_FILE, 'a').close()
                await event.reply("🛑 Stop request received. Operation will halt after current message.")

        await self.bot_client.start(bot_token=bot_config["bot_token"])
        asyncio.create_task(self.bot_client.run_until_disconnected())

    async def send_status(self, chat_id=None):
        if not self.bot_client:
            return
            
        status_message = (
            f"🔄 Current Status: {self.current_status}\n"
            f"⏰ Last Update: {self.last_update or 'N/A'}\n"
            "\nUse /stop to cancel operation"
        )
        
        if chat_id:
            try:
                await self.bot_client.send_message(chat_id, status_message)
            except Exception as e:
                log_error(f"Status send failed: {str(e)}")

    async def update_progress(self, message):
        if not self.bot_client or not self.active_chats:
            return
            
        self.current_status = message
        self.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Create or update progress message
            if self.progress_message_id and self.progress_chat_id:
                await self.bot_client.edit_message(
                    self.progress_chat_id,
                    self.progress_message_id,
                    message
                )
            else:
                # Send to first active chat
                if self.active_chats:
                    chat_id = next(iter(self.active_chats))
                    msg = await self.bot_client.send_message(chat_id, message)
                    self.progress_message_id = msg.id
                    self.progress_chat_id = chat_id
                    
            # Send to other active chats
            for chat_id in self.active_chats:
                if chat_id != self.progress_chat_id:
                    try:
                        await self.bot_client.send_message(chat_id, message)
                    except Exception as e:
                        log_error(f"Progress update failed for {chat_id}: {str(e)}")
                        
        except Exception as e:
            log_error(f"Progress update failed: {str(e)}")
            # Reset message tracking if failed
            self.progress_message_id = None
            self.progress_chat_id = None

bot = CloneBot()

async def clone_worker(start_id=None, end_id=None):
    await bot.start_bot()
    config = load_json(CONFIG_FILE)
    
    if not all(k in config for k in ["api_id", "api_hash", "phone", "source_channel_id", "target_channel_id"]):
        await bot.update_progress("❌ Missing configuration in config.json")
        return

    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])
    
    bot.is_cloning = True
    await bot.update_progress("🚀 Starting cloning process...")

    def normalize_channel_id(cid):
        cid = str(cid)
        return int(cid) if cid.startswith("-100") else int("-100" + cid)

    try:
        src_entity = await client.get_entity(normalize_channel_id(config["source_channel_id"]))
        tgt_entity = await client.get_entity(normalize_channel_id(config["target_channel_id"]))
    except Exception as e:
        await bot.update_progress(f"❌ Channel access failed: {str(e)}")
        bot.is_cloning = False
        await client.disconnect()
        return

    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().split()))

    # Message collection
    await bot.update_progress("📂 Collecting messages from source channel...")
    all_messages = []
    offset_id = 0
    limit = 100
    
    while True:
        try:
            history = await client(GetHistoryRequest(
                peer=src_entity,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=0,
                hash=0
            ))
            if not history.messages:
                break
            all_messages.extend(history.messages)
            offset_id = history.messages[-1].id
            
            # Update progress during collection
            if len(all_messages) % 500 == 0:
                await bot.update_progress(f"📥 Collected {len(all_messages)} messages so far...")
                
        except Exception as e:
            await bot.update_progress(f"❌ Error collecting messages: {str(e)}")
            break

    all_messages.reverse()
    
    if start_id and end_id:
        all_messages = [msg for msg in all_messages if start_id <= msg.id <= end_id]

    total_messages = len(all_messages)
    processed = 0
    
    await bot.update_progress(f"📊 Ready to clone {total_messages} messages")

    # Cloning process
    progress_interval = max(1, total_messages // 10)  # Update 10 times during process
    
    for msg in tqdm(all_messages, desc="Cloning"):
        if os.path.exists(STOP_FILE):
            await bot.update_progress("⛔ STOPPED by user request")
            
            break

        try:
            if msg.media:
                file_path = await client.download_media(msg)
                await client.send_file(tgt_entity, file_path, caption=msg.text or msg.message or "")
                os.remove(file_path)
            elif msg.text or msg.message:
                await client.send_message(tgt_entity, msg.text or msg.message)

            with open(SENT_LOG, "a") as f:
                f.write(f"{msg.id}\n")

            processed += 1
            if processed % progress_interval == 0 or processed == total_messages:
                percent = (processed / total_messages) * 100
                await bot.update_progress(
                    f"⏳ Cloning Progress: {processed}/{total_messages} ({percent:.1f}%)\n"
                    f"🕒 Estimated: {(total_messages - processed) * 1.5:.0f}s remaining"
                )

            await asyncio.sleep(1)  # Rate limiting

        except Exception as e:
            error_msg = f"❌ Failed on message {msg.id}: {str(e)}"
            log_error(error_msg)
            await bot.update_progress(error_msg)

    # Completion
    completion_msg = f"✅ Cloning complete! {processed} messages processed"
    if os.path.exists(STOP_FILE):
        completion_msg = f"⏹️ Stopped early: {processed}/{total_messages} messages cloned"
        os.remove(STOP_FILE)
        
    await bot.update_progress(completion_msg)
    bot.is_cloning = False
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(clone_worker())
