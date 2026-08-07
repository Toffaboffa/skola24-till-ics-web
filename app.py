from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import logging
import os
import re
import time
import uuid

from schema import get_active_school_year, normalize_domain
from selection import prepare_schedule, write_ics

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', force=True)

CACHE_PREFIX = 'skola24_prepare_'
CACHE_TTL_SECONDS = 30 * 60


def _cache_path(token):
    if not re.fullmatch(r'[0-9a-f]{32}', token or ''):
        raise ValueError('Ogiltigt schema-ID.')
    return os.path.join('/tmp', f'{CACHE_PREFIX}{token}.json')


def _cleanup_cache():
    now = time.time()
    try:
        for name in os.listdir('/tmp'):
            if not name.startswith(CACHE_PREFIX) or not name.endswith('.json'):
                continue
            path = os.path.join('/tmp', name)
            try:
                if now - os.path.getmtime(path) > CACHE_TTL_SECONDS:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


def _save_prepared(prepared):
    _cleanup_cache()
    token = uuid.uuid4().hex
    path = _cache_path(token)
    payload = {
        'created_at': time.time(),
        'teacher': prepared['teacher'],
        'events': prepared['events'],
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    return token


def _load_prepared(token):
    path = _cache_path(token)
    if not os.path.exists(path):
        raise FileNotFoundError('Det förberedda schemat finns inte längre. Hämta schemat igen.')
    if time.time() - os.path.getmtime(path) > CACHE_TTL_SECONDS:
        try:
            os.remove(path)
        except OSError:
            pass
        raise FileNotFoundError('Det förberedda schemat har gått ut. Hämta schemat igen.')
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _form_values():
    domain = normalize_domain(request.form.get('domain', ''))
    school_name = request.form.get('school_name', '').strip()
    unit_guid = request.form.get('unit_guid', '').strip()
    school_year_id = request.form.get('school_year', '').strip()
    teacher_id = request.form.get('teacher_id', '').strip()
    email = request.form.get('email', '').strip()
    return domain, school_name, unit_guid, school_year_id, teacher_id, email


def _ensure_school_year(domain, school_name, school_year_id):
    if school_year_id:
        return school_year_id
    selected = get_active_school_year(domain, school_name)
    return selected.get('guid', '')


@app.route('/')
def index():
    return render_template('index_v2.html')


@app.route('/readme')
def readme():
    return render_template('readme.html')


@app.route('/school-year', methods=['POST'])
def school_year():
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


@app.route('/prepare', methods=['POST'])
def prepare():
    domain, school_name, unit_guid, school_year_id, teacher_id, email = _form_values()

    if not all([domain, school_name, unit_guid, teacher_id, email]):
        return jsonify({'error': 'Ett eller flera obligatoriska fält saknas.'}), 400

    try:
        school_year_id = _ensure_school_year(domain, school_name, school_year_id)
        if not school_year_id:
            return jsonify({'error': 'Skola24 returnerade inget år-ID.'}), 502

        logging.info(f'Hämtar och analyserar schema för {teacher_id}...')
        prepared = prepare_schedule(
            domain, school_name, unit_guid, school_year_id, teacher_id, email
        )
        token = _save_prepared(prepared)

        return jsonify({
            'token': token,
            'options': prepared['options'],
            'teaching_time': prepared['teaching_time'],
            'event_count': prepared['event_count'],
        })
    except Exception as exc:
        logging.exception('Kunde inte förbereda schema.')
        return jsonify({'error': f'Kunde inte hämta schemat: {exc}'}), 502


@app.route('/generate-selected', methods=['POST'])
def generate_selected():
    data = request.get_json(silent=True) or {}
    token = data.get('token', '')
    selected_keys = data.get('selected_keys')

    if not isinstance(selected_keys, list):
        return jsonify({'error': 'Ogiltigt urval.'}), 400

    try:
        cached = _load_prepared(token)
        filename = write_ics(cached['events'], cached['teacher'], selected_keys)
        if not filename:
            return jsonify({'error': 'Misslyckades med att skapa ICS-fil.'}), 500

        try:
            os.remove(_cache_path(token))
        except OSError:
            pass

        return jsonify({'filename': filename})
    except FileNotFoundError as exc:
        return jsonify({'error': str(exc)}), 410
    except (ValueError, json.JSONDecodeError) as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        logging.exception('Kunde inte skapa filtrerad ICS.')
        return jsonify({'error': f'Misslyckades med att skapa ICS-fil: {exc}'}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Bakåtkompatibel direktgenerering som tar med alla exporterbara poster."""
    domain, school_name, unit_guid, school_year_id, teacher_id, email = _form_values()

    if not all([domain, school_name, unit_guid, teacher_id, email]):
        return jsonify({'error': 'Ett eller flera obligatoriska fält saknas.'}), 400

    try:
        school_year_id = _ensure_school_year(domain, school_name, school_year_id)
        if not school_year_id:
            return jsonify({'error': 'Skola24 returnerade inget år-ID.'}), 502

        prepared = prepare_schedule(
            domain, school_name, unit_guid, school_year_id, teacher_id, email
        )
        ics_filename = write_ics(prepared['events'], teacher_id)
        if not ics_filename:
            return jsonify({'error': 'Misslyckades med att skapa ICS-fil'}), 500
        return jsonify({'filename': ics_filename})
    except Exception as exc:
        logging.exception('Kunde inte generera ICS.')
        return jsonify({'error': f'Misslyckades med att skapa ICS-fil: {exc}'}), 500


@app.route('/download/<filename>')
def download(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({'error': 'Filen hittades inte'}), 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
