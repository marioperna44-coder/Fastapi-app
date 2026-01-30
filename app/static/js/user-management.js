console.log("🟦 user-management.js geladen", performance.now());
let userWSInitialized = false;

// Der Standardwert, ob gelöschte Benutzer angezeigt werden
let isShowingDeleted = false; 

// ==========================================================
//  USER MANAGEMENT – MODUL INITIALISIEREN
// ==========================================================

function initUserManagement() {
    console.log("🚀 User-Management Modul aktiviert");

    const root = document.getElementById("content");
    if (!root) {
        console.error("❌ #content nicht gefunden!");
        return;
    }

    // Events NUR in diesem Bereich
    root.addEventListener("click", onUserClick);
    root.addEventListener("submit", onUserSubmit);

    // 🔥 WebSocket Listener nur EINMAL registrieren!
    if (!userWSInitialized) {
        document.addEventListener("ws-event", onUserWebSocketEvent);
        userWSInitialized = true;
    }

    // Start: Benutzerliste laden
    loadUsers();
}

window.initUserManagement = initUserManagement;


function refreshUserManagement() {
    console.log("🔄 UserManagement Refresh");

    // Tabelle neu laden – Aktuellen Zustand der Ansicht beibehalten
    loadUsers(isShowingDeleted); 

    // Modals schließen (falls aus vorheriger Ansicht noch offen)
    const newModal = document.getElementById("newUserModal");
    if (newModal) newModal.classList.add("hidden");

    const editModal = document.getElementById("editUserModal");
    if (editModal) editModal.classList.add("hidden");
}

window.refreshUserManagement = refreshUserManagement;

// ==========================================================
//  API: Benutzer laden
// ==========================================================

/**
 * Lädt Benutzerdaten. Passt die URL basierend auf isShowingDeleted an.
 */
async function loadUsers() {
    // Die URL wird jetzt durch den globalen Zustand gesteuert
    const url = `/api/users/${isShowingDeleted ? '?show_deleted=true' : ''}`;
    
    console.log(`Fetching users (showDeleted: ${isShowingDeleted}) from: ${url}`);
    
    try {
        const res = await apiFetch(url);
        const users = await res.json();

        const tbody = document.querySelector("#users-table tbody");
        tbody.innerHTML = "";
        
        users.forEach(u => {
            const tr = document.createElement("tr");
            tr.dataset.userid = u.id;
            
            // Visuelle Hervorhebung für gelöschte Benutzer
            if (u.deleted) {
                tr.classList.add("deleted-user"); 
            }
            
            // Logik zur Button-Generierung, jetzt mit getrennten Klassen
            const actionButtonHtml = u.deleted 
                ? `<!-- Gelöscht: Button zum Wiederherstellen -->
                   <button class="btn-restore-user btn btn-success btn-sm">Wiederherstellen</button>`
                : `<!-- Aktiv: Button zum Löschen -->
                   <button class="btn-delete-user btn btn-danger btn-sm">Löschen</button>`;

            // Formatierung der Zeile
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.username}</td>
                <td>${u.email}</td>
                <td>${u.role_name || "-"}</td>
                <td>${u.active ? "Ja" : "Nein"} ${u.deleted ? ' (Gelöscht)' : ''}</td>
                <td>${formatDate(u.last_login)}</td>
                <td>
                    <!-- Bearbeiten Button deaktivieren, wenn gelöscht -->
                    <button class="btn-edit-user btn btn-secondary btn-sm" ${u.deleted ? 'disabled' : ''}>Bearbeiten</button>
                    ${actionButtonHtml}
                </td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("❌ Fehler beim Laden:", err);
    }
}

function formatDate(dateString) {
    if (!dateString) return "-";
    const d = new Date(dateString);
    return d.toLocaleString("de-DE");
}


// ==========================================================
//  CLICK EVENTS
// ==========================================================

async function onUserClick(e) {

    // ➕ Neuer Benutzer
    if (e.target.matches("#btn-new-user")) {
        e.preventDefault();
        if (!(await userHasPermission("user.create"))) {
            alert("❌ Sie haben keine Berechtigung, einen neuen Benutzer anzulegen.");
            return;
        }
        document.getElementById("newUserModal").classList.remove("hidden");
        return;
    }

    // 🔄 Aktualisieren
    if (e.target.matches("#btn-refresh-users")) {
        e.preventDefault();
        loadUsers(isShowingDeleted);
        return;
    }
    
    // 👁️ Umschalten der Ansicht
    if (e.target.matches("#btn-toggle-deleted")) {
        e.preventDefault();
        
        isShowingDeleted = !isShowingDeleted;
        
        const btn = e.target;
        if (isShowingDeleted) {
            btn.textContent = '👀 Aktive Benutzer';
            btn.classList.remove('btn-info');
            btn.classList.add('btn-secondary');
        } else {
            btn.textContent = '👀 Vollständige Ansicht';
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-info');
        }

        loadUsers();
        return;
    }

    // ========================================================
    // 📊 Benutzerliste exportieren (JETZT MIT apiFetch)
    // ========================================================
    if (e.target.matches("#btn-export-users")) {
        console.log("EXPORT BUTTON CLICKED");
        e.preventDefault();

        // --- 1) Permission-Check ---
        if (!(await userHasPermission("user.manage"))) {
            alert("❌ Sie haben keine Berechtigung, Benutzer zu exportieren.");
            return;
        }

        console.log("Permission ok");
        
        try {
            // --- 2) Token holen ---
            const token = localStorage.getItem("token");
            if (!token) {
                alert("❌ Keine gültige Sitzung – bitte erneut anmelden.");
                logoutUser();
                return;
            }

            // --- 3) API-Aufruf (kein JSON-Header!) ---
            const res = await fetch("/api/users/export", {
                method: "GET",
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });

            if (!res.ok) {
                alert("❌ Export fehlgeschlagen (" + res.status + ")");
                return;
            }

            // --- 4) Datei als Blob einlesen ---
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);

            // --- 5) Automatischen Download auslösen ---
            const a = document.createElement("a");
            a.href = url;
            a.download = "users.xlsx"; // Dateiname
            document.body.appendChild(a);
            a.click();
            a.remove();

            // Ressourcen freigeben
            setTimeout(() => URL.revokeObjectURL(url), 5000);

        } catch (error) {
            console.error("Export-Fehler:", error);
            alert("❌ Es ist ein unerwarteter Fehler aufgetreten.");
        }
    }

    // ❌ Modal schließen
    if (e.target.matches("#cancelNewUserModal")) {
        e.preventDefault();
        document.getElementById("newUserModal").classList.add("hidden");
        return;
    }

    // ❌ Modal schließen
    if (e.target.matches("#cancelNewUserModal")) {
        e.preventDefault();
        document.getElementById("newUserModal").classList.add("hidden");
        return;
    }

    // ========================================================
    // ✏️ Benutzer bearbeiten
    // ========================================================
    if (e.target.matches(".btn-edit-user")) {

        if (!(await userHasPermission("user.update"))) {
            alert("❌ Sie haben keine Berechtigung, Benutzer zu bearbeiten.");
            return;
        }

        const tr = e.target.closest("tr");
        const userId = tr.dataset.userid;

        // FRISCHE Daten aus der API holen
        const res = await apiFetch(`/api/users/${userId}`);
        const user = await res.json();
        
        // Obwohl der Button disabled ist, zusätzliche Absicherung
        if (user.deleted) {
             alert("❌ Gelöschte Benutzer können nicht bearbeitet werden. Bitte zuerst wiederherstellen.");
             return;
        }

        // Felder befüllen
        document.getElementById("edit-username").value = user.username;
        document.getElementById("edit-email").value = user.email;
        document.getElementById("edit-role_id").value = user.role_id;
        document.getElementById("edit-active").checked = user.active;

        // OPTIMISTIC LOCKING: updated_at speichern
        const form = document.getElementById("editUserForm");
        form.dataset.userid = userId;
        form.dataset.updated_at = user.updated_at;

        document.getElementById("editUserModal").classList.remove("hidden");
        return;
    }

    // ❌ Edit Modal schließen
    if (e.target.matches("#cancelEditModal")) {
        document.getElementById("editUserModal").classList.add("hidden");
        return;
    }

    // ========================================================
    // 🗑️ Benutzer löschen (Nur für aktive Benutzer)
    // ========================================================
    if (e.target.matches(".btn-delete-user")) {
        
        if (!(await userHasPermission("user.delete"))) {
            alert("❌ Sie haben keine Berechtigung, Benutzer zu löschen.");
            return;
        }

        const tr = e.target.closest("tr");
        const userId = tr.dataset.userid;
        
        if (!confirm(`⚠️ Benutzer wirklich löschen?`)) return;

        try {
            const res = await apiFetch(`/api/users/${userId}`, {
                method: "DELETE",
            });
            
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.detail || "Fehler");
            
            alert(`Benutzer erfolgreich gelöscht.`);
            loadUsers(); 
            
        } catch (err) {
            alert("Fehler beim Löschen:\n" + err.message);
        }
        return;
    }

    // ========================================================
    // ♻️ Benutzer wiederherstellen (Nur für gelöschte Benutzer)
    // ========================================================
    if (e.target.matches(".btn-restore-user")) {
        
        if (!(await userHasPermission("user.update"))) { // Permission beibehalten
            alert("❌ Sie haben keine Berechtigung, Benutzer wiederherzustellen.");
            return;
        }

        const tr = e.target.closest("tr");
        const userId = tr.dataset.userid;
        
        if (!confirm(`⚠️ Benutzer wirklich wiederherstellen?`)) return;

        try {
            // Endpunkt zur Wiederherstellung nutzen
            const res = await apiFetch(`/api/users/restore/${userId}`, { 
                method: "PUT",
            });
            
            const data = await res.json();
            
            if (!res.ok) throw new Error(data.detail || "Fehler");
            
            alert(`Benutzer erfolgreich wiederhergestellt.`);
            loadUsers(); 
            
        } catch (err) {
            alert("Fehler beim Wiederherstellen:\n" + err.message);
        }
        return;
    }
}


// ==========================================================
//  SUBMIT EVENTS (Formulare)
// ==========================================================

async function onUserSubmit(e) {
    e.preventDefault();
    const form = e.target;

    // ➕ Neuen Benutzer anlegen
    if (form.id === "newUserForm") {
        return handleNewUser(form);
    }

    // ✏️ Benutzer bearbeiten
    if (form.id === "editUserForm") {
        return handleEditUser(form);
    }
}


// ==========================================================
//  HANDLER – Benutzer erstellen
// ==========================================================

async function handleNewUser(form) {
    const payload = {
        username: form.username.value.trim(),
        email: form.email.value.trim(),
        role_id: parseInt(form.role_id.value),
        active: form.active.checked
    };

    try {
        const res = await apiFetch("/api/users/", {
            method: "POST",
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (!res.ok) throw new Error(data.detail || "Fehler");

        alert(`Benutzer angelegt. Passwort:\n${data.temp_password}`);
        document.getElementById("newUserModal").classList.add("hidden");
        loadUsers();

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }
}


// ==========================================================
//  HANDLER – Benutzer bearbeiten
// ==========================================================

async function handleEditUser(form) {
    const userId = form.dataset.userid;

    const payload = {
        username: form["edit-username"].value.trim(),
        email: form["edit-email"].value.trim(),
        role_id: parseInt(form["edit-role_id"].value),
        active: form["edit-active"].checked,
        
        updated_at: form.dataset.updated_at
    };

    try {
        const res = await apiFetch(`/api/users/${userId}`, {
            method: "PUT",
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.status === 409) {
            alert("⚠️ Dieser Benutzer wurde inzwischen von einem anderen Benutzer geändert.\nBitte Seite aktualisieren.");
            return;
        }

        if (!res.ok) throw new Error(data.detail || "Fehler");

        alert("Benutzer gespeichert.");
        document.getElementById("editUserModal").classList.add("hidden");
        loadUsers();

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }

}

// ==========================================================
//  WEBSOCKET Events Live Update
// ==========================================================

function onUserWebSocketEvent(e) {
    const msg = e.detail;

    if (msg.event === "user_created" || msg.event === "user_updated" || msg.event === "user_deleted") {
        console.log(`📡 WS: User Event ${msg.event} → reload`);
        loadUsers();
        return;
    }
}