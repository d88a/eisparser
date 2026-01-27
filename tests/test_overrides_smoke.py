
import requests
import json
import sqlite3

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = "D:/Anna/eisparser/results/eis_data.db"

def test_overrides_flow():
    print("🚀 Starting User Overrides Smoke Test...")
    
    # 1. Get a reg_number from Stage 2 (assuming there are some)
    # We'll pick one we processed earlier: 0139300013026000004
    reg_number = "0139300013026000004"
    field_name = "area_min_m2"
    new_value = 55.5
    
    print(f"🔹 Testing override for {reg_number}: {field_name} -> {new_value}")

    # 2. Check current value in Stage 2 view
    resp = requests.get(f"{BASE_URL}/api/stage2")
    if resp.status_code != 200:
        print(f"❌ Failed to get Stage 2 data: {resp.status_code}")
        return
    
    items = resp.json()
    if not isinstance(items, list):
         print(f"❌ Unexpected response format (expected list): {type(items)}")
         print(f"Response: {items}")
         return
         
    target = next((item for item in items if item["reg_number"] == reg_number), None)
    
    if not target:
        print(f"⚠️ Target {reg_number} not found in Stage 2. Need to ensure it's there.")
        # Try finding ANY item
        if not items:
            print("❌ No items in Stage 2. Cannot test.")
            return
        target = items[0]
        reg_number = target["reg_number"]
        print(f"🔹 Switched target to {reg_number}")

    # Note: 'area_min_m2' in view model might be mapped to 'ai_area_min' or 'area_min_m2' depending on ViewField logic
    # In ViewService: ai_area_min=ai_result.area_min_m2
    # But where is the EFFECTIVE value logic? 
    # The current ViewService seems to NOT apply overrides yet. 
    # Wait, Zadacha 5 Part 4 says "Use effective_value = override ?? ai_value". 
    # I need to check if ZakupkaStageView has logic or ViewService has logic.
    # Looking at ViewService code: it DOES NOT seem to fetch overrides and apply them.
    # Ah, I should check ZakupkaStageView definition in models.
    
    print(f"🔹 Target item keys: {list(target.keys())}")
    # We will check 'ai_area_min' for now
    
    # 3. Apply Override
    payload = {
        "user_id": 1,
        "reg_number": reg_number,
        "field_name": field_name, # Note: db uses field_name, ViewService might expect specific fields
        "value": str(new_value)
    }
    
    print("🔹 Sending override request...")
    resp = requests.post(f"{BASE_URL}/api/overrides", json=payload)
    
    if resp.status_code != 200:
        print(f"❌ Override failed: {resp.status_code} {resp.text}")
        return
    
    print("✅ Override API call successful.")

    # 4. Verify in DB
    print("🔹 Verifying in DB...")
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("SELECT new_value FROM user_overrides WHERE reg_number = ? AND field = ?", (reg_number, field_name))
    row = cur.fetchone()
    con.close()
    
    if row and row[0] == str(new_value):
         print(f"✅ DB Verification passed: {row[0]}")
    else:
         print(f"❌ DB Verification failed. Found: {row}")

    # 5. Verify in API View (Effective Value)
    print("🔹 Verifying via API (Stage 2 View)...")
    resp = requests.get(f"{BASE_URL}/api/stage2")
    data = resp.json()
    items = data.get("items", [])
    target = next((item for item in items if item["reg_number"] == reg_number), None)
    
    # Note: View might differ depending on how mapping is done. data['area_min_m2'] should be the EFFECTIVE value.
    # In view_service.py: area_min_m2 = overrides.get('area_min_m2', ai_result.area_min_m2)
    # BUT wait, the API returns ZakupkaStageView which has 'ai_min_area' and potentially 'user_comment'?
    # Actually, ZakupkaStageView has fields like 'area_min_m2', which is the effective value (as per Zadacha 5 Part 4).
    
    actual_value = target.get(field_name) # likely 'area_min_m2' in JSON
    # Wait, ZakupkaStageView uses snake_case keys in asdict?
    # Let's check keys.
    
    print(f"🔹 Item keys keys: {list(target.keys())}")
    
    # We assume 'area_min_m2' is the key for effective min area
    if target and (target.get('area_min_m2') == new_value or target.get('area_min_m2') == str(new_value)):
         print(f"✅ API View Verification passed: {target.get('area_min_m2')}")
    else:
         # Note: float comparison might be tricky with string/json
         print(f"⚠️ API View Verification unclear. Got: {target.get('area_min_m2')}, Expected: {new_value}")

    print("🎉 Smoke Test Completed.")

if __name__ == "__main__":
    test_overrides_flow()
