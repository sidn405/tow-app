#!/usr/bin/env python3
"""
Populate lookup tables for vehicle types, service types, and tow reasons
Run with: python populate_lookup_tables.py
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Get database URL from environment variable or set it here
DATABASE_URL = ""

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not set!")
    print("Set it at the top of this file or as environment variable")
    exit(1)

def add_missing_columns(cursor, conn):
    """Add missing columns to lookup tables"""
    
    print("🔧 Adding missing columns to lookup tables...")
    print()
    
    try:
        # Add is_active to customer_vehicle_types
        cursor.execute("""
            ALTER TABLE customer_vehicle_types 
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        """)
        print("  ✅ Added is_active to customer_vehicle_types")
        
        # Add requires_flatbed to service_types
        cursor.execute("""
            ALTER TABLE service_types 
            ADD COLUMN IF NOT EXISTS requires_flatbed BOOLEAN DEFAULT FALSE;
        """)
        print("  ✅ Added requires_flatbed to service_types")
        
        # Add requires_urgent_response to tow_reasons
        cursor.execute("""
            ALTER TABLE tow_reasons 
            ADD COLUMN IF NOT EXISTS requires_urgent_response BOOLEAN DEFAULT FALSE;
        """)
        print("  ✅ Added requires_urgent_response to tow_reasons")
        
        # Add is_active to service_types
        cursor.execute("""
            ALTER TABLE service_types 
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        """)
        print("  ✅ Added is_active to service_types")
        
        # Add is_active to tow_reasons
        cursor.execute("""
            ALTER TABLE tow_reasons 
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
        """)
        print("  ✅ Added is_active to tow_reasons")
        
        conn.commit()
        print()
        
    except Exception as e:
        print(f"  ❌ Error adding columns: {e}")
        conn.rollback()

def populate_vehicle_types(cursor, conn):
    """Populate CustomerVehicleType table"""
    
    vehicle_types = [
        ('sedan', 'Sedan / Coupe', 1.0),
        ('suv', 'SUV / Crossover', 1.3),
        ('truck', 'Pickup Truck', 1.3),
        ('van', 'Van / Minivan', 1.3),
        ('luxury', 'Luxury / High-End Vehicle', 1.5),
        ('exotic', 'Exotic / Supercar', 2.5),
        ('motorcycle', 'Motorcycle', 0.9),
        ('rv', 'RV / Motor Home', 2.0),
        ('large_truck', 'Large Truck / Commercial', 2.5),
    ]
    
    print("📝 Populating vehicle types...")
    
    for name, description, multiplier in vehicle_types:
        try:
            cursor.execute("""
                INSERT INTO customer_vehicle_types (id, name, description, price_multiplier, is_active)
                VALUES (%s, %s, %s, %s, true)
                ON CONFLICT (name) DO UPDATE 
                SET description = EXCLUDED.description,
                    price_multiplier = EXCLUDED.price_multiplier;
            """, (str(uuid.uuid4()), name, description, multiplier))
            
            print(f"  ✅ {name}: {description} (multiplier: {multiplier}x)")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    conn.commit()
    return cursor, conn

def populate_service_types(cursor, conn):
    """Populate ServiceType table"""
    
    service_types = [
        ('standard_tow', 'Standard Tow Service', 75.00, 3.50, 5, False),
        ('flatbed_tow', 'Flatbed Tow Service', 125.00, 4.50, 5, True),
        ('motorcycle_tow', 'Motorcycle Tow', 100.00, 3.00, 5, False),
        ('heavy_duty_tow', 'Heavy Duty Tow', 200.00, 6.00, 5, True),
        ('long_distance_tow', 'Long Distance Tow', 150.00, 3.00, 50, False),
    ]
    
    print("\n📝 Populating service types...")
    
    for name, description, base, per_mile, included, flatbed in service_types:
        try:
            cursor.execute("""
                INSERT INTO service_types (id, name, description, base_price, per_mile_rate, included_miles, requires_flatbed, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (name) DO UPDATE
                SET description = EXCLUDED.description,
                    base_price = EXCLUDED.base_price,
                    per_mile_rate = EXCLUDED.per_mile_rate,
                    included_miles = EXCLUDED.included_miles,
                    requires_flatbed = EXCLUDED.requires_flatbed;
            """, (str(uuid.uuid4()), name, description, base, per_mile, included, flatbed))
            
            print(f"  ✅ {name}: ${base} + ${per_mile}/mi (flatbed: {flatbed})")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    conn.commit()
    return cursor, conn

def populate_tow_reasons(cursor, conn):
    """Populate TowReason table"""
    
    tow_reasons = [
        ('breakdown', 'Breakdown / Mechanical Issue', 0, True),
        ('flat_tire', 'Flat Tire', -10, True),
        ('accident', 'Accident', 50, True),
        ('out_of_gas', 'Out of Gas', -15, True),
        ('dead_battery', 'Dead Battery', -15, True),
        ('relocation', 'Vehicle Relocation', 0, False),
        ('other', 'Other', 0, False),
    ]
    
    print("\n📝 Populating tow reasons...")
    
    for name, description, adjustment, urgent in tow_reasons:
        try:
            cursor.execute("""
                INSERT INTO tow_reasons (id, name, description, price_adjustment, requires_urgent_response, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (name) DO UPDATE
                SET description = EXCLUDED.description,
                    price_adjustment = EXCLUDED.price_adjustment,
                    requires_urgent_response = EXCLUDED.requires_urgent_response;
            """, (str(uuid.uuid4()), name, description, adjustment, urgent))
            
            adjustment_str = f"+${adjustment}" if adjustment > 0 else f"${adjustment}" if adjustment < 0 else "$0"
            print(f"  ✅ {name}: {adjustment_str} (urgent: {urgent})")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    conn.commit()
    return cursor, conn

def verify_data(cursor):
    """Verify lookup tables were populated"""
    
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    cursor.execute("SELECT COUNT(*) as count FROM customer_vehicle_types")
    count = cursor.fetchone()['count']
    print(f"\n✅ Vehicle Types: {count} records")
    
    cursor.execute("SELECT COUNT(*) as count FROM service_types")
    count = cursor.fetchone()['count']
    print(f"✅ Service Types: {count} records")
    
    cursor.execute("SELECT COUNT(*) as count FROM tow_reasons")
    count = cursor.fetchone()['count']
    print(f"✅ Tow Reasons: {count} records")

try:
    print("=" * 60)
    print("FIX & POPULATE LOOKUP TABLES")
    print("=" * 60)
    print()
    print("🔗 Connecting to database...")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("✓ Connected successfully")
    print()
    
    # First, add missing columns
    add_missing_columns(cursor, conn)
    
    # Then populate data
    cursor, conn = populate_vehicle_types(cursor, conn)
    cursor, conn = populate_service_types(cursor, conn)
    cursor, conn = populate_tow_reasons(cursor, conn)
    
    verify_data(cursor)
    
    print("\n" + "=" * 60)
    print("✅ All lookup tables fixed and populated!")
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

