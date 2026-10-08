import json
firebase_env = '{"private_key": "-----BEGIN PRIVATE KEY-----\nMIIC...\n-----END PRIVATE KEY-----\n"}'
try:
    cred_dict = json.loads(firebase_env, strict=False)
    print("SUCCESS strict=False!", repr(cred_dict['private_key']))
except Exception as e:
    print("ERROR strict=False:", e)
