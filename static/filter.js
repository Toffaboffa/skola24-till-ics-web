let yearFetchTimer = null;
let yearFetchController = null;
let preparedToken = null;
let preparedOptions = [];

function logToConsole(message) {
    const consoleDiv = document.getElementById('console');
    const messageElement = document.createElement('div');
    messageElement.textContent = message;
    consoleDiv.appendChild(messageElement);
    consoleDiv.scrollTop = consoleDiv.scrollHeight;
}

function updateFields() {
    const dropdown = document.getElementById('school_dropdown');
    const selectedOption = dropdown.options[dropdown.selectedIndex];
    document.getElementById('school_name').value = dropdown.value ? selectedOption.text : '';
    document.getElementById('unit_guid').value = dropdown.value || '';
}

async function fetchSchoolYear() {
    updateFields();
    const domain = document.getElementById('domain').value.trim();
    const schoolName = document.getElementById('school_name').value.trim();
    const schoolYearInput = document.getElementById('school_year');

    if (!domain || !schoolName) {
        schoolYearInput.value = '';
        return false;
    }

    if (yearFetchController) yearFetchController.abort();
    yearFetchController = new AbortController();

    try {
        const response = await fetch('/school-year', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({domain, school_name: schoolName}),
            signal: yearFetchController.signal
        });
        const data = await response.json();
        if (!response.ok || !data.guid) throw new Error(data.error || 'Skola24 returnerade inget år-ID.');

        schoolYearInput.value = data.guid;
        const period = data.from && data.to ? ` (${data.from.substring(0, 4)}/${data.to.substring(0, 4)})` : '';
        logToConsole(`Aktuellt läsår hittat automatiskt${period}.`);
        return true;
    } catch (error) {
        if (error.name === 'AbortError') return false;
        schoolYearInput.value = '';
        logToConsole(`Fel vid hämtning av läsår: ${error.message}`);
        return false;
    }
}

function scheduleSchoolYearFetch() {
    clearTimeout(yearFetchTimer);
    yearFetchTimer = setTimeout(fetchSchoolYear, 500);
}

function formatMinutes(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return hours ? `${hours} h ${mins} min` : `${mins} min`;
}

function updateSelectionSummary() {
    const checkboxes = document.querySelectorAll('.event-option-checkbox');
    const weekly = {};
    let eventCount = 0;

    checkboxes.forEach(box => {
        if (!box.checked) return;
        const option = preparedOptions[Number(box.dataset.index)];
        eventCount += option.count || 0;
        Object.entries(option.weekly_minutes || {}).forEach(([week, minutes]) => {
            weekly[week] = (weekly[week] || 0) + Number(minutes || 0);
        });
    });

    const weekValues = Object.values(weekly).filter(value => value > 0);
    const maxMinutes = weekValues.length ? Math.max(...weekValues) : 0;
    const averageMinutes = weekValues.length
        ? Math.round(weekValues.reduce((a, b) => a + b, 0) / weekValues.length)
        : 0;
    const limit = 1080;
    const percent = limit ? (maxMinutes / limit) * 100 : 0;

    document.getElementById('selectedEventCount').textContent = eventCount;
    document.getElementById('teachingMax').textContent = `${maxMinutes} min (${formatMinutes(maxMinutes)})`;
    document.getElementById('teachingAverage').textContent = `${averageMinutes} min (${formatMinutes(averageMinutes)})`;
    document.getElementById('teachingPercent').textContent = `${percent.toFixed(1).replace('.', ',')} %`;

    const bar = document.getElementById('teachingBar');
    bar.style.width = `${Math.min(percent, 100)}%`;
    bar.classList.toggle('over-limit', maxMinutes > limit);

    const warning = document.getElementById('teachingWarning');
    if (maxMinutes > limit) {
        warning.textContent = `Över maxgränsen med ${maxMinutes - limit} min under den tyngsta veckan.`;
        warning.hidden = false;
    } else {
        warning.hidden = true;
    }
}

function renderOptions(data) {
    preparedToken = data.token;
    preparedOptions = data.options || [];
    const list = document.getElementById('eventOptions');
    list.innerHTML = '';

    preparedOptions.forEach((option, index) => {
        const row = document.createElement('label');
        row.className = 'event-option';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'event-option-checkbox';
        checkbox.checked = true;
        checkbox.dataset.index = String(index);
        checkbox.addEventListener('change', updateSelectionSummary);

        const text = document.createElement('span');
        text.className = 'event-option-name';
        text.textContent = option.label;

        const meta = document.createElement('span');
        meta.className = 'event-option-meta';
        meta.textContent = `${option.count} poster${option.teaching_minutes ? ' · undervisning' : ''}`;

        row.append(checkbox, text, meta);
        list.appendChild(row);
    });

    document.getElementById('foundSummary').textContent =
        `${preparedOptions.length} olika schemaposter hittades, ${data.event_count || 0} kalenderhändelser totalt.`;
    updateSelectionSummary();
    document.getElementById('selectionModal').classList.add('visible');
    document.getElementById('selectionModal').setAttribute('aria-hidden', 'false');
}

function setAllOptions(checked) {
    document.querySelectorAll('.event-option-checkbox').forEach(box => { box.checked = checked; });
    updateSelectionSummary();
}

function closeModal() {
    document.getElementById('selectionModal').classList.remove('visible');
    document.getElementById('selectionModal').setAttribute('aria-hidden', 'true');
}

async function submitForm(event) {
    event.preventDefault();
    updateFields();

    const submitButton = document.getElementById('generateButton');
    submitButton.disabled = true;
    submitButton.textContent = 'Hämtar schema...';

    try {
        const schoolYearInput = document.getElementById('school_year');
        if (!schoolYearInput.value) {
            logToConsole('Hämtar aktuellt läsår från Skola24...');
            await fetchSchoolYear();
        }

        const formData = new FormData(document.getElementById('form'));
        logToConsole('Hämtar och analyserar schemat. Detta kan ta en stund...');

        const response = await fetch('/prepare', {method: 'POST', body: formData});
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || 'Schemahämtningen misslyckades.');

        logToConsole(`Schema hämtat: ${data.event_count || 0} kalenderhändelser.`);
        renderOptions(data);
    } catch (error) {
        logToConsole(`Fel: ${error.message}`);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = 'Skapa .ics';
    }
}

async function downloadSelected() {
    const selectedKeys = [];
    document.querySelectorAll('.event-option-checkbox').forEach(box => {
        if (box.checked) selectedKeys.push(preparedOptions[Number(box.dataset.index)].key);
    });

    const button = document.getElementById('downloadSelectedButton');
    button.disabled = true;
    button.textContent = 'Skapar fil...';

    try {
        const response = await fetch('/generate-selected', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({token: preparedToken, selected_keys: selectedKeys})
        });
        const data = await response.json();
        if (!response.ok || data.error) throw new Error(data.error || 'Genereringen misslyckades.');

        closeModal();
        logToConsole(`ICS skapad med ${document.getElementById('selectedEventCount').textContent} valda kalenderhändelser.`);
        window.location.href = `/download/${encodeURIComponent(data.filename)}`;
    } catch (error) {
        logToConsole(`Fel: ${error.message}`);
    } finally {
        button.disabled = false;
        button.textContent = 'Ladda ner vald .ics';
    }
}

function clearForm() {
    document.getElementById('form').reset();
    document.getElementById('school_year').value = '';
    updateFields();
    closeModal();
    logToConsole('Formuläret har tömts.');
    scheduleSchoolYearFetch();
}

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('form');
    const domain = document.getElementById('domain');
    const schoolDropdown = document.getElementById('school_dropdown');

    form.addEventListener('submit', submitForm);
    document.getElementById('clearButton').addEventListener('click', clearForm);
    document.getElementById('selectAllButton').addEventListener('click', () => setAllOptions(true));
    document.getElementById('selectNoneButton').addEventListener('click', () => setAllOptions(false));
    document.getElementById('closeModalButton').addEventListener('click', closeModal);
    document.getElementById('downloadSelectedButton').addEventListener('click', downloadSelected);

    domain.addEventListener('input', scheduleSchoolYearFetch);
    domain.addEventListener('blur', fetchSchoolYear);
    schoolDropdown.addEventListener('change', function() {
        document.getElementById('school_year').value = '';
        updateFields();
        fetchSchoolYear();
    });

    updateFields();
    if (domain.value.trim()) fetchSchoolYear();
});
