import os
import csv
from datetime import datetime
from web3 import Web3
import matplotlib.pyplot as plt
import pandas as pd
import requests

# ==== 設定 ====
RPC_URL = "https://rpc.hypurrscan.io"
POSITION_MANAGER = "0xbd19e19e4b70eb7f248695a42208c1bdebbfb57d"  # Nonfungible Position Manager
TOKEN_ID = 101400  # 対象のLP NFT ID
HYPE_COINGECKO_ID = "hyperliquid"   # 要確認: HYPE の正しい Coingecko ID

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
        writer.writerow(["timestamp", "liquidity", "owed_HYPE", "owed_USDT", "reward_usdt"])

# ==== Coingecko API ====
def get_hype_price():
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={HYPE_COINGECKO_ID}&vs_currencies=usd"
    try:
        res = requests.get(url, timeout=10).json()
        return res[HYPE_COINGECKO_ID]["usd"]
    except Exception as e:
        print("⚠️ Price fetch failed:", e)
        return None

# ==== データ取得 ====
def fetch_lp_data():
    pos = pm_contract.functions.positions(TOKEN_ID).call()
    owed0 = pos[10] / (10 ** DECIMALS["HYPE"])   # HYPE
    owed1 = pos[11] / (10 ** DECIMALS["USDT"])  # USDT
    hype_price = get_hype_price() or 0
    reward_usdt = owed1 + owed0 * hype_price
    return {
        "liquidity": pos[7],
        "owed_HYPE": owed0,
        "owed_USDT": owed1,
        "reward_usdt": reward_usdt
    }

# ==== CSV 保存 ====
def log_data():
    data = fetch_lp_data()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, data["liquidity"], data["owed_HYPE"], data["owed_USDT"], data["reward_usdt"]])

    print(f"[{now}] Reward (USDT)={data['reward_usdt']:.4f}")

# ==== グラフ作成 ====
def plot_graph():
    df = pd.read_csv(CSV_FILE)
    if df.empty: return

    # 日次リターン計算
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["daily_change"] = df["reward_usdt"].diff()
    df["daily_yield_%"] = (df["daily_change"] / df["reward_usdt"].shift(1)) * 100

    # グラフ1: リワード推移
    plt.figure(figsize=(10,6))
    plt.plot(df["timestamp"], df["reward_usdt"], label="Total Rewards (USDT)")
    plt.xticks(rotation=45)
    plt.xlabel("Time (UTC)")
    plt.ylabel("USDT Value")
    plt.title("LP Rewards (USDT) Over Time")
    plt.legend()
    plt.tight_layout()
    plt.savefig("lp_value.png")
    plt.close()

    # グラフ2: 日利推移
    plt.figure(figsize=(10,6))
    plt.plot(df["timestamp"], df["daily_yield_%"], label="Daily Yield (%)", color="orange")
    plt.xticks(rotation=45)
    plt.xlabel("Time (UTC)")
    plt.ylabel("Daily Yield %")
    plt.title("Daily Yield from LP Rewards")
    plt.legend()
    plt.tight_layout()
    plt.savefig("lp_daily_yield.png")
    plt.close()

    print("📊 lp_value.png & lp_daily_yield.png updated")

if __name__ == "__main__":
    log_data()
    plot_graph()
