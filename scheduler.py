from datetime import datetime
from main import main as run_price_update

if __name__ == "__main__":
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running price update...")
    try:
        run_price_update()
    except Exception as e:
        print(f"✗ Error during update: {e}")
