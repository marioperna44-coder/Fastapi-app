console.log("=== LADEN ROLLENRECHTE.JS ===")

// ============================================================
// 🔹 Globale Daten
// ============================================================

let ALL_PERMISSIONS = [];
let ALL_ROLES = [];
let CURRENT_ROLE = null;
let rolesWSInitialized = false;


// ============================================================
// 🚀 Rollen & Rechte – MODUL INITIALISIEREN
// ============================================================

function initRolesPage() {
    console.log("🚀 Rollen & Rechte Modul gestartet");

    loadRoles();
    loadPermissions();

    const root = document.getElementById("content");

    root.addEventListener("click", onClick);
    root.addEventListener("submit", onSubmit);

    // WebSocket Listener NUR EINMAL registrieren
    if (!rolesWSInitialized) {
        document.addEventListener("ws-event", onRolesWebSocketEvent);
        rolesWSInitialized = true;
    }
}

window.initRolesPage = initRolesPage;


// ============================================================
// 📌 Rollen laden
// ============================================================

async function loadRoles() {
    try {
        const res = await apiFetch("/api/roles/roles");
        ALL_ROLES = await res.json();

        const list = document.getElementById("roles-list");
        list.innerHTML = "";

        ALL_ROLES.forEach(role => {
            const li = document.createElement("li");
            li.classList.add("role-item");
            li.dataset.id = role.id;

            li.innerHTML = `<span>${role.name}</span>`;
            list.appendChild(li);
        });

    } catch (err) {
        console.error("❌ Fehler beim Laden der Rollen:", err);
    }
}


// ============================================================
// 📌 Permissions laden
// ============================================================

async function loadPermissions() {
    try {
        const res = await apiFetch("/api/roles/permissions");
        ALL_PERMISSIONS = await res.json();
    } catch (err) {
        console.error("❌ Fehler beim Laden der Permissions:", err);
    }
}


// ============================================================
// 🔄 KLICK EVENTS
// ============================================================

async function onClick(e) {

    // Rolle auswählen
    if (e.target.closest(".role-item")) {
        console.log("→ ROLE CLICK");
        const id = e.target.closest(".role-item").dataset.id;
        selectRole(Number(id));
        return;
    }

    // Neue Rolle
    if (e.target.closest("#btn-add-role")) {
        console.log("→ ADD ROLE CLICK");
        openNewRoleModal();
        return;
    }

    // Rechte speichern
    if (e.target.closest("#btn-save-permissions")) {
        console.log("→ DIRECT SAVE");
        handleSavePermissions();
        return;

    }
}

// ============================================================
// 📝 SUBMIT EVENTS
// ============================================================

async function onSubmit(e) {
    e.preventDefault();
    const form = e.target;

    if (form.id === "newRoleForm") {
        return handleCreateRole(form);
    }
}


// ============================================================
// 📌 Rolle auswählen & Rechte laden
// ============================================================

async function selectRole(roleId) {

    CURRENT_ROLE = ALL_ROLES.find(r => r.id === roleId);
    if (!CURRENT_ROLE) return;

    document.getElementById("role-title").textContent =
        `Rechte: ${CURRENT_ROLE.name}`;
    document.getElementById("role-description").textContent =
        CURRENT_ROLE.description || "";

    document.getElementById("btn-save-permissions").classList.remove("hidden");

    try {
        const res = await apiFetch(`/api/roles/roles/${roleId}/permissions`);
        const data = await res.json();

        renderPermissionCheckboxes(data.permissions);

        // Für Optimistic Locking speichern
        CURRENT_ROLE.updated_at = data.updated_at;

    } catch (err) {
        console.error("❌ Fehler beim Laden der Rollenrechte:", err);
    }
}


// ============================================================
// 📌 Permissions anzeigen
// ============================================================

function renderPermissionCheckboxes(assignedIds) {
    const container = document.getElementById("permissions-list");
    container.innerHTML = "";

    ALL_PERMISSIONS.forEach(perm => {
        const box = document.createElement("div");
        box.classList.add("permission-item");

        box.innerHTML = `
            <label>
                <input type="checkbox" 
                       class="perm-check"
                       data-id="${perm.id}"
                       ${assignedIds.includes(perm.id) ? "checked" : ""} />
                <strong>${perm.name}</strong>
                <small>${perm.description || ""}</small>
            </label>
        `;

        container.appendChild(box);
    });
}


// ============================================================
// 💾 Rechte speichern (Handler)
// ============================================================

async function handleSavePermissions() {

    if (!(await userHasPermission("manage.permission"))) {
        alert("❌ Sie haben keine Berechtigung, Rollenrechte zu speichern.");
        return;
    }

    if (!CURRENT_ROLE) return;

    const ids = [...document.querySelectorAll(".perm-check:checked")]
        .map(c => Number(c.dataset.id));

    try {
        const res = await apiFetch("/api/roles/assign_permissions", {
            method: "POST",
            body: JSON.stringify({
                role_id: CURRENT_ROLE.id,
                permission_ids: ids,
                updated_at: CURRENT_ROLE.updated_at
            })
        });

        const json = await res.json();

        if (!res.ok) throw new Error(json.detail || "Fehler");

        CURRENT_ROLE.updated_at = json.updated_at;

        alert("Rechte erfolgreich gespeichert!");

    } catch (err) {

        if (err.message.includes("inzwischen geändert")) {
            alert("⚠️ Diese Rolle wurde inzwischen geändert. Bitte neu laden.");
            return;
        }

        alert("Fehler:\n" + err.message);
    }
}


// ============================================================
// ✏️ Neue Rolle Modal öffnen → Prompt-Version
// ============================================================

async function openNewRoleModal() {

    if (!(await userHasPermission("new.role"))) {
        alert("❌ Sie haben keine Berechtigung, eine neue Rolle anzulegen.");
        return;
    }

    const name = prompt("Name der neuen Rolle:");
    if (!name) return;

    const description = prompt("Beschreibung (optional):") || "";

    handleCreateRolePrompt(name, description);
}


// ============================================================
// ✏️ Neue Rolle erstellen (Prompt Variante)
// ============================================================

async function handleCreateRolePrompt(name, description) {
    try {
        const res = await apiFetch("/api/roles/", {
            method: "POST",
            body: JSON.stringify({ name, description })
        });

        const json = await res.json();
        if (!res.ok) throw new Error(json.detail);

        alert("Rolle erstellt!");
        loadRoles();

    } catch (err) {
        alert("Fehler:\n" + err.message);
    }
}


// ============================================================
// 🌐 WebSocket – Live Updates
// ============================================================

function onRolesWebSocketEvent(e) {
    const msg = e.detail;

    if (msg.event === "role_created") {
        console.log("🆕 WS: role_created → reload lists");
        loadRoles();
        loadPermissions();
        return;
    }

    if (msg.event === "role_updated") {
        console.log("✏️ WS: role_updated → reload lists");
        loadRoles();
        loadPermissions();
        return;
    }
} 
