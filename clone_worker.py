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
        self.status_chat_id = None
        self.status_message_id = None
        self.is_cloning = False
        self.allowed_users = set()
        self.current_status = "Idle"
        self.last_update = None
        self.message_queue = asyncio.Queue()

    async def initialize(self):
        bot_config = load_json(BOT_FILE)
        if not bot_config.get("bot_token"):
            return False

        self.allowed_users = set(bot_config.get("allowed_users", []))
        if not self.allowed_users:
            return False

        self.bot_client = TelegramClient(
            'bot_session',
            load_json(CONFIG_FILE)["api_id"],
            load_json(CONFIG_FILE)["api_hash"]
        )

        @self.bot_client.on(events.NewMessage())
        async def message_handler(event):
            if event.sender_id in self.allowed_users:
                await self.message_queue.put(event)

        await self.bot_client.start(bot_token=bot_config["bot_token"])
        self.status_chat_id = next(iter(self.allowed_users))
        return True

    async def send_initial_status(self):
        if not self.bot_client or not self.status_chat_id:
            return
            
        try:
            msg = await self.bot_client.send_message(
                self.status_chat_id,
                "🔄 Cloning process initialized...\n"
                "Standby for live progress updates"
            )
            self.status_message_id = msg.id
            self.status_chat_id = msg.chat_id
        except Exception as e:
            log_error(f"Initial status send failed: {str(e)}")

    async def update_status(self, message):
        if not self.bot_client or not self.status_chat_id:
            return

        self.current_status = message
        self.last_update = datetime.now().strftime("%H:%M:%S")
        
        try:
            if self.status_message_id:
                await self.bot_client.edit_message(
                    self.status_chat_id,
                    self.status_message_id,
                    f"🔄 {message}\n"
                    f"⏰ Last Update: {self.last_update}"
                )
            else:
                msg = await self.bot_client.send_message(
                    self.status_chat_id,
                    f"🔄 {message}\n"
                    f"⏰ Last Update: {self.last_update}"
                )
                self.status_message_id = msg.id
                self.status_chat_id = msg.chat_id
        except Exception as e:
            log_error(f"Status update failed: {str(e)}")
            self.status_message_id = None

    async def handle_messages(self):
        while self.is_cloning:
            try:
                event = await asyncio.wait_for(self.message_queue.get(), timeout=0.1)
                if event.text == '/status':
                    await event.reply(f"Current Status:\n{self.current_status}\nLast Update: {self.last_update}")
                elif event.text == '/stop':
                    open(STOP_FILE, 'a').close()
                    await event.reply("🛑 Stop request received. Operation will halt after current message.")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log_error(f"Message handling error: {str(e)}")

    async def cleanup(self):
        if self.bot_client:
            await self.bot_client.disconnect()

bot = CloneBot()

async def live_updates():
    """Initialize and maintain live updates during cloning"""
    if not await bot.initialize():
        print("❌ Bot initialization failed")
        return False
    
    await bot.send_initial_status()
    bot.is_cloning = True
    asyncio.create_task(bot.handle_messages())
    return True

async def clone_worker(start_id=None, end_id=None):
    if not bot.is_cloning:
        if not await live_updates():
            return

    config = load_json(CONFIG_FILE)
    if not all(k in config for k in ["api_id", "api_hash", "phone", "source_channel_id", "target_channel_id"]):
        await bot.update_status("❌ Missing configuration")
        bot.is_cloning = False
        await bot.cleanup()
        return

    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])
    
    await bot.update_status("🚀 Starting cloning process...")

    def normalize_channel_id(cid):
        cid = str(cid)
        return int(cid) if cid.startswith("-100") else int("-100" + cid)

    try:
        src_entity = await client.get_entity(normalize_channel_id(config["source_channel_id"]))
        tgt_entity = await client.get_entity(normalize_channel_id(config["target_channel_id"]))
    except Exception as e:
        await bot.update_status(f"❌ Channel access failed: {str(e)}")
        bot.is_cloning = False
        await client.disconnect()
        await bot.cleanup()
        return

    # Message collection
    await bot.update_status("📂 Collecting messages...")
    all_messages = []
    offset_id = 0
    limit = 100
    
    while True:
        if os.path.exists(STOP_FILE):
            await bot.update_status("⛔ Stopped by user request")
            os.remove(STOP_FILE)
            break

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
            
            if len(all_messages) % 100 == 0:
                await bot.update_status(f"📥 Collected {len(all_messages)} messages")
                
        except Exception as e:
            await bot.update_status(f"❌ Collection error: {str(e)}")
            break

    all_messages.reverse()
    if start_id and end_id:
        all_messages = [msg for msg in all_messages if start_id <= msg.id <= end_id]

    total_messages = len(all_messages)
    processed = 0
    
    await bot.update_status(f"📊 Ready to clone {total_messages} messages")

    # Cloning process
    progress_interval = max(5, total_messages // 20)
    
    for msg in tqdm(all_messages, desc="Cloning"):
        if os.path.exists(STOP_FILE):
            await bot.update_status(f"⛔ Stopped ({processed}/{total_messages} done)")
            os.remove(STOP_FILE)
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
                await bot.update_status(
                    f"⏳ Cloning: {percent:.1f}% complete\n"
                    f"({processed}/{total_messages} messages)\n"
                    f"⏱️ ~{(total_messages - processed)//2}s remaining"
                )

            await asyncio.sleep(0.5)

        except Exception as e:
            log_error(f"Message {msg.id} failed: {str(e)}")
            if processed % 1 == 0:
                await bot.update_status(f"⚠️ Error on message {msg.id} (continuing)")

    # Final status
    completion_msg = f"✅ Completed: {processed}/{total_messages} messages"
    if os.path.exists(STOP_FILE):
        completion_msg = f"⏹️ Stopped early: {processed}/{total_messages}"
        os.remove(STOP_FILE)
        
    await bot.update_status(completion_msg)
    bot.is_cloning = False
    await client.disconnect()
    await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(clone_worker())
