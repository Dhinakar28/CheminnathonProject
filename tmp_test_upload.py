import requests
from pathlib import Path
url = 'http://127.0.0.1:8502'
sample = Path('data/raw/ai4i2020.csv')
if not sample.exists():
    print('sample missing:', sample)
    raise SystemExit(1)
with open(sample, 'rb') as f:
    files = {'file': (sample.name, f)}
    r = requests.post(url + '/upload_file', files=files)
    print('upload status', r.status_code)
    print(r.text[:1000])
    if r.ok:
        j = r.json()
        file_path = j['file_path']
        stem = j['stem']
        print('got file_path', file_path, 'stem', stem)
        r2 = requests.post(url + '/run_inference', json={'file_path': file_path, 'stem': stem})
        print('run_inference', r2.status_code)
        print(r2.text[:2000])
