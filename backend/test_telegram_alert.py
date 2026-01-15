
import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we can import app modules
sys.path.append(os.getcwd())
load_dotenv(override=True)

from app.services.alert_engine import get_alert_engine, AlertEngine, AlertType

async def test_alert():
    print("🚀 Initializing Alert Engine Test...")
    
    engine = get_alert_engine()
    
    if not engine.enabled:
        print("❌ Alert Engine is DISABLED. Check your .env config.")
        print(f"Token present: {bool(engine.token)}")
        print(f"Chat ID present: {bool(engine.chat_id)}")
        return

    print(f"📤 Sending test alert to Chat ID: {engine.chat_id}")
    
    # 1. Create a sample SPRING alert (Most exciting template)
    alert = AlertEngine.create_spring_alert(
        symbol="BBCA.JK",
        support_level=9800,
        current_price=9850,
        top_buyer="KZ (CLSA Indonesia)",
        buy_value=150_000_000_000  # 150 Miliar
    )
    
    # 2. Add specific test title to distinguish
    alert.title = "[TEST] " + alert.title
    
    # 3. Send
    success = await engine.send_alert(alert)
    
    if success:
        print("\n✅ SENT! Check your Telegram Group 'Testbot' now.")
        print("You should see a message with:")
        print("---------------------------------------------------")
        print(f"🔥 SPRING - BBCA.JK")
        print(f"📢 [TEST] Wyckoff Spring Detected!")
        print(f"...")
        print("---------------------------------------------------")
    else:
        print("\n❌ FAILED to send alert.")
        print("Possible reasons:")
        print("1. Bot is not Admin in the group")
        print("2. Chat ID is incorrect")
        print("3. Internet connection issue")

if __name__ == "__main__":
    asyncio.run(test_alert())
