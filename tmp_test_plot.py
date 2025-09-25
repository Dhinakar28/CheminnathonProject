import requests, json, os
SERVER='http://127.0.0.1:8502'
file_path = r'c:\ChemProj3\CheminnathonProject\data\raw\ai4i2020.csv'
if not os.path.exists(file_path):
    print('sample file missing:', file_path)
    raise SystemExit(1)
# upload
with open(file_path,'rb') as fh:
    files={'file':('ai4i2020.csv', fh)}
    r = requests.post(SERVER + '/upload_file', files=files)
    print('upload status', r.status_code)
    j = r.json()
    print(json.dumps(j, indent=2))
    # choose numeric col
    cols = j.get('summary', {}).get('numeric_cols', [])
    if not cols:
        print('no numeric cols in summary')
        raise SystemExit(1)
    col = cols[0]
    # request plot
    params = {'file_path': j['file_path'], 'col': col}
    print('requesting plot for', params)
    pr = requests.get(SERVER + '/plot_series.png', params=params)
    print('plot status', pr.status_code, 'content-type', pr.headers.get('content-type'))
    out = r'tmp_plot.png'
    if pr.status_code == 200 and pr.headers.get('content-type','').startswith('image'):
        with open(out,'wb') as of:
            of.write(pr.content)
        print('saved to', out)
    else:
        print('plot failed, text:', pr.text)
