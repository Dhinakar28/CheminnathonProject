from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from pathlib import Path
import io
import joblib
import json
import matplotlib
# use a non-interactive backend to avoid GUI/window issues on the server
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

from src.data_loader import load_any
from src.inference import run_anomaly_inference, run_classifier_inference, run_rul_inference, generate_maintenance_report

# The templates and static assets are located under app/ so point Flask there when
# this module lives at repository root.
ROOT = Path(__file__).resolve().parent
# point Flask to the app templates/static under the repository
app = Flask(__name__, static_folder=str(ROOT / 'app' / 'static'), template_folder=str(ROOT / 'app' / 'templates'))
MODELS_DIR = ROOT / 'models_auto_run'
SAMPLE_DIR = ROOT / 'data' / 'raw'
TMP_UPLOAD = ROOT / 'tmp_upload'
TMP_UPLOAD.mkdir(parents=True, exist_ok=True)

# Simple user store for demo (use a DB in production)
USER_STORE = ROOT / 'users.json'
def load_users():
    if USER_STORE.exists():
        return json.load(open(USER_STORE))
    return {}
def save_users(users):
    with open(USER_STORE, 'w') as f:
        json.dump(users, f)

app.secret_key = secrets.token_hex(16)

# About Us page
@app.route('/about')
def about():
    return render_template('about.html', user=session.get('user'))

# Contact Us page
@app.route('/contact')
def contact():
    return render_template('contact.html', user=session.get('user'))
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from pathlib import Path
import io
import joblib
import json
import matplotlib
# use a non-interactive backend to avoid GUI/window issues on the server
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

from src.data_loader import load_any
from src.inference import run_anomaly_inference, run_classifier_inference, run_rul_inference, generate_maintenance_report

# The templates and static assets are located under app/ so point Flask there when
# this module lives at repository root.
ROOT = Path(__file__).resolve().parent
# point Flask to the app templates/static under the repository
app = Flask(__name__, static_folder=str(ROOT / 'app' / 'static'), template_folder=str(ROOT / 'app' / 'templates'))
MODELS_DIR = ROOT / 'models_auto_run'
SAMPLE_DIR = ROOT / 'data' / 'raw'
TMP_UPLOAD = ROOT / 'tmp_upload'
TMP_UPLOAD.mkdir(parents=True, exist_ok=True)

# Simple user store for demo (use a DB in production)
USER_STORE = ROOT / 'users.json'
def load_users():
    if USER_STORE.exists():
        return json.load(open(USER_STORE))
    return {}
def save_users(users):
    with open(USER_STORE, 'w') as f:
        json.dump(users, f)

app.secret_key = secrets.token_hex(16)

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        users = load_users()
        user = users.get(email)
        if user and check_password_hash(user['password'], password):
            session['user'] = {'email': email, 'name': user['name']}
            return redirect(url_for('index'))
        else:
            error = 'Invalid email or password.'
    return render_template('login.html', error=error)

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        users = load_users()
        if email in users:
            error = 'Email already registered.'
        else:
            users[email] = {'name': name, 'password': generate_password_hash(password)}
            save_users(users)
            return redirect(url_for('login'))
    return render_template('signup.html', error=error)

# Logout route
@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


def list_models_for_stem(stem: str):
    res = {'anomaly': None, 'classifier': None, 'rul': None}
    if not stem:
        return res
    base = MODELS_DIR / stem
    if not base.exists():
        return res
    an = base / 'anomaly'
    if an.exists():
        model = an / f"{stem}__isof.joblib"
        scaler = an / f"{stem}__scaler.joblib"
        meta = an / f"{stem}__isof__meta.json"
        if model.exists() and scaler.exists():
            res['anomaly'] = {'model': str(model), 'scaler': str(scaler), 'meta': json.load(open(meta)) if meta.exists() else None}
    clf = base / 'classifier'
    if clf.exists():
        metas = list(clf.glob('*__meta.json'))
        if metas:
            meta = json.load(open(metas[0]))
            target = meta.get('target')
            model = clf / f"{stem}__{target.replace(' ','_')}__rf_clf.joblib"
            scaler = clf / f"{stem}__{target.replace(' ','_')}__scaler.joblib"
            if model.exists() and scaler.exists():
                res['classifier'] = {'model': str(model), 'scaler': str(scaler), 'meta': meta}
    rul = base / 'rul'
    if rul.exists():
        model = rul / f"{stem}__RUL__rf.joblib"
        scaler = rul / f"{stem}__RUL__scaler.joblib"
        meta = rul / f"{stem}__RUL__meta.json"
        if model.exists() and scaler.exists():
            res['rul'] = {'model': str(model), 'scaler': str(scaler), 'meta': json.load(open(meta)) if meta.exists() else None}
    return res


@app.route('/', methods=['GET', 'POST'])
def index():
    # Require login
    if 'user' not in session:
        return redirect(url_for('login'))
    uploaded_df = None
    stem = None
    selected_sample = request.form.get('sample') if request.method=='POST' else None

    if request.method == 'POST' and 'file' in request.files:
        f = request.files['file']
        if f.filename:
            tmp = TMP_UPLOAD / f.filename
            f.save(tmp)
            uploaded_df = load_any(tmp)
            stem = tmp.stem
    elif selected_sample:
        path = SAMPLE_DIR / selected_sample
        if path.exists():
            uploaded_df = load_any(path)
            stem = Path(selected_sample).stem

    try:
        samples = [p.name for p in SAMPLE_DIR.iterdir() if p.is_file()]
    except FileNotFoundError:
        samples = []
    models = list_models_for_stem(stem) if stem else {'anomaly': None, 'classifier': None, 'rul': None}

    # show a compact summary
    summary = None
    if uploaded_df is not None:
        numcols = uploaded_df.select_dtypes(include=[np.number]).columns.tolist()
        summary = {'n_rows': int(len(uploaded_df)), 'n_numeric': len(numcols), 'numeric_cols': numcols[:12]}

    return render_template('index.html', samples=samples, df=uploaded_df, models=models, summary=summary, stem=stem, user=session.get('user'))


@app.route('/run_inference', methods=['POST'])
def run_inference():
    data = request.json
    file_path = data.get('file_path')
    stem = data.get('stem')
    df = None
    if file_path:
        try:
            p = Path(file_path)
            if not p.is_absolute():
                p = ROOT / file_path
            df = load_any(p)
        except Exception as e:
            return jsonify({'error': f'failed to load dataset: {e}'}), 400
    elif stem:
        df = load_any(SAMPLE_DIR / f"{stem}.csv") if (SAMPLE_DIR / f"{stem}.csv").exists() else None

    if df is None:
        return jsonify({'error': 'dataset not found'}), 400

    # derive stem from file_path when possible
    if not stem and file_path:
        try:
            stem = Path(file_path).stem
        except Exception:
            stem = None

    models = list_models_for_stem(stem)
    anom = None
    clf = None
    rul = None
    try:
        if models['anomaly']:
            anom = run_anomaly_inference(models['anomaly']['model'], models['anomaly']['scaler'], df)
        if models['classifier']:
            clf = run_classifier_inference(models['classifier']['model'], models['classifier']['scaler'], df, target_col=models['classifier']['meta'].get('target'))
        if models['rul']:
            rul = run_rul_inference(models['rul']['model'], models['rul']['scaler'], df, id_col=models['rul']['meta'].get('id_col') if models['rul']['meta'] else None, cycle_col=models['rul']['meta'].get('cycle_col') if models['rul']['meta'] else None)
    except Exception as e:
        return jsonify({'error': f'inference error: {e}'}), 500

    # prepare summary and report
    failure_modes_map = {
        '0': 'none', '1': 'Tool Wear Failure', '2': 'Heat Dissipation Failure',
        '3': 'Power Failure', '4': 'Overstrain Failure', '5': 'Random Failure',
        '6': 'bearing', '7': 'wear', '8': 'electrical'
    }
    report = generate_maintenance_report(rul, anom, clf, failure_modes_map)

    # annotate classifier summary with human-readable labels when possible
    if clf and isinstance(clf, dict) and clf.get('summary') and isinstance(clf['summary'], dict):
        counts = clf['summary'].get('counts', {})
        readable = {}
        for k, v in counts.items():
            readable_label = failure_modes_map.get(str(k), str(k))
            readable[readable_label] = int(v)
        # add readable counts and top 3 modes
        clf['summary']['readable_counts'] = readable
        sorted_modes = sorted(readable.items(), key=lambda kv: kv[1], reverse=True)
        clf['summary']['top_modes'] = [ {'mode': m, 'count': c} for m, c in sorted_modes[:3] ]

    resp = {'anom': anom, 'clf': clf, 'rul': rul, 'report': report}
    # overall status: first report line (most important) if available
    resp['overall_status'] = report[0] if report and len(report) > 0 else 'Status unknown'

    # convert numpy types to native Python for JSON
    def _make_json_safe(o):
        import numpy as _np
        if o is None:
            return None
        if isinstance(o, _np.generic):
            return o.item()
        if isinstance(o, _np.ndarray):
            return o.tolist()
        if isinstance(o, dict):
            return {k: _make_json_safe(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_make_json_safe(v) for v in o]
        return o

    safe = _make_json_safe(resp)
    return jsonify(safe)



@app.route('/upload_file', methods=['POST'])
def upload_file():
    # AJAX upload endpoint: saves uploaded file to tmp and returns JSON with path and summary
    if 'file' not in request.files:
        return jsonify({'error': 'no file part'}), 400
    f = request.files['file']
    if not f or not f.filename:
        return jsonify({'error': 'no selected file'}), 400
    tmp = TMP_UPLOAD / f.filename
    f.save(tmp)
    try:
        df = load_any(tmp)
    except Exception as e:
        return jsonify({'error': f'failed to load uploaded file: {e}'}), 400
    numcols = df.select_dtypes(include=[np.number]).columns.tolist()
    summary = {'n_rows': int(len(df)), 'n_numeric': len(numcols), 'numeric_cols': numcols[:12]}
    return jsonify({'file_path': str(tmp), 'stem': tmp.stem, 'summary': summary})


@app.route('/plot_series.png')
def plot_series():
    # expects query params: file_path, col
    from flask import request
    file_path = request.args.get('file_path')
    col = request.args.get('col')
    if not file_path or not col:
        return '', 400
    p = Path(file_path)
    if not p.is_absolute():
        p = ROOT / file_path
    try:
        df = load_any(p)
        if col not in df.columns:
            return jsonify({'error': f'column {col} not found in dataset'}), 400
        fig, ax = plt.subplots(figsize=(10,4))
        # protect against non-numeric columns
        try:
            series = pd.to_numeric(df[col], errors='coerce')
        except Exception:
            series = df[col]
        ax.plot(df.index, series, color='blue')
        ax.set_title(col)
        ax.set_xlabel('Index')
        ax.set_ylabel(col)
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        # don't let plotting errors crash the server; return a JSON error so the client can show a message
        import traceback
        tb = traceback.format_exc()
        print('plot_series error:', tb)
        return jsonify({'error': str(e), 'trace': tb}), 500


if __name__ == '__main__':
    app.run(debug=True, port=8502)
