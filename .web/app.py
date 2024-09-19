from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import datetime
import logging
from schema import geticsfor  # Importera din ICS-genereringsfunktion

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/home/Toffaboffa/mysite/temp/'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_message(message):
    app.logger.info(message)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    domain = request.form['domain']
    school_name = request.form['school_name']
    unit_guid = request.form['unit_guid']
    school_year = request.form['school_year']
    teacher_id = request.form['teacher_id']

    log_message(f'Skapar ICS-fil för {teacher_id}...')

    # Generera ICS-fil med riktiga händelser
    ics_filename = geticsfor(domain, school_name, unit_guid, school_year, teacher_id)

    log_message(f'ICS-fil skapad: {ics_filename}')

    # Returnera filnamnet till klienten
    return jsonify({'filename': ics_filename})

@app.route('/status')
def status():
    # Här kan du lägga till kod för att returnera status eller progressinformation
    return jsonify({'status': 'Färdig', 'progress': 100})

@app.route('/download/<filename>')
def download(filename):
    try:
        # Säkerställ att filen existerar innan den laddas ned
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        return jsonify({'error': 'Filen hittades inte'}), 404

if __name__ == '__main__':
    app.run(debug=True)
