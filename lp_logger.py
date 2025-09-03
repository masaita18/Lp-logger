import os
import csv
from datetime import datetime
from web3 import Web3
import matplotlib.pyplot as plt
import pandas as pd
import requests

# ==== 設定 ====
RPC_URL = "https://rpc.hypurrscan.io"

# Nonfungible Position Manager（固定アドレス）
POSITION_MANAGER = Web3.to_checksum_address("0xbd19e19e4b70eb7f248695a42208c1bdebbfb57d")

TOKEN_ID = 101400   # 対象のLP NFT ID
HYPE_COINGECKO_ID = "hyperliquid"  # HYPE の Coingecko ID（要確認）

DECIMALS = {
    "HYPE": 18,
    "USDT": 6
}

# ==== ABI の必要部分 ====
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
        "type": "function"
    }
]

# ==== Web3 接続 ====
w3 = Web3(Web3.HTTPProvider(RPC_URL))
pm_contract = w3.eth.contract(address=POSITION_MANAGER, abi=POSITION_MANAGER_ABI)

# ==== CSV 初期化 ====
CSV_FILE = "lp_history.csv"
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "HYPE", "USDT", "total_usdt"])

# ==== Coingecko から価格取得 ====
def get_price(token_id):
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={token_id}&vs_currencies=usd"
    res = requests.get(url).json()
    return res[token_id]["usd"]

# ==== ポジション情報取得 ====
def get_position(token_id):
    return pm_contract.functions.positions(token_id).call()

# ==== メイン処理 ====
def main():
    pos = get_position(TOKEN_ID)
    hype_reward = pos[10] / (10 ** DECIMALS["HYPE"])
    usdt_reward = pos[11] / (10 ** DECIMALS["USDT"])

    # HYPE→USDT 換算
    hype_price = get_price(HYPE_COINGECKO_ID)
    hype_in_usdt = hype_reward * hype_price
    total_usdt = hype_in_usdt + usdt_reward

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # CSV 追記
    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, hype_reward, usdt_reward, total_usdt])

    # グラフ生成
    df = pd.read_csv(CSV_FILE)
    plt.figure(figsize=(10, 6))
    plt.plot(pd.to_datetime(df["date"]), df["total_usdt"], marker="o")
    plt.title("LP Reward (in USDT)")
    plt.xlabel("Date")
    plt.ylabel("USDT Value")
    plt.grid(True)
    plt.savefig("lp_value.png")
    plt.close()

if __name__ == "__main__":
    main()
