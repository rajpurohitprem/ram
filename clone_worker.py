import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm

# Config files
CONFIG_FILE = "config.json"
BOT_FILE = "bot.json"
SESSION_FILE = "anon.session"  # Changed to .session extension
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

    async def start_bot(self):
        bot_config = load_json(BOT_FILE)
        if not bot_config.get("bot_token"):
            return

        self.bot_client = TelegramClient(
            'bot_session',
            load_json(CONFIG_FILE)["api_id"],
            load_json(CONFIG_FILE)["api_hash"]
        )

        @self.bot_client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            self.active_chats.add(event.chat_id)
            await event.reply("🤖 Clone Bot Activated\nSend /status to check progress")

        @self.bot_client.on(events.NewMessage(pattern='/status'))
        async def status_handler(event):
            if self.is_cloning:
                if self.progress_message:
                    await event.reply(self.progress_message)
                else:
                    await event.reply("🔄 Cloning in progress...")
            else:
                await event.reply("💤 Bot is idle")

        await self.bot_client.start(bot_token=bot_config["bot_token"])
        asyncio.create_task(self.bot_client.run_until_disconnected())

    async def send_update(self, message):
        if not self.bot_client or not self.active_chats:
            return

        self.progress_message = message
        for chat_id in self.active_chats:
            try:
                await self.bot_client.send_message(chat_id, message)
            except Exception as e:
                log_error(f"Failed to send update to {chat_id}: {str(e)}")

async def clone_worker(start_id=None, end_id=None):
    #"""Main function to be imported by other scripts"""
    bot = CloneBot()
    await bot.start_bot()
    
    config = load_json(CONFIG_FILE)
    if not config:
        await bot.send_update("❌ Missing or invalid config.json")
        return False

    try:
        client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
        await client.start(phone=config["phone"])
        
        await bot.send_update("🚀 Starting cloning process...")
        bot.is_cloning = True

        # [Your existing cloning logic here]
        
        await bot.send_update("✅ Cloning completed successfully")
        return True
    except Exception as e:
        await bot.send_update(f"❌ Error during cloning: {str(e)}")
        return False
    finally:
        bot.is_cloning = False
        if 'client' in locals():
            await client.disconnect()

async def main():
    bot = CloneBot()
    await bot.start_bot()

    config = load_json(CONFIG_FILE)
    if not all(k in config for k in ["api_id", "api_hash", "phone", "source_channel_id", "target_channel_id"]):
        await bot.send_update("❌ Missing configuration in config.json")
        return

    client = TelegramClient(SESSION_FILE, config["api_id"], config["api_hash"])
    await client.start(phone=config["phone"])

    await bot.send_update("🚀 Starting cloning process...")
    bot.is_cloning = True

    try:
        # Your cloning logic here
        for i in range(1, 101):  # Example progress
            if os.path.exists(STOP_FILE):
                await bot.send_update("⏹️ Stopped by user request")
                break

            progress = f"🔄 Progress: {i}%"
            await bot.send_update(progress)
            await asyncio.sleep(1)

        await bot.send_update("✅ Cloning completed successfully")
    except Exception as e:
        await bot.send_update(f"❌ Error during cloning: {str(e)}")
    finally:
        bot.is_cloning = False
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
