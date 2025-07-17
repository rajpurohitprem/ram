import os
import json
import asyncio
from telethon.sync import TelegramClient
from telethon.tl.types import MessageService
from telethon.errors import FloodWaitError
from telethon.tl.types import DocumentAttributeFilename

CONFIG_FILE = "config.json"
SESSION_FILE = "anon.session"
CHECKPOINT_FILE = "checkpoint.json"

# Status variables
active = False
status_chat_id = None

def is_cloning_active():
    return active

def stop_cloning():
    global active
    active = False

def save_checkpoint(message_id):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_id": message_id}, f)

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f).get("last_id", 0)
    return 0

async def send_status(message: str):
    from telegram import Bot
    with open("bot.json") as f:
        bot_token = json.load(f)["bot_token"]
    bot = Bot(bot_token)
    if status_chat_id:
        try:
            await bot.send_message(chat_id=status_chat_id, text=message)
        except:
            pass

def start_clone_full():
    asyncio.run(clone_full())

def start_clone_range(start_id: int, end_id: int):
    asyncio.run(clone_range(start_id, end_id))

# Main Full Clone Logic
async def clone_full():
    global active, status_chat_id
    active = True

    config = load_config()
    source = int(config["source_channel_id"])
    target = int(config["target_channel_id"])
    status_chat_id = int(config["status_chat_id"])

    last_id = load_checkpoint()

    async with TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"]) as client:
        async for message in client.iter_messages(source, min_id=last_id):
            if not active:
                await send_status("🛑 Clone stopped by user.")
                return
            try:
                await copy_message(client, message, target)
                save_checkpoint(message.id)
            except FloodWaitError as e:
                await send_status(f"⏳ Flood wait: sleeping for {e.seconds} seconds.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                await send_status(f"❌ Error copying message {message.id}: {e}")
                continue
        await send_status("✅ Full Clone Complete!")
        active = False

# Range Clone
async def clone_range(start_id: int, end_id: int):
    global active, status_chat_id
    active = True

    config = load_config()
    source = int(config["source_channel_id"])
    target = int(config["target_channel_id"])
    status_chat_id = int(config["status_chat_id"])

    async with TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"]) as client:
        for message_id in range(start_id, end_id + 1):
            if not active:
                await send_status("🛑 Range Clone Stopped.")
                return
            try:
                msg = await client.get_messages(source, ids=message_id)
                if msg:
                    await copy_message(client, msg, target)
                    save_checkpoint(message_id)
            except Exception as e:
                await send_status(f"⚠️ Failed message {message_id}: {e}")
                continue
        await send_status("✅ Range Clone Complete.")
        active = False

# Copy One Message At a Time
async def copy_message(client, message, target):
    if isinstance(message, MessageService):
        return  # skip joins/pins/etc

    # Forward text/photo/etc
    if message.media is None:
        await client.send_message(target, message.text or "")
    else:
        file_path = await message.download_media(file="./temp/")
        if message.document:
            attributes = message.document.attributes
            filename = None
            for attr in attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                    break
            await client.send_file(target, file_path, caption=message.text or "", file_name=filename)
        else:
            await client.send_file(target, file_path, caption=message.text or "")
        os.remove(file_path)

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)
