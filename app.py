from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import logging
from schema import geticsfor, get_active_school_year, normalize_domain

app = Flask(__name__)

# Konfigurera uppladdningsmappen till /tmp
app.config['UPLOAD_FOLDER'] = '/tmp'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/readme')
def readme():
    return render_template('readme.html')


@app.route('/school-year', methods=['POST'])
def school_year():
    """Hämta aktivt läsår från Skola24 när domän och skola har valts."""
    data = request.get_json(silent=True) or {}
    domain = normalize_domain(data.get('domain', ''))
    school_name = (data.get('school_name') or '').strip()

    if not domain or not school_name:
        return jsonify({'error': 'Domän och skola måste anges.'}), 400

    try:
        selected = get_active_school_year(domain, school_name)
        return jsonify({
            'guid': selected.get('guid'),
            'name': selected.get('name'),
            'from': selected.get('from'),
            'to': selected.get('to'),
        })
    except Exception as exc:
        logging.exception('Kunde inte hämta aktivt läsår från Skola24.')
        return jsonify({'error': f'Kunde inte hämta läsår från Skola24: {exc}'}), 502


@app.route('/generate', methods=['POST'])
def generate():
    domain = normalize_domain(request.form.get('domain', ''))
    school_name = request.form.get('school_name', '').strip()
    unit_guid = request.form.get('unit_guid', '').strip()
    school_year_id = request.form.get('school_year', '').strip()
    teacher_id = request.form.get('teacher_id', '').strip()
    email = request.form.get('email', '').strip()

    if not all([domain, school_name, unit_guid, teacher_id, email]):
        return jsonify({'error': 'Ett eller flera obligatoriska fält saknas.'}), 400

    # Reservlösning: om webbläsaren inte hann hämta år-ID gör servern det här.
    if not school_year_id:
        try:
            selected = get_active_school_year(domain, school_name)
            school_year_id = selected.get('guid', '')
        except Exception as exc:
            logging.exception('Kunde inte hämta år-ID vid generering.')
            return jsonify({'error': f'Kunde inte hämta aktuellt läsår: {exc}'}), 502

    if not school_year_id:
        return jsonify({'error': 'Skola24 returnerade inget år-ID.'}), 502

    logging.info(f'Skapar ICS-fil för {teacher_id}...')

    ics_filename = geticsfor(
        domain,
        school_name,
        unit_guid,
        school_year_id,
        teacher_id,
        email,
    )
    if not ics_filename:
        logging.error(f"Misslyckades med att skapa ICS-fil för {teacher_id}.")
        return jsonify({'error': 'Misslyckades med att skapa ICS-fil'}), 500

    logging.info(f'ICS-fil skapad: {ics_filename}')
    return jsonify({'filename': ics_filename})


@app.route('/download/<filename>')
def download(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        logging.error(f'Filen {filename} hittades inte.')
        return jsonify({'error': 'Filen hittades inte'}), 404


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=True)
