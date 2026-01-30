/* console.log("🟦 user-management.js geladen", performance.now());
let userWSInitialized = false;

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

    // Tabelle neu laden
    loadUsers();

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

async function loadUsers() {
    try {
        const res = await apiFetch("/api/users/");
        const users = await res.json();

        const tbody = document.querySelector("#users-table tbody");
        tbody.innerHTML = "";

        users.forEach(u => {
            const tr = document.createElement("tr");
            tr.dataset.userid = u.id;
            tr.innerHTML = `
                <td>${u.id}</td>
                <td>${u.username}</td>
                <td>${u.email}</td>
                <td>${u.role_name || "-"}</td>
                <td>${u.active ? "Ja" : "Nein"}</td>
                <td>${formatDate(u.last_login)}</td>
                <td>
                    <button class="btn-edit-user btn btn-secondary btn-sm">Bearbeiten</button>
                    <button class="btn-delete-user btn btn-danger btn-sm">Löschen</button>
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

        // 🔐 Permission prüfen
        if (!(await userHasPermission("user.create"))) {
            alert("❌ Sie haben keine Berechtigung, einen neuen Benutzer anzulegen.");
            return;
        }

        document.getElementById("newUserModal").classList.remove("hidden");
        return;
    }

    // ❌ Modal schließen
    if (e.target.matches("#cancelNewUserModal")) {
        e.preventDefault();
        document.getElementById("newUserModal").classList.add("hidden");
        return;
    }

    // ✏️ Benutzer bearbeiten
    if (e.target.matches(".btn-edit-user")) {

        if (!(await userHasPermission("user.update"))) {
            alert("❌ Sie haben keine Berechtigung, Benutzer zu bearbeiten.");
            return;
        }

        const tr = e.target.closest("tr");
        const userId = tr.dataset.userid;

        // 🔄 FRISCHE Daten aus der API holen (wichtig für updated_at!)
        const res = await apiFetch(`/api/users/${userId}`);
        const user = await res.json();

        // Felder befüllen
        document.getElementById("edit-username").value = user.username;
        document.getElementById("edit-email").value = user.email;
        document.getElementById("edit-role_id").value = user.role_id;
        document.getElementById("edit-active").checked = user.active;

        // 🔥 OPTIMISTIC LOCKING: updated_at speichern
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

    // 🗑️ Benutzer löschen
    if (e.target.matches(".btn-delete-user")) {

        // 🔐 Permission prüfen
        if (!(await userHasPermission("user.delete"))) {
            alert("❌ Sie haben keine Berechtigung, Benutzer zu löschen.");
            return;
        }

        const tr = e.target.closest("tr");
        const userId = tr.dataset.userid;

        if (!confirm("⚠️ Benutzer wirklich löschen?")) return;

        try {
            const res = await apiFetch(`/api/users/${userId}`, {
                method: "DELETE",
            });
            const data = await res.json();

            if (!res.ok) throw new Error(data.detail || "Fehler");

            alert("Benutzer gelöscht.");
            loadUsers();

        } catch (err) {
            alert("Fehler:\n" + err.message);
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

    if (msg.event === "user_created") {
        console.log("👤 WS: user_created → reload");
        loadUsers();
        return;
    }

    if (msg.event === "user_updated") {
        console.log("✏️ WS: user_updated → reload");
        loadUsers();
        return;
    }

    if (msg.event === "user_deleted") {
        console.log("❌ WS: user_deleted → reload");
        loadUsers();
        return;
    }
}
*/