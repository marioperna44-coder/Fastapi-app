/* console.log("📌 rollenrechte.js geladen");

function initRolesPage() {
    console.log("🚀 Rollen & Rechte Modul gestartet");

    loadRoles();
    loadPermissions();

    const root = document.getElementById("content");
    root.addEventListener("click", onClick);
    root.addEventListener("submit", onSubmit);
}

window.initRolesPage = initRolesPage;

// ============================================================
// 🔹 Globale Daten
// ============================================================

let ALL_PERMISSIONS = [];
let ALL_ROLES = [];
let CURRENT_ROLE = null;

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

            li.innerHTML = `
                <span>${role.name}</span>
            `;

            list.appendChild(li);
        });

    } catch (err) {
        console.error("❌ Fehler beim Laden der Rollen:", err);
    }
}

// ============================================================
// 📌 Alle Permissions laden
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
// 🔄 Rolle anklicken → Rechte anzeigen
// ============================================================

async function onClick(e) {
    if (e.target.closest(".role-item")) {
        const id = e.target.closest(".role-item").dataset.id;
        selectRole(Number(id));
        return;
    }

    // Neue Rolle
    if (e.target.matches("#btn-add-role")) {
        openNewRoleModal();
    }
}

// ============================================================
// 📌 Rolle auswählen
// ============================================================

async function selectRole(roleId) {
    CURRENT_ROLE = ALL_ROLES.find(r => r.id === roleId);

    if (!CURRENT_ROLE) return;

    // UI setzen
    document.getElementById("role-title").textContent = `Rechte: ${CURRENT_ROLE.name}`;
    document.getElementById("role-description").textContent =
        CURRENT_ROLE.description || "";

    document.getElementById("btn-save-permissions").classList.remove("hidden");

    try {
        const res = await apiFetch(`/api/roles/roles/${roleId}/permissions`);
        const data = await res.json();

        renderPermissionCheckboxes(data.permissions);

    } catch (err) {
        console.error("❌ Fehler beim Laden der Rollenrechte:", err);
    }
}

// ============================================================
// 📌 Permission-Checkboxen anzeigen
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
// 💾 Rechte speichern
// ============================================================

async function savePermissions() {
    
    if (!CURRENT_ROLE) return;

    const ids = [...document.querySelectorAll(".perm-check:checked")]
        .map(c => Number(c.dataset.id));

    try {
        const res = await apiFetch("/api/roles/assign_permissions", {
            method: "POST",
            body: JSON.stringify({
                role_id: CURRENT_ROLE.id,
                permission_ids: ids
            })
        });

        const json = await res.json();
        if (!res.ok) throw new Error(json.detail);

        alert("Rechte erfolgreich gespeichert!");

    } catch (err) {
        alert("Fehler beim Speichern:\n" + err.message);
    }
}

// ============================================================
// ✏ Neue Rolle erstellen
// ============================================================

async function openNewRoleModal() {

    if (!(await userHasPermission("new.role"))) {
        alert("❌ Sie haben keine Berechtigung, eine neue Rolle anzulegen.");
        return;
    }

    const name = prompt("Name der neuen Rolle:");
    if (!name) return;

    const description = prompt("Beschreibung (optional):") || "";

    createRole(name, description);
}

async function createRole(name, description) {
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
// 📌 Event Listener für Speichern
// ============================================================

async function onSubmit(e) {
    if (e.target.matches("#save-permissions-form")) {

        if (!(await userHasPermission("manage.permission"))) {
            alert("❌ Sie haben keine Berechtigung, Rollenrechte zu speichern.");
            return;
        }

        savePermissions();
    }
}

document.addEventListener("click", e => {
    if (e.target.matches("#btn-save-permissions")) {
        savePermissions();
    }
});
*/