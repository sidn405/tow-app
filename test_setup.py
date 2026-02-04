"""
Test if all critical imports work
Run this to verify your installation
"""
import sys

def test_import(module_name, package_name=None):
    """Test if a module can be imported"""
    try:
        __import__(module_name)
        print(f"✅ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name}: {e}")
        return False

def main():
    print("=" * 60)
    print("TowTruck Platform - Setup Verification")
    print("=" * 60)
    print("\nTesting required packages...\n")

    # Required packages
    required = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("sqlalchemy", "SQLAlchemy"),
        ("asyncpg", "AsyncPG"),
        ("pydantic", "Pydantic"),
        ("jose", "python-jose"),
        ("passlib", "Passlib"),
        ("stripe", "Stripe"),
        ("redis", "Redis"),
        ("dotenv", "python-dotenv"),
    ]

    results = []
    for module, name in required:
        results.append(test_import(module, name))

    print("\n" + "-" * 60)
    print("Optional packages (for full functionality):")
    print("-" * 60 + "\n")
    
    # Optional packages
    optional = [
        ("geoalchemy2", "GeoAlchemy2 (for geographic search)"),
        ("shapely", "Shapely (for geographic calculations)"),
        ("resend", "Resend (for email)"),
        ("openai", "OpenAI (for AI features)"),
        ("twilio", "Twilio (for SMS)"),
        ("firebase_admin", "Firebase Admin (for push notifications)"),
    ]

    for module, name in optional:
        test_import(module, name)

    print("\n" + "=" * 60)
    print(f"Result: {sum(results)}/{len(results)} required packages working")
    print("=" * 60)

    if all(results):
        print("\n🎉 All required packages installed successfully!")
        print("\nYou can now run:")
        print("  python init_db.py")
        print("  uvicorn app.main:app --reload")
    else:
        print("\n⚠️  Some required packages failed.")
        print("\nPlease install missing packages:")
        print("  pip install -r requirements.txt")
        print("\nOr for Windows-specific fixes, see:")
        print("  WINDOWS_SETUP.md")

    # Test app imports
    print("\n" + "-" * 60)
    print("Testing application imports...")
    print("-" * 60 + "\n")
    
    try:
        from app.config import settings
        print("✅ app.config")
    except Exception as e:
        print(f"❌ app.config: {e}")
    
    try:
        from app.database import Base
        print("✅ app.database")
    except Exception as e:
        print(f"❌ app.database: {e}")
    
    try:
        from app.models import User, Driver, TowRequest
        print("✅ app.models")
    except Exception as e:
        print(f"❌ app.models: {e}")
    
    try:
        from app.schemas import UserCreate, TowRequestCreate
        print("✅ app.schemas")
    except Exception as e:
        print(f"❌ app.schemas: {e}")
    
    try:
        from app.services import AuthService, PricingService
        print("✅ app.services")
    except Exception as e:
        print(f"❌ app.services: {e}")

    print("\n" + "=" * 60)
    print("Setup verification complete!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
