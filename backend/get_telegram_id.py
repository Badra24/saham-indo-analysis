
import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv

# Force load .env
load_dotenv(override=True)

async def find_group_id():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    print(f"🤖 Connecting to bot with token: {token[:5]}...{token[-5:]}")
    bot = Bot(token=token)
    
    try:
        # Get updates (messages sent to bot)
        updates = await bot.get_updates()
        
        print(f"📥 Found {len(updates)} updates.")
        
        found_groups = []
        
        for u in updates:
            # Check for channel post or message
            msg = u.effective_message
            if not msg:
                continue
                
            chat = msg.chat
            if chat.type in ['group', 'supergroup']:
                print(f"✅ FOUND GROUP: {chat.title} | ID: {chat.id}")
                found_groups.append(f"TELEGRAM_CHAT_ID={chat.id}")
            elif chat.type == 'private':
                print(f"ℹ️ Private Chat: {chat.first_name} | ID: {chat.id}")

        if found_groups:
            print("\n🎯 COPY THIS TO YOUR .env FILE:")
            print("--------------------------------")
            for line in set(found_groups):
                print(line)
            print("--------------------------------")
        else:
            print("\n⚠️ No group messages found yet.")
            print("👉 TIP: Send a message like '/start' or 'hello' inside your Group now, then run this script again!")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(find_group_id())
