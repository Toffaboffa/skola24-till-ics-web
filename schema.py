import os
import requests
import arrow
from datetime import datetime

# Loggning
def log_message(message):
    log_file_path = '/tmp/log.txt'  # Uppdaterad loggfilplats för Render
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"{datetime.now()}: {message}\n")

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

# Ny funktion: Justera veckodagar
def adjust_day(api_day):
    """
    Justera veckodag från söndag som första dag (API-logik) till måndag som första dag (ISO-standard).
    """
    adjusted_day = (api_day - 1) % 7 + 1
    log_message(f"Justerar dag från API: {api_day} till ISO-standard: {adjusted_day}")
    return adjusted_day

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
        return data["data"].get("lessonInfo", [])
    except Exception as e:
        log_message(f"Fel vid get_week: {e}")
        return []

def get_weekdata(week_nr, larare_id, s, domain, school_year, unit_guid):
    log_message(f"Hämtar veckodata för vecka {week_nr}")
    indata = get_week(week_nr, larare_id, s, domain, school_year, unit_guid)
    week = [[], [], [], [], [], [], []]  # Justera för 7 dagar i veckan
    if indata:
        for event in indata:
            raw_day = event.get("dayOfWeekNumber", 1)  # Original dag från API:t
            adjusted_day = adjust_day(raw_day)  # Justerad dag
            log_message(f"Event från API: raw_day={raw_day}, adjusted_day={adjusted_day}")
            week[adjusted_day - 1].append(event)
    return week

def todatestr(week, day):
    """
    Beräkna datum från vecka och veckodag enligt ISO-standard
    """
    year = arrow.now().year
    first_week = arrow.get(year, 1, 4).floor("week")  # ISO-standard: första torsdagen definierar vecka 1
    date = first_week.shift(weeks=week - 1, days=day - 1)
    date = date.shift(days=-1)
    log_message(f"Beräknar datum för vecka {week}, dag {day}: {date.format('YYYY-MM-DD')}")
    return date.format("YYYYMMDD")

def todate(date_str, time_str):
    if ":" in time_str:
        time_str = time_str.replace(":", "")[:4]
    return f"{date_str}T{time_str}Z"

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
        for day in range(5):
            date = todatestr(week, day + 2)
            for line in weeks[week][day]:
                event = {"date": date}
                event["end"] = line.get("timeEnd", "")
                event["start"] = line.get("timeStart", "")
                event["uid"] = f"{line.get('guidId', '')}-{date}-{line.get('timeStart', '0000')}"
                event["summary"] = ""

                # Sammanfoga texter om de finns
                if "texts" in line and line["texts"]:
                    event["summary"] = " ".join(
                        [t.get("value", "") if isinstance(t, dict) else t for t in line["texts"]]
                    )
    
                # Lägg till lärares namn om det finns
                if "teachers" in line and line["teachers"]:
                    teacher_names = " ".join([t.get("fullName", "") for t in line["teachers"]])
                    event["summary"] += f" {teacher_names}"
    
                # Skippa oönskade händelser
                if not event["summary"] or "Lunch" in event["summary"] or "Rastvärd" in event["summary"]:
                    continue
    
                log_message(f"Skapar event: {event}")
                events.append(event)

    NNN = larare
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    file_name = f"schema_{NNN}_{timestamp}.ics"
    file_path = os.path.join('/tmp', file_name)

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
