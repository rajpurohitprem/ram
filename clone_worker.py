#!/usr/bin/env python3
import os
import sys
import asyncio
import argparse
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

# Configuration files
CONFIG_FILE = "config.json"
SESSION_FILE = "anon.session"
PROGRESS_FILE = "clone_progress.json"
STOP_FILE = "stop.flag"

def load_config():
    """Load configuration from file"""
    if not os.path.exists(CONFIG_FILE):
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_progress(status, progress, total, current, chat_id):
    """Save cloning progress"""
    data = {
        "status": status,
        "progress": progress,
        "total": total,
        "current": current,
        "timestamp": datetime.now().isoformat(),
        "chat_id": chat_id
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def should_stop():
    """Check if cloning should stop"""
    return os.path.exists(STOP_FILE)

async def get_message_count(client, entity):
    """Get total message count in channel"""
    return await client.get_messages(entity, limit=0).total

async def clone_message(client, source_entity, target_entity, message_id):
    """Clone a single message"""
    try:
        msg = await client.get_messages(source_entity, ids=message_id)
        if not msg:
            return False

        # Prepare media if exists
        media = None
        if msg.media:
            if isinstance(msg.media, MessageMediaPhoto):
                media = msg.media
            elif isinstance(msg.media, MessageMediaDocument):
                media = msg.media

        # Clone the message
        await client.send_message(
            target_entity,
            msg.text,
            file=media,
            link_preview=False,
            silent=True
        )
        return True
    except Exception as e:
        print(f"Error cloning message {message_id}: {str(e)}")
        return False

async def clone_range(client, source_id, target_id, start_id=None, end_id=None):
    """Clone a range of messages"""
    source_entity = await client.get_entity(source_id)
    target_entity = await client.get_entity(target_id)

    total_messages = await get_message_count(client, source_entity)
    if not start_id:
        start_id = 1
    if not end_id:
        end_id = total_messages

    cloned_count = 0
    for msg_id in range(start_id, end_id + 1):
        if should_stop():
            save_progress("paused", cloned_count, total_messages, msg_id, target_id)
            return

        success = await clone_message(client, source_entity, target_entity, msg_id)
        if success:
            cloned_count += 1

        # Update progress every 10 messages
        if msg_id % 10 == 0:
            save_progress("active", cloned_count, total_messages, msg_id, target_id)

    save_progress("completed", cloned_count, total_messages, end_id, target_id)

async def main():
    parser = argparse.ArgumentParser(description='Telegram Channel Cloner')
    parser.add_argument('--chat_id', required=True, help='Chat ID for progress reporting')
    parser.add_argument('--start', type=int, help='Start message ID')
    parser.add_argument('--end', type=int, help='End message ID')
    args = parser.parse_args()

    config = load_config()
    if not config:
        print("Error: Configuration file not found or invalid")
        return

    if not all(k in config for k in ('api_id', 'api_hash', 'phone', 'source_channel_id', 'target_channel_id')):
        print("Error: Incomplete configuration")
        return

    client = TelegramClient(SESSION_FILE, config['api_id'], config['api_hash'])
    await client.start(config['phone'])

    try:
        save_progress("active", 0, 0, "starting", args.chat_id)
        await clone_range(
            client,
            config['source_channel_id'],
            config['target_channel_id'],
            args.start,
            args.end
        )
    except Exception as e:
        print(f"Clone error: {str(e)}")
        save_progress("error", 0, 0, str(e), args.chat_id)
    finally:
        await client.disconnect()
        if os.path.exists(STOP_FILE):
            os.remove(STOP_FILE)

if __name__ == '__main__':
    asyncio.run(main())
