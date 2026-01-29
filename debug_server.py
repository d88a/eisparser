
import sys
import os
from pathlib import Path

# Add src to sys.path just like in app.py
sys.path.insert(0, str(Path("d:/Anna/eisparser/src")))

try:
    from api.app import app
    print("✅ App imported successfully")
    
    print("Registered routes:")
    for route in app.routes:
        print(f"  - {route.path} ({route.name})")

    from api.routes import templates
    print(f"✅ Templates directory: {templates.env.loader.searchpath}")
    
except Exception as e:
    print(f"❌ Error importing app: {e}")
    import traceback
    traceback.print_exc()
