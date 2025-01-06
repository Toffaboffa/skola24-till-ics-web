import os
import requests
import arrow
from datetime import datetime
def log_message(message):
    log_file_path = '/tmp/log.txt'
    formatted_message = f"{datetime.now()}: {message}"
    print(formatted_message)  # Logga till konsolen
    try:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{formatted_message}\n")
    except Exception as e:
        print(f"Fel vid loggning till fil: {e}")

hdata = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'sv-SE,sv;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '1',
    'Origin': 'https://web.skola24.se',
    'Referer': '',
    "X-Requested-With": "XMLHttpRequest",
    "X-Scope": "8a22163c-8662-4535-9050-bc5e1923df48"
}

def generate_referer(domain, school_name):
    return f"https://web.skola24.se/timetable/timetable-viewer/{domain}/{school_name}/"

def get_id_for(larare, s):
    log_message("Startar funktionen get_id_for")
    try:
        singsresp = s.post("https://web.skola24.se/api/encrypt/signature", headers=hdata, json={"signature": larare})
        singsresp.raise_for_status()
        log_message(f"Svar från get_id_for: {singsresp.json()}")
        return singsresp.json()["data"]["signature"]
    except Exception as e:
        log_message(f"Fel vid get_id_for: {e}")
        return None

def get_key(s):
    log_message("Startar funktionen get_key")
    try:
        keyr = s.post("https://web.skola24.se/api/get/timetable/render/key", headers=hdata, json={})
        keyr.raise_for_status()
        log_message(f"Svar från get_key: {keyr.json()}")
        return keyr.json()["data"]["key"]
    except Exception as e:
        log_message(f"Fel vid get_key: {e}")
        return None

def get_week(week, larare_id, s, domain, school_year, unit_guid):
    log_message(f"Hämtar veckodata för vecka {week}")
    if week == 26:
        return None

    if arrow.now().week < 26:
        htyear = arrow.now().year - 1
        vtyear = arrow.now().year
    else:
        htyear = arrow.now().year
        vtyear = arrow.now().year + 1

    year = vtyear if week < 26 else htyear

    weekrequest = {
        'blackAndWhite': False,
        'customerKey': "",
        'endDate': None,
        'height': 550,
        'host': domain,
        'periodText': "",
        'privateFreeTextMode': False,
        'privateSelectionMode': None,
        'renderKey': get_key(s),
        'scheduleDay': 0,
        'schoolYear': school_year,
        'selection': larare_id,
        'selectionType': 4,
        'showHeader': False,
        'startDate': None,
        'unitGuid': unit_guid,
        'week': week,
        'width': 1200,
        'year': year
    }
    try:
        response = s.post("https://web.skola24.se/api/render/timetable", headers=hdata, json=weekrequest)
        response.raise_for_status()
        data = response.json()
        log_message(f"Svar från get_week: {data}")
        log_message(f"API-svar för vecka {week}: {data}")
        return data["data"].get("lessonInfo", [])
    except Exception as e:
        log_message(f"Fel vid get_week: {e}")
        return []

def get_weekdata(week_nr, larare_id, s, domain, school_year, unit_guid):
    log_message(f"Hämtar veckodata för vecka {week_nr}")
    indata = get_week(week_nr, larare_id, s, domain, school_year, unit_guid)
    week = [[], [], [], [], []]
    if indata:
        for event in indata:
            log_message(f"Lektion: {event} på dag {event.get('dayOfWeekNumber', 1)}")
            week[event.get("dayOfWeekNumber", 1) - 1].append(event)
    return week

def todatestr(week, day, school_year):
    # Hämta startåret från skolåret, t.ex. "2024-2025" -> 2024
    start_year = int(school_year.split("-")[0])
    
    # Använd ISO-standard för att hitta årets första vecka
    first_week_date = arrow.get(start_year, 1, 4).floor('week')  # Första torsdagen i januari
    date = first_week_date.shift(weeks=week-1).shift(days=day-1)
    log_message(f"Vecka {week}, dag {day}: Beräknat datum är {date}")
    return date.format('YYYYMMDD')

def todate(date_str, time_str):
    return f"{date_str}T{time_str}:00Z"

def geticsfor(domain, school_name, unit_guid, school_year, larare):
    log_message("Startar processen för att skapa ICS-fil")
    s = requests.session()
    weeks = {}
    larare_id = get_id_for(larare, s)
    if not larare_id:
        log_message("Ingen lärar-ID mottagen")
        return None

    for week in range(1, 53):
        weeks[week] = get_weekdata(week, larare_id, s, domain, school_year, unit_guid)

    events = []
    for week in weeks:
        for day in range(5):  # Rätt indentering här
            date = todatestr(week, day + 2, school_year)
            for line in weeks[week][day]:
                event = {"date": date}
                event["end"] = line.get("timeEnd", "")
                event["uid"] = line.get("guidId", "")
                event["start"] = line.get("timeStart", "")

                # Sammanfoga SUMMARY (ämne + klass)
                event["summary"] = f"{line.get('texts', [''])[0]} {', '.join([klass['name'] for klass in line.get('classes', [])])}"

                # Bygg DESCRIPTION
                description_parts = []
                if "rooms" in line and line["rooms"]:
                    description_parts.append(f"Salar: {', '.join([room['name'] for room in line['rooms']])}")
                if "teachers" in line and line["teachers"]:
                    description_parts.append(f"Lärare: {', '.join([teacher['fullName'] for teacher in line['teachers']])}")
                description_parts.append(f"Tid: {line.get('timeStart', '')} - {line.get('timeEnd', '')}")
                event["description"] = " | ".join(description_parts)
                
                log_message(f"Skapar event: {event}")
                events.append(event)

    NNN = larare
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    file_name = f"schema_{NNN}_{timestamp}.ics"
    file_path = os.path.join('/tmp', file_name)  # Spara ICS-fil till /tmp

    try:
        with open(file_path, 'w') as f:
            f.write("BEGIN:VCALENDAR\n")
            f.write("VERSION:2.0\n")
            f.write("PRODID:-//Your Organization//NONSGML Your Product//EN\n")
            for event in events:
                f.write("BEGIN:VEVENT\n")
                f.write(f"SUMMARY:{event['summary']}\n")
                f.write(f"DTSTART:{todate(event['date'], event['start'])}\n")
                f.write(f"DTEND:{todate(event['date'], event['end'])}\n")
                f.write(f"UID:{event['uid']}\n")
                f.write("END:VEVENT\n")
            f.write("END:VCALENDAR\n")
        log_message(f"ICS-fil skapad: {file_path}")
        return file_name
    except Exception as e:
        log_message(f"Fel vid skrivning av ICS-fil: {e}")
        return None

if __name__ == '__main__':
    geticsfor("example.com", "SchoolName", "unit-guid", "2024", "TeacherName")
