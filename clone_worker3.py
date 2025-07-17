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
PROGRESS_FILE = "clone_progress.json"

def update_progress(chat_id, current, total, current_file=""):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({
            "status": "active",
            "chat_id": chat_id,
            "progress": current,
            "total": total,
            "current_file": current_file,
            "timestamp": datetime.now().isoformat()
        }, f)

def clear_progress():
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"status": "inactive"}, f)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat_id", required=True, type=int)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    args = parser.parse_args()

    config = json.load(open(CONFIG_FILE))
    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])

    try:
        # Initialize progress
        update_progress(args.chat_id, 0, 0, "Initializing...")

        # Channel setup
        def normalize_id(cid):
            cid = str(cid)
            return int(cid) if cid.startswith("-100") else int("-100" + cid)

        src = await client.get_entity(normalize_id(config["source_channel_id"]))
        tgt = await client.get_entity(normalize_id(config["target_channel_id"]))

        # Get message history
        all_messages = []
        offset_id = 0
        while True:
            history = await client(GetHistoryRequest(
                peer=src,
                offset_id=offset_id,
                limit=100,
                hash=0
            ))
            if not history.messages:
                break
            all_messages.extend(history.messages)
            offset_id = history.messages[-1].id

        all_messages.reverse()

        # Filter by range if specified
        if args.start or args.end:
            all_messages = [m for m in all_messages 
                           if (args.start is None or m.id >= args.start) and 
                              (args.end is None or m.id <= args.end)]

        total = len(all_messages)
        update_progress(args.chat_id, 0, total)

        # Clone messages
        for i, msg in enumerate(tqdm(all_messages, desc="Cloning")):
            if os.path.exists(STOP_FILE):
                await client.send_message(args.chat_id, "⏸ Clone paused by user")
                break

            update_progress(args.chat_id, i+1, total, f"Message {msg.id}")

            try:
                if msg.media:
                    file_path = await client.download_media(msg)
                    await client.send_file(tgt, file_path, caption=msg.text or "")
                    os.remove(file_path)
                elif msg.text:
                    await client.send_message(tgt, msg.text)

                with open(SENT_LOG, "a") as f:
                    f.write(f"{msg.id}\n")

                await asyncio.sleep(1)

            except Exception as e:
                await client.send_message(
                    args.chat_id,
                    f"⚠️ Error copying {msg.id}: {str(e)[:100]}"
                )

        await client.send_message(args.chat_id, "✅ Clone completed!")
        clear_progress()

    except Exception as e:
        await client.send_message(
            args.chat_id,
            f"❌ Clone failed: {str(e)[:200]}"
        )
        clear_progress()
    finally:
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
