import os
import re
import requests
import arrow
from datetime import datetime, date

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

def normalize_domain(domain):
    """Normalisera en Skola24-domän som skrivits in av användaren."""
    domain = (domain or "").strip()
    domain = re.sub(r"^https?://", "", domain, flags=re.IGNORECASE)
    domain = domain.split("/", 1)[0].strip().rstrip(".")
    return domain.lower()

def get_active_school_year(domain, school_name=""):
    """
    Hämta aktuellt aktivt läsår direkt från Skola24.

    Returnerar objektet från activeSchoolYears, till exempel:
    {"guid": "...", "name": "Innevarande",
     "from": "2026-07-01T00:00:00", "to": "2027-06-30T00:00:00"}
    """
    domain = normalize_domain(domain)
    school_name = (school_name or "").strip()

    if not domain:
        raise ValueError("Ingen Skola24-domän angavs.")

    session = requests.Session()
    headers = hdata.copy()

    # Efterlikna webbläsarens flöde och etablera session mot rätt viewer-sida.
    # Years-endpointen brukar fungera ändå, men detta gör anropet robustare.
    if school_name:
        referer = generate_referer(domain, school_name)
        headers["Referer"] = referer
        try:
            session.get(referer, headers=headers, timeout=15)
        except requests.RequestException as exc:
            log_message(f"Kunde inte förladda Skola24-sidan: {exc}")

    response = session.post(
        "https://web.skola24.se/api/get/active/school/years",
        headers=headers,
        json={
            "hostName": domain,
            "checkSchoolYearsFeatures": False,
        },
        timeout=20,
    )
    response.raise_for_status()

    payload = response.json()
    years = payload.get("data", {}).get("activeSchoolYears", [])
    if not years:
        raise RuntimeError("Skola24 returnerade inga aktiva läsår.")

    # Om flera läsår mot förmodan returneras väljer vi det som omfattar dagens
    # datum. Annars används första posten, vilket är samma rimliga fallback som
    # Skola24-viewern själv i praktiken ger oss via listordningen.
    today = arrow.now("Europe/Stockholm").date()
    for item in years:
        try:
            start = datetime.fromisoformat(item["from"]).date()
            end = datetime.fromisoformat(item["to"]).date()
            if start <= today <= end:
                log_message(f"Aktivt läsår valt: {item}")
                return item
        except (KeyError, TypeError, ValueError):
            continue

    log_message(f"Inget läsår matchade dagens datum; använder första: {years[0]}")
    return years[0]

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

def get_school_year_bounds(s, domain, school_year):
    """
    Hämta start- och slutår för valt läsår direkt från Skola24.

    Exempel: ett läsår med from=2026-07-01 och to=2027-06-30
    returnerar (2026, 2027). Om API-anropet misslyckas används en
    försiktig fallback baserad på innevarande datum.
    """
    try:
        response = s.post(
            "https://web.skola24.se/api/get/active/school/years",
            headers=hdata,
            json={
                "hostName": domain,
                "checkSchoolYearsFeatures": False,
            },
        )
        response.raise_for_status()
        school_years = response.json().get("data", {}).get("activeSchoolYears", [])

        selected = next(
            (item for item in school_years if item.get("guid") == school_year),
            None,
        )
        if selected is None and len(school_years) == 1:
            selected = school_years[0]

        if selected and selected.get("from") and selected.get("to"):
            start_year = datetime.fromisoformat(selected["from"]).year
            end_year = datetime.fromisoformat(selected["to"]).year
            log_message(
                f"Läsår från Skola24: {selected.get('from')} - {selected.get('to')} "
                f"(startår={start_year}, slutår={end_year})"
            )
            return start_year, end_year

        log_message(
            f"Kunde inte hitta läsår {school_year} i activeSchoolYears; använder fallback."
        )
    except Exception as e:
        log_message(f"Kunde inte hämta activeSchoolYears: {e}; använder fallback.")

    now = arrow.now("Europe/Stockholm")
    if now.month >= 7:
        return now.year, now.year + 1
    return now.year - 1, now.year

def get_year_for_week(week, school_year_start, school_year_end):
    """Returnera rätt ISO-år för en vecka inom ett svenskt läsår."""
    if 1 <= week < 26:
        return school_year_end
    if 26 < week <= 53:
        return school_year_start
    raise ValueError(f"Vecka {week} ligger på den avsiktligt överhoppade sommargränsen.")

def get_week(week, larare_id, s, domain, school_year, unit_guid, school_year_start, school_year_end):
    log_message(f"Hämtar veckodata för vecka {week}")
    if week == 26:
        return None

    year = get_year_for_week(week, school_year_start, school_year_end)

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

def get_weekdata(week_nr, larare_id, s, domain, school_year, unit_guid, school_year_start, school_year_end):
    log_message(f"Hämtar veckodata för vecka {week_nr}")
    indata = get_week(
        week_nr,
        larare_id,
        s,
        domain,
        school_year,
        unit_guid,
        school_year_start,
        school_year_end,
    )
    week = [[], [], [], [], [], [], []]
    if indata:
        for event in indata:
            raw_day = event.get("dayOfWeekNumber")
            try:
                iso_day = int(raw_day)
            except (TypeError, ValueError):
                log_message(f"Ogiltig dayOfWeekNumber från API: {raw_day!r}; hoppar över event.")
                continue

            # Skola24 använder 1=måndag, 2=tisdag, ... 7=söndag.
            # Detta är redan samma numrering som ISO-8601, så ingen förskjutning ska göras.
            if not 1 <= iso_day <= 7:
                log_message(f"dayOfWeekNumber utanför 1-7: {iso_day}; hoppar över event.")
                continue

            log_message(f"Event från API: dayOfWeekNumber={iso_day} (ISO-dag {iso_day})")
            week[iso_day - 1].append(event)
    return week

def todatestr(week, iso_day, school_year_start, school_year_end):
    """Beräkna lokalt kalenderdatum från ISO-år, ISO-vecka och ISO-veckodag."""
    year = get_year_for_week(week, school_year_start, school_year_end)
    calendar_date = date.fromisocalendar(year, week, iso_day)
    log_message(
        f"Beräknar datum: ISO-år={year}, vecka={week}, dag={iso_day} "
        f"-> {calendar_date.isoformat()}"
    )
    return calendar_date.strftime("%Y%m%d")

def todate(date_str, time_str):

    if ":" in time_str:
        time_str = time_str.replace(":", "")[:4]  # Rensa bort kolon
    local_time = arrow.get(f"{date_str}T{time_str}", "YYYYMMDDTHHmm").replace(tzinfo="Europe/Stockholm")
    utc_time = local_time.to("utc")  # Konvertera till UTC
    # iCalendar kräver bokstaven Z för UTC DATE-TIME; numeriska offset som +0000
    # ska inte användas i DTSTART/DTEND.
    return utc_time.format("YYYYMMDDTHHmmss") + "Z"
    
def categorize_event(texts):
    """
    Tilldela kategorier baserat på den första delen av 'texts' från API-svaret.
    """
    kategorier = []

    # Mappning baserad på ämne
    mapping = {
        "EN": ["Engelska", "Kärnämne", "Undervisning", "Lektion"],
        "SV": ["Svenska", "Kärnämne", "Undervisning", "Lektion"],
        "SVA": ["Svenska som andraspråk", "Kärnämne", "Undervisning", "Lektion"],
        "SL": ["Slöjd", "PREST-ämnen", "Undervisning", "Lektion"],
        "MU": ["Musik", "PREST-ämnen", "Undervisning", "Lektion"],
        "FY": ["Fysik", "NO-ämnen", "Undervisning", "Lektion"],
        "MENTORSTID": ["Mentorstid"],
        "Coachsamtal": ["Coachsamtal"],
        "TK": ["Teknik", "NO-ämnen", "Undervisning", "Lektion"],
        "BI": ["Biologi", "NO-ämnen", "Undervisning", "Lektion"],
        "KE": ["Kemi", "NO-ämnen", "Undervisning", "Lektion"],
        "HKK": ["Hem- & Konsumentkunskap", "PREST-ämnen", "Undervisning", "Lektion"],
        "BL": ["Bild", "PREST-ämnen", "Undervisning", "Lektion"],
        "M2FRA": ["Språkval", "Franska", "Undervisning", "Lektion"],
        "M2SPA": ["Språkval", "Spanska", "Undervisning", "Lektion"],
        "M2DEU": ["Språkval", "Tyska", "Undervisning", "Lektion"],
        "Ma": ["Matematik", "Kärnämne", "Undervisning", "Lektion"],
        "HI": ["Historia", "SO-ämnen", "Undervisning", "Lektion"],
        "RE": ["Religion", "SO-ämnen", "Undervisning", "Lektion"],
        "GE": ["Geografi", "SO-ämnen", "Undervisning", "Lektion"],
        "SH": ["Samhällskunskap", "SO-ämnen", "Undervisning", "Lektion"],
        "IDH": ["Idrott & Hälsa", "Undervisning", "Lektion"],
        "PULS": ["Puls", "Undervisning", "Lektion"],
        "Konferens": ["Konferens", "Övrig tid"],
        "Planeringstid": ["Planering", "Övrig tid"],
        "Planering": ["Planering", "Övrig tid"],
        "Facklig tid": ["Konferens", "Övrig tid"],
    }

    # Kontrollera att 'texts' är en lista och har minst ett element
    if texts and isinstance(texts, list):
        subject = texts[0]  # Första delen av texts
        if subject in mapping:
            kategorier = mapping[subject]
            log_message(f"Ämne '{subject}' matchade kategorier: {kategorier}")
        else:
            kategorier = ["Övrig tid"]
            log_message(f"Ämne '{subject}' hittades INTE i mapping. Tilldelar 'Övrig tid'.")
    else:
        kategorier = ["Övrig tid"]
        log_message("Felaktig 'texts' från API. Tilldelar 'Övrig tid'.")

    # Alla exporterade kalenderposter ska kunna identifieras och filtreras som schema.
    # Lägg alltid "Schema" sist, även om kategorilistan ändras framöver.
    kategorier = [kategori for kategori in kategorier if kategori != "Schema"]
    kategorier.append("Schema")

    return kategorier

def geticsfor(domain, school_name, unit_guid, school_year, larare, email):
    log_message("Startar processen för att skapa ICS-fil")
    s = requests.session()
    weeks = {}
    larare_id = get_id_for(larare, s)
    if not larare_id:
        log_message("Ingen lärar-ID mottagen")
        return None

    school_year_start, school_year_end = get_school_year_bounds(s, domain, school_year)
    log_message(f"Genererar läsår {school_year_start}/{school_year_end}")

    # Hämta data för alla relevanta veckor. Vecka 26 hoppas över som tidigare.
    for week in range(1, 53):
        if week == 26:
            continue
        weeks[week] = get_weekdata(
            week,
            larare_id,
            s,
            domain,
            school_year,
            unit_guid,
            school_year_start,
            school_year_end,
        )

    events = []
    for week in weeks:
        for day_index in range(5):  # Måndag till fredag
            iso_day = day_index + 1
            event_date = todatestr(
                week, iso_day, school_year_start, school_year_end
            )
            for line in weeks[week][day_index]:
                event = {"date": event_date}
                event["end"] = line.get("timeEnd", "")
                event["start"] = line.get("timeStart", "")
                event["uid"] = f"{line.get('guidId', '')}-{event_date}-{line.get('timeStart', '0000')}"
                event["summary"] = ""
                event["attendee"] = email
                description = []

                # Kontrollera om eventet är en konferens
                texts = line.get("texts") or []
                if any("Konferens" in text for text in texts):
                    event["summary"] = "Konferens"
                    event["description"] = "Konferens"
                else:
                    # Sammanfoga texter om de finns
                    if texts:
                        all_texts = [t if isinstance(t, str) else t.get("value", "") for t in texts]
                        event["summary"] = f"{all_texts[0]} {all_texts[2]}" if len(all_texts) > 2 else all_texts[0]
                        description.extend(all_texts[1:])

                    # Lägg till lärares namn om det finns
                    teachers = line.get("teachers") or []
                    if teachers:
                        teacher_names = " ".join([t.get("fullName", "") for t in teachers])
                        description.append(f"Lärare: {teacher_names}")

                    # Lägg till tid och plats
                    if "timeStart" in line and "timeEnd" in line:
                        description.append(f"Tid: {line['timeStart']} - {line['timeEnd']}")
                    if "location" in line:
                        description.append(f"Plats: {line['location']}")

                    # Om description är tom, sätt en default
                    event["description"] = "\n".join(description) if description else "-"

                # Skippa oönskade händelser
                excluded_keywords = ["Lunch", "Rastvärd"]
                if not event["summary"] or any(keyword in event["summary"] for keyword in excluded_keywords):
                    continue
                    
                # Tilldela kategorier baserat på händelsetyp
                event["categories"] = categorize_event(line.get("texts"))
                log_message(f"TEXTS {line.get('texts')} gav kategorier: {event['categories']}")

                # Bygg korrekt LOCATION baserat på domän
                domain_split = domain.split('.')
                city = domain_split[0].capitalize() if domain_split else "Okänd stad"
                event["location"] = f"{school_name}, {city}, Sverige"

                log_message(f"Skapar event: SUMMARY={event['summary']}, DESCRIPTION={event['description']}")
                events.append(event)

    # Veckorna hämtas i nummerordning (1..52), vilket annars placerar VT före HT
    # i själva filen. Kalenderprogram sorterar normalt själva, men en kronologisk
    # ICS är enklare att kontrollera och mer förutsägbar att importera.
    events.sort(key=lambda event: (event["date"], event.get("start", "")))

    # Skapa ICS-fil
    NNN = larare
    timestamp = datetime.now().strftime('%y%m%d_%H%M')
    file_name = f"schema_{NNN}_{timestamp}.ics"
    file_path = os.path.join('/tmp', file_name)

    try:
        with open(file_path, 'w') as f:
            f.write("BEGIN:VCALENDAR\n")
            f.write("VERSION:2.0\n")
            f.write("PRODID:-//Skola24 till ICS//https://skola24-till-ics-web.onrender.com//SV\n")
            f.write("X-WR-CALNAME:Schema\n")
            f.write("X-WR-CALDESC:Kalenderhändelser från Skola24 för lärare.\n")
            for event in events:
                f.write("BEGIN:VEVENT\n")
                f.write(f"SUMMARY:{event['summary']}\n")
                f.write(f"DESCRIPTION:{event['description']}\n")
                f.write(f"DTSTART:{todate(event['date'], event['start'])}\n")
                f.write(f"DTEND:{todate(event['date'], event['end'])}\n")
                f.write(f"UID:{event['uid']}\n")
                f.write(f"LOCATION:{event['location']}\n")  # Lägg till platsen
                f.write(f"STATUS:CONFIRMED\n")  # Lägg till status

                # Lägg till ATTENDEE från hemsidans input
                attendee_email = event.get('attendee', '')
                if attendee_email:
                    f.write(f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:{attendee_email}\n")

                # Lägg till kategori
                f.write(f"CATEGORIES:{','.join(event['categories'])}\n")

                f.write("END:VEVENT\n")
            f.write("END:VCALENDAR\n")

        log_message(f"ICS-fil skapad: {file_path}")
        return file_name
    except Exception as e:
        log_message(f"Fel vid skrivning av ICS-fil: {e}")
        return None

if __name__ == '__main__':
    geticsfor("example.com", "SchoolName", "unit-guid", "2024", "TeacherName", "teacher@example.com")
