# working_userbot.py
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

class WorkingUserBot:
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
        
        # Reply system - using message ID as key for better tracking
        self.reply_group_id = None  # Group where replies will be forwarded
        self.reply_mapping = {}  # Maps forwarded message ID -> original info
        
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
                    self.reply_group_id = data.get('reply_group_id')
                    self.reply_mapping = data.get('reply_mapping', {})
                logger.info("Loaded saved configuration")
            except Exception as e:
                logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save settings"""
        data = {
            'ads': self.ads,
            'target_groups': self.target_groups,
            'interval_minutes': self.interval_minutes,
            'reply_group_id': self.reply_group_id,
            'reply_mapping': self.reply_mapping
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
            welcome = """🤖 UserBot is now active!

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

**Reply System:**
.setreplygroup <id/username> - Set reply forwarding group
.replystatus - Show reply system status

.status - Show all status
.help - Show this help"""

            await self.client.send_message('me', welcome)
            
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
    
    # ============ AD SYSTEM ============
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
    
    # ============ GROUP MANAGEMENT ============
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
    
    # ============ SENDING SYSTEM ============
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
    
    # ============ FIXED REPLY SYSTEM ============
    async def set_reply_group(self, group_input):
        """Set the group where replies will be forwarded"""
        try:
            # Get the group entity
            if group_input.isdigit():
                entity = await self.client.get_entity(int(group_input))
            else:
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
            
            self.reply_group_id = entity.id
            self.save_config()
            
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            await self.send_message_to_self(f"✅ Reply group set to: {group_name}\nAll replies will be forwarded here.")
            
            # Send test message to reply group
            test_msg = await self.client.send_message(
                self.reply_group_id,
                "🤖 **Reply System Active**\n\n"
                "✅ This is your reply group!\n\n"
                "**How it works:**\n"
                "1. When someone replies to your messages, they'll appear here\n"
                "2. Reply to this message to test the system\n"
                "3. Your reply will be sent back to where the original message came from"
            )
            
            # Store this test message mapping
            mapping_key = f"test_{test_msg.id}"
            self.reply_mapping[mapping_key] = {
                'original_chat_id': 'me',
                'original_message_id': test_msg.id,
                'reply_group_id': self.reply_group_id,
                'forwarded_message_id': test_msg.id,
                'is_test': True,
                'timestamp': datetime.now().isoformat()
            }
            self.save_config()
            
        except Exception as e:
            await self.send_message_to_self(f"❌ Could not find group: {group_input}\nError: {str(e)}")
    
    async def forward_reply_to_group(self, reply_message):
        """Forward a reply to the designated reply group"""
        try:
            if not self.reply_group_id:
                return
            
            # Get the original message that was replied to
            original_message = await reply_message.get_reply_message()
            if not original_message:
                logger.info("No original message found")
                return
            
            # Only forward if the original message was sent by us (the bot)
            if not original_message.out:
                logger.info("Original message not sent by us, skipping")
                return
            
            # Get sender info
            sender = reply_message.sender
            sender_name = sender.first_name
            if sender.last_name:
                sender_name += f" {sender.last_name}"
            if sender.username:
                sender_name += f" (@{sender.username})"
            
            # Get original chat info
            original_chat = await reply_message.get_chat()
            original_chat_name = getattr(original_chat, 'title', None) or getattr(original_chat, 'first_name', 'Unknown')
            
            # Create forwarded message with context
            forward_text = f"""**📨 New Reply Received!**

**From:** {sender_name}
**In:** {original_chat_name}
**Replied to:** {original_message.text[:200]}...

---
**Reply Message:**
{reply_message.text}
---
**To reply:** Send a reply to this message and it will be sent back!"""

            # Send to reply group
            sent = await self.client.send_message(self.reply_group_id, forward_text)
            
            # Store mapping with unique key
            mapping_key = f"{sent.id}_{self.reply_group_id}"
            self.reply_mapping[mapping_key] = {
                'original_chat_id': original_chat.id,
                'original_message_id': original_message.id,
                'reply_group_id': self.reply_group_id,
                'forwarded_message_id': sent.id,
                'original_reply_id': reply_message.id,
                'original_sender': sender_name,
                'original_chat_name': original_chat_name,
                'timestamp': datetime.now().isoformat()
            }
            self.save_config()
            
            logger.info(f"Forwarded reply from {original_chat_name} to reply group. Mapping: {mapping_key}")
            
            # Send confirmation
            await self.send_message_to_self(f"📨 Reply forwarded from {original_chat_name}")
            
        except Exception as e:
            logger.error(f"Error forwarding reply: {e}")
            await self.send_message_to_self(f"❌ Error forwarding reply: {str(e)}")
    
    async def auto_reply_to_original(self, message):
        """When user replies in reply group, send back to original chat"""
        try:
            # Check if message is in reply group
            if not self.reply_group_id or message.chat_id != self.reply_group_id:
                return
            
            # Check if it's a reply to a forwarded message
            if not message.is_reply:
                logger.info("Message not a reply, skipping auto-reply")
                return
            
            # Get the original forwarded message
            original_forwarded = await message.get_reply_message()
            if not original_forwarded:
                logger.info("Could not get original forwarded message")
                return
            
            logger.info(f"Processing reply in reply group. Forwarded message ID: {original_forwarded.id}")
            
            # Look up mapping
            found_mapping = None
            for key, info in self.reply_mapping.items():
                if info.get('forwarded_message_id') == original_forwarded.id:
                    found_mapping = info
                    logger.info(f"Found mapping: {key}")
                    break
            
            if not found_mapping:
                logger.info(f"No mapping found for forwarded message ID: {original_forwarded.id}")
                await self.client.send_message(
                    self.reply_group_id,
                    "❌ Could not find original message. This mapping may have expired.",
                    reply_to=message.id
                )
                return
            
            # Don't auto-reply to test messages
            if found_mapping.get('is_test'):
                await self.client.send_message(
                    self.reply_group_id,
                    "✅ Test successful! Your reply system is working.\n\n"
                    "This was just a test. Real replies will work the same way!",
                    reply_to=message.id
                )
                return
            
            # Prepare reply text
            sender_name = message.sender.first_name
            if message.sender.last_name:
                sender_name += f" {message.sender.last_name}"
            
            reply_text = f"**Reply from {sender_name}:**\n{message.text}"
            
            # Send reply to original chat
            try:
                sent = await self.client.send_message(
                    found_mapping['original_chat_id'],
                    reply_text,
                    reply_to=found_mapping['original_message_id']
                )
                
                logger.info(f"Auto-replied to {found_mapping['original_chat_id']}")
                
                # Notify in reply group that reply was sent
                await self.client.send_message(
                    self.reply_group_id,
                    f"✅ Reply sent back to **{found_mapping.get('original_chat_name', 'original chat')}**!\n\n"
                    f"Your reply: {message.text[:100]}...",
                    reply_to=message.id
                )
                
                # Optional: Remove mapping after use
                # del self.reply_mapping[key]
                # self.save_config()
                
            except Exception as e:
                error_msg = f"❌ Failed to send reply: {str(e)}"
                logger.error(error_msg)
                await self.client.send_message(
                    self.reply_group_id,
                    error_msg,
                    reply_to=message.id
                )
            
        except Exception as e:
            logger.error(f"Error in auto-reply: {e}")
            try:
                await self.client.send_message(
                    self.reply_group_id,
                    f"❌ Auto-reply error: {str(e)}",
                    reply_to=message.id if message else None
                )
            except:
                pass
    
    async def reply_status(self):
        """Show reply system status"""
        if not self.reply_group_id:
            await self.send_message_to_self("❌ Reply system not configured!\nUse .setreplygroup <id/username> to set it up.")
            return
        
        try:
            entity = await self.client.get_entity(self.reply_group_id)
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            
            # Count active mappings (excluding test ones)
            active_mappings = {k: v for k, v in self.reply_mapping.items() if not v.get('is_test')}
            
            status = f"""**📨 Reply System Status**

✅ **Active**
📱 **Reply Group:** {group_name} (ID: {self.reply_group_id})
📊 **Active Mappings:** {len(active_mappings)}
🔄 **Total Mappings:** {len(self.reply_mapping)}

**How it works:**
1. When someone replies to your messages, it's forwarded here
2. Reply to the forwarded message to respond back
3. Your reply will be sent to the original chat

**Test it:**
- Send a test reply to the welcome message in your reply group
- The bot will confirm if it's working

**Commands:**
`.clearreplymappings` - Clear all mappings
`.replystatus` - Show this status"""
            
            await self.send_message_to_self(status)
            
        except Exception as e:
            await self.send_message_to_self(f"❌ Error: {str(e)}")
    
    async def clear_reply_mappings(self):
        """Clear all reply mappings"""
        self.reply_mapping = {}
        self.save_config()
        await self.send_message_to_self("✅ Cleared all reply mappings")
    
    # ============ STATUS SYSTEM ============
    async def show_status(self):
        """Show current status"""
        active_mappings = {k: v for k, v in self.reply_mapping.items() if not v.get('is_test')}
        
        status = f"""📊 **UserBot Status**

**Ad System:**
✅ Ads: {len(self.ads)} ad(s)
⏱️ Interval: {self.interval_minutes} minute(s)
👥 Target Groups: {len(self.target_groups)} group(s)
🔄 Sending: {'✅ Active' if self.is_sending else '❌ Stopped'}

**Reply System:**
📨 Reply Group: {'✅ Set' if self.reply_group_id else '❌ Not set'}
🔄 Active Mappings: {len(active_mappings)}

**Commands:**
📝 .add <text> - Add ad
🗑️ .remove <num> - Remove ad
📋 .listads - List all ads
⏰ .time <mins> - Set interval
👥 .group <id/username> - Add group
❌ .rmgroup <id/username> - Remove group
📊 .listgroups - List groups
▶️ .start - Start sending
⏹️ .stop - Stop sending

**Reply Commands:**
📨 .setreplygroup <id/username> - Set reply group
📊 .replystatus - Show reply system status
🧹 .clearreplymappings - Clear reply mappings

💡 .status - Show this status
❓ .help - Show this help"""
        
        await self.send_message_to_self(status)
    
    # ============ COMMAND HANDLER ============
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
        
        elif cmd == '.setreplygroup':
            if arg:
                await self.set_reply_group(arg)
            else:
                await self.send_message_to_self("❌ Usage: .setreplygroup <id/username>")
        
        elif cmd == '.replystatus':
            await self.reply_status()
        
        elif cmd == '.clearreplymappings':
            await self.clear_reply_mappings()
        
        elif cmd == '.status':
            await self.show_status()
        
        elif cmd == '.help':
            await self.show_status()
        
        else:
            await self.send_message_to_self(f"❌ Unknown command: {cmd}\nUse .help for commands")

async def main():
    """Main function"""
    bot = WorkingUserBot()
    
    # Setup and login
    if not await bot.setup():
        print("Setup failed. Exiting...")
        return
    
    print("\n✅ UserBot is running!")
    print("📝 Send commands in your Saved Messages")
    print("💡 Type .help to see all commands")
    
    # Register command handler for Saved Messages
    @bot.client.on(events.NewMessage(from_users='me'))
    async def command_handler(event):
        await bot.handle_commands(event)
    
    # Register reply handler for all messages
    @bot.client.on(events.NewMessage)
    async def reply_handler(event):
        # Handle forwarding replies to reply group
        if event.message.is_reply and not event.out:
            await bot.forward_reply_to_group(event.message)
        
        # Handle auto-reply from reply group
        await bot.auto_reply_to_original(event.message)
    
    # Keep running
    try:
        await bot.client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping UserBot...")
        await bot.stop_sending()
        print("✅ UserBot stopped!")

if __name__ == "__main__":
    asyncio.run(main())
