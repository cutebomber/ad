# session_userbot.py
import asyncio
import logging
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateStatusRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('userbot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SessionUserBot:
    def __init__(self):
        # Session string (will be loaded from config)
        self.session_string = None
        self.client = None
        
        # Bot settings
        self.ads = []
        self.target_groups = []
        self.interval_minutes = 5
        self.is_sending = False
        self.send_task = None
        self.startup_time = datetime.now()
        
        # Reply system
        self.reply_group_id = None
        self.reply_mapping = {}
        
        # API credentials (just for creating client)
        self.api_id = None
        self.api_hash = None
        
        # Config file
        self.config_file = Path(__file__).parent / 'config.json'
        
        # Load config
        self.load_config()
    
    def load_config(self):
        """Load configuration from config.json"""
        if not self.config_file.exists():
            print("\n" + "="*60)
            print("First time setup - Creating config.json")
            print("="*60)
            
            # Create config template
            config_template = {
                "api_id": 0,
                "api_hash": "your_api_hash_here",
                "session_string": "your_session_string_here",
                "ads": [],
                "target_groups": [],
                "interval_minutes": 5,
                "reply_group_id": None,
                "reply_mapping": {}
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_template, f, indent=4)
            
            print(f"\n✅ Created {self.config_file}")
            print("\n📝 Please edit config.json with your:")
            print("   - API ID")
            print("   - API Hash")
            print("   - Session String")
            print("\nThen run the script again!")
            sys.exit(0)
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                
                self.api_id = data.get('api_id')
                self.api_hash = data.get('api_hash')
                self.session_string = data.get('session_string')
                self.ads = data.get('ads', [])
                self.target_groups = data.get('target_groups', [])
                self.interval_minutes = data.get('interval_minutes', 5)
                self.reply_group_id = data.get('reply_group_id')
                self.reply_mapping = data.get('reply_mapping', {})
                
            logger.info("Configuration loaded successfully")
            
            # Validate config
            if not self.api_id or not self.api_hash:
                logger.error("API ID or API Hash missing in config.json")
                sys.exit(1)
                
            if not self.session_string:
                logger.error("Session string missing in config.json")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            sys.exit(1)
    
    def save_config(self):
        """Save configuration to config.json"""
        data = {
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'session_string': self.session_string,
            'ads': self.ads,
            'target_groups': self.target_groups,
            'interval_minutes': self.interval_minutes,
            'reply_group_id': self.reply_group_id,
            'reply_mapping': self.reply_mapping
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    async def setup(self):
        """Initialize client with session string"""
        try:
            # Create client with StringSession
            self.client = TelegramClient(
                StringSession(self.session_string),
                self.api_id,
                self.api_hash
            )
            
            # Connect
            await self.client.connect()
            
            # Check if authorized
            if not await self.client.is_user_authorized():
                logger.error("Session string is invalid or expired!")
                print("\n❌ Session string is invalid or expired!")
                print("Please generate a new session string and update config.json")
                return False
            
            # Test connection
            me = await self.client.get_me()
            print(f"\n✅ Successfully logged in as: {me.first_name} (@{me.username})")
            print(f"📱 User ID: {me.id}")
            
            # Set online status
            await self.client(UpdateStatusRequest(offline=False))
            
            # Send startup notification
            await self.send_to_self(f"🤖 **UserBot Started**\n\n"
                                   f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                                   f"Status: ✅ Running\n\n"
                                   f"Type .help to see commands")
            
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            print(f"\n❌ Setup failed: {e}")
            return False
    
    async def send_to_self(self, text):
        """Send message to saved messages"""
        try:
            await self.client.send_message('me', text)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    # ============ AD SYSTEM ============
    async def add_ad(self, text):
        self.ads.append(text)
        self.save_config()
        await self.send_to_self(f"✅ Added ad #{len(self.ads)}: {text[:50]}...")
        logger.info(f"Added ad: {text[:50]}")
    
    async def remove_ad(self, index):
        if 1 <= index <= len(self.ads):
            removed = self.ads.pop(index - 1)
            self.save_config()
            await self.send_to_self(f"✅ Removed ad #{index}: {removed[:50]}...")
        else:
            await self.send_to_self(f"❌ Invalid ad number!")
    
    async def list_ads(self):
        if not self.ads:
            await self.send_to_self("📝 No ads added. Use .add <text>")
            return
        
        msg = "📝 **Your Ads:**\n\n"
        for i, ad in enumerate(self.ads, 1):
            msg += f"{i}. {ad}\n\n"
        await self.send_to_self(msg)
    
    async def set_interval(self, minutes):
        try:
            minutes = int(minutes)
            if minutes < 1:
                await self.send_to_self("❌ Interval must be at least 1 minute!")
                return
            
            self.interval_minutes = minutes
            self.save_config()
            await self.send_to_self(f"✅ Interval set to {minutes} minute(s)")
            
            # Restart sending if running
            if self.is_sending:
                await self.stop_sending()
                await self.start_sending()
        except ValueError:
            await self.send_to_self("❌ Please enter a valid number!")
    
    # ============ GROUP MANAGEMENT ============
    async def add_group(self, group_input):
        try:
            if group_input.isdigit():
                entity = await self.client.get_entity(int(group_input))
            else:
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
            
            group_id = entity.id
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            
            if group_id not in self.target_groups:
                self.target_groups.append(group_id)
                self.save_config()
                await self.send_to_self(f"✅ Added group: {group_name} (ID: {group_id})")
            else:
                await self.send_to_self(f"⚠️ Group already in list!")
                
        except Exception as e:
            await self.send_to_self(f"❌ Could not find group: {group_input}\nError: {str(e)}")
    
    async def remove_group(self, group_input):
        try:
            if group_input.isdigit():
                group_id = int(group_input)
            else:
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
                group_id = entity.id
            
            if group_id in self.target_groups:
                self.target_groups.remove(group_id)
                self.save_config()
                await self.send_to_self(f"✅ Removed group ID: {group_id}")
            else:
                await self.send_to_self(f"⚠️ Group not found!")
                
        except Exception as e:
            await self.send_to_self(f"❌ Error: {str(e)}")
    
    async def list_groups(self):
        if not self.target_groups:
            await self.send_to_self("📝 No target groups added. Use .group <id/username>")
            return
        
        msg = "📝 **Target Groups:**\n\n"
        for i, group_id in enumerate(self.target_groups, 1):
            try:
                entity = await self.client.get_entity(group_id)
                name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                msg += f"{i}. {name}\n   ID: {group_id}\n\n"
            except:
                msg += f"{i}. ID: {group_id}\n\n"
        
        await self.send_to_self(msg)
    
    # ============ SENDING SYSTEM ============
    async def send_ad(self, group_id, ad_text):
        try:
            await asyncio.sleep(random.uniform(2, 5))
            await self.client.send_message(group_id, ad_text)
            logger.info(f"Sent to group {group_id}")
            return True
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds}s")
            await self.send_to_self(f"⚠️ Flood wait: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error sending to {group_id}: {e}")
            return False
    
    async def send_loop(self):
        """Main sending loop"""
        ad_index = 0
        cycle_count = 0
        
        while self.is_sending:
            try:
                if not self.ads:
                    await asyncio.sleep(60)
                    continue
                
                if not self.target_groups:
                    await asyncio.sleep(60)
                    continue
                
                # Get current ad (rotate)
                current_ad = self.ads[ad_index % len(self.ads)]
                ad_index += 1
                cycle_count += 1
                
                # Send to all groups
                for group_id in self.target_groups:
                    if not self.is_sending:
                        break
                    await self.send_ad(group_id, current_ad)
                    await asyncio.sleep(random.uniform(5, 10))
                
                # Wait for interval
                await asyncio.sleep(self.interval_minutes * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in send loop: {e}")
                await asyncio.sleep(60)
    
    async def start_sending(self):
        if self.is_sending:
            await self.send_to_self("⚠️ Already sending!")
            return
        
        if not self.ads:
            await self.send_to_self("❌ No ads added! Use .add <text>")
            return
        
        if not self.target_groups:
            await self.send_to_self("❌ No target groups! Use .group <id/username>")
            return
        
        self.is_sending = True
        self.send_task = asyncio.create_task(self.send_loop())
        await self.send_to_self(f"✅ Started sending ads every {self.interval_minutes} minute(s)")
        logger.info("Started sending ads")
    
    async def stop_sending(self):
        if self.send_task:
            self.is_sending = False
            self.send_task.cancel()
            try:
                await self.send_task
            except asyncio.CancelledError:
                pass
            self.send_task = None
            await self.send_to_self("⏹️ Stopped sending ads")
            logger.info("Stopped sending ads")
    
    # ============ REPLY SYSTEM ============
    async def set_reply_group(self, group_input):
        try:
            if group_input.isdigit():
                entity = await self.client.get_entity(int(group_input))
            else:
                username = group_input.lstrip('@')
                entity = await self.client.get_entity(username)
            
            self.reply_group_id = entity.id
            self.save_config()
            
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            await self.send_to_self(f"✅ Reply group set to: {group_name}")
            
            # Send test message
            test_msg = await self.client.send_message(
                self.reply_group_id,
                "🤖 **Reply System Active**\n\n"
                "Reply to this message to test the auto-reply system."
            )
            
            self.reply_mapping[str(test_msg.id)] = {
                'type': 'test',
                'original_chat_id': self.reply_group_id,
                'original_message_id': test_msg.id
            }
            self.save_config()
            
        except Exception as e:
            await self.send_to_self(f"❌ Error: {str(e)}")
    
    async def forward_reply(self, event):
        """Forward replies to your messages to the reply group"""
        try:
            if not self.reply_group_id:
                return
            
            if not event.message.is_reply:
                return
            
            original = await event.message.get_reply_message()
            if not original or not original.out:
                return
            
            chat = await event.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown')
            
            forward_text = f"""**📨 New Reply**

**From:** {event.sender.first_name}
**In:** {chat_name}
**Replied to:** {original.text[:150]}

**Reply:** {event.message.text}

---
💡 Reply to this message to respond back!"""
            
            sent = await self.client.send_message(self.reply_group_id, forward_text)
            
            self.reply_mapping[str(sent.id)] = {
                'type': 'reply',
                'original_chat_id': chat.id,
                'original_message_id': original.id,
                'original_text': original.text[:100]
            }
            self.save_config()
            
            logger.info(f"Forwarded reply from {chat_name}")
            
        except Exception as e:
            logger.error(f"Error forwarding reply: {e}")
    
    async def auto_reply(self, event):
        """Handle replies in the reply group"""
        try:
            if not self.reply_group_id or event.chat_id != self.reply_group_id:
                return
            
            if not event.message.is_reply:
                return
            
            forwarded_msg = await event.message.get_reply_message()
            if not forwarded_msg:
                return
            
            mapping = self.reply_mapping.get(str(forwarded_msg.id))
            if not mapping:
                return
            
            if mapping.get('type') == 'test':
                await event.reply("✅ Test successful! Auto-reply is working!")
                return
            
            if mapping.get('type') == 'reply':
                await self.client.send_message(
                    mapping['original_chat_id'],
                    f"**Reply from {event.sender.first_name}:**\n{event.message.text}",
                    reply_to=mapping['original_message_id']
                )
                await event.reply(f"✅ Reply sent back to original chat!")
                logger.info(f"Auto-replied to chat {mapping['original_chat_id']}")
            
        except Exception as e:
            logger.error(f"Error in auto-reply: {e}")
    
    async def reply_status(self):
        if not self.reply_group_id:
            await self.send_to_self("❌ Reply system not configured!")
            return
        
        try:
            entity = await self.client.get_entity(self.reply_group_id)
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            active = sum(1 for m in self.reply_mapping.values() if m.get('type') == 'reply')
            
            await self.send_to_self(f"""**Reply System Status**

✅ **Active**
📱 **Reply Group:** {group_name}
📊 **Active Mappings:** {active}

**How to use:**
1. Replies to your messages appear here
2. Reply to them to respond back
3. Test by replying to the welcome message""")
        except Exception as e:
            await self.send_to_self(f"❌ Error: {str(e)}")
    
    async def clear_mappings(self):
        self.reply_mapping = {}
        self.save_config()
        await self.send_to_self("✅ Cleared all reply mappings")
    
    def get_uptime(self):
        """Get bot uptime"""
        delta = datetime.now() - self.startup_time
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    async def show_status(self):
        active_mappings = sum(1 for m in self.reply_mapping.values() if m.get('type') == 'reply')
        
        status = f"""📊 **UserBot Status**

**Uptime:** {self.get_uptime()}

**Ad System:**
📝 Ads: {len(self.ads)}
⏱️ Interval: {self.interval_minutes} min
👥 Groups: {len(self.target_groups)}
🔄 Sending: {'✅ Active' if self.is_sending else '❌ Stopped'}

**Reply System:**
📨 Reply Group: {'✅ Set' if self.reply_group_id else '❌ Not set'}
🔄 Active Mappings: {active_mappings}

**Commands:**
.add <text> - Add ad
.remove <num> - Remove ad
.listads - List ads
.time <mins> - Set interval
.group <id> - Add group
.rmgroup <id> - Remove group
.listgroups - List groups
.start - Start sending
.stop - Stop sending
.setreplygroup <id> - Set reply group
.replystatus - Reply system status
.clearmappings - Clear mappings
.status - Show status
.help - Show help"""
        
        await self.send_to_self(status)
    
    # ============ COMMAND HANDLER ============
    async def handle_commands(self, event):
        msg = event.message.text.strip()
        if not msg.startswith('.'):
            return
        
        parts = msg.split(' ', 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ''
        
        commands = {
            '.add': lambda: self.add_ad(arg) if arg else self.send_to_self("Usage: .add <text>"),
            '.remove': lambda: self.remove_ad(int(arg)) if arg and arg.isdigit() else self.send_to_self("Usage: .remove <number>"),
            '.listads': self.list_ads,
            '.time': lambda: self.set_interval(arg) if arg else self.send_to_self("Usage: .time <minutes>"),
            '.group': lambda: self.add_group(arg) if arg else self.send_to_self("Usage: .group <id/username>"),
            '.rmgroup': lambda: self.remove_group(arg) if arg else self.send_to_self("Usage: .rmgroup <id/username>"),
            '.listgroups': self.list_groups,
            '.start': self.start_sending,
            '.stop': self.stop_sending,
            '.setreplygroup': lambda: self.set_reply_group(arg) if arg else self.send_to_self("Usage: .setreplygroup <id/username>"),
            '.replystatus': self.reply_status,
            '.clearmappings': self.clear_mappings,
            '.status': self.show_status,
            '.help': self.show_status,
        }
        
        if cmd in commands:
            try:
                result = commands[cmd]()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                await self.send_to_self(f"❌ Error: {str(e)}")
        else:
            await self.send_to_self(f"❌ Unknown command: {cmd}\nUse .help")

async def main():
    """Main function"""
    bot = SessionUserBot()
    
    # Setup and login with session string
    if not await bot.setup():
        return
    
    print("\n" + "="*50)
    print("✅ UserBot is running!")
    print("📝 Send commands in Saved Messages")
    print("💡 Type .help to see commands")
    print("="*50)
    
    # Register handlers
    @bot.client.on(events.NewMessage(from_users='me'))
    async def cmd_handler(event):
        await bot.handle_commands(event)
    
    @bot.client.on(events.NewMessage)
    async def reply_handler(event):
        await bot.forward_reply(event)
        await bot.auto_reply(event)
    
    try:
        await bot.client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping UserBot...")
        await bot.stop_sending()
        await bot.client.disconnect()
        print("✅ UserBot stopped!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nUserBot terminated by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
