import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def clear_database():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ Error: DATABASE_URL not found.")
        return

    try:
        print("⏳ Connecting to clear data...")
        conn = psycopg2.connect(db_url)
        c = conn.cursor()
        
        # The TRUNCATE command empties the table completely and extremely fast
        c.execute('TRUNCATE TABLE game_sessions;')
        
        conn.commit()
        conn.close()
        print("🧹 Successfully cleared all data in the Render database!")
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == '__main__':
    clear_database()