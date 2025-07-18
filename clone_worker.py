import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm

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
        f.write(msg + "\n")

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

class CloneBot:
    def __init__(self):
        self.bot_client = None
        self.active_chats = set()
        self.progress_message = None
        self.is_cloning = False
        self.last_progress = None
        self.allowed_users = set()

    async def start_bot(self):
        bot_config = load_json(BOT_FILE)
        if not bot_config.get("bot_token"):
            return

        # Load allowed users
        self.allowed_users = set(bot_config.get("allowed_users", []))
        
        self.bot_client = TelegramClient(
            'bot_session',
            load_json(CONFIG_FILE)["api_id"],
            load_json(CONFIG_FILE)["api_hash"]
        )

        @self.bot_client.on(events.NewMessage())
        async def message_handler(event):
            # Check if user is allowed
            if event.sender_id not in self.allowed_users:
                await event.reply("⛔ You are not authorized to use this bot")
                return

            if event.text == '/start':
                self.active_chats.add(event.chat_id)
                await event.reply("🤖 Clone Bot Activated\nSend /status to check progress")
            elif event.text == '/status':
                if self.is_cloning:
                    if self.last_progress:
                        await event.reply(self.last_progress)
                    else:
                        await event.reply("🔄 Cloning in progress...")
                else:
                    await event.reply("💤 Bot is idle")
            elif event.text == '/stop':
                open(STOP_FILE, 'a').close()
                await event.reply("🛑 Stop request received. Current operation will halt after completing current message.")

        await self.bot_client.start(bot_token=bot_config["bot_token"])
        asyncio.create_task(self.bot_client.run_until_disconnected())

    async def send_update(self, message):
        if not self.bot_client:
            return

        self.last_progress = message
        
        for chat_id in self.active_chats:
            try:
                await self.bot_client.send_message(chat_id, message)
            except Exception as e:
                log_error(f"Failed to send update to {chat_id}: {str(e)}")

bot = CloneBot()

async def clone_worker(start_id=None, end_id=None):
    await bot.start_bot()
    config = load_json(CONFIG_FILE)
    
    if not all(k in config for k in ["api_id", "api_hash", "phone", "source_channel_id", "target_channel_id"]):
        await bot.send_update("❌ Missing configuration in config.json")
        return

    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])
    
    await bot.send_update("🚀 Cloning process started")
    bot.is_cloning = True

    def normalize_channel_id(cid):
        cid = str(cid)
        return int(cid) if cid.startswith("-100") else int("-100" + cid)

    try:
        src_entity = await client.get_entity(normalize_channel_id(config["source_channel_id"]))
        tgt_entity = await client.get_entity(normalize_channel_id(config["target_channel_id"]))
    except Exception as e:
        await bot.send_update(f"❌ Failed to access channels: {str(e)}")
        bot.is_cloning = False
        await client.disconnect()
        return

    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().split()))

    offset_id = 0
    limit = 100
    all_messages = []

    # Get all messages
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
        except Exception as e:
            await bot.send_update(f"❌ Error fetching messages: {str(e)}")
            break

    all_messages.reverse()

    if start_id and end_id:
        all_messages = [msg for msg in all_messages if start_id <= msg.id <= end_id]

    total_messages = len(all_messages)
    processed = 0
    
    await bot.send_update(f"📊 Total messages to clone: {total_messages}")

    for msg in tqdm(all_messages, desc="Cloning"):
        if os.path.exists(STOP_FILE):
            stop_msg = "⛔ Stop request received. Halting..."
            print(stop_msg)
            await bot.send_update(stop_msg)
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
            if processed % 10 == 0 or processed == total_messages:
                progress = f"⏳ Progress: {processed}/{total_messages} ({processed/total_messages:.1%})"
                await bot.send_update(progress)

            await asyncio.sleep(1)

        except Exception as e:
            error_msg = f"Failed to send message {msg.id}: {str(e)}"
            log_error(error_msg)
            await bot.send_update(f"⚠️ {error_msg}")

    completion_msg = "✅ Cloning complete."
    print(completion_msg)
    await bot.send_update(completion_msg)
    bot.is_cloning = False
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(clone_worker())
