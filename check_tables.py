#!/usr/bin/env python3
"""
Check existing table structures
"""
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = ""

if not DATABASE_URL:
    print("❌ Set DATABASE_URL first!")
    exit(1)

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    tables = ['customer_vehicle_types', 'service_types', 'tow_reasons']
    
    for table in tables:
        print(f"\n{'='*60}")
        print(f"TABLE: {table}")
        print('='*60)
        
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        
        if columns:
            print(f"{'COLUMN':<30} {'TYPE':<20} {'NULLABLE':<10}")
            print('-'*60)
            for col in columns:
                nullable = "YES" if col['is_nullable'] == 'YES' else "NO"
                print(f"{col['column_name']:<30} {col['data_type']:<20} {nullable:<10}")
        else:
            print("Table doesn't exist!")
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()