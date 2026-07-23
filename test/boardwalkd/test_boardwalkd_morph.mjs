import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { JSDOM } from "jsdom";

const staticRoot = new URL("../../src/boardwalkd/static/", import.meta.url);

async function loadBrowserLibraries(html = "<!doctype html><body></body>", beforeBoardwalk = null) {
    const dom = new JSDOM(html, {
        runScripts: "outside-only",
        url: "http://localhost:8888/",
    });
    if (dom.window.document.readyState === "loading") {
        await new Promise((resolve) => {
            dom.window.document.addEventListener("DOMContentLoaded", resolve, {once: true});
        });
    }
    dom.window.scrollBy = () => {};
    dom.window.scrollTo = () => {};
    const evaluate = dom.window.XPathExpression.prototype.evaluate;
    dom.window.XPathExpression.prototype.evaluate = function (
        contextNode,
        resultType = dom.window.XPathResult.ANY_TYPE,
        result = null,
    ) {
        return evaluate.call(this, contextNode, resultType, result);
    };
    dom.window.eval(await readFile(new URL("htmx.min.js", staticRoot), "utf8"));
    dom.window.eval(await readFile(new URL("idiomorph-ext.min.js", staticRoot), "utf8"));
    if (beforeBoardwalk) beforeBoardwalk(dom.window);
    dom.window.eval(await readFile(new URL("boardwalkd.js", staticRoot), "utf8"));
    return dom;
}

test("vendored browser libraries expose the pinned versions", async () => {
    const dom = await loadBrowserLibraries();
    assert.equal(dom.window.htmx.version, "2.0.10");
    assert.equal(typeof dom.window.Idiomorph.morph, "function");
});

function dashboardMarkup(rows) {
    return `<!doctype html>
        <body>
            <main class="bw-frame">
                <section id="workspace-dashboard" class="bw-dashboard">
                    <form data-bulk-delete-form>
                        <button type="submit" data-delete-selected disabled>
                            Delete selected (<span data-delete-count>0</span>)
                        </button>
                        <span data-delete-count-live>Delete selected (0)</span>
                    </form>
                    ${rows}
                </section>
            </main>
        </body>`;
}

function workspaceMarkup(key, options = {}) {
    const {
        status = "running",
        expanded = false,
        checkbox = true,
        checkboxAttributes = "",
        rowAttributes = "",
        progress = "10%",
        eventText = "old event",
        extraText = "old extra",
        eventsExpanded = false,
        inputValue = "filter text",
    } = options;
    return `
        <article
            id="row-${key}"
            class="bw-row status-${status}${expanded ? " is-expanded" : ""}"
            data-workspace-row
            data-workspace-key="${key}"
            ${rowAttributes}
        >
            <button
                id="toggle-${key}"
                type="button"
                data-row-toggle
                data-workspace-key="${key}"
                aria-controls="details-${key}"
                aria-expanded="${expanded ? "true" : "false"}"
            >Toggle</button>
            ${
                checkbox
                    ? `<input
                        id="checkbox-${key}"
                        type="checkbox"
                        data-delete-workspace
                        data-workspace-key="${key}"
                        data-workspace-status="${status}"
                        value="${key}"
                        ${checkboxAttributes}
                    >`
                    : ""
            }
            <input id="filter-${key}" name="filter" value="${inputValue}">
            <span id="progress-${key}" data-progress>${progress}</span>
        </article>
        <section
            id="details-${key}"
            class="bw-row-details${expanded ? " is-expanded" : ""}"
            data-workspace-key="${key}"
            ${expanded ? "" : "hidden"}
        >
            <div class="bw-events">
                <div id="event-${key}">${eventText}</div>
                <div id="event-extra-${key}" data-event-extra ${eventsExpanded ? "" : "hidden"}>
                    ${extraText}
                </div>
                <button
                    id="events-toggle-${key}"
                    type="button"
                    data-events-toggle
                    ${eventsExpanded ? "hidden" : ""}
                >Show more</button>
            </div>
        </section>`;
}

function morphDashboard(dom, rows) {
    const dashboard = dom.window.document.getElementById("workspace-dashboard");
    dom.window.Idiomorph.morph(
        dashboard,
        `<section id="workspace-dashboard" class="bw-dashboard">
            <form data-bulk-delete-form>
                <button type="submit" data-delete-selected disabled>
                    Delete selected (<span data-delete-count>0</span>)
                </button>
                <span data-delete-count-live>Delete selected (0)</span>
            </form>
            ${rows}
        </section>`,
    );
    return dashboard;
}

function beginSwap(dom) {
    const frame = dom.window.document.querySelector(".bw-frame");
    const xhr = {getResponseHeader: () => null};
    frame.dispatchEvent(
        new dom.window.CustomEvent("htmx:beforeSwap", {
            bubbles: true,
            detail: {
                target: frame,
                xhr,
                shouldSwap: true,
                isError: false,
            },
        }),
    );
    return {frame, xhr};
}

function finishSwap(dom, transaction) {
    transaction.frame.dispatchEvent(
        new dom.window.CustomEvent("htmx:afterSwap", {
            bubbles: true,
            detail: {target: transaction.frame, xhr: transaction.xhr},
        }),
    );
}

test("afterSwap leaves matched expansion and retained focus untouched while server truth wins", async () => {
    const alpha = workspaceMarkup("alpha", {
        expanded: true,
        eventsExpanded: true,
        progress: "10%",
    });
    const beta = workspaceMarkup("beta", {status: "done"});
    const dom = await loadBrowserLibraries(dashboardMarkup(alpha + beta));
    const {document, sessionStorage} = dom.window;
    sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    sessionStorage.setItem("boardwalk.expandedEvents", "alpha");

    const originalRow = document.getElementById("row-alpha");
    const originalBetaRow = document.getElementById("row-beta");
    const originalPanel = document.getElementById("details-alpha");
    const originalToggle = document.getElementById("toggle-alpha");
    const originalInput = document.getElementById("filter-alpha");
    originalInput.focus();
    originalInput.setSelectionRange(2, 5);
    const originalFocus = originalInput.focus.bind(originalInput);
    const lifecycleFocusCalls = [];
    originalInput.focus = (options) => {
        lifecycleFocusCalls.push(options);
        originalFocus(options);
    };
    const transaction = beginSwap(dom);

    morphDashboard(
        dom,
        workspaceMarkup("beta", {status: "done"}) +
            workspaceMarkup("alpha", {
                status: "done",
                progress: "100%",
                eventText: "server event",
                extraText: "server extra",
            }),
    );

    assert.strictEqual(document.getElementById("row-alpha"), originalRow);
    assert.strictEqual(document.getElementById("row-beta"), originalBetaRow);
    assert.deepEqual(
        Array.from(document.querySelectorAll("[data-workspace-row]"), (row) => row.id),
        ["row-beta", "row-alpha"],
    );
    assert.strictEqual(document.getElementById("details-alpha"), originalPanel);
    assert.strictEqual(document.getElementById("toggle-alpha"), originalToggle);
    assert.match(originalRow.className, /status-done/);
    assert.doesNotMatch(originalRow.className, /status-running/);
    assert.equal(originalRow.classList.contains("is-expanded"), true);
    assert.equal(originalPanel.hidden, false);
    assert.equal(originalPanel.classList.contains("is-expanded"), true);
    assert.equal(originalToggle.getAttribute("aria-expanded"), "true");
    assert.equal(document.getElementById("progress-alpha").textContent, "100%");
    assert.equal(document.getElementById("event-alpha").textContent, "server event");
    assert.equal(document.getElementById("event-extra-alpha").textContent.trim(), "server extra");
    assert.equal(document.getElementById("event-extra-alpha").hidden, false);
    assert.equal(document.getElementById("events-toggle-alpha").hidden, true);
    assert.strictEqual(document.activeElement, originalInput);
    assert.equal(originalInput.selectionStart, 2);
    assert.equal(originalInput.selectionEnd, 5);

    finishSwap(dom, transaction);
    transaction.frame.dispatchEvent(
        new dom.window.CustomEvent("htmx:afterSettle", {
            bubbles: true,
            detail: {target: transaction.frame, xhr: transaction.xhr},
        }),
    );
    assert.deepEqual(lifecycleFocusCalls, []);
});

test("newly added dashboard nodes project stored workspace and event state while detached", async () => {
    const dom = await loadBrowserLibraries(dashboardMarkup(workspaceMarkup("beta")), (window) => {
        window.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
        window.sessionStorage.setItem("boardwalk.expandedEvents", "alpha");
    });
    const installedBeforeNodeAdded = dom.window.Idiomorph.defaults.callbacks.beforeNodeAdded;
    const detachedObservations = {};
    const postInsertionAttributes = [];
    const observer = new dom.window.MutationObserver((records) => {
        for (const record of records) {
            if (
                record.type === "attributes" &&
                (record.target.id === "row-alpha" ||
                    record.target.id === "toggle-alpha" ||
                    record.target.id === "details-alpha" ||
                    record.target.id === "event-extra-alpha" ||
                    record.target.id === "events-toggle-alpha")
            ) {
                postInsertionAttributes.push([record.target.id, record.attributeName]);
            }
        }
    });
    observer.observe(dom.window.document.getElementById("workspace-dashboard"), {
        attributes: true,
        subtree: true,
    });
    dom.window.Idiomorph.defaults.callbacks.beforeNodeAdded = (newNode) => {
        const result = installedBeforeNodeAdded(newNode);
        if (result === false || !newNode.matches) return result;
        if (newNode.matches("#row-alpha")) {
            detachedObservations.row = {
                connected: newNode.isConnected,
                expanded: newNode.classList.contains("is-expanded"),
                aria: newNode.querySelector("[data-row-toggle]").getAttribute("aria-expanded"),
            };
        }
        if (newNode.matches("#details-alpha")) {
            detachedObservations.details = {
                connected: newNode.isConnected,
                hidden: newNode.hidden,
                expanded: newNode.classList.contains("is-expanded"),
                extraHidden: newNode.querySelector("[data-event-extra]").hidden,
                toggleHidden: newNode.querySelector("[data-events-toggle]").hidden,
            };
        }
        return result;
    };

    morphDashboard(
        dom,
        workspaceMarkup("beta") +
            workspaceMarkup("alpha", {
                eventText: "new event",
                extraText: "new extra",
            }),
    );

    assert.deepEqual(detachedObservations, {
        row: {connected: false, expanded: true, aria: "true"},
        details: {
            connected: false,
            hidden: false,
            expanded: true,
            extraHidden: false,
            toggleHidden: true,
        },
    });
    assert.equal(dom.window.document.getElementById("row-alpha").classList.contains("is-expanded"), true);
    assert.equal(dom.window.document.getElementById("toggle-alpha").getAttribute("aria-expanded"), "true");
    assert.equal(dom.window.document.getElementById("details-alpha").hidden, false);
    assert.equal(dom.window.document.getElementById("event-extra-alpha").hidden, false);
    assert.equal(dom.window.document.getElementById("events-toggle-alpha").hidden, true);
    await Promise.resolve();
    observer.disconnect();
    assert.deepEqual(postInsertionAttributes, []);
});

test("afterSwap selection reconciliation follows raw Idiomorph and prunes ineligible or removed keys", async () => {
    const dom = await loadBrowserLibraries(
        dashboardMarkup(workspaceMarkup("alpha", {status: "done"})),
    );
    const {document} = dom.window;
    const originalCheckbox = document.getElementById("checkbox-alpha");
    originalCheckbox.checked = true;
    originalCheckbox.dispatchEvent(new dom.window.Event("change", {bubbles: true}));

    let transaction = beginSwap(dom);
    morphDashboard(dom, workspaceMarkup("alpha", {status: "done"}));
    let checkbox = document.getElementById("checkbox-alpha");
    assert.strictEqual(checkbox, originalCheckbox);
    assert.equal(checkbox.checked, false);
    finishSwap(dom, transaction);
    assert.equal(checkbox.checked, true);

    transaction = beginSwap(dom);
    morphDashboard(
        dom,
        workspaceMarkup("alpha", {
            status: "done",
            checkboxAttributes: "disabled",
        }),
    );
    checkbox = document.getElementById("checkbox-alpha");
    assert.equal(checkbox.checked, false);
    finishSwap(dom, transaction);
    assert.equal(checkbox.checked, false);

    transaction = beginSwap(dom);
    morphDashboard(dom, workspaceMarkup("alpha", {status: "done"}));
    finishSwap(dom, transaction);
    assert.equal(document.getElementById("checkbox-alpha").checked, false);

    checkbox = document.getElementById("checkbox-alpha");
    checkbox.checked = true;
    checkbox.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    transaction = beginSwap(dom);
    morphDashboard(
        dom,
        workspaceMarkup("alpha", {
            status: "done",
            rowAttributes: "hidden",
        }),
    );
    checkbox = document.getElementById("checkbox-alpha");
    assert.equal(checkbox.checked, false);
    finishSwap(dom, transaction);
    assert.equal(checkbox.checked, false);

    transaction = beginSwap(dom);
    morphDashboard(dom, workspaceMarkup("alpha", {status: "done"}));
    finishSwap(dom, transaction);
    assert.equal(document.getElementById("checkbox-alpha").checked, false);

    checkbox = document.getElementById("checkbox-alpha");
    checkbox.checked = true;
    checkbox.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
    transaction = beginSwap(dom);
    morphDashboard(
        dom,
        workspaceMarkup("alpha", {
            status: "done",
            checkbox: false,
        }),
    );
    assert.equal(document.getElementById("checkbox-alpha"), null);
    finishSwap(dom, transaction);

    transaction = beginSwap(dom);
    morphDashboard(dom, workspaceMarkup("alpha", {status: "done"}));
    finishSwap(dom, transaction);
    assert.equal(document.getElementById("checkbox-alpha").checked, false);
});

test("afterSwap focus fallback targets the nearest surviving control without scrolling", async () => {
    const dom = await loadBrowserLibraries(dashboardMarkup(workspaceMarkup("alpha")));
    const {document} = dom.window;
    const originalInput = document.getElementById("filter-alpha");
    originalInput.focus();
    originalInput.setSelectionRange(2, 5);
    const transaction = beginSwap(dom);

    morphDashboard(dom, workspaceMarkup("beta", {inputValue: "server filter"}));
    const fallback = document.getElementById("filter-beta");
    const fallbackFocus = fallback.focus.bind(fallback);
    const focusCalls = [];
    fallback.focus = (options) => {
        focusCalls.push(options);
        fallbackFocus(options);
    };

    finishSwap(dom, transaction);

    assert.equal(focusCalls.length, 1);
    assert.equal(focusCalls[0].preventScroll, true);
    assert.strictEqual(document.activeElement, fallback);
    assert.equal(fallback.value, "server filter");
});

test("morph callbacks preserve existing callback vetoes and ignore unmarked content", async () => {
    const calls = {added: [], morphed: []};
    const previousCallbacks = {};
    const dom = await loadBrowserLibraries(
        `<!doctype html><body>
            <div id="outside">
                <div id="outside-row" data-workspace-row class="status-running is-expanded">old</div>
            </div>
            ${dashboardMarkup(
                `<div id="veto-row" data-workspace-row class="status-running is-expanded">old</div>`,
            ).replace(/<!doctype html>|<body>|<\/body>/g, "")}
        </body>`,
        (window) => {
            previousCallbacks.beforeNodeMorphed = (oldNode) => {
                calls.morphed.push(oldNode.id);
                if (oldNode.id === "veto-row") return false;
                return true;
            };
            previousCallbacks.beforeNodeAdded = (newNode) => {
                calls.added.push(newNode.id);
                if (newNode.id === "veto-added") return false;
                return true;
            };
            window.Idiomorph.defaults.callbacks.beforeNodeMorphed =
                previousCallbacks.beforeNodeMorphed;
            window.Idiomorph.defaults.callbacks.beforeNodeAdded = previousCallbacks.beforeNodeAdded;
        },
    );
    const {document, Idiomorph} = dom.window;
    assert.notStrictEqual(
        Idiomorph.defaults.callbacks.beforeNodeMorphed,
        previousCallbacks.beforeNodeMorphed,
    );
    assert.notStrictEqual(
        Idiomorph.defaults.callbacks.beforeNodeAdded,
        previousCallbacks.beforeNodeAdded,
    );

    Idiomorph.morph(
        document.getElementById("outside"),
        `<div id="outside">
            <div id="outside-row" data-workspace-row class="status-done">server</div>
        </div>`,
    );
    const outsideRow = document.getElementById("outside-row");
    assert.equal(outsideRow.classList.contains("is-expanded"), false);
    assert.equal(outsideRow.classList.contains("status-done"), true);

    morphDashboard(
        dom,
        `<div id="veto-row" data-workspace-row class="status-done">server</div>
         <div id="veto-added" data-workspace-row>added</div>`,
    );
    assert.equal(document.getElementById("veto-row").textContent, "old");
    assert.equal(document.getElementById("veto-row").classList.contains("status-running"), true);
    assert.equal(document.getElementById("veto-added"), null);
    assert.ok(calls.morphed.includes("veto-row"));
    assert.ok(calls.added.includes("veto-added"));
});
