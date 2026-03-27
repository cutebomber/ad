import asyncio
import time
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from colorama import init, Fore, Back, Style

init(autoreset=True)

# --- Configuration ---
API_ID = 21752358
API_HASH = "fb46a136fed4a4de27ab057c7027fec3"

# --- Colored print helpers ---
def info(msg):    print(f"{Fore.CYAN}{Style.BRIGHT}  ℹ  {Style.NORMAL}{msg}{Style.RESET_ALL}")
def success(msg): print(f"{Fore.GREEN}{Style.BRIGHT}  ✅ {Style.NORMAL}{msg}{Style.RESET_ALL}")
def warning(msg): print(f"{Fore.YELLOW}{Style.BRIGHT}  ⚠️  {Style.NORMAL}{msg}{Style.RESET_ALL}")
def error(msg):   print(f"{Fore.RED}{Style.BRIGHT}  ❌ {Style.NORMAL}{msg}{Style.RESET_ALL}")
def sent(msg):    print(f"{Fore.MAGENTA}{Style.BRIGHT}  ✉️  {Style.NORMAL}{msg}{Style.RESET_ALL}")
def timer(msg):   print(f"{Fore.BLUE}{Style.BRIGHT}  ⏳ {Style.NORMAL}{msg}{Style.RESET_ALL}")

def banner():
    print(f"""
{Fore.CYAN}{Style.BRIGHT}
  ╔══════════════════════════════════════════╗
  ║       🚀  TELEGRAM AUTO PROMOTER  🚀     ║
  ║          Powered by Telethon             ║
  ╚══════════════════════════════════════════╝
{Style.RESET_ALL}""")

def divider():
    print(f"{Fore.CYAN}  {'─' * 44}{Style.RESET_ALL}")

# --- Custom Emoji Helper ---
def ce(emoji_id: str, fallback: str = "⭐") -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

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

# --- Login ---
async def login(phone: str) -> TelegramClient:
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        divider()
        info("Sending OTP to your Telegram...")
        await client.send_code_request(phone)
        otp = input(f"{Fore.YELLOW}{Style.BRIGHT}  📩 Enter OTP: {Style.RESET_ALL}").strip()

        try:
            await client.sign_in(phone, otp)

        except SessionPasswordNeededError:
            warning("2FA is enabled on this account.")
            password = input(f"{Fore.YELLOW}{Style.BRIGHT}  🔒 Enter 2FA Password: {Style.RESET_ALL}").strip()
            await client.sign_in(password=password)

    me = await client.get_me()
    divider()
    success(f"Logged in as: {Fore.GREEN}{Style.BRIGHT}{me.first_name}{Style.NORMAL} (@{me.username})")
    divider()
    return client


# --- Message Sender ---
async def send_messages(client: TelegramClient, group: str, interval: int):
    print()
    info(f"Total messages loaded : {Fore.WHITE}{Style.BRIGHT}{len(MESSAGES)}")
    info(f"Target group          : {Fore.WHITE}{Style.BRIGHT}{group}")
    info(f"Interval              : {Fore.WHITE}{Style.BRIGHT}{interval // 60} minutes")
    divider()
    success("Starting message loop...  (Ctrl+C to stop)")
    divider()
    print()

    index = 0
    while True:
        try:
            msg_num  = (index % len(MESSAGES)) + 1
            message  = MESSAGES[index % len(MESSAGES)]
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

            await client.send_message(group, message, parse_mode="html")

            sent(f"[{Fore.WHITE}{timestamp}{Fore.MAGENTA}] Message {Style.BRIGHT}{msg_num}/{len(MESSAGES)}{Style.NORMAL} sent!")
            print(f"     {Fore.WHITE}→ {message[:65]}...{Style.RESET_ALL}")

            index += 1
            next_time = time.strftime('%H:%M:%S', time.localtime(time.time() + interval))
            timer(f"Next message at {Fore.BLUE}{Style.BRIGHT}{next_time}")
            print()

            await asyncio.sleep(interval)

        except FloodWaitError as e:
            warning(f"Rate limited by Telegram! Waiting {Fore.YELLOW}{Style.BRIGHT}{e.seconds}s{Style.NORMAL}...")
            await asyncio.sleep(e.seconds)

        except KeyboardInterrupt:
            print()
            divider()
            warning("Stopped by user. Goodbye! 👋")
            divider()
            break

        except Exception as e:
            error(f"{e} — Retrying in 60s...")
            await asyncio.sleep(60)


# --- Main ---
async def main():
    banner()
    divider()

    phone = input(f"{Fore.CYAN}{Style.BRIGHT}  📱 Phone number (e.g. +91XXXXXXXXXX): {Style.RESET_ALL}").strip()
    client = await login(phone)

    print(f"{Fore.CYAN}{Style.BRIGHT}  --- Promotion Details ---{Style.RESET_ALL}")
    group = input(f"{Fore.CYAN}{Style.BRIGHT}  👥 Group username or ID: {Style.RESET_ALL}").strip()
    mins  = input(f"{Fore.CYAN}{Style.BRIGHT}  ⏱️  Interval in minutes : {Style.RESET_ALL}").strip()

    await send_messages(client, group, int(mins) * 60)
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
