from web_app import app
from pathlib import Path
import io

sample = Path('data/raw/ai4i2020.csv')
if not sample.exists():
    print('sample missing', sample)
    raise SystemExit(1)

with app.test_client() as client:
    data = {'file': (open(sample, 'rb'), sample.name)}
    r = client.post('/upload_file', data=data, content_type='multipart/form-data')
    print('upload status', r.status_code)
    print(r.get_data(as_text=True)[:1000])
    if r.status_code==200:
        j = r.get_json()
        file_path = j['file_path']
        stem = j['stem']
        print('file_path', file_path, 'stem', stem)
        r2 = client.post('/run_inference', json={'file_path': file_path, 'stem': stem})
        print('run_inference', r2.status_code)
        print(r2.get_data(as_text=True)[:2000])
