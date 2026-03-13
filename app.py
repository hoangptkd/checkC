import streamlit as st
from pymongo import MongoClient
import requests
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import pandas as pd
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qs, urlencode

# ─── Cấu hình trang ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Coin Trading Tracker",
    page_icon="📈",
    layout="wide"
)

# Auto refresh mỗi 30 phút bằng JS thuần (không cần thư viện ngoài)
st.markdown(
    '<meta http-equiv="refresh" content="1800">',
    unsafe_allow_html=True
)

# ─── CSS tùy chỉnh ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .profit  { color: #198754; font-weight: bold; }
    .loss    { color: #dc3545; font-weight: bold; }
    .neutral { color: #6c757d; }
    .closed  { color: #adb5bd; }
    div[data-testid="stDataFrame"] { font-size: 13px; }
    .stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ─── Kết nối MongoDB ──────────────────────────────────────────────────────────
def _encode_mongo_uri(uri: str) -> str:
    """Encode username/password theo RFC 3986 để pymongo mới không lỗi."""
    parsed = urlparse(uri)
    if parsed.username and parsed.password:
        user = quote_plus(parsed.username)
        pwd = quote_plus(parsed.password)
        # Rebuild netloc with encoded credentials
        host = parsed.hostname
        if parsed.port:
            host = f"{host}:{parsed.port}"
        netloc = f"{user}:{pwd}@{host}"
        uri = urlunparse(parsed._replace(netloc=netloc))
    return uri

@st.cache_resource
def get_db():
    uri = st.secrets["MONGO_URI"]
    uri = _encode_mongo_uri(uri)
    client = MongoClient(uri, tlsAllowInvalidCertificates=True)
    db = client["coin_tracker"]
    return db

db = get_db()
collection = db["trades"]
morelogin_collection = db["morelogin_list"]

COIN_LIST = [
    "AVAX","ATOM","BNB","TRX","NEO","AAVE","NOT","ONE",
    "BCH","LTC","XRP","CRV","ICP","FIL","PEPE","DOT",
    "ETC","SUI","ADA","ALGO","SOL","BTC","POL","ETH",
    "SHIB","TON","NEAR","DYDX","XLM","DOGE"
]

# ─── Map tên coin cho CoinGecko ────────────────────────────────────────────────
COINGECKO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin", "SOL": "solana",
    "ADA": "cardano", "XRP": "ripple", "DOT": "polkadot", "DOGE": "dogecoin",
    "AVAX": "avalanche-2", "ATOM": "cosmos", "TRX": "tron", "NEO": "neo",
    "AAVE": "aave", "NOT": "notcoin", "ONE": "harmony", "BCH": "bitcoin-cash",
    "LTC": "litecoin", "CRV": "curve-dao-token", "ICP": "internet-computer",
    "FIL": "filecoin", "PEPE": "pepe", "ETC": "ethereum-classic", "SUI": "sui",
    "ALGO": "algorand", "POL": "matic-network", "SHIB": "shiba-inu",
    "TON": "the-open-network", "NEAR": "near", "DYDX": "dydx-chain",
    "XLM": "stellar",
}

# ─── Hàm tiện ích ─────────────────────────────────────────────────────────────
def _try_binance(coin: str):
    """Thử lấy giá từ Binance Global."""
    try:
        r = requests.get(
            f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT",
            timeout=5
        )
        if r.status_code == 200:
            return float(r.json()["price"])
    except Exception:
        pass
    return None

def _try_binance_us(coin: str):
    """Thử lấy giá từ Binance US (ít bị chặn hơn trên cloud)."""
    try:
        r = requests.get(
            f"https://api.binance.us/api/v3/ticker/price?symbol={coin}USDT",
            timeout=5
        )
        if r.status_code == 200:
            return float(r.json()["price"])
    except Exception:
        pass
    return None

def _try_coingecko(coin: str):
    """Fallback: lấy giá từ CoinGecko (miễn phí, không cần API key)."""
    cg_id = COINGECKO_IDS.get(coin)
    if not cg_id:
        return None
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={cg_id}&vs_currencies=usd",
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if cg_id in data and "usd" in data[cg_id]:
                return float(data[cg_id]["usd"])
    except Exception:
        pass
    return None

def get_coin_price(coin: str):
    """Lấy giá coin, thử lần lượt Binance → Binance US → CoinGecko."""
    for fetcher in (_try_binance, _try_binance_us, _try_coingecko):
        price = fetcher(coin)
        if price:
            return price
    return None

def calc_profit_pct(entry, current, position, leverage):
    if position == "LONG":
        pct = ((current - entry) / entry) * 100
    else:
        pct = ((entry - current) / entry) * 100
    return pct * leverage

def calc_profit_usdt(profit_pct, usdt_amount):
    return (usdt_amount * profit_pct) / 100

def load_morelogin_list():
    return [m["name"] for m in morelogin_collection.find().sort("name", 1)]

def save_morelogin(name: str):
    if name and name not in load_morelogin_list():
        morelogin_collection.insert_one({"name": name, "created_at": datetime.now()})

def load_trades(query=None):
    if query is None:
        query = {"coin": {"$exists": True, "$nin": [None, ""]}}
    trades = list(collection.find(query).sort("created_at", -1))
    rows = []
    for t in trades:
        if not t.get("coin") or not t.get("position"):
            continue
        usdt   = t.get("usdt_amount", 50)
        lev    = t.get("leverage", 10)
        pct    = t.get("profit_percent", 0.0)
        pusdt  = calc_profit_usdt(pct, usdt)
        dt     = t.get("open_time", t.get("created_at"))
        is_closed = t.get("is_closed", False)
        rows.append({
            "_id":           str(t["_id"]),
            "Coin":          t["coin"],
            "Vị thế":        t["position"],
            "Profile":       t.get("profile_number", ""),
            "MoreLogin":     t.get("morelogin", ""),
            "Email":         t.get("email", ""),
            "Giá vào":       t.get("entry_price", 0),
            "Giá hiện tại":  t.get("current_price", 0),
            "USDT":          usdt,
            "Đòn bẩy":       lev,
            "Lãi/Lỗ (%)":   round(pct, 2),
            "Lãi/Lỗ (USDT)":round(pusdt, 2),
            "Trạng thái":    "🔒 Đã chốt" if is_closed else "📈 Đang mở",
            "Ghi chú":       t.get("note", ""),
            "Thời gian":     dt.strftime("%Y-%m-%d %H:%M") if dt else "",
            "is_closed":     is_closed,
        })
    return rows

def update_all_prices():
    trades = list(collection.find({
        "coin":      {"$exists": True, "$nin": [None, ""]},
        "is_closed": {"$ne": True}
    }))
    updated = 0
    for t in trades:
        price = get_coin_price(t["coin"])
        if price:
            pct = calc_profit_pct(t["entry_price"], price, t["position"], t.get("leverage", 10))
            collection.update_one({"_id": t["_id"]}, {"$set": {
                "current_price": price,
                "profit_percent": pct,
                "updated_at": datetime.now()
            }})
            updated += 1
    return updated

def auto_close_overdue():
    trades = list(collection.find({
        "coin":      {"$exists": True, "$ne": None, "$ne": ""},
        "is_closed": {"$ne": True}
    }))
    closed = 0
    now = datetime.now()
    for t in trades:
        close_days = t.get("close_days", 2)
        open_time  = t.get("open_time", t.get("created_at"))
        if not open_time:
            continue
        if now - open_time < timedelta(days=close_days):
            continue
        price = get_coin_price(t["coin"])
        if not price:
            price = t.get("current_price", t["entry_price"])
        pct   = calc_profit_pct(t["entry_price"], price, t["position"], t.get("leverage", 10))
        pusdt = calc_profit_usdt(pct, t.get("usdt_amount", 50))
        txt   = f"lời ${pusdt:.2f}" if pusdt >= 0 else f"lỗ ${abs(pusdt):.2f}"
        collection.update_one({"_id": t["_id"]}, {"$set": {
            "current_price":  price,
            "profit_percent": pct,
            "note":           f"⏰ Tự động chốt ({close_days} ngày): {txt} ({pct:+.2f}%)",
            "is_closed":      True,
            "closed_at":      now,
            "updated_at":     now
        }})
        closed += 1
    return closed

# ─── Sidebar: Thêm giao dịch ──────────────────────────────────────────────────
with st.sidebar:
    st.header("➕ Thêm Giao Dịch")

    coin      = st.selectbox("Coin", COIN_LIST, index=COIN_LIST.index("BTC"))
    position  = st.radio("Vị thế", ["LONG", "SHORT"], horizontal=True)
    price_in  = st.text_input("Giá vào (để trống = lấy tự động)")
    usdt_amt  = st.number_input("Số USDT", value=50.0, min_value=1.0)
    leverage  = st.number_input("Đòn bẩy", value=10, min_value=1, max_value=125)
    profile   = st.number_input("Profile", value=1, min_value=1, step=1)

    ml_list   = load_morelogin_list()
    ml_opts   = ml_list + ["➕ Thêm mới..."]
    ml_sel    = st.selectbox("MoreLogin", ml_opts)

    if ml_sel == "➕ Thêm mới...":
        new_ml = st.text_input("Nhập MoreLogin mới")
        if st.button("💾 Lưu MoreLogin") and new_ml.strip():
            save_morelogin(new_ml.strip())
            st.success(f"Đã thêm: {new_ml.strip()}")
            st.rerun()
        morelogin = new_ml.strip() if new_ml.strip() else ""
    else:
        morelogin = ml_sel

    email      = st.text_input("Email (tuỳ chọn)")
    note       = st.text_input("Ghi chú")
    close_days = st.number_input("Số ngày tự chốt", value=2, min_value=1)

    if st.button("🚀 Thêm Giao Dịch", type="primary"):
        if not morelogin:
            st.error("Vui lòng chọn hoặc nhập MoreLogin!")
        else:
            # Lấy giá
            if price_in.strip():
                try:
                    entry_price = float(price_in)
                except ValueError:
                    st.error("Giá vào phải là số!")
                    st.stop()
            else:
                with st.spinner(f"Đang lấy giá {coin}..."):
                    entry_price = get_coin_price(coin)
                if not entry_price:
                    st.error(f"Không lấy được giá {coin}!")
                    st.stop()

            now = datetime.now()
            existing = collection.find_one({
                "profile_number": int(profile),
                "morelogin":      morelogin
            })
            data = {
                "coin": coin, "position": position,
                "note": note, "email": email.strip(),
                "entry_price": entry_price,
                "current_price": entry_price, "usdt_amount": float(usdt_amt),
                "leverage": int(leverage), "profit_percent": 0.0,
                "open_time": now, "close_days": int(close_days),
                "is_closed": False, "updated_at": now
            }
            if existing:
                collection.update_one({"_id": existing["_id"]}, {"$set": data})
                st.success(f"✅ Đã cập nhật {position} {coin} - Profile {profile}")
            else:
                data.update({
                    "profile_number": int(profile),
                    "morelogin": morelogin,
                    "created_at": now
                })
                collection.insert_one(data)
                st.success(f"✅ Đã thêm {position} {coin} @ ${entry_price:,.5f}")
            st.rerun()

    st.divider()
    st.subheader("⚙️ Điều khiển")

    if st.button("🔄 Cập nhật tất cả giá"):
        with st.spinner("Đang cập nhật..."):
            n = update_all_prices()
        st.success(f"Đã cập nhật {n} coin")
        st.rerun()

    if st.button("⏰ Quét chốt tự động"):
        with st.spinner("Đang quét..."):
            n = auto_close_overdue()
        st.success(f"Đã chốt {n} giao dịch")
        st.rerun()

# ─── Nội dung chính ───────────────────────────────────────────────────────────
st.title("📈 Coin Trading Tracker")

# Bộ lọc
col1, col2, col3, col4 = st.columns([2,2,2,1])
with col1:
    filter_coin = st.text_input("🔍 Tìm Coin", placeholder="VD: BTC")
with col2:
    filter_ml   = st.text_input("🔍 Lọc MoreLogin", placeholder="Nhập tên...")
with col3:
    filter_status = st.selectbox("Trạng thái", ["Tất cả", "Đang mở", "Đã chốt"])
with col4:
    sort_col = st.selectbox("Sắp xếp", ["Thời gian", "Lãi/Lỗ (%)", "Profile", "MoreLogin"])

# Xây query
query: dict = {"coin": {"$exists": True, "$nin": [None, ""]}}
if filter_coin.strip():
    query["coin"] = {"$regex": filter_coin.strip(), "$options": "i"}
if filter_ml.strip():
    query["morelogin"] = {"$regex": filter_ml.strip(), "$options": "i"}
if filter_status == "Đang mở":
    query["is_closed"] = {"$ne": True}
elif filter_status == "Đã chốt":
    query["is_closed"] = True

rows = load_trades(query)

# Sắp xếp
sort_map = {
    "Thời gian":   "Thời gian",
    "Lãi/Lỗ (%)":  "Lãi/Lỗ (%)",
    "Profile":      "Profile",
    "MoreLogin":    "MoreLogin"
}
if rows:
    df = pd.DataFrame(rows)
    df = df.sort_values(sort_map[sort_col], ascending=(sort_col != "Lãi/Lỗ (%)"))
else:
    df = pd.DataFrame()

# Thống kê nhanh
st.divider()
m1, m2, m3, m4 = st.columns(4)
if not df.empty:
    open_trades  = df[df["is_closed"] == False]
    closed_trades = df[df["is_closed"] == True]
    total_pnl    = open_trades["Lãi/Lỗ (USDT)"].sum() if not open_trades.empty else 0
    m1.metric("📊 Tổng giao dịch", len(df))
    m2.metric("📈 Đang mở", len(open_trades))
    m3.metric("🔒 Đã chốt", len(closed_trades))
    color = "normal" if total_pnl >= 0 else "inverse"
    m4.metric("💰 Tổng P&L (USDT)", f"${total_pnl:+.2f}", delta_color=color)
else:
    m1.metric("📊 Tổng giao dịch", 0)
    m2.metric("📈 Đang mở", 0)
    m3.metric("🔒 Đã chốt", 0)
    m4.metric("💰 Tổng P&L (USDT)", "$0.00")

st.divider()

# Bảng dữ liệu
if df.empty:
    st.info("Chưa có giao dịch nào. Thêm giao dịch mới ở thanh bên trái.")
else:
    display_cols = ["Coin","Vị thế","Profile","MoreLogin","Email",
                    "Giá vào","Giá hiện tại","USDT","Đòn bẩy",
                    "Lãi/Lỗ (%)","Lãi/Lỗ (USDT)","Trạng thái","Ghi chú","Thời gian"]
    
    def color_pnl(val):
        if isinstance(val, float):
            if val > 3:   return "color: #198754; font-weight:bold"
            if val < -3:  return "color: #dc3545; font-weight:bold"
        return ""
    
    styled = df[display_cols].style\
        .map(color_pnl, subset=["Lãi/Lỗ (%)","Lãi/Lỗ (USDT)"])
    
    st.dataframe(styled, use_container_width=True, height=420, hide_index=True)

    st.divider()

    # ─── Hành động theo dòng ──────────────────────────────────────────────────
    st.subheader("⚡ Hành động nhanh")
    action_col1, action_col2 = st.columns(2)

    with action_col1:
        st.markdown("**🔒 Chốt giao dịch**")
        open_ids = df[df["is_closed"] == False]["_id"].tolist()
        open_labels = []
        for _, r in df[df["is_closed"] == False].iterrows():
            open_labels.append(f"Profile {r['Profile']} | {r['Coin']} {r['Vị thế']} | {r['MoreLogin']}")
        
        if open_ids:
            sel_close = st.selectbox("Chọn để chốt", open_labels, key="sel_close")
            if st.button("🔒 Chốt", type="primary", key="btn_close"):
                idx    = open_labels.index(sel_close)
                tid    = ObjectId(open_ids[idx])
                trade  = collection.find_one({"_id": tid})
                price  = get_coin_price(trade["coin"]) or trade["current_price"]
                pct    = calc_profit_pct(trade["entry_price"], price, trade["position"], trade.get("leverage",10))
                pusdt  = calc_profit_usdt(pct, trade.get("usdt_amount",50))
                txt    = f"lời ${pusdt:.2f}" if pusdt >= 0 else f"lỗ ${abs(pusdt):.2f}"
                collection.update_one({"_id": tid}, {"$set": {
                    "current_price":  price,
                    "profit_percent": pct,
                    "note":           f"🔒 Đã chốt: {txt} ({pct:+.2f}%)",
                    "is_closed":      True,
                    "closed_at":      datetime.now(),
                    "updated_at":     datetime.now()
                }})
                st.success(f"Đã chốt! {txt}")
                st.rerun()
        else:
            st.info("Không có giao dịch đang mở.")

    with action_col2:
        st.markdown("**🗑️ Xóa giao dịch**")
        all_ids    = df["_id"].tolist()
        all_labels = []
        for _, r in df.iterrows():
            all_labels.append(f"Profile {r['Profile']} | {r['Coin']} {r['Vị thế']} | {r['MoreLogin']}")
        
        if all_ids:
            sel_del = st.selectbox("Chọn để xóa", all_labels, key="sel_del")
            if st.button("🗑️ Xóa", key="btn_del"):
                idx = all_labels.index(sel_del)
                collection.delete_one({"_id": ObjectId(all_ids[idx])})
                st.success("Đã xóa!")
                st.rerun()

    # ─── Sửa giao dịch ────────────────────────────────────────────────────────
    st.divider()
    with st.expander("✏️ Sửa giao dịch"):
        edit_labels = []
        for _, r in df.iterrows():
            edit_labels.append(f"Profile {r['Profile']} | {r['Coin']} {r['Vị thế']} | {r['MoreLogin']}")
        
        if edit_labels:
            sel_edit = st.selectbox("Chọn để sửa", edit_labels, key="sel_edit")
            e_idx    = edit_labels.index(sel_edit)
            e_row    = df.iloc[e_idx]
            e_id     = ObjectId(df.iloc[e_idx]["_id"])

            c1, c2, c3 = st.columns(3)
            with c1:
                e_coin   = st.text_input("Coin",      value=e_row["Coin"],          key="e_coin")
                e_pos    = st.selectbox("Vị thế",     ["LONG","SHORT"],
                                        index=0 if e_row["Vị thế"]=="LONG" else 1, key="e_pos")
                e_prof   = st.number_input("Profile", value=int(e_row["Profile"]),  key="e_prof")
            with c2:
                e_ml     = st.text_input("MoreLogin", value=str(e_row["MoreLogin"]),key="e_ml")
                e_entry  = st.number_input("Giá vào", value=float(e_row["Giá vào"]),key="e_entry", format="%.5f")
                e_usdt   = st.number_input("USDT",    value=float(e_row["USDT"]),   key="e_usdt")
            with c3:
                e_lev    = st.number_input("Đòn bẩy", value=int(e_row["Đòn bẩy"]), key="e_lev")
                e_note   = st.text_input("Ghi chú",   value=str(e_row["Ghi chú"]), key="e_note")

            if st.button("💾 Lưu thay đổi", type="primary"):
                collection.update_one({"_id": e_id}, {"$set": {
                    "coin":           e_coin.upper().strip(),
                    "position":       e_pos,
                    "profile_number": int(e_prof),
                    "morelogin":      e_ml.strip(),
                    "entry_price":    float(e_entry),
                    "usdt_amount":    float(e_usdt),
                    "leverage":       int(e_lev),
                    "note":           e_note,
                    "updated_at":     datetime.now()
                }})
                st.success("✅ Đã lưu!")
                st.rerun()

    # ─── Profiles chưa đánh ───────────────────────────────────────────────────
    st.divider()
    with st.expander("🔍 Profiles chưa đánh"):
        if st.button("Kiểm tra profiles chưa đánh"):
            pipeline = [
                {"$match": {
                    "profile_number": {"$exists": True, "$ne": None},
                    "morelogin":      {"$exists": True, "$nin": [None, ""]}
                }},
                {"$group": {
                    "_id": {"profile_number": "$profile_number", "morelogin": "$morelogin"},
                    "doc_count":  {"$sum": 1},
                    "coin_count": {"$sum": {"$cond": [
                        {"$and": [{"$ifNull":["$coin",False]}, {"$ne":["$coin",""]}]}, 1, 0
                    ]}}
                }},
                {"$match": {"coin_count": 0}},
                {"$sort":  {"_id.profile_number": 1}}
            ]
            untraded = list(collection.aggregate(pipeline))
            if untraded:
                rows_ut = [{"Profile": u["_id"]["profile_number"],
                            "MoreLogin": u["_id"]["morelogin"],
                            "Số docs": u["doc_count"]} for u in untraded]
                st.dataframe(pd.DataFrame(rows_ut), use_container_width=True, hide_index=True)
                st.info(f"Tổng: {len(untraded)} profiles chưa đánh")
            else:
                st.success("✅ Tất cả profiles đều đã được đánh!")
