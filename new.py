import asyncio
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import os

from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageEntityMention, MessageEntityTextUrl
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.errors import FloodWaitError, RPCError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('userbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramUserBot:
    def __init__(self, api_id: int, api_hash: str, phone_number: str):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('userbot_session', api_id, api_hash)
        
        # Bot settings
        self.ads = []  # List of ad texts
        self.current_ad_index = 0
        self.interval_minutes = 5  # Default interval
        self.target_groups = []  # List of target group IDs/entities
        self.is_running = False
        self.sending_task = None
        
        # Reply system
        self.reply_group_id = None  # Group where replies will be forwarded
        self.reply_mapping = {}  # Map original message IDs to reply messages
        
        # Control settings
        self.control_group_id = None  # Group where commands can be sent
        
        # Load config
        self.load_config()
        
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists('userbot_config.json'):
            try:
                with open('userbot_config.json', 'r') as f:
                    config = json.load(f)
                    self.ads = config.get('ads', [])
                    self.interval_minutes = config.get('interval_minutes', 5)
                    self.target_groups = config.get('target_groups', [])
                    self.reply_group_id = config.get('reply_group_id')
                    self.control_group_id = config.get('control_group_id')
                    logger.info("Configuration loaded")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        config = {
            'ads': self.ads,
            'interval_minutes': self.interval_minutes,
            'target_groups': self.target_groups,
            'reply_group_id': self.reply_group_id,
            'control_group_id': self.control_group_id
        }
        try:
            with open('userbot_config.json', 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    async def login(self) -> bool:
        """Login to Telegram account"""
        try:
            await self.client.start(phone=self.phone_number)
            logger.info("Successfully logged in to Telegram")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    async def get_entity_from_input(self, input_str: str):
        """Get entity from ID or username"""
        try:
            # Try as integer ID
            if input_str.isdigit():
                return await self.client.get_entity(int(input_str))
            # Try as username
            else:
                # Remove @ if present
                username = input_str.lstrip('@')
                return await self.client.get_entity(username)
        except Exception as e:
            logger.error(f"Error getting entity: {e}")
            return None
    
    async def add_ad(self, text: str):
        """Add advertisement text"""
        self.ads.append(text)
        self.save_config()
        await self.send_message_to_control(f"✅ Added ad #{len(self.ads)}: {text[:50]}...")
        logger.info(f"Added ad: {text[:50]}...")
    
    async def remove_ad(self, index: int):
        """Remove advertisement by index"""
        if 1 <= index <= len(self.ads):
            removed = self.ads.pop(index - 1)
            self.save_config()
            await self.send_message_to_control(f"✅ Removed ad #{index}: {removed[:50]}...")
        else:
            await self.send_message_to_control(f"❌ Invalid ad index! Use .listads to see available ads.")
    
    async def list_ads(self):
        """List all advertisements"""
        if not self.ads:
            await self.send_message_to_control("📝 No ads added yet. Use .add <text> to add ads.")
            return
        
        message = "📝 **Your Ads:**\n\n"
        for i, ad in enumerate(self.ads, 1):
            message += f"{i}. {ad}\n\n"
        await self.send_message_to_control(message)
    
    async def set_interval(self, minutes: int):
        """Set sending interval in minutes"""
        if minutes < 1:
            await self.send_message_to_control("❌ Interval must be at least 1 minute!")
            return
        
        self.interval_minutes = minutes
        self.save_config()
        await self.send_message_to_control(f"✅ Interval set to {minutes} minute(s)")
        
        # Restart sending if running
        if self.is_running:
            await self.stop_sending()
            await self.start_sending()
    
    async def add_group(self, group_input: str):
        """Add target group by ID or username"""
        entity = await self.get_entity_from_input(group_input)
        if entity:
            group_info = {
                'id': entity.id,
                'username': getattr(entity, 'username', None),
                'title': getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            }
            
            # Check if already added
            if group_info['id'] not in [g['id'] for g in self.target_groups]:
                self.target_groups.append(group_info)
                self.save_config()
                await self.send_message_to_control(f"✅ Added group: {group_info['title']} (ID: {group_info['id']})")
            else:
                await self.send_message_to_control(f"⚠️ Group already added!")
        else:
            await self.send_message_to_control(f"❌ Could not find group: {group_input}")
    
    async def remove_group(self, group_input: str):
        """Remove target group"""
        entity = await self.get_entity_from_input(group_input)
        if entity:
            group_id = entity.id
            removed = [g for g in self.target_groups if g['id'] == group_id]
            self.target_groups = [g for g in self.target_groups if g['id'] != group_id]
            self.save_config()
            
            if removed:
                await self.send_message_to_control(f"✅ Removed group: {removed[0]['title']}")
            else:
                await self.send_message_to_control(f"⚠️ Group not found in target list")
        else:
            await self.send_message_to_control(f"❌ Could not find group: {group_input}")
    
    async def list_groups(self):
        """List all target groups"""
        if not self.target_groups:
            await self.send_message_to_control("📝 No target groups added yet. Use .group <id/username> to add groups.")
            return
        
        message = "📝 **Target Groups:**\n\n"
        for i, group in enumerate(self.target_groups, 1):
            username = f"@{group['username']}" if group['username'] else "No username"
            message += f"{i}. {group['title']}\n   ID: {group['id']}\n   Username: {username}\n\n"
        
        await self.send_message_to_control(message)
    
    async def send_ad_to_group(self, group_id: int, ad_text: str):
        """Send advertisement to a group"""
        try:
            # Random delay between 2-7 seconds to avoid patterns
            await asyncio.sleep(random.uniform(2, 7))
            
            # Send the message
            await self.client.send_message(group_id, ad_text)
            logger.info(f"Sent ad to group {group_id}")
            return True
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error sending ad: {e}")
            return False
    
    async def send_ads_loop(self):
        """Main loop for sending advertisements"""
        while self.is_running:
            try:
                if not self.ads:
                    await asyncio.sleep(60)
                    continue
                
                if not self.target_groups:
                    await asyncio.sleep(60)
                    continue
                
                # Get next ad (rotate)
                ad_text = self.ads[self.current_ad_index]
                self.current_ad_index = (self.current_ad_index + 1) % len(self.ads)
                
                # Send to all groups
                for group in self.target_groups:
                    if not self.is_running:
                        break
                    
                    success = await self.send_ad_to_group(group['id'], ad_text)
                    if not success:
                        await asyncio.sleep(30)
                
                # Wait for interval
                await asyncio.sleep(self.interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in send loop: {e}")
                await asyncio.sleep(60)
    
    async def start_sending(self):
        """Start the advertisement sending loop"""
        if self.is_running:
            await self.send_message_to_control("⚠️ Already running!")
            return
        
        if not self.ads:
            await self.send_message_to_control("❌ No ads added! Use .add <text> to add ads.")
            return
        
        if not self.target_groups:
            await self.send_message_to_control("❌ No target groups added! Use .group <id/username> to add groups.")
            return
        
        self.is_running = True
        self.sending_task = asyncio.create_task(self.send_ads_loop())
        await self.send_message_to_control(f"✅ Started sending ads every {self.interval_minutes} minute(s)")
        logger.info("Started sending ads")
    
    async def stop_sending(self):
        """Stop the advertisement sending loop"""
        if self.sending_task:
            self.is_running = False
            self.sending_task.cancel()
            try:
                await self.sending_task
            except asyncio.CancelledError:
                pass
            self.sending_task = None
            await self.send_message_to_control("⏹️ Stopped sending ads")
            logger.info("Stopped sending ads")
    
    async def set_reply_group(self, group_input: str):
        """Set the group where replies will be forwarded"""
        entity = await self.get_entity_from_input(group_input)
        if entity:
            self.reply_group_id = entity.id
            self.save_config()
            await self.send_message_to_control(f"✅ Reply group set to: {getattr(entity, 'title', 'Group')}")
        else:
            await self.send_message_to_control(f"❌ Could not find group: {group_input}")
    
    async def set_control_group(self, group_input: str):
        """Set the group where commands can be sent"""
        entity = await self.get_entity_from_input(group_input)
        if entity:
            self.control_group_id = entity.id
            self.save_config()
            await self.send_message_to_control(f"✅ Control group set to: {getattr(entity, 'title', 'Group')}")
        else:
            await self.send_message_to_control(f"❌ Could not find group: {group_input}")
    
    async def send_message_to_control(self, message: str):
        """Send message to control group or saved messages"""
        try:
            if self.control_group_id:
                await self.client.send_message(self.control_group_id, message)
            else:
                # Send to saved messages if no control group set
                await self.client.send_message('me', message)
        except Exception as e:
            logger.error(f"Error sending control message: {e}")
    
    async def forward_reply_to_group(self, original_message: Message):
        """Forward a reply to the designated reply group"""
        try:
            if self.reply_group_id:
                # Format the reply with context
                reply_text = f"**Reply received in:** {original_message.chat.title}\n\n"
                reply_text += f"**Original message:**\n{original_message.text}\n\n"
                reply_text += f"**Reply:**"
                
                await self.client.send_message(self.reply_group_id, reply_text)
                # Send the actual reply message
                await self.client.forward_messages(self.reply_group_id, original_message)
                
                # Store mapping for auto-reply
                self.reply_mapping[original_message.id] = {
                    'original_chat': original_message.chat.id,
                    'original_message_id': original_message.id
                }
        except Exception as e:
            logger.error(f"Error forwarding reply: {e}")
    
    async def auto_reply_to_original(self, reply_message: Message):
        """Automatically reply to the original message when replying in reply group"""
        try:
            # Check if this is a reply in the reply group
            if reply_message.chat.id == self.reply_group_id and reply_message.reply_to_msg_id:
                # Get the original message reference from mapping
                for original_id, info in self.reply_mapping.items():
                    # This is a simplified approach - you might need a more sophisticated mapping
                    pass
                
                # For now, just mention that this feature is in development
                await self.send_message_to_control("⚠️ Auto-reply feature needs proper message ID mapping")
                
        except Exception as e:
            logger.error(f"Error in auto-reply: {e}")
    
    async def status(self):
        """Show current status"""
        status_text = f"""📊 **UserBot Status**

**Ads:** {len(self.ads)} ad(s)
**Interval:** {self.interval_minutes} minute(s)
**Target Groups:** {len(self.target_groups)} group(s)
**Sending:** {'✅ Active' if self.is_running else '❌ Stopped'}
**Reply Group:** {'✅ Set' if self.reply_group_id else '❌ Not set'}
**Control Group:** {'✅ Set' if self.control_group_id else '❌ Not set'}

Use .help for available commands"""
        
        await self.send_message_to_control(status_text)

    async def help(self):
        """Show help message"""
        help_text = """🤖 **UserBot Commands**

**Ad Management:**
`.add <text>` - Add advertisement text
`.remove <index>` - Remove ad by number
`.listads` - List all ads

**Group Management:**
`.group <id/username>` - Add target group
`.rmgroup <id/username>` - Remove target group
`.listgroups` - List target groups

**Settings:**
`.time <minutes>` - Set sending interval
`.replygroup <id/username>` - Set reply forwarding group
`.controlgroup <id/username>` - Set control group for commands
`.start` - Start sending ads
`.stop` - Stop sending ads
`.status` - Show current status
`.help` - Show this help

**Examples:**
`.add Check out our amazing products!`
`.time 5`
`.group @mygroup`
`.start`"""
        
        await self.send_message_to_control(help_text)

async def main():
    """Main function to run the userbot"""
    print("=" * 50)
    print("Telegram UserBot - Setup")
    print("=" * 50)
    
    # Get credentials
    api_id = input("Enter your API ID (from my.telegram.org): ")
    api_hash = input("Enter your API Hash: ")
    phone_number = input("Enter your phone number (with country code, e.g., +1234567890): ")
    
    # Create bot instance
    bot = TelegramUserBot(int(api_id), api_hash, phone_number)
    
    # Login
    if not await bot.login():
        print("Login failed! Exiting...")
        return
    
    print("\n✅ Login successful!")
    print("\n🤖 UserBot is running!")
    print("Send commands in your control group or saved messages")
    print("Type .help to see available commands")
    
    # Set up command handlers
    @bot.client.on(events.NewMessage(incoming=True))
    async def command_handler(event: events.NewMessage.Event):
        """Handle commands"""
        # Only process messages from self or control group
        is_self = event.out or event.message.from_id == (await bot.client.get_me()).id
        is_control = bot.control_group_id and event.chat_id == bot.control_group_id
        
        if not (is_self or is_control):
            return
        
        message = event.message.text.strip()
        if not message.startswith('.'):
            return
        
        # Parse command
        parts = message.split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        
        # Handle commands
        if command == '.add':
            if args:
                await bot.add_ad(args)
            else:
                await bot.send_message_to_control("❌ Usage: .add <text>")
        
        elif command == '.remove':
            if args and args.isdigit():
                await bot.remove_ad(int(args))
            else:
                await bot.send_message_to_control("❌ Usage: .remove <index>")
        
        elif command == '.listads':
            await bot.list_ads()
        
        elif command == '.time':
            if args and args.isdigit():
                await bot.set_interval(int(args))
            else:
                await bot.send_message_to_control("❌ Usage: .time <minutes>")
        
        elif command == '.group':
            if args:
                await bot.add_group(args)
            else:
                await bot.send_message_to_control("❌ Usage: .group <id/username>")
        
        elif command == '.rmgroup':
            if args:
                await bot.remove_group(args)
            else:
                await bot.send_message_to_control("❌ Usage: .rmgroup <id/username>")
        
        elif command == '.listgroups':
            await bot.list_groups()
        
        elif command == '.start':
            await bot.start_sending()
        
        elif command == '.stop':
            await bot.stop_sending()
        
        elif command == '.replygroup':
            if args:
                await bot.set_reply_group(args)
            else:
                await bot.send_message_to_control("❌ Usage: .replygroup <id/username>")
        
        elif command == '.controlgroup':
            if args:
                await bot.set_control_group(args)
            else:
                await bot.send_message_to_control("❌ Usage: .controlgroup <id/username>")
        
        elif command == '.status':
            await bot.status()
        
        elif command == '.help':
            await bot.help()
        
        else:
            await bot.send_message_to_control(f"❌ Unknown command: {command}\nUse .help for available commands")
    
    # Handle replies for forwarding
    @bot.client.on(events.NewMessage(incoming=True))
    async def reply_handler(event: events.NewMessage.Event):
        """Handle replies to bot messages"""
        # Skip if it's a command
        if event.message.text.startswith('.'):
            return
        
        # Check if this is a reply to a message sent by the bot
        if event.message.reply_to_msg_id:
            # This is a reply - forward to reply group
            original = await event.get_reply_message()
            if original and original.out:
                await bot.forward_reply_to_group(event.message)
    
    # Keep the bot running
    try:
        await bot.client.run_until_disconnected()
    except KeyboardInterrupt:
        await bot.stop_sending()
        print("\nUserBot stopped!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nUserBot terminated by user")
    except Exception as e:
        print(f"Error: {e}")
