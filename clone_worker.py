import os
import json
import asyncio
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, UpdatePinnedMessageRequest
from telethon.tl.types import Message
from tqdm import tqdm

CONFIG_FILE = "config.json"
SESSION_FILE = "anon"
SENT_LOG = "sent_ids.txt"
ERROR_LOG = "errors.txt"
STOP_FILE = "stop.flag"

open(SENT_LOG, "a").close()
open(ERROR_LOG, "a").close()

def log_error(msg):
    with open(ERROR_LOG, "a") as f:
        f.write(msg + "\n")

def load_json():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_json(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

async def clone_worker(start_id=None, end_id=None):
    if os.path.exists("stop.flag"):
        os.remove("stop.flag")
    config = load_json()
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])

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

    for msg in tqdm(all_messages, desc="Cloning"):
        if os.path.exists(STOP_FILE):
            print("⛔ Stop file detected. Halting...")
            os.remove("stop.flag")
            
            break
        if not isinstance(msg, Message) or msg.id in sent_ids:
            continue

        try:
            if msg.media:
                file_path = await client.download_media(msg)
                await client.send_file(tgt_entity, file_path, caption=msg.text or msg.message or "")
                os.remove(file_path)
            elif msg.text or msg.message:
                await client.send_message(tgt_entity, msg.text or msg.message)

            with open(SENT_LOG, "a") as f:
                f.write(f"{msg.id}\n")

            await asyncio.sleep(1)

        except Exception as e:
            log_error(f"Failed to send message {msg.id}: {e}")
        # Final cleanup if needed
        if os.path.exists("stop.flag"):
            os.remove("stop.flag")
    
    print("✅ Cloning complete.")
    await client.disconnect()
