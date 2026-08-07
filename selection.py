import os
import re
from datetime import datetime

import requests

import schema


CATEGORY_MAPPING = {
    'EN': ['Engelska', 'Kärnämne', 'Undervisning', 'Lektion'],
    'SV': ['Svenska', 'Kärnämne', 'Undervisning', 'Lektion'],
    'SVA': ['Svenska som andraspråk', 'Kärnämne', 'Undervisning', 'Lektion'],
    'SL': ['Slöjd', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'MU': ['Musik', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'FY': ['Fysik', 'NO-ämnen', 'Undervisning', 'Lektion'],
    'MENTORSTID': ['Mentorstid'],
    'Coachsamtal': ['Coachsamtal'],
    'TK': ['Teknik', 'NO-ämnen', 'Undervisning', 'Lektion'],
    'BI': ['Biologi', 'NO-ämnen', 'Undervisning', 'Lektion'],
    'KE': ['Kemi', 'NO-ämnen', 'Undervisning', 'Lektion'],
    'HKK': ['Hem- & Konsumentkunskap', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'BL': ['Bild', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'M2FRA': ['Språkval', 'Franska', 'Undervisning', 'Lektion'],
    'M2SPA': ['Språkval', 'Spanska', 'Undervisning', 'Lektion'],
    'M2DEU': ['Språkval', 'Tyska', 'Undervisning', 'Lektion'],
    'Ma': ['Matematik', 'Kärnämne', 'Undervisning', 'Lektion'],
    'MA': ['Matematik', 'Kärnämne', 'Undervisning', 'Lektion'],
    'HI': ['Historia', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'RE': ['Religion', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'GE': ['Geografi', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'SH': ['Samhällskunskap', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'IDH': ['Idrott & Hälsa', 'Undervisning', 'Lektion'],
    'PULS': ['Puls', 'Undervisning', 'Lektion'],
    'Konferens': ['Konferens', 'Övrig tid'],
    'Planeringstid': ['Planering', 'Övrig tid'],
    'Planering': ['Planering', 'Övrig tid'],
    'Facklig tid': ['Konferens', 'Övrig tid'],
    'BI:KE': ['Biologi & Kemi', 'NO-ämnen', 'Undervisning', 'Lektion'],
    'SV:SVA': ['Svenska/SVA', 'Kärnämne', 'Undervisning', 'Lektion'],
    'GE:SH': ['Geografi & Samhällskunskap', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'HI:RE': ['Historia & Religion', 'SO-ämnen', 'Undervisning', 'Lektion'],
    'GE:HI:RE:SH': ['SO-ämnen', 'Undervisning', 'Lektion'],
    'M2EN': ['Språkval', 'Engelska', 'Undervisning', 'Lektion'],
    'M2SV:M2SVA': ['Språkval', 'Svenska/SVA', 'Undervisning', 'Lektion'],
    'M2SV:M2SVA:SV:SVA': ['Svenska/SVA', 'Språkval', 'Undervisning', 'Lektion'],
    'SLtm': ['Träslöjd', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'SLtx': ['Textilslöjd', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'Enskild elev': ['Elevstöd', 'Undervisning'],
    'Förstelärarträff': ['Förstelärarträff', 'Övrig tid'],
    'Hkk IM': ['Hem- & Konsumentkunskap', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'Hkk-malmen': ['Hem- & Konsumentkunskap', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'Hkk-stene': ['Hem- & Konsumentkunskap', 'PREST-ämnen', 'Undervisning', 'Lektion'],
    'IT-support': ['IT-support', 'Övrig tid'],
    'Kollegialt lärande': ['Kollegialt lärande', 'Övrig tid'],
    'Kärnämne en': ['Engelska', 'Kärnämne', 'Undervisning', 'Lektion'],
    'Kärnämne ma': ['Matematik', 'Kärnämne', 'Undervisning', 'Lektion'],
    'Ledningsgrupp': ['Ledningsgrupp', 'Övrig tid'],
    'Lunch': ['Lunch'],
    'Mentorspar': ['Mentorspar', 'Övrig tid'],
    'MVP': ['MVP', 'Övrig tid'],
    'Måndagsinfo': ['Måndagsinfo', 'Konferens', 'Övrig tid'],
    'Studiestöd simning': ['Studiestöd', 'Undervisning'],
    'Studietid': ['Studietid', 'Undervisning'],
    'Ämnestid': ['Ämnestid', 'Övrig tid'],
}

_CATEGORY_MAPPING_CASEFOLD = {
    key.casefold(): value for key, value in CATEGORY_MAPPING.items()
}


def _text_values(texts):
    values = []
    for item in texts or []:
        if isinstance(item, str):
            values.append(item.strip())
        elif isinstance(item, dict):
            values.append(str(item.get('value', '')).strip())
        else:
            values.append(str(item).strip())
    return values


def categories_for_line(line):
    values = _text_values(line.get('texts'))
    subject = values[0] if values else ''
    categories = _CATEGORY_MAPPING_CASEFOLD.get(subject.casefold())
    if categories:
        return list(categories)
    return ['Övrig tid']


def _clean_group_label(subject, group):
    subject = (subject or '').strip()
    group = (group or '').strip()
    if not group:
        return ''
    if subject:
        pattern = rf'-{re.escape(subject)}(?::\d+)?$'
        cleaned = re.sub(pattern, '', group, flags=re.IGNORECASE)
        if cleaned != group:
            return cleaned.strip(' -')
    return group


def get_filter_identity(line):
    values = _text_values(line.get('texts'))
    subject = values[0] if values else 'Övrigt'
    group = values[2] if len(values) > 2 else ''
    clean_group = _clean_group_label(subject, group)

    pretty_subject = {
        'mentorstid': 'Mentorstid',
        'coachsamtal': 'Coachsamtal',
        'mentorspar': 'Mentorspar',
    }.get(subject.strip().lower(), subject)

    label = f'{pretty_subject} {clean_group}'.strip() if clean_group else pretty_subject
    key = f'{subject}\x1f{clean_group}'
    return key, label, subject, group


def is_teaching_event(line):
    _, _, subject, group = get_filter_identity(line)
    subject_key = subject.strip().lower()

    if subject_key == 'mentorspar':
        return False
    if subject_key in {'coachsamtal', 'mentorstid'}:
        return True

    if line.get('classes') or line.get('groups'):
        return True
    return bool((group or '').strip())


def duration_minutes(start_time, end_time):
    def parse(value):
        parts = str(value or '').split(':')
        if len(parts) < 2:
            return None
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return None

    start = parse(start_time)
    end = parse(end_time)
    if start is None or end is None or end < start:
        return 0
    return end - start


def _build_event(line, event_date, week, email, school_name, domain):
    values = _text_values(line.get('texts'))
    subject = values[0] if values else ''

    # Ramtid ska aldrig exporteras till ICS eller visas som val i popupen.
    if subject.casefold() == 'ramtid':
        return None

    event = {
        'date': event_date,
        'end': line.get('timeEnd', ''),
        'start': line.get('timeStart', ''),
        'uid': f"{line.get('guidId', '')}-{event_date}-{line.get('timeStart', '0000')}",
        'summary': '',
        'attendee': email,
    }
    description = []

    if any('konferens' in text.lower() for text in values):
        event['summary'] = 'Konferens'
        event['description'] = 'Konferens'
    elif values:
        event['summary'] = f'{values[0]} {values[2]}' if len(values) > 2 else values[0]
        description.extend(values[1:])

        teachers = line.get('teachers') or []
        teacher_names = ' '.join(
            t.get('fullName', '') for t in teachers if isinstance(t, dict) and t.get('fullName')
        )
        if teacher_names:
            description.append(f'Lärare: {teacher_names}')

        if 'timeStart' in line and 'timeEnd' in line:
            description.append(f"Tid: {line['timeStart']} - {line['timeEnd']}")
        if 'location' in line:
            description.append(f"Plats: {line['location']}")
        event['description'] = '\n'.join(description) if description else '-'

    if not event['summary']:
        return None
    if any(keyword in event['summary'].lower() for keyword in ('lunch', 'rastvärd')):
        return None

    event['categories'] = categories_for_line(line)
    city = domain.split('.')[0].capitalize() if domain else 'Okänd stad'
    event['location'] = f'{school_name}, {city}, Sverige'

    filter_key, filter_label, _, _ = get_filter_identity(line)
    event['filter_key'] = filter_key
    event['filter_label'] = filter_label
    event['week'] = week
    event['teaching'] = is_teaching_event(line)
    event['duration_minutes'] = duration_minutes(event['start'], event['end'])
    return event


def summarize_filter_options(events):
    options = {}
    for event in events:
        key = event['filter_key']
        option = options.setdefault(key, {
            'key': key,
            'label': event['filter_label'],
            'count': 0,
            'teaching_minutes': 0,
            'weekly_minutes': {},
        })
        option['count'] += 1
        if event.get('teaching'):
            minutes = int(event.get('duration_minutes', 0) or 0)
            option['teaching_minutes'] += minutes
            week_key = str(event.get('week'))
            option['weekly_minutes'][week_key] = option['weekly_minutes'].get(week_key, 0) + minutes

    return sorted(options.values(), key=lambda item: item['label'].lower())


def teaching_time_summary(events):
    weekly = {}
    for event in events:
        if not event.get('teaching'):
            continue
        week_key = str(event.get('week'))
        weekly[week_key] = weekly.get(week_key, 0) + int(event.get('duration_minutes', 0) or 0)

    values = [value for value in weekly.values() if value > 0]
    max_minutes = max(values) if values else 0
    average_minutes = round(sum(values) / len(values)) if values else 0
    return {
        'max_minutes': max_minutes,
        'average_minutes': average_minutes,
        'limit_minutes': 1080,
        'max_percent': round(max_minutes / 1080 * 100, 1) if max_minutes else 0,
        'weekly_minutes': weekly,
    }


def prepare_schedule(domain, school_name, unit_guid, school_year, teacher, email):
    schema.log_message('Startar hämtning och analys av schema för popup')
    session = requests.session()
    teacher_id = schema.get_id_for(teacher, session)
    if not teacher_id:
        raise RuntimeError('Kunde inte hitta lärar-ID i Skola24.')

    school_year_start, school_year_end = schema.get_school_year_bounds(session, domain, school_year)
    weeks = {}
    for week in range(1, 53):
        if week == 26:
            continue
        weeks[week] = schema.get_weekdata(
            week, teacher_id, session, domain, school_year, unit_guid,
            school_year_start, school_year_end,
        )

    events = []
    for week, week_data in weeks.items():
        for day_index in range(5):
            iso_day = day_index + 1
            event_date = schema.todatestr(week, iso_day, school_year_start, school_year_end)
            for line in week_data[day_index]:
                event = _build_event(line, event_date, week, email, school_name, domain)
                if event:
                    events.append(event)

    events.sort(key=lambda event: (event['date'], event.get('start', '')))
    return {
        'teacher': teacher,
        'events': events,
        'options': summarize_filter_options(events),
        'teaching_time': teaching_time_summary(events),
        'event_count': len(events),
    }


def _ics_escape(value):
    value = str(value or '')
    return value.replace('\\', '\\\\').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')


def _is_ramtid_event(event):
    filter_key = str(event.get('filter_key', ''))
    subject = filter_key.split('\x1f', 1)[0].strip()
    if subject:
        return subject.casefold() == 'ramtid'
    return str(event.get('summary', '')).strip().casefold().startswith('ramtid')


def write_ics(events, teacher, selected_keys=None):
    # Filtrera defensivt även här, så äldre cachedata aldrig kan exportera Ramtid.
    events = [event for event in events if not _is_ramtid_event(event)]

    selected = set(selected_keys) if selected_keys is not None else None
    if selected is not None:
        events = [event for event in events if event.get('filter_key') in selected]

    events = sorted(events, key=lambda event: (event['date'], event.get('start', '')))
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    file_name = f'schema_{teacher}_{timestamp}.ics'
    file_path = os.path.join('/tmp', file_name)

    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write('BEGIN:VCALENDAR\r\n')
        f.write('VERSION:2.0\r\n')
        f.write('PRODID:-//Skola24 till ICS//https://skola24-till-ics-web.onrender.com//SV\r\n')
        f.write('X-WR-CALNAME:Schema\r\n')
        f.write('X-WR-CALDESC:Kalenderhändelser från Skola24 för lärare.\r\n')
        for event in events:
            f.write('BEGIN:VEVENT\r\n')
            f.write(f"SUMMARY:{_ics_escape(event['summary'])}\r\n")
            f.write(f"DESCRIPTION:{_ics_escape(event['description'])}\r\n")
            f.write(f"DTSTART:{schema.todate(event['date'], event['start'])}\r\n")
            f.write(f"DTEND:{schema.todate(event['date'], event['end'])}\r\n")
            f.write(f"UID:{_ics_escape(event['uid'])}\r\n")
            f.write(f"LOCATION:{_ics_escape(event['location'])}\r\n")
            f.write('STATUS:CONFIRMED\r\n')
            if event.get('attendee'):
                f.write(f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:{event['attendee']}\r\n")
            f.write(f"CATEGORIES:{','.join(_ics_escape(c) for c in event['categories'])}\r\n")
            f.write('END:VEVENT\r\n')
        f.write('END:VCALENDAR\r\n')

    schema.log_message(f'Filtrerad ICS skapad: {file_path} ({len(events)} events)')
    return file_name
