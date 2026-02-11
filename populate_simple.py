#!/usr/bin/env python3
"""
Simple populate - just INSERT without ON CONFLICT
Run with: python populate_simple.py
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

DATABASE_URL = ""

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not set!")
    exit(1)

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
            # Check if it already exists
            cursor.execute("SELECT id FROM customer_vehicle_types WHERE name = %s", (name,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"  ⏭️  {name} already exists, skipping")
            else:
                cursor.execute("""
                    INSERT INTO customer_vehicle_types (id, name, description, price_multiplier, is_active)
                    VALUES (%s, %s, %s, %s, true)
                """, (str(uuid.uuid4()), name, description, multiplier))
                conn.commit()
                print(f"  ✅ {name}: {description} (multiplier: {multiplier}x)")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()

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
            # Check if it already exists
            cursor.execute("SELECT id FROM service_types WHERE name = %s", (name,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"  ⏭️  {name} already exists, skipping")
            else:
                cursor.execute("""
                    INSERT INTO service_types (id, name, description, base_price, per_mile_rate, included_miles, requires_flatbed, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                """, (str(uuid.uuid4()), name, description, base, per_mile, included, flatbed))
                conn.commit()
                print(f"  ✅ {name}: ${base} + ${per_mile}/mi (flatbed: {flatbed})")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()

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
            # Check if it already exists
            cursor.execute("SELECT id FROM tow_reasons WHERE name = %s", (name,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"  ⏭️  {name} already exists, skipping")
            else:
                cursor.execute("""
                    INSERT INTO tow_reasons (id, name, description, price_adjustment, requires_urgent_response, is_active)
                    VALUES (%s, %s, %s, %s, %s, true)
                """, (str(uuid.uuid4()), name, description, adjustment, urgent))
                conn.commit()
                adjustment_str = f"+${adjustment}" if adjustment > 0 else f"${adjustment}" if adjustment < 0 else "$0"
                print(f"  ✅ {name}: {adjustment_str} (urgent: {urgent})")
        
        except Exception as e:
            print(f"  ❌ Failed to add {name}: {e}")
            conn.rollback()

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
    
    # Show what was inserted
    print("\n" + "="*60)
    print("VEHICLE TYPES INSERTED:")
    print("="*60)
    cursor.execute("SELECT name, description, price_multiplier FROM customer_vehicle_types ORDER BY price_multiplier")
    for row in cursor.fetchall():
        print(f"  {row['name']:<15} {row['description']:<40} {row['price_multiplier']}x")
    
    print("\n" + "="*60)
    print("SERVICE TYPES INSERTED:")
    print("="*60)
    cursor.execute("SELECT name, base_price, per_mile_rate, requires_flatbed FROM service_types ORDER BY base_price")
    for row in cursor.fetchall():
        flatbed = "✅" if row['requires_flatbed'] else "❌"
        print(f"  {row['name']:<20} ${row['base_price']:<6} + ${row['per_mile_rate']}/mi  Flatbed: {flatbed}")

try:
    print("=" * 60)
    print("POPULATE LOOKUP TABLES (Simple)")
    print("=" * 60)
    print()
    print("🔗 Connecting to database...")
    
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("✓ Connected successfully")
    print()
    
    populate_vehicle_types(cursor, conn)
    populate_service_types(cursor, conn)
    populate_tow_reasons(cursor, conn)
    
    verify_data(cursor)
    
    print("\n" + "=" * 60)
    print("✅ Done! Lookup tables populated!")
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