(function () {
    var EXPANDED_WORKSPACE_KEY = "boardwalk.expandedWorkspace";
    var EXPANDED_EVENTS_KEY = "boardwalk.expandedEvents";
    var activeControlSnapshot = null;

    function storedTheme() {
        try {
            return localStorage.getItem("boardwalk.theme") || "dark";
        } catch (error) {
            return "dark";
        }
    }

    function rememberTheme(theme) {
        try {
            localStorage.setItem("boardwalk.theme", theme);
        } catch (error) {
            return;
        }
    }

    function storedSessionValue(key) {
        try {
            return sessionStorage.getItem(key) || "";
        } catch (error) {
            return "";
        }
    }

    function rememberSessionValue(key, value) {
        try {
            if (value) {
                sessionStorage.setItem(key, value);
            } else {
                sessionStorage.removeItem(key);
            }
        } catch (error) {
            return;
        }
    }

    function storedEventKeys() {
        var raw = storedSessionValue(EXPANDED_EVENTS_KEY);
        return raw ? raw.split(",").filter(Boolean) : [];
    }

    function rememberEventKey(key) {
        if (!key) return;
        var keys = storedEventKeys();
        if (keys.indexOf(key) === -1) {
            keys.push(key);
            rememberSessionValue(EXPANDED_EVENTS_KEY, keys.join(","));
        }
    }

    function findByWorkspaceKey(root, selector, key) {
        var match = null;
        (root || document).querySelectorAll(selector).forEach(function (element) {
            if (!match && element.dataset.workspaceKey === key) {
                match = element;
            }
        });
        return match;
    }

    function applyTheme(theme) {
        var root = document.documentElement;
        var dark = theme === "dark";
        root.classList.toggle("bw-theme-dark", dark);
        root.classList.toggle("bw-theme-light", !dark);
        rememberTheme(dark ? "dark" : "light");

        var toggle = document.querySelector("[data-theme-toggle]");
        if (toggle) {
            toggle.setAttribute("aria-pressed", dark ? "true" : "false");
            toggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
            toggle.setAttribute("title", dark ? "Switch to light mode" : "Switch to dark mode");
        }
    }

    function fitNames(root) {
        (root || document).querySelectorAll("[data-fit-name]").forEach(function (el) {
            el.dataset.fit = "normal";
            if (el.scrollWidth <= el.clientWidth + 0.5) return;
            el.dataset.fit = "long";
            if (el.scrollWidth <= el.clientWidth + 0.5) return;
            el.dataset.fit = "very-long";
        });
    }

    function closeRows(remember) {
        document.querySelectorAll(".bw-row-details").forEach(function (panel) {
            panel.hidden = true;
            panel.classList.remove("is-expanded");
        });
        document.querySelectorAll("[data-workspace-row]").forEach(function (row) {
            row.classList.remove("is-expanded");
        });
        document.querySelectorAll("[data-row-toggle]").forEach(function (toggle) {
            toggle.setAttribute("aria-expanded", "false");
        });
        if (remember) {
            rememberSessionValue(EXPANDED_WORKSPACE_KEY, "");
        }
    }

    function openRowByKey(key, remember) {
        var button = findByWorkspaceKey(document, "[data-row-toggle]", key);
        if (!button) return false;
        var panel = document.getElementById(button.getAttribute("aria-controls"));
        var row = findByWorkspaceKey(document, "[data-workspace-row]", key);
        if (!panel) return false;

        closeRows(false);
        panel.hidden = false;
        panel.classList.add("is-expanded");
        if (row) {
            row.classList.add("is-expanded");
        }
        button.setAttribute("aria-expanded", "true");
        if (remember) {
            rememberSessionValue(EXPANDED_WORKSPACE_KEY, key);
        }
        fitNames(panel);
        return true;
    }

    // Expansion state is per browser tab via sessionStorage. HTMX refreshes can
    // redraw the table without turning one user's expanded row into server state.
    function restoreExpandedState(root) {
        var key = storedSessionValue(EXPANDED_WORKSPACE_KEY);
        if (key) {
            openRowByKey(key, false);
        }
        storedEventKeys().forEach(function (eventKey) {
            var panel = findByWorkspaceKey(root || document, ".bw-row-details", eventKey);
            if (!panel) return;
            panel.querySelectorAll("[data-event-extra]").forEach(function (line) {
                line.hidden = false;
            });
            panel.querySelectorAll("[data-events-toggle]").forEach(function (button) {
                button.hidden = true;
            });
        });
    }

    function bindRows(root) {
        (root || document).querySelectorAll("[data-row-toggle]").forEach(function (button) {
            if (button.dataset.bound === "1") return;
            button.dataset.bound = "1";
            button.addEventListener("click", function (event) {
                event.stopPropagation();
                var target = document.getElementById(button.getAttribute("aria-controls"));
                if (!target) return;
                var open = target.hidden;
                if (open) {
                    openRowByKey(button.dataset.workspaceKey, true);
                } else {
                    closeRows(true);
                }
            });
        });

        (root || document).querySelectorAll("[data-workspace-row]").forEach(function (row) {
            if (row.dataset.bound === "1") return;
            row.dataset.bound = "1";
            row.addEventListener("click", function (event) {
                if (event.target.closest("a, button, input, select, label")) return;
                var toggle = row.querySelector("[data-row-toggle]");
                if (toggle) toggle.click();
            });
        });
    }

    function bindEventToggles(root) {
        (root || document).querySelectorAll("[data-events-toggle]").forEach(function (button) {
            if (button.dataset.bound === "1") return;
            button.dataset.bound = "1";
            button.addEventListener("click", function (event) {
                event.stopPropagation();
                var container = button.closest(".bw-events");
                if (!container) return;
                container.querySelectorAll("[data-event-extra]").forEach(function (line) {
                    line.hidden = false;
                });
                button.hidden = true;
                var panel = button.closest(".bw-row-details");
                if (panel) {
                    rememberEventKey(panel.dataset.workspaceKey);
                }
            });
        });
    }

    function bindThemeToggle() {
        var toggle = document.querySelector("[data-theme-toggle]");
        if (!toggle || toggle.dataset.bound === "1") return;
        toggle.dataset.bound = "1";
        toggle.addEventListener("click", function () {
            applyTheme(document.documentElement.classList.contains("bw-theme-dark") ? "light" : "dark");
        });
    }

    function isEditableControl(element) {
        if (!element || !element.matches) return false;
        if (!element.matches("input, textarea, select")) return false;
        return element.type !== "hidden";
    }

    function userIsEditingDashboard() {
        var active = document.activeElement;
        return isEditableControl(active) && Boolean(active.closest(".bw-dashboard"));
    }

    function fieldMatchesSnapshot(element, snapshot) {
        if (!element || !snapshot) return false;
        if (element.name !== snapshot.name) return false;
        if (element.tagName !== snapshot.tagName) return false;
        return !snapshot.type || element.type === snapshot.type;
    }

    function findControlBySnapshot(root, snapshot) {
        var match = null;
        (root || document).querySelectorAll("input, textarea, select").forEach(function (element) {
            if (!match && fieldMatchesSnapshot(element, snapshot)) {
                match = element;
            }
        });
        return match;
    }

    // Auto-refresh replaces the dashboard fragment. Capture the focused control
    // so in-progress search/filter typing survives the swap.
    function captureActiveControl() {
        var active = document.activeElement;
        if (!isEditableControl(active) || !active.closest(".bw-dashboard")) return null;
        return {
            name: active.name || "",
            tagName: active.tagName,
            type: active.type || "",
            value: active.value,
            selectionStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
            selectionEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
        };
    }

    function restoreActiveControl(root) {
        if (!activeControlSnapshot || !activeControlSnapshot.name) return;
        var control = findControlBySnapshot(root || document, activeControlSnapshot);
        if (!control) {
            activeControlSnapshot = null;
            return;
        }
        control.value = activeControlSnapshot.value;
        control.focus({ preventScroll: true });
        if (
            typeof control.setSelectionRange === "function" &&
            activeControlSnapshot.selectionStart !== null &&
            activeControlSnapshot.selectionEnd !== null
        ) {
            control.setSelectionRange(activeControlSnapshot.selectionStart, activeControlSnapshot.selectionEnd);
        }
        activeControlSnapshot = null;
    }

    function isDashboardAutoRefresh(event) {
        var detail = event.detail || {};
        var element = detail.elt;
        return Boolean(element && element.matches && element.matches(".bw-dashboard"));
    }

    function boot(root) {
        bindThemeToggle();
        bindRows(root || document);
        bindEventToggles(root || document);
        restoreExpandedState(root || document);
        fitNames(root || document);
    }

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(storedTheme());
        boot(document);
    });

    if (document.body) {
        document.body.addEventListener("htmx:beforeRequest", function (event) {
            if (isDashboardAutoRefresh(event) && userIsEditingDashboard()) {
                event.preventDefault();
            }
        });
        document.body.addEventListener("htmx:beforeSwap", function () {
            activeControlSnapshot = captureActiveControl();
        });
        document.body.addEventListener("htmx:afterSwap", function (event) {
            boot(event.target);
        });
        document.body.addEventListener("htmx:afterSettle", function (event) {
            restoreExpandedState(event.target);
            restoreActiveControl(event.target);
        });
    }
})();
