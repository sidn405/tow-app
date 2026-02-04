"""
Comprehensive Import and Syntax Checker
Checks all Python files for import errors before running the app
"""
import os
import sys
from pathlib import Path
import ast

def check_file_syntax(filepath):
    """Check if a Python file has valid syntax"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_imports(filepath):
    """Check if all imports in a file are available"""
    errors = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                for alias in node.names:
                    try:
                        # Try to import
                        __import__(module)
                    except ImportError:
                        errors.append(f"Cannot import {module}")
                        
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    try:
                        __import__(alias.name)
                    except ImportError:
                        errors.append(f"Cannot import {alias.name}")
    except Exception as e:
        errors.append(f"Error checking imports: {e}")
    
    return errors

def main():
    """Check all Python files in the app directory"""
    print("=" * 70)
    print("TowTruck Platform - Pre-Flight Check")
    print("=" * 70)
    print("\nChecking Python files for errors...\n")
    
    backend_dir = Path(__file__).parent
    app_dir = backend_dir / "app"
    
    if not app_dir.exists():
        print("❌ app directory not found!")
        return False
    
    # Collect all Python files
    python_files = list(app_dir.rglob("*.py"))
    
    syntax_errors = []
    import_errors = []
    
    # Check each file
    for filepath in python_files:
        relative_path = filepath.relative_to(backend_dir)
        
        # Check syntax
        valid, error = check_file_syntax(filepath)
        if not valid:
            syntax_errors.append((relative_path, error))
            print(f"❌ SYNTAX ERROR: {relative_path}")
            print(f"   {error}\n")
        else:
            print(f"✅ {relative_path}")
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if syntax_errors:
        print(f"\n❌ {len(syntax_errors)} file(s) with syntax errors:\n")
        for filepath, error in syntax_errors:
            print(f"   {filepath}")
            print(f"   → {error}\n")
    else:
        print("\n✅ All files have valid Python syntax!")
    
    print(f"\nTotal files checked: {len(python_files)}")
    
    # Check for common issues
    print("\n" + "-" * 70)
    print("Checking for common issues...")
    print("-" * 70 + "\n")
    
    issues_found = False
    
    # Check for missing __init__.py files
    directories = [d for d in app_dir.rglob("*") if d.is_dir() and not d.name.startswith('__')]
    for directory in directories:
        init_file = directory / "__init__.py"
        if not init_file.exists():
            print(f"⚠️  Missing __init__.py in: {directory.relative_to(backend_dir)}")
            issues_found = True
    
    if not issues_found:
        print("✅ All directories have __init__.py files")
    
    # Check specific imports
    print("\n" + "-" * 70)
    print("Checking critical imports...")
    print("-" * 70 + "\n")
    
    critical_imports = [
        ("fastapi", "FastAPI"),
        ("sqlalchemy", "SQLAlchemy"),
        ("pydantic", "Pydantic"),
        ("stripe", "Stripe"),
        ("jose", "python-jose"),
    ]
    
    all_imports_ok = True
    for module, name in critical_imports:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} - Not installed!")
            all_imports_ok = False
    
    # Check if settings can be imported
    print("\n" + "-" * 70)
    print("Checking app imports...")
    print("-" * 70 + "\n")
    
    sys.path.insert(0, str(backend_dir))
    
    app_imports = [
        ("app.config", "settings"),
        ("app.database", "Base"),
        ("app.models", "User"),
        ("app.schemas", "UserCreate"),
        ("app.services", "AuthService"),
    ]
    
    for module, obj in app_imports:
        try:
            mod = __import__(module, fromlist=[obj])
            getattr(mod, obj)
            print(f"✅ {module}.{obj}")
        except Exception as e:
            print(f"❌ {module}.{obj} - {str(e)[:50]}")
            all_imports_ok = False
    
    # Final summary
    print("\n" + "=" * 70)
    print("FINAL RESULT")
    print("=" * 70 + "\n")
    
    if not syntax_errors and all_imports_ok:
        print("🎉 ALL CHECKS PASSED!")
        print("\nYou can now run:")
        print("  python init_db.py")
        print("  uvicorn app.main:app --reload\n")
        return True
    else:
        print("⚠️  ISSUES FOUND - Please fix the errors above\n")
        if syntax_errors:
            print("Syntax errors need to be fixed first.")
        if not all_imports_ok:
            print("Missing dependencies - run: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
