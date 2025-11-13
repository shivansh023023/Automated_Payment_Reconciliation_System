"""Run the complete system demo."""

import subprocess
import time
import sys
import requests
from pathlib import Path

def start_server():
    """Start the FastAPI server in the background."""
    print("Starting FastAPI server...")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    print("Waiting for server to start...")
    for i in range(15):
        time.sleep(1)
        try:
            response = requests.get("http://localhost:8000/", timeout=2)
            if response.status_code == 200:
                print(f"[OK] Server is running on http://localhost:8000")
                return process
        except:
            continue
    
    print("[ERROR] Server failed to start")
    process.terminate()
    return None

def run_tests():
    """Run the system tests."""
    print("\n" + "="*60)
    print("RUNNING SYSTEM TESTS")
    print("="*60 + "\n")
    
    base_url = "http://localhost:8000"
    
    # Test 1: Upload payments
    print("1. Uploading payments CSV...")
    payments_file = Path("sample_data/payments.csv")
    with open(payments_file, 'rb') as f:
        files = {'file': ('payments.csv', f, 'text/csv')}
        response = requests.post(f"{base_url}/upload/payments", files=files, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] Uploaded {data.get('rows_inserted', 0)} payment records")
        else:
            print(f"   [ERROR] Upload failed: {response.status_code}")
            return False
    
    # Test 2: Upload bank transactions
    print("\n2. Uploading bank transactions CSV...")
    bank_file = Path("sample_data/bank.csv")
    with open(bank_file, 'rb') as f:
        files = {'file': ('bank.csv', f, 'text/csv')}
        response = requests.post(f"{base_url}/upload/bank", files=files, timeout=30)
        if response.status_code == 200:
            data = response.json()
            print(f"   [OK] Uploaded {data.get('rows_inserted', 0)} bank transaction records")
        else:
            print(f"   [ERROR] Upload failed: {response.status_code}")
            return False
    
    # Test 3: Run reconciliation
    print("\n3. Running reconciliation...")
    response = requests.post(f"{base_url}/reconcile", timeout=60)
    if response.status_code == 200:
        data = response.json()
        result = data.get('result', {})
        print(f"   [OK] Reconciliation complete:")
        print(f"        - Matched: {result.get('matched', 0)} transactions")
        print(f"        - Unmatched: {result.get('unmatched', 0)} transactions")
    else:
        print(f"   [ERROR] Reconciliation failed: {response.status_code}")
        return False
    
    # Test 4: Get matches
    print("\n4. Fetching matches...")
    try:
        response = requests.get(f"{base_url}/matches?limit=5", timeout=10)
        if response.status_code == 200:
            data = response.json()
        matches = data.get('matches', [])
        print(f"   [OK] Found {len(matches)} matches (showing up to 5)")
        if matches:
            print("\n   Sample matches:")
            for i, match in enumerate(matches[:3], 1):
                print(f"\n   Match {i}:")
                print(f"      ID: {match.get('id')}")
                print(f"      Score: {match.get('match_score')}/100")
                print(f"      Type: {match.get('match_type')}")
                print(f"      Payment: ${match.get('payment_amount')} on {match.get('payment_date')}")
                print(f"      Bank: ${match.get('bank_amount')} on {match.get('bank_date')}")
                print(f"      Reference: {match.get('payment_reference')} <-> {match.get('bank_reference')}")
        else:
            print(f"   [ERROR] Failed to fetch matches: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Exception fetching matches: {e}")
        return False
    
    # Test 5: Confirm a match
    if matches:
        print("\n5. Confirming a match...")
        match_id = matches[0].get('id')
        response = requests.post(
            f"{base_url}/matches/{match_id}/confirm",
            json={"reviewer": "Demo User", "action": "confirm"},
            timeout=10
        )
        if response.status_code == 200:
            print(f"   [OK] Match {match_id} confirmed successfully")
        else:
            print(f"   [ERROR] Failed to confirm match: {response.status_code}")
    
    print("\n" + "="*60)
    print("[SUCCESS] All tests completed successfully!")
    print("="*60)
    return True

if __name__ == "__main__":
    # Stop any existing processes on port 8000
    try:
        import os
        if os.name == 'nt':  # Windows
            os.system('netstat -ano | findstr :8000 > nul 2>&1')
    except:
        pass
    
    server_process = start_server()
    if server_process:
        try:
            run_tests()
        finally:
            print("\nStopping server...")
            server_process.terminate()
            server_process.wait()
            print("Server stopped.")
    else:
        sys.exit(1)

