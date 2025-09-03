# -*- coding: utf-8 -*-
"""
PRJX (HyperEVM / Hyperliquid) Uniswap v3 LPトラッカー
- 毎日(日本時間)1回: 現在評価額と未請求リワードUSDをCSVに追記
- グラフを日付(JST)付きPNGで保存（例: lp_value_2025-09-04.png）
- 合計USDと、実績リワード累積の「擬似複利」曲線を可視化

依存: requests, web3, pandas, matplotlib
"""

import os, csv, math, requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import matplotlib.pyplot as plt
from web3 import Web3

# ===== 設定（必要に応じて変更） =====
RPC_URL = "https://rpc.hyperliquid.xyz/evm"  # HyperEVM 公式RPC
POSITION_MANAGER = "0xbd19e19e4b70eb7f248695a42208bc1edbbfb57d"  # NonfungiblePositionManager
POOL = "0xeaD19AE861c29bBb2101E834922B2FEee69B9091"               # HYPE/USDT プール
TOKEN_ID = 101400                                                # あなたのLP NFT
COINGECKO_ID_HYPE = "hyperliquid"                                # HYPEのCoinGecko ID
CSV_FILE = "lp_history.csv"                                      # 履歴CSV
IMG_DIR = "."                                                    # 画像の保存先（リポジトリ直下）
# ================================

# 日本時間
JST = timezone(timedelta(hours=9))

w3 = Web3(Web3.HTTPProvider(RPC_URL))
assert w3.is_connected(), "RPCに接続できません。RPC_URLを確認してください。"

Q96 = 2 ** 96

# --- 必要最小限のABI ---
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}],
     "stateMutability": "view", "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}],
     "stateMutability": "view", "type": "function"},
]
POOL_ABI = [
    {"inputs": [], "name": "slot0", "outputs": [
        {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"internalType": "int24", "name": "tick", "type": "int24"},
        {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
        {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
        {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
        {"internalType": "bool", "name": "unlocked", "type": "bool"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token0", "outputs": [{"internalType": "address", "name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token1", "outputs": [{"internalType": "address", "name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
]
NPM_ABI = [
    {"inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
     "name": "positions", "outputs": [
        {"internalType": "uint96", "name": "nonce", "type": "uint96"},
        {"internalType": "address", "name": "operator", "type": "address"},
        {"internalType": "address", "name": "token0", "type": "address"},
        {"internalType": "address", "name": "token1", "type": "address"},
        {"internalType": "uint24", "name": "fee", "type": "uint24"},
        {"internalType": "int24", "name": "tickLower", "type": "int24"},
        {"internalType": "int24", "name": "tickUpper", "type": "int24"},
        {"internalType": "uint128", "name": "liquidity", "type": "uint128"},
        {"internalType": "uint256", "name": "feeGrowthInside0LastX128", "type": "uint256"},
        {"internalType": "uint256", "name": "feeGrowthInside1LastX128", "type": "uint256"},
        {"internalType": "uint128", "name": "tokensOwed0", "type": "uint128"},
        {"internalType": "uint128", "name": "tokensOwed1", "type": "uint128"}],
     "stateMutability": "view", "type": "function"}
]

pool = w3.eth.contract(address=Web3.to_checksum_address(POOL), abi=POOL_ABI)
npm  = w3.eth.contract(address=Web3.to_checksum_address(POSITION_MANAGER), abi=NPM_ABI)

def sqrt_price_x96_from_tick(tick: int) -> int:
    # 近似: sqrt(1.0001^tick) * Q96
    return int((1.0001 ** (tick / 2)) * Q96)

def get_amounts_for_liquidity_baseunits(sqrtP, sqrtA, sqrtB, L):
    """Uniswap v3の概算：返り値はトークンの「最小単位（base units）」"""
    if sqrtA > sqrtB:
        sqrtA, sqrtB = sqrtB, sqrtA
    if sqrtP <= sqrtA:
        amt0 = L * (sqrtB - sqrtA) * Q96 / (sqrtB * sqrtA)
        amt1 = 0.0
    elif sqrtP < sqrtB:
        amt0 = L * (sqrtB - sqrtP) * Q96 / (sqrtB * sqrtP)
        amt1 = L * (sqrtP - sqrtA) / Q96
    else:
        amt0 = 0.0
        amt1 = L * (sqrtB - sqrtA) / Q96
    return float(amt0), float(amt1)

def get_coingecko_price_usd(coin_id: str) -> float | None:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": coin_id, "vs_currencies": "usd"}, timeout=20)
        r.raise_for_status()
        return float(r.json()[coin_id]["usd"])
    except Exception:
        return None

def hype_price_usd_fallback_from_pool(sqrtP, dec0, dec1, sym0, sym1):
    """CoinGeckoが落ちた場合のフォールバック: プール価格からHYPE/USDTを推定"""
    # token0 1単位のtoken1価格 = (sqrtP/Q96)^2 * 10^(dec0 - dec1)
    price_token0_in_token1 = (sqrtP / Q96) ** 2 * (10 ** (dec0 - dec1))
    if sym0.upper() == "HYPE" and sym1.upper() in ("USDT", "USD₮", "USDC"):
        return price_token0_in_token1  # HYPE in USDT
    if sym1.upper() == "HYPE" and sym0.upper() in ("USDT", "USD₮", "USDC"):
        return 1.0 / price_token0_in_token1
    return None

# ==== メイン処理 ====
# ポジション情報
(_nonce, _op, pos_token0, pos_token1, _fee, tick_lower, tick_upper,
 liquidity, _fg0, _fg1, owed0, owed1) = npm.functions.positions(TOKEN_ID).call()

sqrtPriceX96, cur_tick, *_ = pool.functions.slot0().call()
token0_addr = pool.functions.token0().call()
token1_addr = pool.functions.token1().call()
assert pos_token0.lower() == token0_addr.lower() and pos_token1.lower() == token1_addr.lower(), "プールとポジションのトークン不一致"

t0 = w3.eth.contract(address=Web3.to_checksum_address(token0_addr), abi=ERC20_ABI)
t1 = w3.eth.contract(address=Web3.to_checksum_address(token1_addr), abi=ERC20_ABI)
dec0, sym0 = t0.functions.decimals().call(), t0.functions.symbol().call()
dec1, sym1 = t1.functions.decimals().call(), t1.functions.symbol().call()

sqrtA = sqrt_price_x96_from_tick(tick_lower)
sqrtB = sqrt_price_x96_from_tick(tick_upper)

# 保有量（base units）
amt0_base, amt1_base = get_amounts_for_liquidity_baseunits(sqrtPriceX96, sqrtA, sqrtB, liquidity)
# 未請求手数料（base units）
owed0_base, owed1_base = float(owed0), float(owed1)

# 表示用に decimals で正規化（"トークン数"）
amt0_tokens = amt0_base / (10 ** dec0)
amt1_tokens = amt1_base / (10 ** dec1)
owed0_tokens = owed0_base / (10 ** dec0)
owed1_tokens = owed1_base / (10 ** dec1)

amt0_total = amt0_tokens + owed0_tokens
amt1_total = amt1_tokens + owed1_tokens

# 価格（USD）
price_hype_usd = get_coingecko_price_usd(COINGECKO_ID_HYPE)
if price_hype_usd is None:
    price_hype_usd = hype_price_usd_fallback_from_pool(sqrtPriceX96, dec0, dec1, sym0, sym1) or 0.0
price_usdt_usd = 1.0

# USD評価
def tok_usd(amount, sym):
    return amount * (price_hype_usd if sym.upper() == "HYPE" else price_usdt_usd)

usd0 = tok_usd(amt0_total, sym0)
usd1 = tok_usd(amt1_total, sym1)
total_usd = usd0 + usd1

# 未請求リワードのUSD（情報として別列）
usd_rewards = tok_usd(owed0_tokens, sym0) + tok_usd(owed1_tokens, sym1)

# === CSV 追記（同一JST日付が既にあれば上書き） ===
date_jst = datetime.now(JST).strftime("%Y-%m-%d")
row = [date_jst, amt0_total, amt1_total, usd0, usd1, total_usd, usd_rewards]
header = ["date", sym0, sym1, f"{sym0}_usd", f"{sym1}_usd", "total_usd", "rewards_usd"]

if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
    if not df.empty and str(df["date"].iloc[-1]) == date_jst:
        df.iloc[-1] = row  # 同日があれば上書き
    else:
        df.loc[len(df)] = row
else:
    df = pd.DataFrame([row], columns=header)

# 擬似複利（実績リワード累積）カラムを作成
df["compound_usd"] = df["total_usd"].iloc[0] + df["rewards_usd"].cumsum()

df.to_csv(CSV_FILE, index=False)

# === グラフ（その日の1枚だけ、日付(JST)付きファイル名） ===
plt.figure(figsize=(9,5))
plt.plot(df["date"], df["total_usd"], marker="o", label="Total USD")
plt.plot(df["date"], df["compound_usd"], marker="x", linestyle="--", label="Compound (from rewards)")
plt.title("LP Position Value & Compound (JST-daily)")
plt.xlabel("Date (JST)")
plt.ylabel("USD Value")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()

img_filename = os.path.join(IMG_DIR, f"lp_value_{date_jst}.png")
plt.savefig(img_filename)
plt.close()

print(f"[{date_jst}] Total=${total_usd:.2f}  Rewards=${usd_rewards:.2f}  -> {CSV_FILE}, {img_filename}")
