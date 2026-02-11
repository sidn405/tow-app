#!/usr/bin/env python3
"""
Add vehicle detail fields to TowRequest table
Run with: python add_vehicle_fields.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Get database URL from environment variable or set it here
DATABASE_URL = ""

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not set!")
    print("Set it at the top of this file or as environment variable")
    exit(1)

try:
    print("=" * 60)
    print("DATABASE MIGRATION: Add Vehicle Detail Fields")
    print("=" * 60)
    print()
    print("🔗 Connecting to database...")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("✓ Connected successfully")
    print()
    
    migrations = [
        # Add boolean fields for special vehicle requirements
        """
        ALTER TABLE tow_requests 
        ADD COLUMN IF NOT EXISTS is_awd BOOLEAN DEFAULT FALSE;
        """,
        
        """
        ALTER TABLE tow_requests 
        ADD COLUMN IF NOT EXISTS is_lowered BOOLEAN DEFAULT FALSE;
        """,
        
        """
        ALTER TABLE tow_requests 
        ADD COLUMN IF NOT EXISTS is_damaged BOOLEAN DEFAULT FALSE;
        """,
    ]
    
    print("Starting database migration...")
    print()
    
    for i, migration in enumerate(migrations, 1):
        try:
            cursor.execute(migration)
            conn.commit()
            print(f"✅ Migration {i}/{len(migrations)} completed")
        except Exception as e:
            print(f"❌ Migration {i} failed: {e}")
            conn.rollback()
    
    print()
    print("✅ All migrations completed!")
    print()
    
    # Verify the new fields were added
    print("🔍 Verifying new columns...")
    print()
    
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'tow_requests'
        AND column_name IN ('is_awd', 'is_lowered', 'is_damaged')
        ORDER BY column_name;
    """)
    
    rows = cursor.fetchall()
    
    if rows:
        print("✅ VERIFICATION - New columns added:")
        print("-" * 80)
        print(f"{'COLUMN':<20} {'TYPE':<20} {'NULLABLE':<10} {'DEFAULT':<20}")
        print("-" * 80)
        for row in rows:
            nullable = "YES" if row['is_nullable'] == 'YES' else "NO"
            default = str(row['column_default'])[:20] if row['column_default'] else '-'
            print(f"{row['column_name']:<20} {row['data_type']:<20} {nullable:<10} {default:<20}")
    else:
        print("⚠️  Warning: Could not verify new columns")
    
    print()
    print("=" * 60)
    print("Migration complete! You can now accept vehicle details from frontend.")
    print("=" * 60)
    
    cursor.close()
    conn.close()

except psycopg2.Error as e:
    print(f"❌ Database error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
