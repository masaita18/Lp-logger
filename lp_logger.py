import os
import csv
import time
from datetime import datetime
from web3 import Web3

# ==== 設定 ====
RPC_URL = "https://rpc.hypurrscan.io"
POSITION_MANAGER = "0xbd19e19e4b70eb7f248695a42208c1bdebbfb57d"  # Nonfungible Position Manager
TOKEN_ID = 101400  # 対象のLP NFT ID

# HYPE = token0, USDT = token1
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
        writer.writerow(["timestamp", "liquidity", "owed_HYPE", "owed_USDT"])

# ==== データ取得 ====
def fetch_lp_data():
    pos = pm_contract.functions.positions(TOKEN_ID).call()
    liquidity = pos[7]
    owed0 = pos[10] / (10 ** DECIMALS["HYPE"])   # HYPE
    owed1 = pos[11] / (10 ** DECIMALS["USDT"])  # USDT

    return {
        "liquidity": liquidity,
        "owed_HYPE": owed0,
        "owed_USDT": owed1,
    }

# ==== 保存処理 ====
def log_data():
    data = fetch_lp_data()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    with open(CSV_FILE, mode="a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, data["liquidity"], data["owed_HYPE"], data["owed_USDT"]])

    print(f"[{now}] Liquidity={data['liquidity']}, Owed HYPE={data['owed_HYPE']:.6f}, Owed USDT={data['owed_USDT']:.6f}")

if __name__ == "__main__":
    log_data()
