import os
import csv
import uuid
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# Load configuration from .env file (Ensure .env contains the external DATABASE_URL)
load_dotenv()

def import_csv_to_db(csv_file_path):
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ Error: DATABASE_URL not found. Please check your .env file.")
        return

    try:
        print("⏳ Connecting to Render PostgreSQL...")
        conn = psycopg2.connect(db_url)
        c = conn.cursor()
        
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            success_count = 0
            for row in reader:
                # Generate a random ID if the CSV file doesn't have an 'id' column
                game_id = row.get('id', str(uuid.uuid4()))
                start_time = row.get('start_time', datetime.now().isoformat())
                end_time = row.get('end_time', datetime.now().isoformat())
                
                # Extract data from CSV, default to 0 if empty
                score = int(row.get('score', 0))
                coins = int(row.get('coins_collected', 0))
                ufos = int(row.get('ufos_shot', 0))
                bullets = int(row.get('bullets_fired', 0))
                duration = int(row.get('game_duration', 0))
                pipes = int(row.get('pipes_passed', 0))
                death = row.get('death_reason', 'unknown')

                # Insert each row into the database
                c.execute('''
                    INSERT INTO game_sessions 
                    (id, start_time, end_time, score, coins_collected, ufos_shot, bullets_fired, death_reason, game_duration, pipes_passed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                ''', (game_id, start_time, end_time, score, coins, ufos, bullets, death, duration, pipes))
                
                success_count += 1

        conn.commit()
        conn.close()
        print(f"✅ Success! Imported {success_count} game sessions from CSV to Render PostgreSQL.")

    except Exception as e:
        print(f"❌ An error occurred during import: {e}")

if __name__ == '__main__':
    # Automatically get the absolute path of the current script's directory (analytics)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the CSV file (go up one directory from analytics, then into csv_export)
    csv_path = os.path.join(current_dir, '..', 'csv_export', 'game_sessions.csv')
    
    # Normalize the path format for your specific operating system
    csv_path = os.path.normpath(csv_path)
    
    if os.path.exists(csv_path):
        import_csv_to_db(csv_path)
    else:
        print(f"❌ File not found at: {csv_path}")