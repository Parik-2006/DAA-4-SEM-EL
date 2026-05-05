#!/usr/bin/env python3
"""Quick Firebase connection test"""
import sys
from pathlib import Path

try:
    from database.firebase_client import FirebaseClient
    
    print("[INFO] Attempting Firebase connection...")
    firebase = FirebaseClient()
    
    if firebase.fs is None:
        print("[ERROR] Firestore client is None!")
        sys.exit(1)
    
    print("[✓] Firestore connected successfully")
    print(f"[INFO] Project ID: {firebase.fs.project}")
    
    # Try a simple query
    print("\n[INFO] Testing attendance collection query...")
    docs = firebase.fs.collection("attendance").limit(1).stream()
    count = 0
    for doc in docs:
        count += 1
        print(f"[✓] Found document: {doc.id}")
    
    if count == 0:
        print("[INFO] No attendance records yet (that's ok)")
    
    print("\n[SUCCESS] Firebase connection working!")
    
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
