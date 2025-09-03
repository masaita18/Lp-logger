import os
import csv
from datetime import datetime
from web3 import Web3
import matplotlib.pyplot as plt
import pandas as pd
import requests

# ==== 設定 ====
RPC_URL = "https://rpc.hyperliquid.xyz/evm"

# 正しい NonfungiblePositionManager (Hyperliquid EVM)
POSITION_MANAGER = Web3.to_checksum_address("0xeaD19AE861c29bBb2101E834922B2FFeee69B9091")

# 追跡する LP NFT ID
TOKEN_ID = 101400   # <-- あなたのNFT IDに変更してください

# Coingecko ID (要確認: Hyperliquid の HYPE トークンID)
HYPE_COINGECKO_ID = "hyperliquid"

DECIMALS = {
    "HYPE": 18,
    "USDT": 6,
}

# ==== ABI (positions 関数のみ) ====
POSITION_MANAGER_ABI = [
    {
        "name": "positions",
        "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"},
        ],
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]

# ==== Web3 接続 ====
w3 = Web3(Web3.HTTPProvider(RPC_URL))
pm_contract = w3.eth.contract(address=POSITION_MANAGER, abi=POSITION_MANAGER_ABI)


# ==== LP情報取得 ====
def get_position(token_id):
    return pm_contract.functions.positions(token_id).call()


# ==== Coingeckoから価格取得 ====
def get_price(token_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_id}&vs_currencies=usd"
    r = requests.get(url)
    return r.json()[token_id]["usd"]


# ==== CSV保存 ====
CSV_FILE = "lp_history.csv"

def save_to_csv(timestamp, value_usd):
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "value_usd"])
        writer.writerow([timestamp, value_usd])


# ==== グラフ生成 ====
def plot_graph():
    df = pd.read_csv(CSV_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["value_usd"], marker="o")
    plt.title("LP Value Over Time (USD)")
    plt.xlabel("Date")
    plt.ylabel("Value (USD)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("lp_value.png")
    plt.close()


# ==== メイン処理 ====
def main():
    pos = get_position(TOKEN_ID)
    liquidity = pos[7]  # "liquidity"

    # 簡易的に HYPE のみの流動性として計算
    price_hype = get_price(HYPE_COINGECKO_ID)
    value_usd = liquidity / (10**DECIMALS["HYPE"]) * price_hype

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    save_to_csv(timestamp, value_usd)
    plot_graph()
    print(f"[{timestamp}] Value: ${value_usd:.2f}")


if __name__ == "__main__":
    main()
