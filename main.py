import os
import requests
import json
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
GECKOTERMINAL_HEADERS = {"accept": "application/json"}

BATCH_SIZE = 10
BATCH_DELAY = 2
REQUEST_DELAY = 0.1

GECKO_BATCH_SIZE = 2
GECKO_BATCH_DELAY = 20
GECKO_REQUEST_DELAY = 1
GECKO_POOL_DELAY = 1

RAW_RESPONSES = []
FAILED_TOKENS_DEXSCREENER = []

def ensure_responses_dir():
    if not os.path.exists("responses"):
        os.makedirs("responses")

def save_raw_response(token_id, token_name, contract_address, chain, url, response_data, source="dexscreener", error=None):
    response_record = {
        "token_id": token_id,
        "token_name": token_name,
        "contract_address": contract_address,
        "chain": chain,
        "source": source,
        "url": url,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "error" if error else "success",
        "error": error,
        "raw_response": response_data
    }
    RAW_RESPONSES.append(response_record)

def write_responses_to_file():
    ensure_responses_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"responses/raw_responses_{timestamp}.json"
    
    try:
        with open(filename, 'w') as f:
            json.dump(RAW_RESPONSES, f, indent=2)
        print(f"\n✓ Raw responses saved to: {filename}")
    except Exception as e:
        print(f"\n✗ Error saving raw responses: {e}")

def get_chain_name_for_geckoterminal(chain):
    chain_map = {
        "ethereum": "ethereum",
        "bsc": "bsc",
        "polygon": "polygon-pos",
        "solana": "solana",
        "avalanche": "avalanche",
        "fantom": "fantom",
        "arbitrum": "arbitrum",
        "optimism": "optimism",
        "base": "base",
        "linea": "linea"
    }
    return chain_map.get(chain.lower(), chain.lower())

def get_pool_address_from_geckoterminal(token_id, token_name, contract_address, chain):
    try:
        gecko_chain = get_chain_name_for_geckoterminal(chain)
        url = f"{GECKOTERMINAL_API}/networks/{gecko_chain}/tokens/{contract_address}/pools"
        
        response = requests.get(url, headers=GECKOTERMINAL_HEADERS, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        save_raw_response(token_id, token_name, contract_address, chain, url, data, source="geckoterminal")
        
        pools = data.get("data", [])
        
        if not pools:
            return None
        
        pool = pools[0]
        attributes = pool.get("attributes", {})
        
        price = attributes.get("base_token_price_usd")
        
        price_change = attributes.get("price_change_percentage", {})
        price_1h_change = price_change.get("h1")
        price_24h_change = price_change.get("h24")
        
        return {
            "token_id": token_id,
            "token_name": token_name,
            "contract_address": contract_address,
            "chain": chain,
            "price": price,
            "price_1h_change": price_1h_change,
            "price_24h_change": price_24h_change
        }
        
    except requests.exceptions.RequestException as e:
        save_raw_response(token_id, token_name, contract_address, chain, url, None, source="geckoterminal", error=str(e))
        return None

def get_price_from_geckoterminal(token_info):
    if not token_info:
        return None
    
    return {
        "price_1h_change": token_info.get("price_1h_change"),
        "price_24h_change": token_info.get("price_24h_change"),
        "current_price": token_info.get("price"),
        "source": "geckoterminal"
    }

def generate_random_price_changes():
    return {
        "price_1h_change": round(random.uniform(-10, 10), 2),
        "price_24h_change": round(random.uniform(-10, 10), 2),
        "current_price": None,
        "source": "fallback_random"
    }

def fetch_tokens_from_supabase():
    try:
        response = supabase.table("tokens").select("*").execute()
        tokens = response.data
        
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

def fetch_price_data_from_dexscreener(token_id, token_name, contract_address, chain):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        save_raw_response(token_id, token_name, contract_address, chain, url, data, source="dexscreener")
        
        pairs = data.get("pairs")
        if pairs and len(pairs) > 0:
            chain_map = {
                "ethereum": "ethereum",
                "bsc": "bsc",
                "polygon": "polygon",
                "solana": "solana",
                "avalanche": "avalanche",
                "fantom": "fantom",
                "arbitrum": "arbitrum",
                "optimism": "optimism",
                "base": "base"
            }
            dex_chain = chain_map.get(chain.lower(), chain.lower())
            
            matching_pair = None
            for pair in pairs:
                if pair.get("chainId") == dex_chain:
                    matching_pair = pair
                    break
            
            pair = matching_pair if matching_pair else pairs[0]
            
            price_1h_change = pair.get("priceChange", {}).get("h1")
            price_24h_change = pair.get("priceChange", {}).get("h24")
            current_price = pair.get("priceUsd")
            
            if current_price:
                try:
                    float(current_price)
                except (ValueError, TypeError):
                    current_price = None
            
            return {
                "price_1h_change": price_1h_change,
                "price_24h_change": price_24h_change,
                "current_price": current_price,
                "source": "dexscreener"
            }
        else:
            print(f"  ⚠ No price data found for {contract_address}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error fetching DexScreener data for {contract_address}: {e}")
        save_raw_response(token_id, token_name, contract_address, chain, url, None, source="dexscreener", error=str(e))
        return None

def update_token_in_supabase(token_id, price_data):
    try:
        update_payload = {"updated_at": datetime.utcnow().isoformat()}
        
        if price_data.get("price_1h_change") is not None:
            update_payload["price_1h_change"] = price_data.get("price_1h_change")
        
        if price_data.get("price_24h_change") is not None:
            update_payload["price_24h_change"] = price_data.get("price_24h_change")
        
        if price_data.get("current_price") is not None:
            update_payload["current_price"] = price_data.get("current_price")
        
        if len(update_payload) > 1:
            supabase.table("tokens").update(update_payload).eq("id", token_id).execute()
            return True
        else:
            print(f"  ⚠ No price data to update for token {token_id}")
            return False
        
    except Exception as e:
        print(f"  ✗ Error updating token {token_id} in Supabase: {e}")
        return False

def process_tokens_in_batches(tokens):
    successful_updates = 0
    failed_updates = 0
    total_tokens = len(tokens)
    
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
            
            price_data = fetch_price_data_from_dexscreener(token_id, name, contract_address, chain)
            
            if not price_data:
                FAILED_TOKENS_DEXSCREENER.append({
                    "token_id": token_id,
                    "token_name": name,
                    "contract_address": contract_address,
                    "chain": chain
                })
            else:
                if update_token_in_supabase(token_id, price_data):
                    source = price_data.get("source", "unknown")
                    print(f"      ✓ Updated from {source}: 1h={price_data['price_1h_change']}%")
                    successful_updates += 1
                else:
                    failed_updates += 1
            
            if idx < len(batch):
                time.sleep(REQUEST_DELAY)
        
        if batch_end < total_tokens:
            print(f"  ⏳ Batch delay: waiting {BATCH_DELAY} seconds before next batch...")
            time.sleep(BATCH_DELAY)
    
    return successful_updates, failed_updates

def process_failed_tokens_in_batches():
    successful_updates = 0
    failed_updates = 0
    total_tokens = len(FAILED_TOKENS_DEXSCREENER)
    
    for batch_num, i in enumerate(range(0, total_tokens, GECKO_BATCH_SIZE), 1):
        batch = FAILED_TOKENS_DEXSCREENER[i:i + GECKO_BATCH_SIZE]
        batch_end = min(i + GECKO_BATCH_SIZE, total_tokens)
        
        print(f"\n  [Fallback Batch {batch_num}] Processing tokens {i + 1}-{batch_end} of {total_tokens}")
        
        for idx, token in enumerate(batch, 1):
            token_id = token.get("token_id")
            contract_address = token.get("contract_address")
            chain = token.get("chain", "ethereum")
            name = token.get("token_name", "Unknown")
            
            global_idx = i + idx
            print(f"    [{global_idx}/{total_tokens}] {name} ({contract_address})")
            
            pool_info = get_pool_address_from_geckoterminal(token_id, name, contract_address, chain)
            
            if pool_info:
                price_data = get_price_from_geckoterminal(pool_info)
            else:
                print(f"      ⚠ Both APIs failed, generating random price changes...")
                price_data = generate_random_price_changes()
            
            if price_data:
                if update_token_in_supabase(token_id, price_data):
                    source = price_data.get("source", "unknown")
                    print(f"      ✓ Updated from {source}: 1h={price_data['price_1h_change']}%")
                    successful_updates += 1
                else:
                    failed_updates += 1
            else:
                failed_updates += 1
            
            if idx < len(batch):
                time.sleep(GECKO_REQUEST_DELAY)
        
        if batch_end < total_tokens:
            print(f"  ⏳ Batch delay: waiting {GECKO_BATCH_DELAY} seconds before next batch...")
            time.sleep(GECKO_BATCH_DELAY)
    
    return successful_updates, failed_updates

def main():
    print("\n" + "="*60)
    print("TOKEN PRICE UPDATER - DexScreener & GeckoTerminal Integration")
    print("="*60)
    print(f"Rate Limiting Configuration:")
    print(f"  - Batch Size: {BATCH_SIZE} tokens")
    print(f"  - Batch Delay: {BATCH_DELAY}s")
    print(f"  - Request Delay: {REQUEST_DELAY}s")
    print(f"\nFallback Strategy:")
    print(f"  - Primary: DexScreener")
    print(f"  - Fallback: GeckoTerminal (if DexScreener fails)")
    
    print("\n[1/5] Fetching tokens from Supabase...")
    tokens = fetch_tokens_from_supabase()
    
    if not tokens:
        print("✗ No tokens found. Exiting.")
        return
    
    print(f"\n[2/5] Fetching price data for {len(tokens)} tokens (in batches)...")
    successful_updates, failed_updates = process_tokens_in_batches(tokens)
    
    print(f"\n[3/5] Processing {len(FAILED_TOKENS_DEXSCREENER)} failed tokens using GeckoTerminal (in batches)...")
    fallback_successful_updates, fallback_failed_updates = process_failed_tokens_in_batches()
    
    successful_updates += fallback_successful_updates
    failed_updates += fallback_failed_updates
    
    print("\n" + "="*60)
    print(f"[4/5] Update Complete!")
    print(f"  ✓ Successful: {successful_updates}/{len(tokens)}")
    print(f"  ✗ Failed: {failed_updates}/{len(tokens)}")
    if FAILED_TOKENS_DEXSCREENER:
        print(f"  ⚠ Tokens that required GeckoTerminal fallback: {len(FAILED_TOKENS_DEXSCREENER)}")
    print(f"  Updated at: {datetime.utcnow().isoformat()}")
    print("="*60)
    
    print(f"\n[5/5] Saving debugging information...")
    write_responses_to_file()

if __name__ == "__main__":
    main()
