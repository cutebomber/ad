import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional
import random
import json
import os

from telethon import TelegramClient, events, errors
from telethon.tl.types import Message, InputPeerUser, InputPeerChat
from telethon.tl.functions.messages import SendMessageRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramPromotionBot:
    def __init__(self, api_id: int, api_hash: str, phone_number: str):
        """
        Initialize Telegram promotion bot
        
        Args:
            api_id: Your Telegram API ID (from my.telegram.org)
            api_hash: Your Telegram API Hash
            phone_number: Your phone number with country code
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.client = TelegramClient('session', api_id, api_hash)
        
        # Configuration
        self.messages = []
        self.target_groups = []
        self.schedule = {}
        self.is_running = False
        self.message_history = []
        
        # Load saved config if exists
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    self.messages = config.get('messages', [])
                    self.target_groups = config.get('target_groups', [])
                    self.schedule = config.get('schedule', {})
            except Exception as e:
                logger.error(f"Error loading config: {e}")
    
    def save_config(self):
        """Save configuration to file"""
        config = {
            'messages': self.messages,
            'target_groups': self.target_groups,
            'schedule': self.schedule
        }
        try:
            with open('config.json', 'w') as f:
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
    
    async def get_groups(self) -> List[Dict]:
        """Get list of groups the user is a member of"""
        groups = []
        try:
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group:
                    groups.append({
                        'id': dialog.id,
                        'name': dialog.name,
                        'title': dialog.title,
                        'entity': dialog.entity
                    })
            logger.info(f"Found {len(groups)} groups")
            return groups
        except Exception as e:
            logger.error(f"Error fetching groups: {e}")
            return []
    
    async def add_message(self, message: str, delay_seconds: int = 0):
        """Add a message to the promotion queue"""
        self.messages.append({
            'text': message,
            'delay': delay_seconds,
            'created_at': datetime.now().isoformat()
        })
        self.save_config()
        logger.info(f"Added message: {message[:50]}...")
    
    async def add_target_group(self, group_id: int, interval_minutes: int):
        """Add a target group with sending interval"""
        self.target_groups.append({
            'group_id': group_id,
            'interval_minutes': interval_minutes,
            'last_sent': None,
            'message_index': 0
        })
        self.save_config()
        logger.info(f"Added target group ID: {group_id} with interval {interval_minutes} minutes")
    
    async def send_message_to_group(self, group_id: int, message: str):
        """Send a message to a specific group"""
        try:
            # Add random delay to avoid patterns (5-15 seconds)
            await asyncio.sleep(random.uniform(2, 8))
            
            await self.client.send_message(group_id, message)
            logger.info(f"Message sent to group {group_id}: {message[:50]}...")
            
            # Record in history
            self.message_history.append({
                'group_id': group_id,
                'message': message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Keep only last 1000 messages in history
            if len(self.message_history) > 1000:
                self.message_history = self.message_history[-1000:]
                
            return True
        except errors.FloodWaitError as e:
            logger.warning(f"Flood wait error: Need to wait {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
            return False
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    async def process_scheduled_messages(self):
        """Process and send scheduled messages"""
        while self.is_running:
            try:
                current_time = datetime.now()
                
                for group in self.target_groups:
                    group_id = group['group_id']
                    interval = group['interval_minutes']
                    last_sent = group.get('last_sent')
                    
                    # Check if it's time to send
                    should_send = False
                    if last_sent is None:
                        should_send = True
                    else:
                        time_diff = (current_time - datetime.fromisoformat(last_sent)).total_seconds() / 60
                        if time_diff >= interval:
                            should_send = True
                    
                    if should_send and self.messages:
                        # Rotate through messages
                        message_index = group.get('message_index', 0) % len(self.messages)
                        message = self.messages[message_index]['text']
                        
                        # Send message
                        success = await self.send_message_to_group(group_id, message)
                        
                        if success:
                            group['last_sent'] = current_time.isoformat()
                            group['message_index'] = message_index + 1
                            self.save_config()
                            
                            # Random delay between messages to groups (30-90 seconds)
                            await asyncio.sleep(random.uniform(30, 90))
                
                # Check every 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                await asyncio.sleep(60)
    
    async def start_promotion(self):
        """Start the promotion bot"""
        if not self.target_groups:
            logger.warning("No target groups configured. Please add groups first.")
            return
        
        if not self.messages:
            logger.warning("No messages configured. Please add messages first.")
            return
        
        self.is_running = True
        logger.info("Starting promotion bot...")
        await self.process_scheduled_messages()
    
    def stop_promotion(self):
        """Stop the promotion bot"""
        self.is_running = False
        logger.info("Stopping promotion bot...")
    
    async def delete_all_messages(self):
        """Clear all messages from queue"""
        self.messages = []
        self.save_config()
        logger.info("All messages cleared")
    
    async def remove_group(self, group_id: int):
        """Remove a target group"""
        self.target_groups = [g for g in self.target_groups if g['group_id'] != group_id]
        self.save_config()
        logger.info(f"Removed group {group_id}")
    
    async def show_stats(self):
        """Show bot statistics"""
        stats = {
            'total_messages': len(self.messages),
            'total_groups': len(self.target_groups),
            'messages_sent': len(self.message_history),
            'is_running': self.is_running,
            'recent_messages': self.message_history[-5:] if self.message_history else []
        }
        return stats
    
    async def test_connection(self):
        """Test connection and send test message to saved messages"""
        try:
            await self.client.send_message('me', "Bot is working! 🚀")
            logger.info("Test message sent to Saved Messages")
            return True
        except Exception as e:
            logger.error(f"Test failed: {e}")
            return False

# Interactive CLI for the bot
async def interactive_mode():
    """Interactive command-line interface for bot management"""
    print("=" * 50)
    print("Telegram Promotion Bot - Setup")
    print("=" * 50)
    
    # Get credentials
    api_id = input("Enter your API ID (from my.telegram.org): ")
    api_hash = input("Enter your API Hash: ")
    phone_number = input("Enter your phone number (with country code, e.g., +1234567890): ")
    
    # Create bot instance
    bot = TelegramPromotionBot(int(api_id), api_hash, phone_number)
    
    # Login
    if not await bot.login():
        print("Login failed! Exiting...")
        return
    
    print("\n✅ Login successful!")
    
    while True:
        print("\n" + "=" * 50)
        print("Telegram Promotion Bot - Menu")
        print("=" * 50)
        print("1. 📝 Add promotion message")
        print("2. 👥 Add target group")
        print("3. 📋 List groups")
        print("4. 🚀 Start promotion")
        print("5. ⏹️ Stop promotion")
        print("6. 📊 Show statistics")
        print("7. 🗑️ Delete all messages")
        print("8. ❌ Remove group")
        print("9. 🔍 Test connection")
        print("10. 💾 Save configuration")
        print("11. 🚪 Exit")
        
        choice = input("\nEnter your choice (1-11): ")
        
        if choice == '1':
            message = input("Enter your promotion message: ")
            delay = input("Enter delay in seconds before sending (0 for immediate): ")
            delay = int(delay) if delay.isdigit() else 0
            await bot.add_message(message, delay)
            print("✅ Message added!")
            
        elif choice == '2':
            groups = await bot.get_groups()
            if groups:
                print("\nAvailable groups:")
                for idx, group in enumerate(groups, 1):
                    print(f"{idx}. {group['name']} (ID: {group['id']})")
                
                group_choice = input("\nSelect group number or enter ID: ")
                if group_choice.isdigit() and 1 <= int(group_choice) <= len(groups):
                    group_id = groups[int(group_choice)-1]['id']
                else:
                    group_id = int(group_choice)
                
                interval = input("Enter interval in minutes between messages: ")
                interval = int(interval) if interval.isdigit() else 60
                
                await bot.add_target_group(group_id, interval)
                print("✅ Group added!")
            else:
                print("No groups found!")
                
        elif choice == '3':
            groups = await bot.get_groups()
            if groups:
                print("\nYour groups:")
                for group in groups:
                    print(f"📱 {group['name']} (ID: {group['id']})")
            else:
                print("No groups found!")
                
        elif choice == '4':
            print("Starting promotion... (Press Ctrl+C to stop)")
            try:
                await bot.start_promotion()
            except KeyboardInterrupt:
                bot.stop_promotion()
                print("\nPromotion stopped!")
                
        elif choice == '5':
            bot.stop_promotion()
            print("Promotion stopped!")
            
        elif choice == '6':
            stats = await bot.show_stats()
            print("\n📊 Statistics:")
            print(f"Messages configured: {stats['total_messages']}")
            print(f"Target groups: {stats['total_groups']}")
            print(f"Total messages sent: {stats['messages_sent']}")
            print(f"Bot running: {stats['is_running']}")
            
        elif choice == '7':
            confirm = input("Are you sure? This will delete all messages! (yes/no): ")
            if confirm.lower() == 'yes':
                await bot.delete_all_messages()
                print("All messages deleted!")
                
        elif choice == '8':
            group_id = input("Enter group ID to remove: ")
            if group_id.isdigit():
                await bot.remove_group(int(group_id))
                print("Group removed!")
            else:
                print("Invalid group ID!")
                
        elif choice == '9':
            if await bot.test_connection():
                print("✅ Connection successful! Check your Saved Messages.")
            else:
                print("❌ Connection failed!")
                
        elif choice == '10':
            bot.save_config()
            print("Configuration saved!")
            
        elif choice == '11':
            bot.stop_promotion()
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice!")

# Main execution
if __name__ == "__main__":
    try:
        asyncio.run(interactive_mode())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error: {e}")
