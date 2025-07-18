import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm

# Config files
CONFIG_FILE = "config.json"
BOT_FILE = "bot.json"
SESSION_FILE = "anon"
SENT_LOG = "sent_ids.txt"
ERROR_LOG = "errors.txt"
STOP_FILE = "stop.flag"
START_FILE = "start.flag"
RESUME_FILE = "resume.flag"

# Initialize files
open(SENT_LOG, "a").close()
open(ERROR_LOG, "a").close()

def log_error(msg):
    with open(ERROR_LOG, "a") as f:
        f.write(msg + "\n")

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

class CloneBot:
    def __init__(self):
        self.bot_client = None
        self.active_chats = set()  # To track chats where we should send updates
        self.clone_active = False
        self.current_progress = ""
        self.last_message_id = None  # Track the last sent message ID
        self.last_chat_id = None

    async def initialize_bot(self):
        bot_config = load_json(BOT_FILE)
        if bot_config.get("bot_token"):
            self.bot_client = TelegramClient("bot_session", 
                                           load_json(CONFIG_FILE)["api_id"], 
                                           load_json(CONFIG_FILE)["api_hash"])
            await self.bot_client.start(bot_token=bot_config["bot_token"])
            
            @self.bot_client.on(events.NewMessage(pattern='/start'))
            async def start_handler(event):
                self.active_chats.add(event.chat_id)
                await event.reply("🤖 Clone Bot Active\n"
                                 "I'll send cloning updates here\n"
                                 "Current status: " + ("Running" if self.clone_active else "Idle"))
                
            @self.bot_client.on(events.NewMessage(pattern='/status'))
            async def status_handler(event):
                if self.current_progress:
                    await event.reply(self.current_progress)
                else:
                    await event.reply("No active cloning process")

            # Run bot listener in background
            asyncio.create_task(self.bot_client.run_until_disconnected())

    async def send_update(self, message):
        if not self.bot_client:
            return
            
        self.current_progress = message
        try:
        if update_existing and self.last_message_id and self.last_chat_id:
            # Edit existing message
            await self.bot_client.edit_message(
                self.last_chat_id,
                self.last_message_id,
                message
            )
        else:
            # Send new message and store its ID
            msg = await self.bot_client.send_message(
                self.last_chat_id or list(self.active_chats)[0],
                message
            )
            self.last_message_id = msg.id
            self.last_chat_id = msg.chat_id
    except Exception as e:
        log_error(f"Failed to update progress: {e}")
  
clone_bot = CloneBot()

async def clone_worker(start_id=None, end_id=None):
    await clone_bot.initialize_bot()
    config = load_json(CONFIG_FILE)
    
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])
    
    await clone_bot.send_update("🚀 Cloning process started")

    def normalize_channel_id(cid):
        cid = str(cid)
        return int(cid) if cid.startswith("-100") else int("-100" + cid)

    src_entity = await client.get_entity(normalize_channel_id(config["source_channel_id"]))
    tgt_entity = await client.get_entity(normalize_channel_id(config["target_channel_id"]))

    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().split()))

    offset_id = 0
    limit = 100
    all_messages = []

    # Get all messages
    while True:
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

    all_messages.reverse()

    if start_id and end_id:
        all_messages = [msg for msg in all_messages if start_id <= msg.id <= end_id]

    total_messages = len(all_messages)
    processed = 0
    
    await clone_bot.send_update(f"📊 Total messages to clone: {total_messages}")
    clone_bot.clone_active = True

    for msg in tqdm(all_messages, desc="Cloning"):
        if os.path.exists(STOP_FILE):
            stop_msg = "⛔ Stop file detected. Halting..."
            print(stop_msg)
            await clone_bot.send_update(stop_msg)
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
            # Send progress update every 10 messages or 1 minute
            if processed % 10 == 0 or processed == total_messages:
                progress = (
                    "🚀 Cloning in progress\n"
                    f"📦 {processed}/{total_messages} messages\n"
                    f"📊 {processed/total_messages:.1%}\n"
                    f"{'⬛' * int(20 * processed/total_messages)}{'⬜' * (20 - int(20 * processed/total_messages))}"
                )    
                await clone_bot.send_update(progress, update_existing=True)

            await asyncio.sleep(1)

        except Exception as e:
            error_msg = f"Failed to send message {msg.id}: {e}"
            log_error(error_msg)
            await clone_bot.send_update(f"❌ {error_msg}")

    if processed == total_messages:
        await clone_bot.send_update("✅ Cloning complete!", update_existing=False)
    
    if processed != total_messages:
        completion_msg = "!!!! Cloning Stopped.!!!!"
    completion_msg ="✅ Cloning complete!"
    print(completion_msg)
    await clone_bot.send_update(completion_msg)
    clone_bot.clone_active = False
    
    if os.path.exists("start.flag"):
        os.remove("start.flag")
    
    await client.disconnect()
