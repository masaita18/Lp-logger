from web3 import Web3
import json
import time

# --- RPC 設定 ---
RPC_URL = "https://rpc.hyperliquid.xyz/evm"   # Hyperliquid EVM RPC
web3 = Web3(Web3.HTTPProvider(RPC_URL))

# --- コントラクトアドレス ---
POSITION_MANAGER = "0xeaD19AE861c29bBb2101E834922B2FFeee69B9091"  # NFT Position Manager
FACTORY = "0xf7Fb38c00e57ea31477c32A5B52a58Eea47b072"             # Factory
ROUTER = "0x1EbDFC75fFEb3a3de61E7138a3E8706aC841fA9B"             # Swap Router

# --- ABI の読み込み（事前に保存した JSON ファイルを読み込む想定） ---
with open("abis/NonfungiblePositionManager.json", "r") as f:
    POSITION_MANAGER_ABI = json.load(f)

# --- コントラクトオブジェクト作成 ---
position_manager = web3.eth.contract(address=POSITION_MANAGER, abi=POSITION_MANAGER_ABI)

# --- LP 情報を取得する関数 ---
def get_positions(owner_address):
    balance = position_manager.functions.balanceOf(owner_address).call()
    print(f"Owner {owner_address} has {balance} LP positions")

    positions = []
    for i in range(balance):
        token_id = position_manager.functions.tokenOfOwnerByIndex(owner_address, i).call()
        pos = position_manager.functions.positions(token_id).call()
        positions.append({
            "token_id": token_id,
            "liquidity": pos[7],       # positions() の戻り値の index で参照
            "token0": pos[2],
            "token1": pos[3],
            "fee": pos[4]
        })
    return positions

# --- メイン処理 ---
if __name__ == "__main__":
    test_wallet = "0x1234567890abcdef1234567890abcdef12345678"  # 任意のウォレットアドレスに差し替え

    while True:
        try:
            lp_data = get_positions(test_wallet)
            print(lp_data)
        except Exception as e:
            print("Error:", e)

        time.sleep(60)  # 1分ごとに実行
