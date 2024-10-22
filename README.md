Schema till iCal (.ics) Generator
================================

Detta projekt genererar en .ics-fil (iCal-fil) från ett schema på Skola24. Du fyller i relevant information och får ut en iCal-fil som du kan importera till din kalender. Du kan läsa mer hur det fungerar längre ned.

Vad du behöver
--------------

För att köra detta projekt behöver du:
- Python 3.7 eller senare.
- Beroenden som listas i `requirements.txt`.


Installation
------------

Följ dessa steg för att installera och köra projektet lokalt på din dator.

1. Klona projektet:

    ```bash
    git clone https://github.com/ditt-användarnamn/ditt-repo.git
    cd ditt-repo
    ```

2. Skapa en virtuell miljö:

    ```bash
    python -m venv venv
    source venv/bin/activate  # På Windows: venv\Scripts\activate
    ```

3. Installera beroenden:

    ```bash
    pip install -r requirements.txt
    ```

4. Kör applikationen:

    ```bash
    python app.py
    ```

   Applikationen kommer då att vara tillgänglig på `http://127.0.0.1:5000/`.

Användning
----------

1. Öppna din webbläsare och navigera till `http://127.0.0.1:5000/`.
2. Fyll i de fält som efterfrågas:

   - Domän:			ex. kumla.skola24.se
   - Skola: 			ex. Vialundskolan
   - Skol-ID (unit_guid): 	ex. ODBmYWIzYjgtM2YwYi10ETT0TEST0ZmMtMjhjZWI0ZTVhZGE0
   - År-ID (school_year): 	ex. 0d35b17b-42eb-4311-9328-00eTt0TeSt00
   - Lärare-ID: 		ex. KÅ

3. Klicka på "Generera .ics" för att skapa din .ics-fil.
4. Filen skapas och laddas hem.
5. Importera till din kalender.


Arbetsflöde
-----------

1. **Formulärinmatning:**
   Användaren fyller i följande fält i formuläret:
   - Domän (ex. kumla.skola24.se)
   - Skolans namn (ex. Vialundskolan)
   - Skol-ID (ex ODBmYWIzYjgtM2YwYi10ETT0TEST0ZmMtMjhjZWI0ZTVhZGE0
   - År-ID (ex. 0d35b17b-42eb-4311-9328-00eTt0TeSt00
   - Lärarens ID (ex. KÅ)


2. **Autentisering**:
   Formulärdatan används för att kontakta Skola24:s API och autentisera användaren baserat på domän och skolinformation. Lärarens schema identifieras med hjälp av Lärar-ID och År-ID.

3. **Hämtning av schema**:
   När användaren är autentiserad hämtas schema-data från Skola24 som bearbetas och konverteras till ett standardiserat .ics-format.

4. **Generering av iCal-fil**:
   - Kalenderhändelser skapas vecka för vecka.
   - Varje lektion får ett start- och sluttid baserat på schemat.
   - Information om klass, ämne, och sal läggs till som beskrivning i varje händelse.
   - Händelserna placeras automatiskt på rätt datum och tid i iCal-formatet.
   - .ics-filen genereras och laddas ner lokalt.

5. **Färdigställande**:
   Filen är redo att användas och innehåller all relevant schemainformation från Skola24.


Sammanställning av de 4 filerna
-------------------------------

Totalt antal rader kod: 382

	- app.py: 50 rader
	- schema.py: 179 rader
	- index.html: 112 rader
	- styles.css: 41 rader

Totalt antal tecken: 14130
Antal variabler totalt: 34

  Variabelnamn:

	app.py:

	- app
	- domain
	- school_name
	- unit_guid
	- school_year
	- teacher_id
	- ics_filename
	- message
	- filename

	schema.py:

	- hdata
	- s
	- larare
	- singsresp
	- keyr
	- weekrequest
	- response
	- data
	- indata
	- week
	- event
	- teacher
	- first_day_of_year
	- date
	- line
	- events
	- NNN
	- timestamp
	- file_name
	- f

	index.html (JavaScript):

	- consoleDiv
	- messageElement
	- formData
	- data
	- error
	- form

        styles.css:

	- Inga variabler (CSS innehåller inte variabler i traditionell mening)


Antal funktioner totalt: 14

  Funktionsnamn:

        app.py:

	- log_message
	- index
	- generate
	- status
	- download

	schema.py:

	- log_message
	- generate_referer
	- get_id_for
	- get_key
	- get_week
	- get_weekdata
	- todatestr
	- todate
	- geticsfor

	index.html (JavaScript):

	- logToConsole
	- submitForm
	- clearForm


Om projektet
------------

Detta projekt är skapat av Kristoffer Åberg med hjälp av ChatGPT för att automatisera hämtningen av schema från Skola24 och generera en iCal-fil.
