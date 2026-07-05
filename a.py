import requests
import json

TOKEN_CA = "B54PYxx3YDy1uYJAcN5F4STAEga8ZRPAe3pDygL4Hzn5"

BASE = "https://api.geckoterminal.com/api/v2"
HEADERS = {"accept": "application/json"}

# Step 1: Fetch pools from token CA
def get_pool_address(token_ca):
    url = f"{BASE}/networks/solana/tokens/{token_ca}/pools"

    print(f"Fetching pools for token: {token_ca}")
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        print("Failed to fetch pools")
        return None

    data = r.json()

    # Save raw response
    with open("1_token_pools_raw.json", "w") as f:
        json.dump(data, f, indent=4)

    pools = data.get("data", [])

    if not pools:
        print("No pools found")
        return None

    # Take first pool (usually main liquidity pool)
    pool_id = pools[0]["id"]  # format: solana_POOLADDRESS
    pool_address = pool_id.split("_")[1]

    return pool_address


# Step 2: Fetch price from pool address
def get_price_from_pool(pool_address):
    url = f"{BASE}/networks/solana/pools/{pool_address}"

    print(f"Fetching price from pool: {pool_address}")
    r = requests.get(url, headers=HEADERS)

    if r.status_code != 200:
        print("Failed to fetch pool data")
        return None

    data = r.json()

    # Save raw response
    with open("2_pool_price_raw.json", "w") as f:
        json.dump(data, f, indent=4)

    attributes = data["data"]["attributes"]

    price = attributes.get("base_token_price_usd")
    liquidity = attributes.get("reserve_in_usd")

    return price, liquidity


def main():
    pool_address = get_pool_address(TOKEN_CA)

    if not pool_address:
        print("Could not find pool")
        return

    print(f"\nPool Address: {pool_address}")

    result = get_price_from_pool(pool_address)

    if not result:
        print("Could not fetch price")
        return

    price, liquidity = result

    print("\n=== RESULT ===")
    print("Token CA:", TOKEN_CA)
    print("Pool Address:", pool_address)
    print("Price USD:", price)
    print("Liquidity USD:", liquidity)


if __name__ == "__main__":
    main()
