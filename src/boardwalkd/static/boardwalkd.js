(function () {
    var EXPANDED_WORKSPACE_KEY = "boardwalk.expandedWorkspace";
    var EXPANDED_EVENTS_KEY = "boardwalk.expandedEvents";
    var refreshTransactions = new WeakMap();
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

    function isDashboardElement(element) {
        if (!element || !element.matches) return false;
        for (var ancestor = element; ancestor; ancestor = ancestor.parentElement) {
            if (ancestor.matches("#workspace-dashboard")) return true;
        }
        return false;
    }

    function dashboardElementsWithin(root, selector) {
        if (!root || !root.matches || !isDashboardElement(root)) return [];
        var elements = [];
        if (root.matches(selector)) elements.push(root);
        if (root.querySelectorAll) {
            root.querySelectorAll(selector).forEach(function (element) {
                if (isDashboardElement(element)) elements.push(element);
            });
        }
        return elements;
    }

    function projectStoredWorkspaceState(newNode) {
        var expandedKey = storedSessionValue(EXPANDED_WORKSPACE_KEY);
        if (!expandedKey) return;
        dashboardElementsWithin(
            newNode,
            "[data-workspace-row], [data-row-toggle], .bw-row-details",
        ).forEach(function (element) {
            if ((element.dataset.workspaceKey || "") !== expandedKey) return;
            if (element.matches("[data-workspace-row]")) {
                element.classList.add("is-expanded");
            } else if (element.matches("[data-row-toggle]")) {
                element.setAttribute("aria-expanded", "true");
            } else if (element.matches(".bw-row-details")) {
                element.hidden = false;
                element.classList.add("is-expanded");
            }
        });
    }

    function projectStoredEventState(newNode) {
        var eventKeys = storedEventKeys();
        if (!eventKeys.length) return;
        dashboardElementsWithin(newNode, "[data-event-extra], [data-events-toggle]").forEach(
            function (element) {
                var panel = element.closest(".bw-row-details");
                var key = panel && panel.dataset ? panel.dataset.workspaceKey || "" : "";
                if (eventKeys.indexOf(key) === -1) return;
                element.hidden = element.matches("[data-events-toggle]");
            },
        );
    }

    function transferMatchedDashboardState(oldNode, newNode) {
        if (!isDashboardElement(oldNode) || !isDashboardElement(newNode)) return;
        if (oldNode.matches("[data-workspace-row]")) {
            newNode.classList.toggle("is-expanded", oldNode.classList.contains("is-expanded"));
        } else if (oldNode.matches("[data-row-toggle]")) {
            newNode.setAttribute(
                "aria-expanded",
                oldNode.getAttribute("aria-expanded") === "true" ? "true" : "false",
            );
        } else if (oldNode.matches(".bw-row-details")) {
            newNode.hidden = oldNode.hidden;
            newNode.classList.toggle("is-expanded", oldNode.classList.contains("is-expanded"));
        }
        projectStoredEventState(newNode);
    }

    function projectAddedDashboardState(newNode) {
        if (!isDashboardElement(newNode)) return;
        projectStoredWorkspaceState(newNode);
        projectStoredEventState(newNode);
    }

    function installMorphCallbacks() {
        if (!window.Idiomorph || !window.Idiomorph.defaults) return;
        var callbacks = window.Idiomorph.defaults.callbacks;
        var previousMorphed = callbacks.beforeNodeMorphed;
        var previousAdded = callbacks.beforeNodeAdded;

        callbacks.beforeNodeMorphed = function (oldNode, newNode) {
            if (previousMorphed && previousMorphed(oldNode, newNode) === false) return false;
            transferMatchedDashboardState(oldNode, newNode);
            return true;
        };
        callbacks.beforeNodeAdded = function (newNode) {
            if (previousAdded && previousAdded(newNode) === false) return false;
            projectAddedDashboardState(newNode);
            return true;
        };
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

    function updateWorkspaceSelection(checkbox) {
        var scope = checkbox.closest(".bw-dashboard") || document;
        var key = checkbox.dataset.workspaceKey || "";
        if (key && checkbox.checked && deletionCheckboxIsEligible(checkbox)) {
            selectedWorkspaceKeys.add(key);
        } else {
            if (key) selectedWorkspaceKeys.delete(key);
            if (!deletionCheckboxIsEligible(checkbox)) checkbox.checked = false;
        }
        updateDeleteSelectedButton(scope);
    }

    function selectVisibleStatus(button) {
        var scope = button.closest(".bw-dashboard") || document;
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
        var scope = root || document;
        var key = storedSessionValue(EXPANDED_WORKSPACE_KEY);
        if (key) {
            var button = findByWorkspaceKey(scope, "[data-row-toggle]", key);
            var panel = button && document.getElementById(button.getAttribute("aria-controls"));
            var row = findByWorkspaceKey(scope, "[data-workspace-row]", key);
            if (
                button &&
                panel &&
                (panel.hidden ||
                    !panel.classList.contains("is-expanded") ||
                    button.getAttribute("aria-expanded") !== "true" ||
                    (row && !row.classList.contains("is-expanded")))
            ) {
                openRowByKey(key, false);
            }
        }
        storedEventKeys().forEach(function (eventKey) {
            var eventPanel = findByWorkspaceKey(scope, ".bw-row-details", eventKey);
            if (!eventPanel) return;
            eventPanel.querySelectorAll("[data-event-extra]").forEach(function (line) {
                if (line.hidden) line.hidden = false;
            });
            eventPanel.querySelectorAll("[data-events-toggle]").forEach(function (eventButton) {
                if (!eventButton.hidden) eventButton.hidden = true;
            });
        });
    }

    function toggleRow(button) {
        var target = document.getElementById(button.getAttribute("aria-controls"));
        if (!target) return;
        if (target.hidden) {
            openRowByKey(button.dataset.workspaceKey, true);
        } else {
            closeRows(true);
        }
    }

    function expandRecentEvents(button) {
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
    }

    function handleBodyClick(event) {
        var themeToggle = event.target.closest("[data-theme-toggle]");
        if (themeToggle) {
            applyTheme(document.documentElement.classList.contains("bw-theme-dark") ? "light" : "dark");
            return;
        }

        var rowToggle = event.target.closest("[data-row-toggle]");
        if (rowToggle) {
            event.stopPropagation();
            toggleRow(rowToggle);
            return;
        }

        var eventToggle = event.target.closest("[data-events-toggle]");
        if (eventToggle) {
            event.stopPropagation();
            expandRecentEvents(eventToggle);
            return;
        }

        var statusButton = event.target.closest("[data-select-visible-status]");
        if (statusButton) {
            selectVisibleStatus(statusButton);
            return;
        }

        var row = event.target.closest("[data-workspace-row]");
        if (row && !event.target.closest("a, button, input, select, label")) {
            var toggle = row.querySelector("[data-row-toggle]");
            if (toggle) toggleRow(toggle);
        }
    }

    function handleBodyChange(event) {
        var checkbox = event.target.closest("[data-delete-workspace]");
        if (checkbox) updateWorkspaceSelection(checkbox);
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

    // Capture stable fallback identity for the focused dashboard control.
    // Retained controls are left to node identity; this lifecycle never rewrites them.
    function captureActiveControl(dashboard) {
        var active = document.activeElement;
        if (!isRestorableControl(active) || !dashboard || !dashboard.contains(active)) return null;
        var controls = restorableControls(dashboard);
        var controlIndex = controls.indexOf(active);
        if (controlIndex < 0) return null;
        return {
            node: active,
            controlIndex: controlIndex,
            workspaceKey: workspaceKeyForElement(active),
            discriminator: controlDiscriminator(active),
            name: active.name || "",
            tagName: active.tagName,
            type: active.type || "",
            selectionStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
            selectionEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
        };
    }

    function restoreActiveControlIfLost(root, snapshot) {
        if (!snapshot) return;
        if (snapshot.node && snapshot.node.isConnected) return;
        var control = findControlBySnapshot(root || document, snapshot);
        if (control && !controlCanReceiveFocus(control, root || document)) control = null;
        var exactMatch = Boolean(control);
        if (!control) {
            var controls = restorableControls(root || document);
            if (!controls.length) return;
            var fallbackIndex = Math.min(Math.max(snapshot.controlIndex || 0, 0), controls.length - 1);
            control = controls[fallbackIndex];
        }
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
            var activeAnchor = isInViewport(activeWorkspace) && anchorSnapshot(activeWorkspace);
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
        var frame = swapOwner(event);
        if (!frame || frame.classList.contains("bw-admin-panel")) return null;
        var dashboard = dashboardForSwap(event);
        return {
            frame: frame,
            viewport: dashboard
                ? {
                      anchor: visibleWorkspaceAnchor(dashboard),
                      scrollY: window.scrollY,
                  }
                : null,
            activeControl: dashboard ? captureActiveControl(dashboard) : null,
            applied: false,
        };
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

    function restoreViewport(root, snapshot) {
        if (!snapshot) return;
        var anchor = snapshot.anchor;
        var restoredAnchor = anchor && matchingWorkspaceElement(root || document, anchor);
        if (restoredAnchor) {
            var currentTop = restoredAnchor.getBoundingClientRect().top;
            var delta = currentTop - anchor.top;
            if (delta !== 0) {
                window.scrollBy({ behavior: "instant", left: 0, top: delta });
            }
            return;
        }

        var documentHeight = document.documentElement ? document.documentElement.scrollHeight || 0 : 0;
        var fallbackTop = Math.max(
            0,
            Math.min(snapshot.scrollY, documentHeight - window.innerHeight),
        );
        window.scrollTo({
            behavior: "instant",
            left: 0,
            top: fallbackTop,
        });
    }

    function enhanceDashboard(root) {
        var scope = root || document;
        clearSelectionUnlessEditing(scope);
        restoreDeletionSelection(scope);
        localizeEventTimes(scope);
        fitNames(scope);
    }

    function xhrForEvent(event) {
        var detail = (event && event.detail) || {};
        var xhr = detail.xhr;
        return xhr && (typeof xhr === "object" || typeof xhr === "function") ? xhr : null;
    }

    function applyRefreshTransaction(xhr, frame) {
        var snapshot = xhr ? refreshTransactions.get(xhr) : null;
        if (!snapshot || snapshot.applied || frame !== snapshot.frame) return;
        snapshot.applied = true;

        try {
            enhanceDashboard(frame);
            restoreExpandedState(frame);
            restoreActiveControlIfLost(frame, snapshot.activeControl);
            restoreViewport(frame, snapshot.viewport);
        } finally {
            refreshTransactions.delete(xhr);
        }
    }

    function discardRefreshTransaction(event) {
        var xhr = xhrForEvent(event);
        if (xhr) refreshTransactions.delete(xhr);
    }

    installMorphCallbacks();

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(storedTheme());
        enhanceDashboard(document);
        restoreExpandedState(document);
    });

    if (document.body) {
        document.body.addEventListener("click", handleBodyClick);
        document.body.addEventListener("change", handleBodyChange);
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
            if (refreshTransactions.has(xhr)) return;
            var snapshot = captureRefreshState(event);
            if (snapshot) {
                refreshTransactions.set(xhr, snapshot);
            }
        });
        document.body.addEventListener("htmx:afterSwap", function (event) {
            applyRefreshTransaction(xhrForEvent(event), swapOwner(event));
        });
        [
            "htmx:responseError",
            "htmx:swapError",
            "htmx:sendAbort",
            "htmx:sendError",
            "htmx:timeout",
        ].forEach(function (eventName) {
            document.body.addEventListener(eventName, discardRefreshTransaction);
        });
    }
})();
