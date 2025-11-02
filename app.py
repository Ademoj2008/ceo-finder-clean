import os
from flask import Flask, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Folders
UPLOADS = os.path.join(os.path.dirname(__file__), 'uploads')
DATABASE = os.path.join(os.path.dirname(__file__), 'database')
OUTPUT = os.path.join(os.path.dirname(__file__), 'output')

for p in (UPLOADS, DATABASE, OUTPUT):
    os.makedirs(p, exist_ok=True)

ALLOWED_EXT = {'txt', 'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def build_email_ceo_mapping(database_folder=DATABASE):
    print("✅ Using robust build_email_ceo_mapping function")
    """
    Build a mapping of company emails to CEO names safely.
    Skips malformed lines without crashing.
    """
    mapping = {}
    try:
        files = [f for f in os.listdir(database_folder) if os.path.isfile(os.path.join(database_folder, f))]
    except Exception as e:
        print(f"Error accessing folder {database_folder}: {e}")
        return mapping

    for fname in files:
        if not fname.lower().endswith(('.txt', '.csv')):
            continue
        path = os.path.join(database_folder, fname)
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                raw_lines = [ln.rstrip('\n') for ln in fh.readlines()]
        except Exception as e:
            print(f"Error reading file {fname}: {e}")
            continue

        current_ceo = None
        for idx, ln in enumerate(raw_lines, start=1):
            line = ln.strip()
            if not line:
                continue

            if '@' not in line:
                current_ceo = line  # update CEO name
                continue

            parts = line.split('@', 1)
            if len(parts) < 2 or not current_ceo:
                print(f"Skipping malformed line {idx} in {fname}: '{line}'")
                continue

            try:
                domain = parts[1].split()[0].strip().lower()
                mapping[domain] = current_ceo.strip()
            except Exception as e:
                print(f"Error processing line {idx} in {fname}: '{line}' - {e}")
                continue

    return mapping

# initial mapping loaded at startup
email_to_ceo = build_email_ceo_mapping()

@app.route('/process', methods=['POST'])
def process_file_route():
    if 'file' not in request.files:
        return render_template('index.html', message='No file part in request')
    file = request.files['file']
    if not file or file.filename == '':
        return render_template('index.html', message='No file selected')
    if not allowed_file(file.filename):
        return render_template('index.html', message='Invalid file type (only .txt/.csv)')

    filename = secure_filename(file.filename)
    in_path = os.path.join(UPLOADS, filename)
    file.save(in_path)

    try:
        with open(in_path, 'r', encoding='utf-8', errors='ignore') as fh:
            lines = fh.readlines()
    except Exception:
        return render_template('index.html', message='Failed to read uploaded file')

    output_lines = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped:
        # Preserve blank lines from the input
        if output_lines and output_lines[-1] != '':
            output_lines.append('')
        continue

    ceo = None
    if '@' in stripped:
        domain = stripped.split('@', 1)[1].split()[0].lower()
        ceo = email_to_ceo.get(domain)

    if ceo:
        # Insert CEO name right above company line, no extra blank line
        if output_lines and output_lines[-1] != '':
            output_lines.append('')  # single blank line separation
        output_lines.append(ceo)

    output_lines.append(line.rstrip())

# ensure final file ends with exactly one newline
while len(output_lines) > 1 and output_lines[-1] == '' and output_lines[-2] == '':
    output_lines.pop()


            out_name = f'with_ceos_{filename}'
            out_path = os.path.join(OUTPUT, out_name)
            with open(out_path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(output_lines) + '\n')

            download_url = url_for('download_file', filename=out_name)
            return render_template('success.html', download_url=download_url)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return process_file_route()
    return render_template('index.html')

@app.route('/upload_db', methods=['GET', 'POST'])
def upload_db():
    global email_to_ceo
    if request.method == 'POST':
        if 'db_file' not in request.files:
            return render_template('upload_db.html', message='No file part in request')
        file = request.files['db_file']
        if not file or file.filename == '':
            return render_template('upload_db.html', message='No file selected')
        if not allowed_file(file.filename):
            return render_template('upload_db.html', message='Invalid file type')

        filename = secure_filename(file.filename)
        dst = os.path.join(DATABASE, filename)
        file.save(dst)
        email_to_ceo = build_email_ceo_mapping(DATABASE)
        return render_template('upload_db.html', message='Database uploaded successfully!')
    return render_template('upload_db.html')

@app.route('/uploads/<path:filename>')
def download_file(filename):
    return send_from_directory(OUTPUT, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

