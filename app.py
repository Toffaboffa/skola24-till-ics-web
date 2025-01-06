from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import logging
from schema import geticsfor  # Importera din ICS-genereringsfunktion

app = Flask(__name__)

# Konfigurera uppladdningsmappen till /tmp
app.config['UPLOAD_FOLDER'] = '/tmp'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/readme')
def readme():
    return render_template('readme.html')

@app.route('/generate', methods=['POST'])
def generate():
    domain = request.form['domain']
    school_name = request.form['school_name']
    unit_guid = request.form['unit_guid']
    school_year = request.form['school_year']
    teacher_id = request.form['teacher_id']

    logging.info(f'Skapar ICS-fil för {teacher_id}...')

    # Generera ICS-fil
    ics_filename = geticsfor(domain, school_name, unit_guid, school_year, teacher_id)
    if not ics_filename:
        logging.error(f"Misslyckades med att skapa ICS-fil för {teacher_id}.")
        return jsonify({'error': 'Misslyckades med att skapa ICS-fil'}), 500

    logging.info(f'ICS-fil skapad: {ics_filename}')
    return jsonify({'filename': ics_filename})

@app.route('/download/<filename>')
def download(filename):
    try:
        # Returnera filen från /tmp-mappen
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        logging.error(f'Filen {filename} hittades inte.')
        return jsonify({'error': 'Filen hittades inte'}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 1337))
    app.run(host="0.0.0.0", port=port, debug=True)