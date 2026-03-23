"""Test kết nối MongoDB Atlas - chạy xong xóa file này."""
from pymongo import MongoClient
from urllib.parse import quote_plus

# Thử với password gốc (không có @)
user = "hoangptkdhy_db_user"
password = "hoang123"  # password gốc từ file secrets.toml ban đầu

uri = f"mongodb+srv://{quote_plus(user)}:{quote_plus(password)}@englishvocab.whlrwdl.mongodb.net/?retryWrites=true&w=majority"

print(f"Testing connection with user: {user}")
print(f"URI (masked): mongodb+srv://{user}:****@englishvocab.whlrwdl.mongodb.net/...")

try:
    client = MongoClient(uri, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=10000)
    # Force connection test
    db = client["coin_tracker"]
    collections = db.list_collection_names()
    print(f"✅ Kết nối THÀNH CÔNG!")
    print(f"   Database: coin_tracker")
    print(f"   Collections: {collections}")
    count = db["trades"].count_documents({})
    print(f"   Trades count: {count}")
    client.close()
except Exception as e:
    print(f"❌ Kết nối THẤT BẠI: {e}")
    print()
    print("Hãy kiểm tra lại password trong MongoDB Atlas Dashboard:")
    print("  1. Vào https://cloud.mongodb.com")
    print("  2. Database Access > Edit user > Change Password")
