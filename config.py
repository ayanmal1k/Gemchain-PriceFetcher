import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY")

# DexScreener API Configuration
DEXSCREENER_API_BASE = "https://api.dexscreener.com/latest/dex"

# Application Settings
UPDATE_INTERVAL_SECONDS = 300  # Update every 5 minutes
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2

# Supported Chains
SUPPORTED_CHAINS = [
    "ethereum",
    "bsc",
    "polygon",
    "arbitrum",
    "optimism",
    "avalanche",
    "fantom",
    "solana",
    "near",
    "flow"
]

# Table Names
TOKENS_TABLE = "tokens"

# Batch processing
BATCH_SIZE = 5  # Process tokens in batches to avoid rate limiting
