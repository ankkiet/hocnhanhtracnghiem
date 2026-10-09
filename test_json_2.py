import json
s1 = '{"key": "abc\\ndef"}' # Escaped newlines
s2 = '{"key": "abc\ndef"}' # Raw newlines

d1 = json.loads(s1, strict=False)
print("Escaped:", repr(d1['key']))

try:
    d2 = json.loads(s2, strict=False)
    print("Raw:", repr(d2['key']))
except Exception as e:
    print("Raw Failed:", e)
