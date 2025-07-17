import os
import json
import asyncio
import argparse
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import Message
from tqdm import tqdm

# Configuration
CONFIG_FILE = "config.json"
SESSION_FILE = "anon.session"
SENT_LOG = "sent_ids.txt"
STOP_FILE = "stop.flag"
STATE_FILE = "clone_state.json"

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def normalize_channel_id(cid):
    cid = str(cid)
    return int(cid) if cid.startswith("-100") else int("-100" + cid)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat_id", required=True, type=int)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    args = parser.parse_args()

    config = load_config()
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])

    try:
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

        if args.start or args.end:
            all_messages = [msg for msg in all_messages 
                          if (args.start is None or msg.id >= args.start) and 
                             (args.end is None or msg.id <= args.end)]

        progress_msg = await client.send_message(
            entity=args.chat_id,
            message="🔄 Cloning started..."
        )

        for msg in tqdm(all_messages, desc="Cloning"):
            if os.path.exists(STOP_FILE):
                await client.send_message(
                    entity=args.chat_id,
                    message="⏸ Clone paused. Use 'Resume' to continue."
                )
                break

            if not isinstance(msg, Message) or msg.id in sent_ids:
                continue

            try:
                if msg.media:
                    file_path = await client.download_media(msg)
                    await client.send_file(tgt_entity, file_path, caption=msg.text or "")
                    os.remove(file_path)
                elif msg.text:
                    await client.send_message(tgt_entity, msg.text)

                with open(SENT_LOG, "a") as f:
                    f.write(f"{msg.id}\n")

                await asyncio.sleep(1)

            except Exception as e:
                await client.send_message(
                    entity=args.chat_id,
                    message=f"⚠️ Error at message {msg.id}: {str(e)[:100]}"
                )

        await client.send_message(
            entity=args.chat_id,
            message="✅ Cloning completed!"
        )

    except Exception as e:
        await client.send_message(
            entity=args.chat_id,
            message=f"❌ Clone failed: {str(e)[:200]}"
        )
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
