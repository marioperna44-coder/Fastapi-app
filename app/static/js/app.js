let globalWS = null;
let CURRENT_USER = null;   // Cache für /api/me
let CURRENT_USER_LOADING = null; // Verhindert doppelte Requests

/* ============================================================
   📌 PAGE → SCRIPT ZUORDNUNG
============================================================ */

const PAGE_SCRIPTS = {
    rollenrechte: "/static/js/rollenrechte.js",
    pulverlager: "/static/js/pulverlager.js",
    benutzer: "/static/js/user-management.js"
};

function initGlobalWebSocket() {
    console.log("🔌 Verbinde globalen WebSocket...");
    
    // *** WICHTIGE KORREKTUR FÜR RENDER (WSS/WS) ***
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    
    // Verbinde unter Verwendung des korrekten Protokolls (wss:// auf Render)
    globalWS = new WebSocket(`${protocol}://${location.host}/ws/app`);
    
    // ... der Rest Ihrer Funktion bleibt unverändert ...
    globalWS.onopen = () => {
        console.log("✅ Globaler WebSocket verbunden!");
    };

    globalWS.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            document.dispatchEvent(
                new CustomEvent("ws-event", { detail: msg })
            );
        } catch (e) {
            console.error("❌ Fehler beim Lesen der WS-Nachricht:", e);
        }
    };

    globalWS.onerror = (err) => {
        console.error("❌ Globaler WebSocket Fehler:", err);
    };

    globalWS.onclose = () => {
        console.warn("⚠️ Globaler WebSocket getrennt — versuche Reconnect in 2s...");
        setTimeout(initGlobalWebSocket, 2000);
    };
}

// WebSocket beim Laden der Seite initialisieren
initGlobalWebSocket();


console.log("✅ Neue app.js geladen (Professional Mode)");

function refreshRolesPage() {
    console.log("🔄 Refresh Rollenrechte");
    loadRoles();
    loadPermissions();
}

window.refreshRolesPage = refreshRolesPage;

/* ============================================================
   🔐 AUTH & PERMISSIONS
============================================================ */

function getToken() {
    return localStorage.getItem("token");
}

async function loadCurrentUser() {
    // Verhindert mehrere parallele Requests
    if (CURRENT_USER_LOADING) return CURRENT_USER_LOADING;

    CURRENT_USER_LOADING = (async () => {
        try {
            const res = await apiFetch("/api/me");
            if (!res.ok) throw new Error("Fehler beim Laden des Benutzers");
            CURRENT_USER = await res.json();
            return CURRENT_USER;
        } finally {
            CURRENT_USER_LOADING = null;
        }
    })();

    return CURRENT_USER_LOADING;
}

async function userHasPermission(perm) {
    const user = await loadCurrentUser();
    return user.permissions.includes(perm);
}

function logoutUser() {
    localStorage.clear();
    sessionStorage.clear();
    window.location.href = "/login";
}

function isExpiring(token) {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const expMs = payload.exp * 1000;
        const now = Date.now();

        return expMs - now < 10 * 60 * 1000;  // < 10 Minuten
    } catch {
        return false;
    }
}

/* ============================================================
   🌐 API WRAPPER (automatische Token-Behandlung)
============================================================ */

window.apiFetch = async (url, options = {}) => {
    let token = getToken();

    if (!token) {
        console.warn("⚠️ Kein Token – redirect");
        logoutUser();
        return;
    }

    // Token auslesen und prüfen, ob es bald abläuft (<10 Minuten)
    const isExpiring = (() => {
        try {
            const payload = JSON.parse(atob(token.split(".")[1]));
            const expMs = payload.exp * 1000;
            const now = Date.now();
            return expMs - now < 10 * 60 * 1000; // 10 Minuten
        } catch {
            return false;
        }
    })();

    // 🔄 Token erneuern, falls nötig
    if (isExpiring) {
        console.log("⏳ Token läuft bald ab → erneuere...");

        const refreshRes = await fetch("/api/refresh", {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` }
        });

        if (refreshRes.ok) {
            const data = await refreshRes.json();
            localStorage.setItem("token", data.access_token);
            token = data.access_token; // neuen Token verwenden
        } else {
            console.warn("⚠️ Token-Erneuerung fehlgeschlagen");
        }
    }

    // Header mit (neuem) Token erstellen
    const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {})
    };

    // Eigentliche API-Request
    const res = await fetch(url, {
        ...options,
        headers
    });

    // Ungültiger Token → Session beenden
    if (res.status === 401) {
        alert("🔒 Sitzung abgelaufen, bitte erneut anmelden.");
        logoutUser();
        return;
    }

    return res;
};


/* ============================================================
   📌 INIT ON PAGE LOAD
============================================================ */

document.addEventListener("DOMContentLoaded", async () => {

    const ok = await checkSessionValid();
    if (!ok) return; // login redirect wurde bereits ausgelöst

    
    setupLogoutButton();
    setupSidebarNavigation();
    loadContent("startseite"); // Standardseite
});


/* ============================================================
   🧪 LOGIN STATUS PRÜFEN
============================================================ */

function checkLogin() {
    const token = getToken();
    if (!token) {
        window.location.href = "/login";
        return;
    }

    const username = localStorage.getItem("username");
    if (username && document.getElementById("username")) {
        document.getElementById("username").textContent = `Angemeldet als: ${username}`;
    }
}

async function checkSessionValid() {
    const token = getToken();
    if (!token) {
        console.log("❌ Kein Token → redirect login");
        logoutUser();
        return false;
    }

    // Token dekodieren
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));
        const expMs = payload.exp * 1000;
        const now = Date.now();

        // Token bereits abgelaufen
        if (now >= expMs) {
            console.log("❌ Token abgelaufen → redirect login");
            logoutUser();
            return false;
        }

        // Token läuft bald ab → versuchen zu verlängern
        if (expMs - now < 10 * 60 * 1000) {
            console.log("⏳ Token läuft bald ab → versuche Erneuerung…");

            const refreshRes = await fetch("/api/refresh", {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` }
            });

            if (refreshRes.ok) {
                const data = await refreshRes.json();
                localStorage.setItem("token", data.access_token);
                console.log("🔄 Token erfolgreich erneuert");
            } else {
                console.warn("⚠️ Token konnte nicht erneuert werden → logout");
                logoutUser();
                return false;
            }
        }

        return true;

    } catch (err) {
        console.log("❌ Ungültiges Token → redirect login");
        logoutUser();
        return false;
    }
}

/* ============================================================
   🚪 LOGOUT BUTTON
============================================================ */

function setupLogoutButton() {
    const btn = document.getElementById("logout-btn");
    if (!btn) return;

    btn.addEventListener("click", () => {
        if (confirm("Möchtest du dich wirklich abmelden?")) {
            logoutUser();
        }
    });
}


/* ============================================================
   🔽 SEITEN PERMISSION-TABELLE
============================================================ */

const PAGE_PERMISSIONS = {
    "pulverlager": "pulver.manage",
    "benutzer": "user.manage",
    "rollenrechte": "roles.manage",
    "auftragsdisplay": "auftraege.manage"
};


/* ============================================================
   📁 SIDEBAR NAVIGATION
============================================================ */

function setupSidebarNavigation() {
    document.querySelectorAll(".sidebar-link").forEach(link => {
        link.addEventListener("click", async e => {
            e.preventDefault();

            const page = link.dataset.page;
            const required = PAGE_PERMISSIONS[page];

            // active marker aktualisieren
            document.querySelectorAll(".sidebar-link").forEach(l => l.classList.remove("active"));
            link.classList.add("active");

            // Permission prüfen (Option A: sichtbar, aber blockiert)
            if (required && !(await userHasPermission(required))) {
                console.warn(`⛔ Keine Berechtigung für Seite ${page}`);
                loadContent("no_permission");
                return;
            }

            loadContent(page);
        });
    });
}


/* ============================================================
   📦 CONTENT LOADER (HTML + Scripts + Module Start)
============================================================ */

async function loadContent(page) {
    console.log(`📄 Lade Seite: ${page}`);

    try {
        const res = await fetch(`/static/content/${page}.html`);
        if (!res.ok) throw new Error(`Seite ${page} nicht gefunden`);

        const html = await res.text();
        const container = document.getElementById("content");

        // HTML einsetzen
        container.innerHTML = html;

        // Alte dynamische Skripte entfernen
        cleanupDynamicScripts();

        // Falls die Seite ein JS-Modul hat → laden
        if (PAGE_SCRIPTS[page]) {
            // Prüfen, ob das Script bereits existiert
            const alreadyLoaded = document.querySelector(`script[src="${PAGE_SCRIPTS[page]}"]`);

            if (!alreadyLoaded) {
                console.log("📥 Lade Seitenscript:", PAGE_SCRIPTS[page]);

                const s = document.createElement("script");
                s.src = PAGE_SCRIPTS[page];

                s.onload = () => startModules();
                document.body.appendChild(s);
            } else {
                console.log("⏭️ Seitenscript bereits geladen → nutze vorhandenes");
                startModules();
            }
        }

    } catch (err) {
        document.getElementById("content").innerHTML =
            `<p style="color:red;">Fehler: ${err.message}</p>`;
    }
}


/* ============================================================
   🧹 SKRIPTE REINIGEN / NEU LADEN
============================================================ */

function cleanupDynamicScripts() {

    // Liste aller Modul-Dateien, die niemals doppelt im DOM sein dürfen
    const MODULE_SCRIPTS = [
        "user-management.js",
        "rollenrechte.js",
        "pulverlager.js",
        "auftragsdisplay.js"
    ];
   
    // 2️⃣ Zusätzlich alte dynamische Scripts entfernen
    document.querySelectorAll("script[data-dynamic]")
        .forEach(s => s.remove());
}

/* ============================================================
   📌 MODULE DEFINITIONS (Selector → Init-Funktion)
============================================================ */

const MODULES = {
    roles: {
        selector: ".roles-container",
        init: "initRolesPage",
        refresh: "refreshRolesPage"
    },
    pulver: {
        selector: "#pulver-table",
        init: "initPulverlager",
        refresh: "refreshPulverlager"
    },
    users: {
        selector: "#users-table",
        init: "initUserManagement",
        refresh: "refreshUserManagement"
    }
};

/* ============================================================
   🚀 MODUL-SYSTEM (Auto-Detection)
============================================================ */

const MODULE_STATE = {}; // Merkt sich, welche Module schon initialisiert wurden

function startModules() {
    console.log("🔍 Module scannen...");

    Object.entries(MODULES).forEach(([key, mod]) => {
        const existsInDOM = document.querySelector(mod.selector);
        const initFn = window[mod.init];
        const refreshFn = window[mod.refresh];

        if (!existsInDOM) return;

        // Modul wurde bereits gestartet → nur refreshe
        if (MODULE_STATE[key]) {
            if (typeof refreshFn === "function") {
                console.log(`🔄 Refreshe Modul: ${mod.refresh}`);
                refreshFn();
            }
            return;
        }

        // Modul zum ersten Mal starten
        if (typeof initFn === "function") {
            console.log(`➡️ Starte Modul: ${mod.init}`);
            initFn();
            MODULE_STATE[key] = true;
        }
    });
}