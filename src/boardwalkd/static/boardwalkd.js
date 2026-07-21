(function () {
    var EXPANDED_WORKSPACE_KEY = "boardwalk.expandedWorkspace";
    var EXPANDED_EVENTS_KEY = "boardwalk.expandedEvents";
    var refreshTransactions = new WeakMap();
    var restorationCounts = new WeakMap();
    var selectedWorkspaceKeys = new Set();

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

    function deletionCheckboxes(root) {
        return Array.prototype.slice.call((root || document).querySelectorAll("[data-delete-workspace]"));
    }

    function deletionCheckboxIsEligible(checkbox) {
        if (!checkbox || checkbox.disabled) return false;
        for (var element = checkbox; element; element = element.parentElement) {
            if (element.hidden || (element.hasAttribute && element.hasAttribute("hidden"))) return false;
            var style = window.getComputedStyle ? window.getComputedStyle(element) : null;
            if (
                style &&
                (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse")
            ) {
                return false;
            }
        }
        return true;
    }

    function clearSelectionUnlessEditing(root) {
        if (!(root || document).querySelector("[data-delete-selected]")) {
            selectedWorkspaceKeys.clear();
        }
    }

    function updateDeleteSelectedButton(root) {
        var scope = root || document;
        var button = scope.querySelector("[data-delete-selected]");
        if (!button) return;
        var checked = deletionCheckboxes(scope).filter(function (checkbox) {
            return deletionCheckboxIsEligible(checkbox) && checkbox.checked;
        });
        var count = checked.length;
        var countNode = scope.querySelector("[data-delete-count]");
        var liveNode = scope.querySelector("[data-delete-count-live]");
        var form = scope.querySelector("[data-bulk-delete-form]");
        if (countNode) countNode.textContent = String(count);
        if (liveNode) liveNode.textContent = "Delete selected (" + count + ")";
        button.disabled = count === 0;
        if (form && count) form.setAttribute("hx-confirm", deletionConfirmationMessage(checked));
        else if (form) form.removeAttribute("hx-confirm");
    }

    function restoreDeletionSelection(root) {
        var scope = root || document;
        clearSelectionUnlessEditing(scope);
        if (!scope.querySelector("[data-delete-selected]")) return;

        var eligibleKeys = new Set();
        deletionCheckboxes(scope).forEach(function (checkbox) {
            var key = checkbox.dataset.workspaceKey || "";
            var eligible = Boolean(key) && deletionCheckboxIsEligible(checkbox);
            checkbox.checked = eligible && selectedWorkspaceKeys.has(key);
            if (eligible) eligibleKeys.add(key);
        });
        selectedWorkspaceKeys.forEach(function (key) {
            if (!eligibleKeys.has(key)) selectedWorkspaceKeys.delete(key);
        });
        updateDeleteSelectedButton(scope);
    }

    function bindDeletionSelection(root) {
        var scope = root || document;
        clearSelectionUnlessEditing(scope);
        deletionCheckboxes(scope).forEach(function (checkbox) {
            if (checkbox.dataset.deletionBound === "1") return;
            checkbox.dataset.deletionBound = "1";
            checkbox.addEventListener("change", function () {
                var key = checkbox.dataset.workspaceKey || "";
                if (key && checkbox.checked && deletionCheckboxIsEligible(checkbox)) {
                    selectedWorkspaceKeys.add(key);
                } else {
                    if (key) selectedWorkspaceKeys.delete(key);
                    if (!deletionCheckboxIsEligible(checkbox)) checkbox.checked = false;
                }
                updateDeleteSelectedButton(scope);
            });
        });

        scope.querySelectorAll("[data-select-visible-status]").forEach(function (button) {
            if (button.dataset.deletionBound === "1") return;
            button.dataset.deletionBound = "1";
            button.addEventListener("click", function () {
                var status = button.dataset.selectVisibleStatus || "";
                deletionCheckboxes(scope).forEach(function (checkbox) {
                    var key = checkbox.dataset.workspaceKey || "";
                    if (
                        key &&
                        checkbox.dataset.workspaceStatus === status &&
                        deletionCheckboxIsEligible(checkbox)
                    ) {
                        checkbox.checked = true;
                        selectedWorkspaceKeys.add(key);
                    }
                });
                updateDeleteSelectedButton(scope);
            });
        });
        updateDeleteSelectedButton(scope);
    }

    function localizeEventTimes(root) {
        var compactFormatter;
        var accessibleFormatter;
        try {
            compactFormatter = new Intl.DateTimeFormat(undefined, {
                hour: "numeric",
                minute: "2-digit",
                second: "2-digit",
            });
            accessibleFormatter = new Intl.DateTimeFormat(undefined, {
                dateStyle: "full",
                timeStyle: "long",
            });
        } catch (error) {
            compactFormatter = null;
            accessibleFormatter = null;
        }

        (root || document).querySelectorAll("time[data-event-time]").forEach(function (node) {
            var originalText = node.textContent;
            var originalTitle = node.getAttribute("title");
            var originalLabel = node.getAttribute("aria-label");
            var raw = node.getAttribute("datetime");
            var timestamp = raw ? new Date(raw) : null;
            if (!timestamp || isNaN(timestamp.getTime())) {
                node.textContent = "—";
                node.removeAttribute("title");
                node.removeAttribute("aria-label");
                return;
            }
            if (!compactFormatter || !accessibleFormatter) return;
            try {
                var compact = compactFormatter.format(timestamp);
                var accessible = accessibleFormatter.format(timestamp);
                node.textContent = compact;
                node.setAttribute("title", accessible);
                node.setAttribute("aria-label", accessible);
            } catch (error) {
                node.textContent = originalText;
                if (originalTitle === null) node.removeAttribute("title");
                else node.setAttribute("title", originalTitle);
                if (originalLabel === null) node.removeAttribute("aria-label");
                else node.setAttribute("aria-label", originalLabel);
            }
        });
    }

    function deletionConfirmationMessage(checkboxes) {
        var names = checkboxes.map(function (checkbox) {
            return checkbox.value || checkbox.dataset.workspaceKey || "Unnamed workspace";
        });
        var listedNames = names.slice(0, 10);
        if (names.length > listedNames.length) {
            listedNames.push("and " + (names.length - listedNames.length) + " more");
        }
        var noun = names.length === 1 ? "workspace" : "workspaces";
        return (
            "Delete " +
            names.length +
            " selected " +
            noun +
            "?\n\n" +
            listedNames.join("\n") +
            "\n\nBoardwalk's stored workspace data for these workspaces will be removed. " +
            "This action cannot be undone."
        );
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

    function isRestorableControl(element) {
        return Boolean(
            element &&
                element.matches &&
                element.matches("input:not([type=hidden]), textarea, select, button"),
        );
    }

    function isRefreshBlockingControl(element) {
        if (!isRestorableControl(element)) return false;
        if (element.matches("textarea, select")) return true;
        return element.matches("input:not([type=hidden]):not([type=checkbox]):not([type=radio])");
    }

    function controlCanReceiveFocus(element, root) {
        if (!isRestorableControl(element) || element.disabled || element.hidden) return false;
        for (var ancestor = element; ancestor; ancestor = ancestor.parentElement) {
            if (ancestor.hidden || (ancestor.hasAttribute && ancestor.hasAttribute("hidden"))) return false;
            var style = window.getComputedStyle ? window.getComputedStyle(ancestor) : null;
            if (
                style &&
                (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse")
            ) {
                return false;
            }
            if (ancestor === root) break;
        }
        return true;
    }

    function restorableControls(root) {
        return Array.prototype.slice
            .call((root || document).querySelectorAll("input:not([type=hidden]), textarea, select, button"))
            .filter(function (element) {
                return controlCanReceiveFocus(element, root);
            });
    }

    function userIsEditingDashboard() {
        var active = document.activeElement;
        return isRefreshBlockingControl(active) && Boolean(active.closest(".bw-dashboard"));
    }

    function workspaceKeyForElement(element) {
        if (!element || !element.closest) return "";
        var workspace = element.closest("[data-workspace-key]");
        return workspace && workspace.dataset ? workspace.dataset.workspaceKey || "" : "";
    }

    function controlDiscriminator(element) {
        if (!element) return "";
        var parts = [];
        if (element.id) parts.push("id=" + element.id);
        var dataset = element.dataset || {};
        ["rowToggle", "eventsToggle", "themeToggle", "selectVisibleStatus", "deleteSelected"].forEach(
            function (key) {
                if (Object.prototype.hasOwnProperty.call(dataset, key)) {
                    parts.push("data:" + key + "=" + dataset[key]);
                }
            },
        );
        ["aria-controls", "hx-post", "hx-delete"].forEach(function (name) {
            var value = element.getAttribute ? element.getAttribute(name) : null;
            if (value) parts.push(name + "=" + value);
        });
        return parts.join("|");
    }

    function fieldMatchesSnapshot(element, snapshot) {
        if (!element || !snapshot) return false;
        if (snapshot.workspaceKey && workspaceKeyForElement(element) !== snapshot.workspaceKey) return false;
        if (element.name !== snapshot.name) return false;
        if (element.tagName !== snapshot.tagName) return false;
        if (snapshot.type && element.type !== snapshot.type) return false;
        return controlDiscriminator(element) === snapshot.discriminator;
    }

    function findControlBySnapshot(root, snapshot) {
        var match = null;
        (root || document)
            .querySelectorAll("input:not([type=hidden]), textarea, select, button")
            .forEach(function (element) {
                if (!match && fieldMatchesSnapshot(element, snapshot)) {
                    match = element;
                }
            });
        return match;
    }

    // Auto-refresh replaces the dashboard fragment. Capture the focused control
    // so in-progress search/filter typing survives the swap.
    function captureActiveControl(dashboard) {
        var active = document.activeElement;
        if (!isRestorableControl(active) || !dashboard || !dashboard.contains(active)) return null;
        var controls = restorableControls(dashboard);
        var controlIndex = controls.indexOf(active);
        if (controlIndex < 0) return null;
        return {
            controlIndex: controlIndex,
            workspaceKey: workspaceKeyForElement(active),
            discriminator: controlDiscriminator(active),
            name: active.name || "",
            tagName: active.tagName,
            type: active.type || "",
            value: active.value,
            selectionStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
            selectionEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
        };
    }

    function restoreActiveControl(root, snapshot) {
        if (!snapshot) return;
        var control = findControlBySnapshot(root || document, snapshot);
        if (control && !controlCanReceiveFocus(control, root || document)) control = null;
        var exactMatch = Boolean(control);
        if (!control) {
            var controls = restorableControls(root || document);
            if (!controls.length) return;
            var fallbackIndex = Math.min(Math.max(snapshot.controlIndex || 0, 0), controls.length - 1);
            control = controls[fallbackIndex];
        }
        if (exactMatch) control.value = snapshot.value;
        control.focus({ preventScroll: true });
        if (!exactMatch) return;
        if (
            typeof control.setSelectionRange === "function" &&
            snapshot.selectionStart !== null &&
            snapshot.selectionEnd !== null
        ) {
            control.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
        }
    }

    function isDashboardAutoRefresh(event) {
        var detail = event.detail || {};
        var element = detail.elt;
        return Boolean(element && element.matches && element.matches(".bw-dashboard"));
    }

    function swapOwner(event) {
        var detail = (event && event.detail) || {};
        var target = detail.target || (event && event.target);
        if (!target || !target.matches) return null;
        return target.matches(".bw-frame") ? target : null;
    }

    function dashboardForSwap(event) {
        var frame = swapOwner(event);
        if (!frame || !frame.querySelector) return null;
        return frame.querySelector(".bw-dashboard");
    }

    function anchorSnapshot(element) {
        var key = workspaceKeyForElement(element);
        if (!key || !element || !element.getBoundingClientRect) return null;
        return {
            workspaceKey: key,
            anchorPart: element.matches(".bw-row-details") ? "details" : "row",
            top: element.getBoundingClientRect().top,
        };
    }

    function isInViewport(element) {
        if (!element || element.hidden || !element.getBoundingClientRect) return false;
        var rect = element.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < window.innerHeight;
    }

    function visibleWorkspaceAnchor(dashboard) {
        if (!dashboard) return null;
        var active = document.activeElement;
        if (active && dashboard.contains(active)) {
            var activeWorkspace = active.closest("[data-workspace-row], .bw-row-details");
            var activeAnchor = anchorSnapshot(activeWorkspace);
            if (activeAnchor) return activeAnchor;
        }

        var expandedAnchor = null;
        dashboard.querySelectorAll(".bw-row-details").forEach(function (panel) {
            if (!expandedAnchor && !panel.hidden && isInViewport(panel)) {
                expandedAnchor = anchorSnapshot(panel);
            }
        });
        if (expandedAnchor) return expandedAnchor;

        var rowAnchor = null;
        dashboard.querySelectorAll("[data-workspace-row]").forEach(function (row) {
            if (!rowAnchor && isInViewport(row)) {
                rowAnchor = anchorSnapshot(row);
            }
        });
        return rowAnchor;
    }

    function captureRefreshState(event) {
        var owner = swapOwner(event);
        if (!owner || owner.classList.contains("bw-admin-panel")) return null;
        var dashboard = dashboardForSwap(event);
        if (!dashboard) {
            return {
                owner: owner,
                anchor: null,
                scrollX: window.scrollX,
                scrollY: window.scrollY,
                activeControl: null,
                initial: true,
            };
        }
        return {
            owner: owner,
            anchor: visibleWorkspaceAnchor(dashboard),
            scrollX: window.scrollX,
            scrollY: window.scrollY,
            activeControl: captureActiveControl(dashboard),
            initial: false,
        };
    }

    function beginDashboardRestoration(owner) {
        restorationCounts.set(owner, (restorationCounts.get(owner) || 0) + 1);
        owner.classList.add("is-restoring-dashboard-state");
    }

    function endDashboardRestoration(owner) {
        var remaining = (restorationCounts.get(owner) || 1) - 1;
        if (remaining > 0) {
            restorationCounts.set(owner, remaining);
            return;
        }
        restorationCounts.delete(owner);
        owner.classList.remove("is-restoring-dashboard-state");
    }

    function matchingWorkspaceElement(root, anchor) {
        var preferred = null;
        (root || document).querySelectorAll(".bw-row-details, [data-workspace-row]").forEach(function (element) {
            if (workspaceKeyForElement(element) !== anchor.workspaceKey) return;
            var part = element.matches(".bw-row-details") ? "details" : "row";
            if (!preferred && part === anchor.anchorPart) preferred = element;
        });
        return preferred;
    }

    function restoreViewport(snapshot, root) {
        if (!snapshot) return;
        var anchor = snapshot.anchor;
        var restoredAnchor = anchor && matchingWorkspaceElement(root || document, anchor);
        if (restoredAnchor) {
            var currentTop = restoredAnchor.getBoundingClientRect().top;
            window.scrollBy(0, currentTop - anchor.top);
            return;
        }

        var documentHeight = Math.max(
            document.documentElement ? document.documentElement.scrollHeight || 0 : 0,
            document.body ? document.body.scrollHeight || 0 : 0,
        );
        var maxDocumentScrollY = Math.max(0, documentHeight - window.innerHeight);
        window.scrollTo(snapshot.scrollX, Math.min(snapshot.scrollY, maxDocumentScrollY));
    }

    function boot(root, restoreState) {
        var scope = root || document;
        bindThemeToggle();
        bindRows(scope);
        bindEventToggles(scope);
        bindDeletionSelection(scope);
        localizeEventTimes(scope);
        fitNames(scope);
        if (restoreState) restoreExpandedState(scope);
    }

    function xhrForEvent(event) {
        var detail = (event && event.detail) || {};
        var xhr = detail.xhr;
        return xhr && (typeof xhr === "object" || typeof xhr === "function") ? xhr : null;
    }

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(storedTheme());
        boot(document, true);
    });

    if (document.body) {
        document.body.addEventListener("htmx:beforeRequest", function (event) {
            if (isDashboardAutoRefresh(event) && userIsEditingDashboard()) {
                event.preventDefault();
            }
        });
        document.body.addEventListener("htmx:beforeSwap", function (event) {
            var detail = event.detail || {};
            var marker =
                detail.xhr && detail.xhr.getResponseHeader
                    ? detail.xhr.getResponseHeader("X-Boardwalk-Dashboard-Fragment")
                    : null;
            if (marker === "deletion-error") {
                detail.shouldSwap = true;
                detail.isError = false;
            }
            var xhr = xhrForEvent(event);
            if (!xhr || detail.shouldSwap !== true || detail.isError) return;
            var snapshot = captureRefreshState(event);
            if (snapshot) {
                beginDashboardRestoration(snapshot.owner);
                refreshTransactions.set(xhr, snapshot);
            }
        });
        document.body.addEventListener("htmx:afterSwap", function (event) {
            var xhr = xhrForEvent(event);
            var snapshot = xhr ? refreshTransactions.get(xhr) : null;
            if (!snapshot || swapOwner(event) !== snapshot.owner) return;
            boot(event.target, true);
            if (!snapshot.initial) restoreViewport(snapshot, event.target);
        });
        document.body.addEventListener("htmx:afterSettle", function (event) {
            var xhr = xhrForEvent(event);
            var snapshot = xhr ? refreshTransactions.get(xhr) : null;
            if (!snapshot) return;
            refreshTransactions.delete(xhr);
            endDashboardRestoration(snapshot.owner);
            if (swapOwner(event) !== snapshot.owner) return;
            restoreDeletionSelection(event.target);
            restoreActiveControl(event.target, snapshot.activeControl);
        });
    }
})();
