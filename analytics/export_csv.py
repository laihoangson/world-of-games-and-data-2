import os
import csv
import psycopg2
from dotenv import load_dotenv

# Load configuration from .env file (Ensure .env contains the external DATABASE_URL)
load_dotenv()

def export_db_to_csv(csv_file_path):
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("❌ Error: DATABASE_URL not found. Please check your .env file.")
        return

    try:
        print("⏳ Connecting to Render PostgreSQL to export data...")
        conn = psycopg2.connect(db_url)
        c = conn.cursor()
        
        # Fetch all data from the game_sessions table
        c.execute('SELECT * FROM game_sessions')
        rows = c.fetchall()
        
        if not rows:
            print("⚠️ The database is empty. No data to export.")
            conn.close()
            return

        # Dynamically get column names from the cursor description
        colnames = [desc[0] for desc in c.description]
        
        # Ensure the target directory exists before writing
        os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
        
        # Write data to the CSV file
        with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(colnames)  # Write headers
            writer.writerows(rows)     # Write all rows
            
        conn.close()
        print(f"✅ Success! Exported {len(rows)} game sessions from PostgreSQL to {csv_file_path}")

    except Exception as e:
        print(f"❌ An error occurred during export: {e}")

if __name__ == '__main__':
    # Automatically get the absolute path of the current script's directory (analytics)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the CSV file (go up one directory from analytics, then into csv_export)
    csv_path = os.path.join(current_dir, '..', 'csv_export', 'game_sessions.csv')
    
    # Normalize the path format for your specific operating system
    csv_path = os.path.normpath(csv_path)
    
    export_db_to_csv(csv_path)