import requests, json, os
SERVER='http://127.0.0.1:8502'
# Use the tmp uploaded file created earlier
file_path = r'C:\ChemProj3\CheminnathonProject\tmp_upload\ai4i2020.csv'
if not os.path.exists(file_path):
    print('uploaded file not found, please upload first')
    raise SystemExit(1)
payload = {'file_path': file_path, 'stem': 'ai4i2020'}
print('posting to /run_inference', payload)
r = requests.post(SERVER + '/run_inference', json=payload)
print('status', r.status_code)
try:
    j = r.json()
    print(json.dumps(j, indent=2)[:4000])
except Exception as e:
    print('no json', e)
    print(r.text)
