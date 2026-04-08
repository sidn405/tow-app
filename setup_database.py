"""
Run database setup without needing psql installed
Usage: railway run python setup_database.py
"""

import os
import psycopg2
from psycopg2 import sql

def main():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return
    
    # Read SQL file
    with open('database.sql', 'r') as f:
        sql_content = f.read()
    
    # Connect and execute
    print("Connecting to database...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()
    
    try:
        print("Creating extensions...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        
        print("Creating tables...")
        cursor.execute(sql_content)
        
        print("✅ Database setup complete!")
        
        # Show created tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"\n✅ Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()