"""Test script for the Payment Reconciliation System."""

import requests
import time
import os
from pathlib import Path

BASE_URL = "http://localhost:8000"

def test_system():
    """Test the complete system workflow."""
    print("Testing Payment Reconciliation System...")
    print("=" * 50)
    
    # Wait for server to be ready
    print("\n1. Checking if server is running...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"   [OK] Server is running: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   [ERROR] Server is not running. Please start it with: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return False
    
    # Upload payments
    print("\n2. Uploading payments CSV...")
    payments_file = Path("sample_data/payments.csv")
    if not payments_file.exists():
        print(f"   [ERROR] File not found: {payments_file}")
        return False
    
    try:
        with open(payments_file, 'rb') as f:
            files = {'file': ('payments.csv', f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/upload/payments", files=files, timeout=30)
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] Uploaded {data.get('rows_inserted', 0)} payment records")
            else:
                print(f"   [ERROR] Upload failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"   [ERROR] Error uploading payments: {e}")
        return False
    
    # Upload bank transactions
    print("\n3. Uploading bank transactions CSV...")
    bank_file = Path("sample_data/bank.csv")
    if not bank_file.exists():
        print(f"   [ERROR] File not found: {bank_file}")
        return False
    
    try:
        with open(bank_file, 'rb') as f:
            files = {'file': ('bank.csv', f, 'text/csv')}
            response = requests.post(f"{BASE_URL}/upload/bank", files=files, timeout=30)
            if response.status_code == 200:
                data = response.json()
                print(f"   [OK] Uploaded {data.get('rows_inserted', 0)} bank transaction records")
            else:
                print(f"   [ERROR] Upload failed: {response.status_code} - {response.text}")
                return False
    except Exception as e:
        print(f"   [ERROR] Error uploading bank transactions: {e}")
        return False
    
    # Run reconciliation
    print("\n4. Running reconciliation...")
    try:
        response = requests.post(f"{BASE_URL}/reconcile", timeout=60)
        if response.status_code == 200:
            data = response.json()
            result = data.get('result', {})
            print(f"   [OK] Reconciliation complete:")
            print(f"     - Matched: {result.get('matched', 0)}")
            print(f"     - Unmatched: {result.get('unmatched', 0)}")
        else:
            print(f"   [ERROR] Reconciliation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error during reconciliation: {e}")
        return False
    
    # Get matches
    print("\n5. Fetching matches...")
    try:
        response = requests.get(f"{BASE_URL}/matches?limit=10", timeout=10)
        if response.status_code == 200:
            data = response.json()
            matches = data.get('matches', [])
            print(f"   [OK] Found {len(matches)} matches")
            if matches:
                match = matches[0]
                print(f"     Example match:")
                print(f"       - Match ID: {match.get('id')}")
                print(f"       - Score: {match.get('match_score')}")
                print(f"       - Type: {match.get('match_type')}")
                print(f"       - Payment: ${match.get('payment_amount')} on {match.get('payment_date')}")
                print(f"       - Bank: ${match.get('bank_amount')} on {match.get('bank_date')}")
        else:
            print(f"   [ERROR] Failed to fetch matches: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"   [ERROR] Error fetching matches: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("[SUCCESS] All tests passed! System is working correctly.")
    return True

if __name__ == "__main__":
    test_system()

