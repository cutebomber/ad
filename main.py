import asyncio
import time
from telethon import TelegramClient
from telethon.errors import FloodWaitError

# --- Configuration ---
API_ID = 21752358
API_HASH = "fb46a136fed4a4de27ab057c7027fec3"

# --- Helper to format custom emoji ---
def ce(emoji_id: str, fallback: str = "⭐") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# Custom emojis (replace IDs with your own)
FIRE    = ce("5368324170671202286", "🔥")
DIAMOND = ce("5368324170671202287", "💎")
STAR    = ce("5368324170671202288", "⭐")
ROCKET  = ce("5368324170671202289", "🚀")
CHECK   = ce("5368324170671202290", "✅")

MESSAGES = [
    f"{FIRE} Fresh stock available! Check our latest collection. DM to order. {FIRE}",
    f"{DIAMOND} Premium quality products at best prices! Contact us now. {DIAMOND}",
    f"{CHECK} 100% genuine. Fast delivery across India. Message us! {ROCKET}",
    f"{STAR} Bestsellers back in stock — don't miss out! Order today. {STAR}",
    f"{ROCKET} Limited deal — Buy 2 Get 1 FREE! DM for details. {FIRE}",
]

async def main(phone: str, group: str, interval: int):
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start(phone=phone)
    print("✅ Logged in successfully!")
    print(f"📋 {len(MESSAGES)} messages loaded. Rotating every {interval // 60} min.\n")

    index = 0
    while True:
        try:
            message = MESSAGES[index % len(MESSAGES)]
            await client.send_message(group, message, parse_mode="html")
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ✉️  Sent message {(index % len(MESSAGES)) + 1}/{len(MESSAGES)}")
            index += 1

            next_time = time.strftime('%H:%M:%S', time.localtime(time.time() + interval))
            print(f"  ⏳ Next message at {next_time}\n")
            await asyncio.sleep(interval)

        except FloodWaitError as e:
            print(f"⚠️  Rate limited. Waiting {e.seconds}s...")
            await asyncio.sleep(e.seconds)

        except Exception as e:
            print(f"❌ Error: {e}. Retrying in 60s...")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("=== Telegram Auto Promoter ===\n")
    phone  = input("📱 Enter your phone number (with country code, e.g. +91XXXXXXXXXX): ").strip()
    group  = input("👥 Enter group username or ID (e.g. mygroupname): ").strip()
    mins   = input("⏱️  Interval between messages in minutes (e.g. 60): ").strip()

    interval = int(mins) * 60

    asyncio.run(main(phone, group, interval))
