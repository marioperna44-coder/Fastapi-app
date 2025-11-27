// ==========================================================
//  Globale Variabeln
// ==========================================================

let pulverWSInitialized = false;

// ==========================================================
//  MODULE INITIALISIERUNG
// ==========================================================

function initPulverlager() {
    console.log("🚀 Pulverlager Modul aktiviert");

    const root = document.getElementById("content");
    
    // Event Delegation
    root.addEventListener("click", onPulverClick);
    root.addEventListener("submit", onPulverSubmit);
    root.addEventListener("keydown", onPulverKeydown);

    // 🔥 WS-Event NUR EINMAL abonnieren
    if (!pulverWSInitialized) {
        document.addEventListener("ws-event", onPulverWebSocketEvent);
        pulverWSInitialized = true;
    }

    loadPowders().then(() => {
        setupFilter();
    });
}

window.initPulverlager = initPulverlager;

function refreshPulverlager() {
    console.log("🔄 Pulverlager Refresh");

    // Tabelle laden
    loadPowders().then(() => {
        setupFilter();
    });

    // Modals sicher schließen, falls sie noch offen sind
    const newModal = document.getElementById("newPulverModal");
    if (newModal) newModal.classList.add("hidden");

    const editModal = document.getElementById("editPulverModal");
    if (editModal) editModal.classList.add("hidden");

    const trackingModal = document.getElementById("trackingModal");
    if (trackingModal) trackingModal.classList.add("hidden");
}

window.refreshPulverlager = refreshPulverlager;


// ==========================================================
//  API: Pulverliste laden
// ==========================================================

async function loadPowders() {
    try {
        const res = await apiFetch("/api/pulver/");
        const powders = await res.json();

        const tbody = document.querySelector("#pulver-table tbody");
        tbody.innerHTML = "";

        powders.forEach(p => {
            const tr = document.createElement("tr");
            tr.dataset.id = p.id;

            tr.innerHTML = `
                <td>${p.id}</td>
                <td>${p.barcode}</td>
                <td>${p.artikelnummer || "-"}</td>
                <td>${p.hersteller || "-"}</td>
                <td>${p.farbe || "-"}</td>
                <td>${p.qualitaet || "-"}</td>
                <td>${p.oberflaeche || "-"}</td>
                <td>${p.anwendung || "-"}</td>
                <td>${p.start_menge_kg ?? "-"}</td>
                <td>${p.menge_kg ?? "-"}</td>
                <td>${p.lagerort || "-"}</td>
                <td>
                    <button class="btn-edit btn btn-secondary btn-sm">Bearbeiten</button>
                    <button class="btn-label btn btn-primary btn-sm">Label</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("❌ Fehler beim Laden:", err);
    }
}


// ==========================================================
//  CLICK EVENTS
// ==========================================================

async function onPulverClick(e) {

    // ➕ Neues Pulver
    if (e.target.matches("#btn-new-pulver")) {
        document.getElementById("newPulverModal").classList.remove("hidden");
        return;
    }

    if (e.target.matches("#cancelNewPulverModal")) {
        document.getElementById("newPulverModal").classList.add("hidden");
        return;
    }

    // 🏷️ Label drucken
    if (e.target.matches(".btn-label")) {
        const id = e.target.closest("tr").dataset.id;
        window.open(`/api/pulver/${id}/label`, "_blank");
        return;
    }

    // 🔧 Tracking öffnen
    if (e.target.matches("#btn-tracking")) {
        document.getElementById("trackingModal").classList.remove("hidden");
        document.getElementById("track-beschreibung").value = "Normaler Verbrauch";
        return;
    }

    if (e.target.matches("#cancelTrackingModal")) {
        document.getElementById("trackingModal").classList.add("hidden");
        document.getElementById("trackingForm").reset();
        return;
    }

    if (e.target.matches(".btn-edit")) {

        // 🔐 Permission prüfen
        if (!(await userHasPermission("powder.update"))) {
            alert("❌ Sie haben keine Berechtigung, Pulver zu bearbeiten.");
            return;
        }

        const tr = e.target.closest("tr");
        const id = tr.dataset.id;

        // 🔄 Daten frisch aus API holen (inkl. updated_at!)
        const res = await apiFetch(`/api/pulver/id/${id}`);
        const p = await res.json();

        // Felder befüllen
        document.getElementById("edit-artikelnummer").value = p.artikelnummer;
        document.getElementById("edit-hersteller").value = p.hersteller;
        document.getElementById("edit-farbe").value = p.farbe;
        document.getElementById("edit-qualitaet").value = p.qualitaet;
        document.getElementById("edit-oberflaeche").value = p.oberflaeche;
        document.getElementById("edit-anwendung").value = p.anwendung;
        document.getElementById("edit-start_menge_kg").value = p.start_menge_kg;
        document.getElementById("edit-lagerort").value = p.lagerort;
        document.getElementById("edit-aktiv").checked = p.aktiv;

        // 🟡 WICHTIG für Optimistic Locking:
        const form = document.getElementById("editPulverForm");
        form.dataset.id = id;
        form.dataset.updated_at = p.updated_at;

        document.getElementById("editPulverModal").classList.remove("hidden");
        return;
    }

    if (e.target.matches("#cancelEditPulverModal")) {
        document.getElementById("editPulverModal").classList.add("hidden");
        return;
    }

    if (e.target.matches("#deletePulverBtn")) {

        // 🔐 Permission prüfen
        if (!(await userHasPermission("powder.delete"))) {
            alert("❌ Sie haben keine Berechtigung, Pulver zu löschen.");
            return;
        }

        const id = document.getElementById("editPulverForm").dataset.id;

        if (!confirm("⚠️ Dieses Pulver wirklich löschen?")) return;

        try {
            const res = await apiFetch(`/api/pulver/${id}`, {
                method: "DELETE",
            });

            alert("Pulver gelöscht.");
            document.getElementById("editPulverModal").classList.add("hidden");
            loadPowders();

        } catch (err) {
            alert("Fehler:\n" + err.message);
        }
    }
}


// ==========================================================
//  SUBMIT EVENTS
// ==========================================================

async function onPulverSubmit(e) {
    e.preventDefault();
    const form = e.target;

    if (form.id === "newPulverForm") {
        return handleNewPowder(form);
    }

    if (form.id === "trackingForm") {
        return handleTracking(form);
    }
    if (form.id === "editPulverForm") {
        return handleEditPulver(form);
    }
}


// ==========================================================
//  HANDLER: Neues Pulver
// ==========================================================

async function handleNewPowder(form) {
    const payload = {
        artikelnummer: form.artikelnummer.value.trim(),
        hersteller: form.hersteller.value.trim(),
        farbe: form.farbe.value.trim(),
        qualitaet: form.qualitaet.value.trim(),
        oberflaeche: form.oberflaeche.value.trim(),
        anwendung: form.anwendung.value.trim(),
        start_menge_kg: parseFloat(form.start_menge_kg.value),
        lagerort: form.lagerort.value.trim(),
    };

    try {
        const res = await apiFetch("/api/pulver/", {
            method: "POST",
            body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Fehler");

        alert(`Pulver erzeugt! Barcode: ${data.pulver.barcode}`);
        document.getElementById("newPulverModal").classList.add("hidden");

        loadPowders().then(() => setupFilter());

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }
}

// ==========================================================
//  HANDLER: Pulverbearbeiten
// ==========================================================

async function handleEditPulver(form) {
    const id = form.dataset.id;

    const payload = {
        artikelnummer: form["edit-artikelnummer"].value.trim(),
        hersteller: form["edit-hersteller"].value.trim(),
        farbe: form["edit-farbe"].value.trim(),
        qualitaet: form["edit-qualitaet"].value.trim(),
        oberflaeche: form["edit-oberflaeche"].value.trim(),
        anwendung: form["edit-anwendung"].value.trim(),
        start_menge_kg: parseFloat(form["edit-start_menge_kg"].value),
        lagerort: form["edit-lagerort"].value.trim(),
        aktiv: form["edit-aktiv"].checked,

        // 🔥 Optimistic Locking
        updated_at: form.dataset.updated_at
    };

    try {
        const res = await apiFetch(`/api/pulver/${id}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.status === 409) {
            alert("⚠️ Dieses Pulver wurde inzwischen von einem anderen Benutzer geändert.\nBitte Seite aktualisieren.");
            return;
        }

        if (!res.ok) {
            throw new Error(data.detail || "Unbekannter Fehler");
        }

        alert("Pulver gespeichert.");
        document.getElementById("editPulverModal").classList.add("hidden");
        loadPowders();

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }
}
// ==========================================================
//  HANDLER: Tracking
// ==========================================================

async function handleTracking(form) {
    const payload = {
        barcode: form["track-barcode"].value.trim(),
        menge_neu: parseFloat(form["track-menge-neu"].value),
        beschreibung: form["track-beschreibung"].value.trim() || "Normaler Verbrauch"
    };

    try {
        const res = await apiFetch("/api/pulver/track", {
            method: "POST",
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Fehler");

        alert("Bewegung gespeichert!");
        document.getElementById("trackingModal").classList.add("hidden");

        loadPowders().then(() => setupFilter());

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }
}


// ==========================================================
//  KEYDOWN EVENTS (Barcode-Suche)
// ==========================================================

async function onPulverKeydown(e) {

    if (e.key !== "Enter") return;
    if (document.activeElement.id !== "track-barcode") return;

    e.preventDefault();
    const barcode = e.target.value.trim();
    if (!barcode) return;

    try {
        const res = await apiFetch(`/api/pulver/${barcode}`);
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Fehler");

        document.getElementById("track-menge-alt").value = data.menge_kg || 0;
        document.getElementById("track-menge-neu").focus();

    } catch (err) {
        alert("Pulver nicht gefunden!");
    }
}



// ==========================================================
//  FILTERFUNKTIONEN
// ==========================================================

function setupFilter() {
    const colSelect = document.getElementById("filter-column");
    const queryInput = document.getElementById("filter-query");
    const resetBtn = document.getElementById("filter-reset");

    if (!colSelect || !queryInput) return;

    function applyFilter() {
        const col = colSelect.value;
        const query = queryInput.value.trim().toLowerCase();

        const rows = document.querySelectorAll("#pulver-table tbody tr");

        const map = {
            barcode: 1,
            artikelnummer: 2,
            hersteller: 3,
            farbe: 4,
            qualitaet: 5,
            oberflaeche: 6,
            anwendung: 7
        };

        rows.forEach(row => {
            const cells = row.querySelectorAll("td");
            let show = false;

            if (!query) {
                show = true;
            }
            else if (!col) {
                // Suche in ALLEN relevanten Spalten
                Object.values(map).forEach(i => {
                    const txt = cells[i]?.textContent.toLowerCase();
                    if (txt.includes(query)) show = true;
                });
            }
            else {
                // Suche in bestimmter Spalte
                const colIndex = map[col];
                const txt = cells[colIndex]?.textContent.toLowerCase();
                if (txt.includes(query)) show = true;
            }

            row.style.display = show ? "" : "none";
        });
    }

    colSelect.addEventListener("change", applyFilter);
    queryInput.addEventListener("input", applyFilter);
    resetBtn.addEventListener("click", () => {
        queryInput.value = "";
        colSelect.value = "";
        applyFilter();
    });
}

// ==========================================================
//  WEBSOCKET EVENTS (Live Updates)
// ==========================================================

function onPulverWebSocketEvent(e) {
    const msg = e.detail;

    // Pulver wurde bearbeitet → Tabelle neu laden
    if (msg.event === "pulver_updated") {
        console.log("🔄 WS: pulver_updated → reload");
        loadPowders();
        return;
    }

    // Neues Pulver
    if (msg.event === "pulver_created") {
        console.log("🆕 WS: pulver_created → reload");
        loadPowders();
        return;
    }

    // Pulver gelöscht
    if (msg.event === "pulver_deleted") {
        console.log("❌ WS: pulver_deleted → reload");
        loadPowders();
        return;
    }

    // Pulver getrackt
    if (msg.event === "pulver_tracked") {
        console.log("📦 WS: pulver_tracked → reload");
        loadPowders();
        return;
    }
}