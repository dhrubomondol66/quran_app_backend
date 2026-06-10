import os
import json
import firebase_admin
from firebase_admin import credentials

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK safely.
    Checks if already initialized to prevent AppAlreadyExists exceptions.
    """
    if not firebase_admin._apps:
        # Try loading credentials from environment variable first (as a JSON string)
        firebase_creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if firebase_creds_json:
            try:
                creds_dict = json.loads(firebase_creds_json)
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
                print("[Firebase SDK] Initialized successfully using FIREBASE_CREDENTIALS_JSON environment variable.")
                return
            except Exception as e:
                print(f"[Firebase SDK Error] Failed to initialize from FIREBASE_CREDENTIALS_JSON env: {e}")

        # Fallback to local file
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cred_path = os.path.join(
            base_dir,
            'community',
            'firebase',
            'qari24-7-firebase-adminsdk-fbsvc-a3e80b9b58.json'
        )
        
        if os.path.exists(cred_path):
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                print(f"[Firebase SDK] Initialized successfully using credentials at: {cred_path}")
            except Exception as e:
                print(f"[Firebase SDK Error] Failed to initialize Admin Certificate: {e}")
        else:
            print(f"[Firebase SDK Warning] Credentials file not found at: {cred_path}")
    else:
        # Already initialized
        pass

