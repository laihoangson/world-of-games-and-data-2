import sqlite3
import pandas as pd
import os

DB_FILE = "plane_analytics.db"   # file .db của bạn

def export_all_tables(db_path):
    # Kết nối DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Lấy danh sách tất cả bảng
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]

    if not tables:
        print("❌ Không tìm thấy bảng nào trong database.")
        return

    print("📌 Các bảng tìm thấy:", tables)

    # Tạo thư mục output nếu chưa có
    output_dir = "csv_export"
    os.makedirs(output_dir, exist_ok=True)

    # Xuất từng bảng
    for table in tables:
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        csv_path = os.path.join(output_dir, f"{table}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

        print(f"✔ Đã xuất {table} → {csv_path}")

    conn.close()
    print("\n🎉 Xuất CSV hoàn tất!")

    
if __name__ == "__main__":
    export_all_tables(DB_FILE)
