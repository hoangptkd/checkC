# 📈 Coin Trading Tracker - Hướng dẫn Deploy

## Cấu trúc thư mục
```
coin_tracker/
├── app.py                    ← Code chính
├── requirements.txt          ← Thư viện cần thiết
├── .gitignore                ← Bảo vệ secrets
└── .streamlit/
    └── secrets.toml          ← Cấu hình MongoDB (KHÔNG upload lên GitHub)
```

---

## 🖥️ Chạy LOCAL (kiểm tra trước)

### Bước 1: Cài thư viện
```bash
pip install -r requirements.txt
```

### Bước 2: Cấu hình MongoDB
Tạo file `.streamlit/secrets.toml`:
```toml
MONGO_URI = "mongodb+srv://<user>:<password>@<cluster>.mongodb.net/..."
```

### Bước 3: Chạy app
```bash
streamlit run app.py
```
Mở trình duyệt: http://localhost:8501

---

## ☁️ Deploy lên Streamlit Cloud (MIỄN PHÍ)

### Bước 1: Tạo tài khoản GitHub
Vào https://github.com → Đăng ký (miễn phí)

### Bước 2: Tạo repository mới
1. Click **New repository**
2. Đặt tên: `coin-tracker`
3. Chọn **Public** (bắt buộc để dùng Streamlit Cloud free)
4. Click **Create repository**

### Bước 3: Push code lên GitHub
```bash
# Trong thư mục coin_tracker/
git init
git add app.py requirements.txt .gitignore
# ⚠️ KHÔNG add .streamlit/secrets.toml
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<username>/coin-tracker.git
git push -u origin main
```

### Bước 4: Deploy trên Streamlit Cloud
1. Vào https://share.streamlit.io
2. Đăng nhập bằng GitHub
3. Click **New app**
4. Chọn:
   - Repository: `<username>/coin-tracker`
   - Branch: `main`
   - Main file: `app.py`
5. Click **Advanced settings** → **Secrets**
6. Dán nội dung sau vào ô Secrets:
```toml
MONGO_URI = "mongodb+srv://hoangptkdhy_db_user:hoang123@englishvocab.whlrwdl.mongodb.net/?retries=3&w=majority&tlsAllowInvalidCertificates=true"
```
7. Click **Deploy!**

⏳ Chờ 2-3 phút → App sẽ có link dạng:
`https://<username>-coin-tracker-app-xxxx.streamlit.app`

---

## 🔒 Bảo mật MongoDB Atlas

Để app cloud kết nối được MongoDB, cần whitelist IP:
1. Vào https://cloud.mongodb.com
2. Chọn cluster → **Network Access**
3. Click **Add IP Address**
4. Chọn **Allow access from anywhere** (0.0.0.0/0)
5. Click **Confirm**

---

## ✅ Tính năng

| Tính năng | Mô tả |
|---|---|
| Thêm giao dịch | Sidebar bên trái |
| Auto lấy giá | Từ Binance API khi không nhập giá |
| Cập nhật giá | Tự động mỗi 30 phút (st_autorefresh) |
| Chốt tự động | Dựa theo số ngày cấu hình |
| Lọc/Tìm kiếm | Theo Coin, MoreLogin, Trạng thái |
| Sửa inline | Qua form trong expander |
| Màu lãi/lỗ | Xanh > 3%, Đỏ < -3% |
| Thống kê | Tổng P&L, số lượng giao dịch |

---

## ⚠️ Lưu ý quan trọng

- **KHÔNG** commit file `.streamlit/secrets.toml` lên GitHub
- Streamlit Cloud **free** có giới hạn: 1GB RAM, ngủ sau 7 ngày không dùng
- Để app không ngủ: dùng https://uptimerobot.com ping mỗi 25 phút (miễn phí)
