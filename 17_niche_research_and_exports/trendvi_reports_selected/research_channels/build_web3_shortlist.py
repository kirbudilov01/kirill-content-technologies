import asyncio
import csv
import sys

import asyncpg
from db import _get_dsn


SELECTION = [
    ("https://www.youtube.com/@ton_official_channel", "official_ton", 10, "Core TON official channel: Telegram-native L1, mini apps, wallets, ecosystem"),
    ("https://www.youtube.com/@ton-company", "official_ton", 9, "TON developer/community platform for builders and entrepreneurs"),
    ("https://www.youtube.com/@toncoin_rus", "official_ton", 8, "TON CIS community signal for Telegram/TON mass adoption"),
    ("https://www.youtube.com/@bitgetwallet", "wallet_payments", 9, "Large Web3 wallet with trade, earn, pay, and discover positioning"),
    ("https://www.youtube.com/@nicegramapp", "telegram_ton_app", 9, "Telegram client with TON/EVM wallet and attention-to-rewards angle"),
    ("https://www.youtube.com/@trustwallet", "wallet_payments", 9, "Major self-custody wallet and Web3 gateway"),
    ("https://www.youtube.com/@buildoncircle", "payments_wallet", 9, "USDC, stablecoin payments, and internet financial platform signal"),
    ("https://www.youtube.com/@cryptocomofficial", "wallet_payments", 9, "Large regulated crypto app/payment ecosystem"),
    ("https://www.youtube.com/@krakencryptoexchange", "wallet_payments", 9, "Major exchange/wallet/payment access layer"),
    ("https://www.youtube.com/@bitcoincomofficial", "wallet_payments", 8, "Consumer crypto products and wallet access layer"),
    ("https://www.youtube.com/@xapobankapp", "wallet_payments", 8, "Bitcoin-enabled bank/payment product signal"),
    ("https://www.youtube.com/@thirdweb_", "developer_platform", 9, "Web3 developer platform and full-stack blockchain tutorials"),
    ("https://www.youtube.com/@moralisweb3", "developer_platform", 9, "Web3 data/API infrastructure for wallets, exchanges, and on-chain apps"),
    ("https://www.youtube.com/@dappuniversity", "developer_platform", 8, "Dapp/blockchain development education"),
    ("https://www.youtube.com/@web3foundation", "developer_platform", 8, "Web3 Foundation/Polkadot ecosystem signal"),
    ("https://www.youtube.com/@nikandrsurkov", "developer_platform", 8, "TON developer tutorials and mini app building"),
    ("https://www.youtube.com/@swap.coffee", "ton_defi", 8, "TON DEX aggregator and DeFi product signal"),
    ("https://www.youtube.com/@hot-labs", "wallet_payments", 8, "MPC wallet protocol and Web3 wallet infrastructure"),
    ("https://www.youtube.com/@secux", "wallet_payments", 7, "Blockchain security and hardware wallet product signal"),
    ("https://www.youtube.com/@hamsterkombat_official", "telegram_rewards", 9, "Mass Telegram mini-game/rewards case study"),
    ("https://www.youtube.com/@catgoldminerofficial", "telegram_rewards", 8, "Telegram game-to-airdrop/rewards pattern"),
    ("https://www.youtube.com/@playtoearn_com", "rewards_gaming", 8, "Play-to-earn and Web3 games data/news aggregator"),
    ("https://www.youtube.com/@gomining_official", "rewards_gaming", 8, "Tokenized rewards/mining app with consumer crypto positioning"),
    ("https://www.youtube.com/@tem_project", "rewards_gaming", 7, "Web3 rewards across trading, staking, NFTs, and game-style products"),
    ("https://www.youtube.com/@becexy", "rewards_gaming", 7, "Web3 engagement/rewards product"),
    ("https://www.youtube.com/@cointelegraph", "web3_media", 9, "Large Web3 media brand for topic and format signals"),
    ("https://www.youtube.com/@thedefiant", "web3_media", 9, "High-signal DeFi/Web3 media"),
    ("https://www.youtube.com/@a16zcrypto", "web3_builder_media", 9, "Founder/builder/research perspective on crypto and Web3"),
    ("https://www.youtube.com/@coingecko", "web3_data_media", 8, "Crypto data/media channel useful for trend validation"),
    ("https://www.youtube.com/@thinkingcrypto", "web3_media", 8, "Crypto/Web3 interviews and market sentiment"),
    ("https://www.youtube.com/@altcoindaily", "web3_media", 8, "Large crypto audience and trend/topic signal"),
    ("https://www.youtube.com/@coinvestasi", "web3_media", 8, "Accessible blockchain/crypto/Web3 education"),
    ("https://www.youtube.com/@cryptoast", "web3_media", 8, "French crypto/Web3 media"),
    ("https://www.youtube.com/@synopsis_", "web3_media", 8, "Blockchain/Web3 summit and podcast channel"),
    ("https://www.youtube.com/@web3", "web3_media", 8, "Web3 TV for broad blockchain and digital innovation"),
    ("https://www.youtube.com/@vow3podcast", "web3_media", 8, "Founder/builder interviews in Web3"),
    ("https://www.youtube.com/@unboxingweb3", "web3_media", 8, "Web3 explainers and product discovery"),
    ("https://www.youtube.com/@untanglingweb3", "web3_media", 7, "Simplifies Web3/blockchain/AI themes"),
    ("https://www.youtube.com/@ctcweb3academy", "web3_education", 7, "Web3 academy and beginner education"),
    ("https://www.youtube.com/@incryptednet", "web3_media", 7, "Crypto/Web3 media for Russian-speaking market"),
    ("https://www.youtube.com/@cryptosrus", "web3_media", 7, "Large crypto news/alpha channel for market pulse"),
    ("https://www.youtube.com/@cryptocriticpod", "web3_media", 7, "Critical crypto podcast for skepticism/counter-narrative"),
    ("https://www.youtube.com/@bankless", "web3_media", 9, "High-signal Web3/DeFi show with protocol, app, wallet and founder videos"),
    ("https://www.youtube.com/@coinbureau", "web3_education", 9, "Mainstream crypto/Web3 education with strong topic/video demand signal"),
    ("https://www.youtube.com/@whiteboardcrypto", "web3_education", 9, "Clear Web3/crypto explainers for mainstream onboarding"),
    ("https://www.youtube.com/@finematics", "web3_education", 9, "DeFi explainers and protocol/product education"),
    ("https://www.youtube.com/@chainlink", "developer_platform", 8, "Oracle, cross-chain, developer and Web3 infrastructure videos"),
    ("https://www.youtube.com/@ethereumfoundation", "developer_platform", 8, "Ethereum ecosystem, Devcon, protocol and builder education"),
    ("https://www.youtube.com/@nearprotocol", "developer_platform", 8, "NEAR protocol, chain abstraction, AI/assets/agents commerce layer"),
    ("https://www.youtube.com/@base", "developer_platform", 8, "Base/onchain builder ecosystem and consumer crypto app signal"),
    ("https://www.youtube.com/@wormholecrypto", "developer_platform", 8, "Cross-chain interoperability and multichain app infrastructure"),
    ("https://www.youtube.com/@arbitrum", "developer_platform", 8, "L2 ecosystem and onchain app builder signal"),
    ("https://www.youtube.com/@avalancheavax", "developer_platform", 8, "Blockchain platform, builders and Web3 app ecosystem"),
    ("https://www.youtube.com/@ripple", "payments_wallet", 8, "Crypto payments, tokenization and institutional Web3 products"),
    ("https://www.youtube.com/@algorandfoundation", "developer_platform", 8, "Blockchain builders, payments and tokenization ecosystem"),
    ("https://www.youtube.com/@web3.revolution", "web3_creator", 8, "Web3 projects, audience behavior, and promo mechanics"),
    ("https://www.youtube.com/@vishalsahu21", "web3_creator", 8, "Crypto airdrops, Web3 projects, and tech tips"),
    ("https://www.youtube.com/@web3droplab", "web3_creator", 8, "Airdrops, Web3 projects, Telegram mining bots, passive-income mechanics"),
    ("https://www.youtube.com/@rudycrypto", "web3_creator", 8, "Russian Web3/crypto community signal"),
    ("https://www.youtube.com/@bahaa_taha", "developer_creator", 8, "Build Web2/Web3 developer bridge"),
    ("https://www.youtube.com/@darrylboo", "web3_creator", 7, "Web3 builder and crypto-native founder content"),
    ("https://www.youtube.com/@xfounders", "startup_builder", 7, "Web3 startup/founder community signal"),
    ("https://www.youtube.com/@pccrypto", "web3_creator", 7, "Web3/NFT/DeFi/metaverse apps and investing education"),
    ("https://www.youtube.com/@mucida_web3", "rewards_gaming", 7, "Web3 games and play-and-earn content"),
    ("https://www.youtube.com/@masterkamote", "rewards_gaming", 7, "Web3 gaming and blockchain game trend signal"),
    ("https://www.youtube.com/@bangbowo", "rewards_gaming", 7, "Indonesian Web3 gaming creator"),
    ("https://www.youtube.com/@slammdunkgaming", "rewards_gaming", 7, "Pixels/Web3 game content"),
    ("https://www.youtube.com/@cryptoblood", "prediction_markets", 8, "Crypto/TradeFi with growing prediction-market focus"),
    ("https://www.youtube.com/@cryptocrowofficial", "prediction_markets", 8, "Prediction-market maker and crypto market channel"),
    ("https://www.youtube.com/@inthemoneycb", "prediction_markets", 8, "AI crypto tokens, prediction markets, and Web3 market motion"),
    ("https://www.youtube.com/@cryptocomix", "prediction_markets", 7, "Prediction markets plus crypto explainers"),
    ("https://www.youtube.com/@polymarketstuff", "prediction_markets", 7, "Polymarket clips and social signal"),
    ("https://www.youtube.com/@predictionnewsnetwork", "prediction_markets", 7, "Prediction markets news/context channel"),
    ("https://www.youtube.com/@electionpredictionsofficial", "prediction_markets", 6, "Prediction format signal, useful cautiously outside crypto-native context"),
    ("https://www.youtube.com/@axiomica", "ton_telegram", 8, "Blockchain solutions and Telegram mini-app match"),
    ("https://www.youtube.com/@cryptosonic1", "ton_telegram", 7, "Telegram/crypto promotions and mini-app discovery signal"),
    ("https://www.youtube.com/@cryptovector6544", "ton_telegram", 7, "TON/Telegram wallet and crypto project signal"),
    ("https://www.youtube.com/@badertevi", "ton_telegram", 7, "Mining apps and Web3 mini-app discovery in Hindi/Urdu"),
    ("https://www.youtube.com/@cryptomaster_786", "rewards_gaming", 7, "NFT/DeFi/Web3/GameFi and reward apps"),
    ("https://www.youtube.com/@crypto_queen_", "rewards_gaming", 7, "Play-to-earn, DeFi, blockchain gaming and rewards"),
    ("https://www.youtube.com/@cryptoleakzofficial", "rewards_gaming", 7, "Web3 innovations, NFT/GameFi, and crypto projects"),
    ("https://www.youtube.com/@andrewpandagames", "rewards_gaming", 7, "Free-to-play/play-to-earn blockchain games"),
    ("https://www.youtube.com/@cryptologistofficial", "web3_creator", 7, "Blockchain, crypto projects, Web3, NFTs, and gaming"),
    ("https://www.youtube.com/@beessocialtv", "web3_social", 7, "Web3 social network and decentralized-economy content"),
    ("https://www.youtube.com/@coinharbor", "payments_wallet", 7, "Wallet/payment style crypto channel signal"),
    ("https://www.youtube.com/@qiblockchain8020", "web3_product", 7, "Blockchain ecosystem with wallet, marketplace, lending, and DeFi products"),
    ("https://www.youtube.com/@hotcuppacrypto", "web3_creator", 7, "Web3/DeFi creator with product discovery signal"),
    ("https://www.youtube.com/@cryptoyuhanis", "wallet_payments", 7, "NFT/wallet education and consumer crypto tutorials"),
    ("https://www.youtube.com/@block-chain-world", "web3_creator", 7, "Web3 tech, DeFi, wallets, tokens, apps, and project discovery"),
    ("https://www.youtube.com/@cryptolove", "market_signal", 6, "Large crypto audience signal; use cautiously for broad market formats"),
    ("https://www.youtube.com/@cryptopeak", "market_signal", 6, "Crypto review/promo mechanics signal"),
    ("https://www.youtube.com/@tigerinsight", "market_signal", 6, "Crypto/online-income audience signal"),
    ("https://www.youtube.com/@coingalaxy7", "market_signal", 6, "Crypto trends, token promotions, NFT drops, and market updates"),
    ("https://www.youtube.com/@cryptodailyupdates", "market_signal", 6, "Degen token/gem content useful only as low-quality-market contrast"),
    ("https://www.youtube.com/@cryptogemsofficial", "market_signal", 6, "Crypto news/analysis/gems, useful as hype-pattern reference"),
    ("https://www.youtube.com/@cryptonardo", "market_signal", 6, "Crypto reviews and influencer/project promo mechanics"),
    ("https://www.youtube.com/@comphocrypto", "market_signal", 6, "Crypto updates, analysis, and promotion mechanics"),
    ("https://www.youtube.com/@crypto_giant", "market_signal", 6, "Crypto/fintech/news audience signal"),
    ("https://www.youtube.com/@cryptocasey", "web3_education", 7, "Crypto and blockchain education for mainstream onboarding"),
    ("https://www.youtube.com/@chicocrypto", "web3_education", 7, "Intermediate/advanced crypto education and altcoin research"),
    ("https://www.youtube.com/@ctcweb3academy", "web3_education", 7, "Web3/blockchain education and community learning"),
    ("https://www.youtube.com/@cryptogorilla", "web3_education", 7, "Airdrops, NFTs, DeFi, and on-chain tools explained simply"),
    ("https://www.youtube.com/@rahulinweb3", "web3_education", 7, "Web3 learning and decentralization education"),
    ("https://www.youtube.com/@laboratorioweb3blockchain", "web3_education", 7, "Web3/blockchain lab content in Spanish"),
    ("https://www.youtube.com/@womenincrypto", "web3_community", 6, "Community/business angle for crypto adoption"),
    ("https://www.youtube.com/@dpo_bynetwork", "payments_wallet", 6, "Payments infrastructure signal adjacent to Web3 payments"),
    ("https://www.youtube.com/@molliepayments", "payments_wallet", 6, "Digital payments product signal adjacent to crypto payments"),
    ("https://www.youtube.com/@tappayments", "payments_wallet", 6, "Regional payments product signal"),
    ("https://www.youtube.com/@paymentscanada", "payments_wallet", 6, "Payments infrastructure reference point"),
    ("https://www.youtube.com/@bananacrystal", "payments_wallet", 6, "Agent payment infrastructure and wallet/payment-adjacent product"),
    ("https://www.youtube.com/@financewithavrin", "rewards_gaming", 6, "Reward apps and finance-app discovery signal"),
    ("https://www.youtube.com/@vinsanereviews", "rewards_gaming", 6, "Rewards/free-methods app review channel"),
    ("https://www.youtube.com/@coinpost", "web3_media", 6, "Crypto/Web3 news and market topic signal for Russian-speaking audience"),
    ("https://www.youtube.com/@coinpostpro5320", "web3_media", 6, "Professional crypto trends/media spin-off"),
    ("https://www.youtube.com/@discovercrypto_", "market_signal", 6, "Large crypto audience and mainstream topic/format signal"),
    ("https://www.youtube.com/@cryptocrewuniversity", "web3_education", 6, "Crypto education and cycle-market framing"),
    ("https://www.youtube.com/@colintalkscrypto", "web3_education", 6, "Long-running crypto education and community perspective"),
]


async def main():
    conn = await asyncpg.connect(_get_dsn())
    try:
        rows = await conn.fetch(
            """
            SELECT channel_id, title, url, subscribers, views, verified,
                   regexp_replace(coalesce(description,''), '[[:space:]]+', ' ', 'g') AS description
            FROM yt_channel_catalog
            WHERE lower(trim(trailing '/' from url)) = ANY($1::text[])
            """,
            [url.rstrip("/").lower() for url, _, _, _ in SELECTION],
        )
    finally:
        await conn.close()

    by_url = {row["url"].rstrip("/").lower(): dict(row) for row in rows}
    final = []
    seen = set()
    missing = []
    for url, category, audit_score, reason in SELECTION:
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        if "fabricbotecosystem" in key:
            continue
        row = by_url.get(key)
        if not row:
            missing.append(url)
            continue
        row["category"] = category
        row["audit_score"] = audit_score
        row["selection_reason"] = reason
        final.append(row)
        if len(final) == 100:
            break

    fields = [
        "rank",
        "audit_score",
        "category",
        "title",
        "url",
        "channel_id",
        "subscribers",
        "views",
        "verified",
        "selection_reason",
        "description_snippet",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    for idx, row in enumerate(final, start=1):
        writer.writerow(
            {
                "rank": idx,
                "audit_score": row["audit_score"],
                "category": row["category"],
                "title": row["title"],
                "url": row["url"],
                "channel_id": row["channel_id"],
                "subscribers": row["subscribers"],
                "views": row["views"],
                "verified": row["verified"],
                "selection_reason": row["selection_reason"],
                "description_snippet": row["description"][:280],
            }
        )

    if missing:
        print(f"missing={len(missing)}", file=sys.stderr)
        for url in missing:
            print(f"MISSING {url}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
