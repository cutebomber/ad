# simple_userbot.py
import asyncio
import logging
import json
import os
import random
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

# Simple logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleUserBot:
    def __init__(self):
        # These will be set during setup
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.client = None
        
        # Bot settings
        self.ads = []
        self.target_groups = []  # Store group IDs
        self.interval_minutes = 5
        self.is_sending = False
        self.send_task = None
        
        # Load saved config
        self.load_config()
    
    def load_config(self):
        """Load saved settings"""
        if os.path.exists('userbot_data.json'):
            try:
                with open('userbot_data.json', 'r') as f:
                    data = json.load(f)
                    self.ads = data.get('ads', [])
                    self.target_groups = data.get('target_groups', [])
                    self.interval_minutes = data.get('interval_minutes', 5)
                logger.info("Loaded saved configuration")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save settings"""
        data = {
            'ads': self.ads,
            'target_groups': self.target_groups,
            'interval_minutes': self.interval_minutes
        }
        try:
            with open('userbot_data.json', 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    async def setup(self):
        """Setup and login to Telegram"""
        print("\n" + "="*50)
        print("Telegram UserBot Setup")
        print("="*50)
        
        # Get credentials
        self.api_id = int(input("Enter API ID (from my.telegram.org): ").strip())
        self.api_hash = input("Enter API Hash: ").strip()
        self.phone = input("Enter phone number (with country code, e.g., +1234567890): ").strip()
        
        # Create client
        self.client = TelegramClient('userbot_session', self.api_id, self.api_hash)
        
        try:
            # Start the client
            await self.client.start(phone=self.phone)
            
            # Test connection
            me = await self.client.get_me()
            print(f"\n✅ Successfully logged in as: {me.first_name} (@{me.username})")
            
            # Send welcome message
            await self.client.send_message('me', "🤖 UserBot is now active!\nType .help to see available commands.")
            
            return True
        except Exception as e:
            print(f"\n❌ Login failed: {e}")
            return False
    
    async def send_message_to_self(self, text):
        """Send message to saved messages"""
        try:
            await self.client.send_message('me', text)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def add_ad(self, text):
        """Add advertisement text"""
        self.ads.append(text)
        self.save_config()
        await self.send_message_to_self(f"✅ Added ad #{len(self.ads)}: {text[:50]}...")
        logger.info(f"Added ad: {text[:50]}")
    
    async def remove_ad(self, index):
        """Remove ad by index"""
        if 1 <= index <= len(self.ads):
            removed = self.ads.pop(index - 1)
            self.save_config()
            await self.send_message_to_self(f"✅ Removed ad #{index}: {removed[:50]}...")
        else:
            await self.send_message_to_self(f"❌ Invalid ad number! Use .listads to see available ads.")
    
    async def list_ads(self):
        """List all ads"""
        if not self.ads:
            await self.send_message_to_self("📝 No ads added. Use .add <text> to add ads.")
            return
        
        msg = "📝 **Your Ads:**\n\n"
        for i, ad in enumerate(self.ads, 1):
            msg += f"{i}. {ad}\n\n"
        await self.send_message_to_self(msg)
    
    async def set_interval(self, minutes):
        """Set sending interval"""
        try:
            minutes = int(minutes)
            if minutes < 1:
                await self.send_message_to_self("❌ Interval must be at least 1 minute!")
                return
            
            self.interval_minutes = minutes
            self.save_config()
            await self.send_message_to_self(f"✅ Interval set to {minutes} minute(s)")
        except ValueError:
            await self.send_message_to_self("❌ Please enter a valid number!")
    
    async def add_group(self, group_input):
        """Add target group"""
        try:
            # Try to get entity
            if group_input.isdigit():
                entity = await self.client.get_entity(int(group_input))
            else:
                # Remove @ if present
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
            
            group_id = entity.id
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            
            # Check if already added
            if group_id not in self.target_groups:
                self.target_groups.append(group_id)
                self.save_config()
                await self.send_message_to_self(f"✅ Added group: {group_name} (ID: {group_id})")
            else:
                await self.send_message_to_self(f"⚠️ Group already in list!")
                
        except Exception as e:
            await self.send_message_to_self(f"❌ Could not find group: {group_input}\nError: {str(e)}")
    
    async def remove_group(self, group_input):
        """Remove target group"""
        try:
            # Try to get entity to find ID
            if group_input.isdigit():
                group_id = int(group_input)
            else:
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
                group_id = entity.id
            
            if group_id in self.target_groups:
                self.target_groups.remove(group_id)
                self.save_config()
                await self.send_message_to_self(f"✅ Removed group ID: {group_id}")
            else:
                await self.send_message_to_self(f"⚠️ Group not found in list!")
                
        except Exception as e:
            await self.send_message_to_self(f"❌ Error: {str(e)}")
    
    async def list_groups(self):
        """List all target groups"""
        if not self.target_groups:
            await self.send_message_to_self("📝 No target groups added. Use .group <id/username> to add groups.")
            return
        
        msg = "📝 **Target Groups:**\n\n"
        for i, group_id in enumerate(self.target_groups, 1):
            try:
                entity = await self.client.get_entity(group_id)
                name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                msg += f"{i}. {name}\n   ID: {group_id}\n\n"
            except:
                msg += f"{i}. ID: {group_id}\n\n"
        
        await self.send_message_to_self(msg)
    
    async def send_ad_to_group(self, group_id, ad_text):
        """Send ad to a single group"""
        try:
            # Random delay to avoid patterns
            await asyncio.sleep(random.uniform(3, 8))
            
            await self.client.send_message(group_id, ad_text)
            logger.info(f"Sent to group {group_id}")
            return True
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds} seconds")
            await self.send_message_to_self(f"⚠️ Flood wait: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error sending to {group_id}: {e}")
            return False
    
    async def send_loop(self):
        """Main sending loop"""
        ad_index = 0
        
        while self.is_sending:
            try:
                if not self.ads:
                    await self.send_message_to_self("⚠️ No ads to send! Add some ads with .add")
                    await asyncio.sleep(60)
                    continue
                
                if not self.target_groups:
                    await self.send_message_to_self("⚠️ No target groups! Add groups with .group")
                    await asyncio.sleep(60)
                    continue
                
                # Get current ad (rotate)
                current_ad = self.ads[ad_index % len(self.ads)]
                ad_index += 1
                
                # Send to all groups
                for group_id in self.target_groups:
                    if not self.is_sending:
                        break
                    
                    success = await self.send_ad_to_group(group_id, current_ad)
                    if not success:
                        await asyncio.sleep(30)
                
                # Wait for interval
                wait_seconds = self.interval_minutes * 60
                await self.send_message_to_self(f"📤 Cycle complete. Next send in {self.interval_minutes} minutes.")
                await asyncio.sleep(wait_seconds)
                
            except Exception as e:
                logger.error(f"Error in send loop: {e}")
                await asyncio.sleep(60)
    
    async def start_sending(self):
        """Start sending ads"""
        if self.is_sending:
            await self.send_message_to_self("⚠️ Already sending!")
            return
        
        if not self.ads:
            await self.send_message_to_self("❌ No ads added! Use .add <text>")
            return
        
        if not self.target_groups:
            await self.send_message_to_self("❌ No target groups! Use .group <id/username>")
            return
        
        self.is_sending = True
        self.send_task = asyncio.create_task(self.send_loop())
        await self.send_message_to_self(f"✅ Started sending ads every {self.interval_minutes} minute(s)")
        logger.info("Started sending ads")
    
    async def stop_sending(self):
        """Stop sending ads"""
        if self.send_task:
            self.is_sending = False
            self.send_task.cancel()
            try:
                await self.send_task
            except asyncio.CancelledError:
                pass
            self.send_task = None
            await self.send_message_to_self("⏹️ Stopped sending ads")
            logger.info("Stopped sending ads")
    
    async def show_status(self):
        """Show current status"""
        status = f"""📊 **UserBot Status**

✅ **Ads:** {len(self.ads)} ad(s)
⏱️ **Interval:** {self.interval_minutes} minute(s)
👥 **Target Groups:** {len(self.target_groups)} group(s)
🔄 **Sending:** {'✅ Active' if self.is_sending else '❌ Stopped'}

**Commands:**
.add <text> - Add ad
.remove <num> - Remove ad
.listads - List all ads
.time <mins> - Set interval
.group <id/username> - Add group
.rmgroup <id/username> - Remove group
.listgroups - List groups
.start - Start sending
.stop - Stop sending
.status - Show status
.help - Show this help"""
        
        await self.send_message_to_self(status)
    
    async def handle_commands(self, event):
        """Handle incoming commands"""
        message = event.message.text.strip()
        
        # Only respond to commands in Saved Messages
        if not message.startswith('.'):
            return
        
        # Parse command
        parts = message.split(' ', 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ''
        
        # Execute commands
        if cmd == '.add':
            if arg:
                await self.add_ad(arg)
            else:
                await self.send_message_to_self("❌ Usage: .add <text>")
        
        elif cmd == '.remove':
            if arg and arg.isdigit():
                await self.remove_ad(int(arg))
            else:
                await self.send_message_to_self("❌ Usage: .remove <number>")
        
        elif cmd == '.listads':
            await self.list_ads()
        
        elif cmd == '.time':
            if arg:
                await self.set_interval(arg)
            else:
                await self.send_message_to_self("❌ Usage: .time <minutes>")
        
        elif cmd == '.group':
            if arg:
                await self.add_group(arg)
            else:
                await self.send_message_to_self("❌ Usage: .group <id/username>")
        
        elif cmd == '.rmgroup':
            if arg:
                await self.remove_group(arg)
            else:
                await self.send_message_to_self("❌ Usage: .rmgroup <id/username>")
        
        elif cmd == '.listgroups':
            await self.list_groups()
        
        elif cmd == '.start':
            await self.start_sending()
        
        elif cmd == '.stop':
            await self.stop_sending()
        
        elif cmd == '.status':
            await self.show_status()
        
        elif cmd == '.help':
            await self.show_status()
        
        else:
            await self.send_message_to_self(f"❌ Unknown command: {cmd}\nUse .help for commands")

async def main():
    """Main function"""
    bot = SimpleUserBot()
    
    # Setup and login
    if not await bot.setup():
        print("Setup failed. Exiting...")
        return
    
    print("\n✅ UserBot is running!")
    print("📝 Send commands in your Saved Messages")
    print("💡 Type .help to see all commands")
    
    # Register command handler
    @bot.client.on(events.NewMessage(from_users='me'))
    async def handler(event):
        await bot.handle_commands(event)
    
    # Keep running
    try:
        await bot.client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping UserBot...")
        await bot.stop_sending()
        print("✅ UserBot stopped!")

if __name__ == "__main__":
    asyncio.run(main())
