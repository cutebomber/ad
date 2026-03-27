# fixed_userbot.py
import asyncio
import logging
import json
import os
import random
from datetime import datetime

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FixedUserBot:
    def __init__(self):
        self.api_id = None
        self.api_hash = None
        self.phone = None
        self.client = None
        
        # Ad system
        self.ads = []
        self.target_groups = []
        self.interval_minutes = 5
        self.is_sending = False
        self.send_task = None
        
        # Reply system
        self.reply_group_id = None
        self.reply_mapping = {}  # Simple mapping: forwarded_msg_id -> original_info
        
        self.load_config()
    
    def load_config(self):
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
        print("\n" + "="*50)
        print("Telegram UserBot Setup")
        print("="*50)
        
        self.api_id = int(input("Enter API ID: ").strip())
        self.api_hash = input("Enter API Hash: ").strip()
        self.phone = input("Enter phone number (with +): ").strip()
        
        self.client = TelegramClient('userbot_session', self.api_id, self.api_hash)
        
        try:
            await self.client.start(phone=self.phone)
            me = await self.client.get_me()
            print(f"\n✅ Logged in as: {me.first_name}")
            await self.client.send_message('me', "🤖 UserBot is active!\nType .help for commands")
            return True
        except Exception as e:
            print(f"\n❌ Login failed: {e}")
            return False
    
    async def send_to_self(self, text):
        try:
            await self.client.send_message('me', text)
        except Exception as e:
            logger.error(f"Error: {e}")
    
    # ============ AD SYSTEM ============
    async def add_ad(self, text):
        self.ads.append(text)
        self.save_config()
        await self.send_to_self(f"✅ Added ad #{len(self.ads)}: {text[:50]}...")
    
    async def remove_ad(self, index):
        if 1 <= index <= len(self.ads):
            removed = self.ads.pop(index - 1)
            self.save_config()
            await self.send_to_self(f"✅ Removed ad #{index}: {removed[:50]}...")
        else:
            await self.send_to_self("❌ Invalid ad number!")
    
    async def list_ads(self):
        if not self.ads:
            await self.send_to_self("No ads added. Use .add <text>")
            return
        msg = "📝 Your Ads:\n\n"
        for i, ad in enumerate(self.ads, 1):
            msg += f"{i}. {ad}\n\n"
        await self.send_to_self(msg)
    
    async def set_interval(self, minutes):
        try:
            minutes = int(minutes)
            if minutes < 1:
                await self.send_to_self("Interval must be at least 1 minute!")
                return
            self.interval_minutes = minutes
            self.save_config()
            await self.send_to_self(f"✅ Interval set to {minutes} minute(s)")
        except ValueError:
            await self.send_to_self("Please enter a valid number!")
    
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
            await self.send_to_self("No target groups added. Use .group <id/username>")
            return
        msg = "📝 Target Groups:\n\n"
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
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    async def send_loop(self):
        ad_index = 0
        while self.is_sending:
            try:
                if not self.ads or not self.target_groups:
                    await asyncio.sleep(60)
                    continue
                
                current_ad = self.ads[ad_index % len(self.ads)]
                ad_index += 1
                
                for group_id in self.target_groups:
                    if not self.is_sending:
                        break
                    await self.send_ad(group_id, current_ad)
                    await asyncio.sleep(random.uniform(5, 10))
                
                await asyncio.sleep(self.interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Error in send loop: {e}")
                await asyncio.sleep(60)
    
    async def start_sending(self):
        if self.is_sending:
            await self.send_to_self("Already sending!")
            return
        if not self.ads:
            await self.send_to_self("No ads added!")
            return
        if not self.target_groups:
            await self.send_to_self("No target groups!")
            return
        
        self.is_sending = True
        self.send_task = asyncio.create_task(self.send_loop())
        await self.send_to_self(f"✅ Started sending every {self.interval_minutes} minute(s)")
    
    async def stop_sending(self):
        if self.send_task:
            self.is_sending = False
            self.send_task.cancel()
            try:
                await self.send_task
            except:
                pass
            self.send_task = None
            await self.send_to_self("⏹️ Stopped sending")
    
    # ============ FIXED REPLY SYSTEM ============
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
                "Reply to this message to test the auto-reply system.\n"
                "Your reply will be sent back here as a test."
            )
            
            # Store test mapping
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
            
            # Check if this is a reply
            if not event.message.is_reply:
                return
            
            # Get original message
            original = await event.message.get_reply_message()
            if not original:
                return
            
            # Only forward if original message was sent by us
            if not original.out:
                return
            
            # Get chat info
            chat = await event.get_chat()
            chat_name = getattr(chat, 'title', None) or getattr(chat, 'first_name', 'Unknown')
            
            # Create forward message
            forward_text = f"""**📨 New Reply**

**From:** {event.sender.first_name}
**In:** {chat_name}
**Replied to:** {original.text[:150]}

**Reply:** {event.message.text}

---
💡 Reply to this message to respond back!"""
            
            # Send to reply group
            sent = await self.client.send_message(self.reply_group_id, forward_text)
            
            # Store mapping with original info
            self.reply_mapping[str(sent.id)] = {
                'type': 'reply',
                'original_chat_id': chat.id,
                'original_message_id': original.id,
                'original_text': original.text[:100],
                'reply_sender': event.sender.first_name
            }
            self.save_config()
            
            logger.info(f"Forwarded reply from {chat_name} - Mapping ID: {sent.id}")
            
        except Exception as e:
            logger.error(f"Error forwarding reply: {e}")
    
    async def auto_reply(self, event):
        """Handle replies in the reply group and send back to original"""
        try:
            # Check if message is in reply group
            if not self.reply_group_id or event.chat_id != self.reply_group_id:
                return
            
            # Check if it's a reply
            if not event.message.is_reply:
                return
            
            # Get the message they're replying to (our forwarded message)
            forwarded_msg = await event.message.get_reply_message()
            if not forwarded_msg:
                return
            
            # Look up mapping
            mapping_key = str(forwarded_msg.id)
            
            if mapping_key not in self.reply_mapping:
                logger.info(f"No mapping found for ID: {mapping_key}")
                return
            
            mapping = self.reply_mapping[mapping_key]
            
            # Handle test message
            if mapping.get('type') == 'test':
                await event.reply("✅ Test successful! Your auto-reply system is working!\n\nReal replies will be sent to the original chat.")
                return
            
            # Send reply to original chat
            if mapping.get('type') == 'reply':
                original_chat_id = mapping['original_chat_id']
                original_msg_id = mapping['original_message_id']
                
                reply_text = f"**Reply from {event.sender.first_name}:**\n{event.message.text}"
                
                # Send to original chat
                await self.client.send_message(
                    original_chat_id,
                    reply_text,
                    reply_to=original_msg_id
                )
                
                # Confirm in reply group
                await event.reply(f"✅ Reply sent back to original chat!\n\nYour reply: {event.message.text[:100]}")
                
                logger.info(f"Auto-replied to chat {original_chat_id}")
                
                # Optional: Remove mapping after use
                # del self.reply_mapping[mapping_key]
                # self.save_config()
            
        except Exception as e:
            logger.error(f"Error in auto-reply: {e}")
            try:
                await event.reply(f"❌ Error: {str(e)}")
            except:
                pass
    
    async def reply_status(self):
        if not self.reply_group_id:
            await self.send_to_self("Reply system not configured! Use .setreplygroup <id/username>")
            return
        
        try:
            entity = await self.client.get_entity(self.reply_group_id)
            group_name = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
            
            # Count active mappings
            active = sum(1 for m in self.reply_mapping.values() if m.get('type') == 'reply')
            
            status = f"""**Reply System Status**

✅ **Active**
📱 **Reply Group:** {group_name}
📊 **Active Mappings:** {active}

**How to use:**
1. When someone replies to your messages, it appears here
2. Reply to that message to respond back
3. Your reply will be sent to the original chat

**Test it:**
• Check your reply group for the test message
• Reply to it to test the system"""
            
            await self.send_to_self(status)
        except Exception as e:
            await self.send_to_self(f"Error: {str(e)}")
    
    async def clear_mappings(self):
        self.reply_mapping = {}
        self.save_config()
        await self.send_to_self("✅ Cleared all reply mappings")
    
    async def show_status(self):
        active_mappings = sum(1 for m in self.reply_mapping.values() if m.get('type') == 'reply')
        
        status = f"""📊 **UserBot Status**

**Ad System:**
📝 Ads: {len(self.ads)}
⏱️ Interval: {self.interval_minutes} min
👥 Groups: {len(self.target_groups)}
🔄 Sending: {'✅' if self.is_sending else '❌'}

**Reply System:**
📨 Reply Group: {'✅' if self.reply_group_id else '❌'}
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
        
        if cmd == '.add':
            if arg:
                await self.add_ad(arg)
            else:
                await self.send_to_self("Usage: .add <text>")
        
        elif cmd == '.remove':
            if arg and arg.isdigit():
                await self.remove_ad(int(arg))
            else:
                await self.send_to_self("Usage: .remove <number>")
        
        elif cmd == '.listads':
            await self.list_ads()
        
        elif cmd == '.time':
            if arg:
                await self.set_interval(arg)
            else:
                await self.send_to_self("Usage: .time <minutes>")
        
        elif cmd == '.group':
            if arg:
                await self.add_group(arg)
            else:
                await self.send_to_self("Usage: .group <id/username>")
        
        elif cmd == '.rmgroup':
            if arg:
                await self.remove_group(arg)
            else:
                await self.send_to_self("Usage: .rmgroup <id/username>")
        
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
                await self.send_to_self("Usage: .setreplygroup <id/username>")
        
        elif cmd == '.replystatus':
            await self.reply_status()
        
        elif cmd == '.clearmappings':
            await self.clear_mappings()
        
        elif cmd == '.status':
            await self.show_status()
        
        elif cmd == '.help':
            await self.show_status()
        
        else:
            await self.send_to_self(f"Unknown command: {cmd}\nUse .help")

async def main():
    bot = FixedUserBot()
    
    if not await bot.setup():
        print("Setup failed!")
        return
    
    print("\n✅ UserBot is running!")
    print("Send commands in Saved Messages")
    
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
        print("\nStopping...")
        await bot.stop_sending()
        print("Stopped!")

if __name__ == "__main__":
    asyncio.run(main())
