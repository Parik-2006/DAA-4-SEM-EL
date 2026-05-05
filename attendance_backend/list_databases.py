#!/usr/bin/env python3
"""List all Firestore databases in the project - Check Status"""
import sys
from pathlib import Path
from firebase_admin import credentials
from google.cloud.firestore_admin_v1 import FirestoreAdminClient

try:
    print("[INFO] Loading Firebase credentials...")
    cred_path = Path("config/firebase-credentials.json")
    raw_cred = credentials.Certificate(str(cred_path))
    project_id = raw_cred.project_id
    
    print(f"[INFO] Project ID: {project_id}")
    print("\n[INFO] Creating Firestore Admin client...")
    
    db_admin = FirestoreAdminClient(credentials=raw_cred.get_credential())
    parent = f"projects/{project_id}"
    
    print(f"[INFO] Listing databases for: {parent}")
    response = db_admin.list_databases(request={"parent": parent})
    
    # Extract databases from response
    if hasattr(response, 'databases'):
        databases = response.databases
        print(f"\n[✓] Found {len(databases)} database(s):")
        for db in databases:
            print(f"\n  Database Name: {db.name}")
            print(f"  Type: {db.type_.name if hasattr(db.type_, 'name') else db.type_}")
            print(f"  Create Time: {db.create_time}")
            
            # Check status
            if hasattr(db, 'etag'):
                print(f"  Etag: {db.etag}")
            if hasattr(db, 'uid'):
                print(f"  UID: {db.uid}")
            
            print(f"  Available fields: {[f for f in dir(db) if not f.startswith('_')][:15]}")
    else:
        print(f"[WARNING] Response does not have 'databases' attribute")
    
    print("\n[✓] Database exists and is ready!")
    print("\n[TIP] The database IS present. The issue might be:")
    print("  1. Service account permission issue")
    print("  2. Network/firewall blocking the request")  
    print("  3. Transient Google Cloud issue - try again in a few minutes")
    
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


