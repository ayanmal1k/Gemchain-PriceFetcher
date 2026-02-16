import os
import requests
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# DexScreener API endpoints
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

# Rate limiting configuration
BATCH_SIZE = 10  # Number of tokens to process before batch delay
BATCH_DELAY = 2  # Seconds to wait between batches
REQUEST_DELAY = 0.1  # Seconds to wait between individual requests within a batch

def fetch_tokens_from_supabase():
    """
    Fetch tokens from the Supabase table with filters:
    - status = 'approved'
    - token_token = 'launched' or 'presale'
    - contract_address is populated
    """
    try:
        response = supabase.table("tokens").select("*").execute()
        tokens = response.data
        
        # Filter tokens by:
        # 1. Has contract address
        # 2. Status is 'approved'
        # 3. token_token is either 'launched' or 'presale'
        filtered_tokens = [
            t for t in tokens 
            if t.get("contract_address") 
            and t.get("status") == "approved"
            and t.get("token_type") in ("launched", "presale")
        ]
        
        print(f"✓ Fetched {len(filtered_tokens)} approved tokens (launched/presale) with contract addresses from Supabase")
        if len(filtered_tokens) < len(tokens):
            print(f"  (Filtered from {len(tokens)} total tokens)")
        return filtered_tokens
    except Exception as e:
        print(f"✗ Error fetching tokens from Supabase: {e}")
        return []

def fetch_price_data_from_dexscreener(contract_address, chain):
    """
    Fetch price data from DexScreener for a given token.
    
    Args:
        contract_address: Token contract address
        chain: Blockchain chain (ethereum, bsc, polygon, etc.)
    
    Returns:
        Dictionary with price_1h_change and price_24h_change and current_price
    """
    try:
        # DexScreener endpoint format
        url = f"{DEXSCREENER_API}/tokens/{contract_address}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("pairs") and len(data["pairs"]) > 0:
            pair = data["pairs"][0]
            
            price_1h_change = pair.get("priceChange", {}).get("h1")
            price_24h_change = pair.get("priceChange", {}).get("h24")
            # Keep priceUsd as string to preserve precision for very small decimals
            # e.g., 0.00000008369 instead of converting to float and losing precision
            current_price = pair.get("priceUsd")
            
            # Only convert to float if we need to validate it's a valid number
            if current_price:
                try:
                    float(current_price)  # Validate it's a valid number
                except (ValueError, TypeError):
                    current_price = None
            
            return {
                "price_1h_change": price_1h_change,
                "price_24h_change": price_24h_change,
                "current_price": current_price
            }
        else:
            print(f"  ⚠ No price data found for {contract_address}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error fetching DexScreener data for {contract_address}: {e}")
        return None

def update_token_in_supabase(token_id, price_data):
    """
    Update token price information in Supabase.
    
    Args:
        token_id: Token ID in the database
        price_data: Dictionary containing price_1h_change and price_24h_change
    """
    try:
        update_payload = {
            "price_1h_change": price_data.get("price_1h_change"),
            "price_24h_change": price_data.get("price_24h_change"),
            "current_price": price_data.get("current_price"),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("tokens").update(update_payload).eq("id", token_id).execute()
        return True
        
    except Exception as e:
        print(f"  ✗ Error updating token {token_id} in Supabase: {e}")
        return False

def process_tokens_in_batches(tokens):
    """
    Process tokens in batches to respect API rate limits.
    
    Args:
        tokens: List of tokens to process
    
    Returns:
        Tuple of (successful_updates, failed_updates)
    """
    successful_updates = 0
    failed_updates = 0
    total_tokens = len(tokens)
    
    # Process tokens in batches
    for batch_num, i in enumerate(range(0, total_tokens, BATCH_SIZE), 1):
        batch = tokens[i:i + BATCH_SIZE]
        batch_end = min(i + BATCH_SIZE, total_tokens)
        
        print(f"\n  [Batch {batch_num}] Processing tokens {i + 1}-{batch_end} of {total_tokens}")
        
        for idx, token in enumerate(batch, 1):
            token_id = token.get("id")
            contract_address = token.get("contract_address")
            chain = token.get("chain", "ethereum")
            name = token.get("name", "Unknown")
            
            global_idx = i + idx
            print(f"    [{global_idx}/{total_tokens}] {name} ({contract_address})")
            
            # Fetch price data from DexScreener
            price_data = fetch_price_data_from_dexscreener(contract_address, chain)
            
            if price_data:
                # Update token in Supabase
                if update_token_in_supabase(token_id, price_data):
                    print(f"      ✓ Updated: 1h={price_data['price_1h_change']}%, 24h={price_data['price_24h_change']}%")
                    successful_updates += 1
                else:
                    failed_updates += 1
            else:
                failed_updates += 1
            
            # Add delay between individual requests (except for the last request)
            if idx < len(batch):
                time.sleep(REQUEST_DELAY)
        
        # Add delay between batches (except for the last batch)
        if batch_end < total_tokens:
            print(f"  ⏳ Batch delay: waiting {BATCH_DELAY} seconds before next batch...")
            time.sleep(BATCH_DELAY)
    
    return successful_updates, failed_updates

def main():
    """Main function to orchestrate token price updates."""
    print("\n" + "="*60)
    print("TOKEN PRICE UPDATER - DexScreener & Supabase Integration")
    print("="*60)
    print(f"Rate Limiting Configuration:")
    print(f"  - Batch Size: {BATCH_SIZE} tokens")
    print(f"  - Batch Delay: {BATCH_DELAY}s")
    print(f"  - Request Delay: {REQUEST_DELAY}s")
    
    # Step 1: Fetch tokens from Supabase
    print("\n[1/3] Fetching tokens from Supabase...")
    tokens = fetch_tokens_from_supabase()
    
    if not tokens:
        print("✗ No tokens found. Exiting.")
        return
    
    # Step 2: Fetch price data from DexScreener and update in batches
    print(f"\n[2/3] Fetching price data from DexScreener for {len(tokens)} tokens (in batches)...")
    
    successful_updates, failed_updates = process_tokens_in_batches(tokens)
    
    # Step 3: Summary
    print("\n" + "="*60)
    print(f"[3/3] Update Complete!")
    print(f"  ✓ Successful: {successful_updates}/{len(tokens)}")
    print(f"  ✗ Failed: {failed_updates}/{len(tokens)}")
    print(f"  Updated at: {datetime.utcnow().isoformat()}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
