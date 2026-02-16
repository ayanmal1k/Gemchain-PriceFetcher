import time
import schedule
from datetime import datetime
from main import main as run_price_update
from config import UPDATE_INTERVAL_SECONDS

def job():
    """Job to run the price update process."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running scheduled price update...")
    try:
        run_price_update()
    except Exception as e:
        print(f"✗ Error during scheduled update: {e}")

def start_scheduler():
    """Start the scheduler to run price updates at regular intervals."""
    print("\n" + "="*60)
    print("TOKEN PRICE SCHEDULER - Starting")
    print("="*60)
    print(f"Update interval: {UPDATE_INTERVAL_SECONDS} seconds")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Schedule the job
    schedule.every(UPDATE_INTERVAL_SECONDS).seconds.do(job)
    
    # Run the scheduler
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n✓ Scheduler stopped by user")
            break
        except Exception as e:
            print(f"✗ Scheduler error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    start_scheduler()
