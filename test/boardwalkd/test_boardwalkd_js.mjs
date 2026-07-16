import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = fs.readFileSync(
    new URL("../../src/boardwalkd/static/boardwalkd.js", import.meta.url),
    "utf8",
);
const htmxSource = fs.readFileSync(
    new URL("../../src/boardwalkd/static/htmx.min.js", import.meta.url),
    "utf8",
);

class FakeEventTarget {
    constructor() {
        this.listeners = new Map();
    }

    addEventListener(type, listener) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(listener);
        this.listeners.set(type, listeners);
    }

    dispatch(type, event = {}) {
        event.type = type;
        for (const listener of this.listeners.get(type) || []) listener(event);
        return event;
    }
}

class FakeClassList {
    constructor(values = []) {
        this.values = new Set(values);
    }

    add(...values) {
        for (const value of values) this.values.add(value);
    }

    remove(...values) {
        for (const value of values) this.values.delete(value);
    }

    contains(value) {
        return this.values.has(value);
    }

    toggle(value, force) {
        const enabled = force === undefined ? !this.values.has(value) : force;
        if (enabled) this.values.add(value);
        else this.values.delete(value);
        return enabled;
    }
}

class FakeElement extends FakeEventTarget {
    constructor(tagName = "div", options = {}) {
        super();
        this.tagName = tagName.toUpperCase();
        this.id = options.id || "";
        this.name = options.name || "";
        this.type = options.type || "";
        this.dataset = {...options.dataset};
        this.classList = new FakeClassList(options.classes);
        this.attributes = new Map(Object.entries(options.attributes || {}));
        this.children = [];
        this.parentElement = null;
        this._hidden = Boolean(options.hidden);
        this.hiddenWrites = [];
        this.open = Boolean(options.open);
        this.checked = Boolean(options.checked);
        this.disabled = Boolean(options.disabled);
        this.textContent = options.textContent || "";
        this.value = options.value || "";
        this.rect = options.rect || {top: 0, bottom: 20, height: 20};
        this.focusCalls = [];
        this.queryOverrides = new Map();
    }

    append(...children) {
        for (const child of children) {
            child.parentElement = this;
            this.children.push(child);
            if (this.ownerDocument) this.ownerDocument.adopt(child);
        }
    }

    replaceChildren(...children) {
        for (const child of this.children) child.parentElement = null;
        this.children = [];
        this.append(...children);
    }

    get hidden() {
        return this._hidden;
    }

    set hidden(value) {
        this._hidden = Boolean(value);
        this.hiddenWrites.push(this._hidden);
    }

    setAttribute(name, value) {
        this.attributes.set(name, String(value));
    }

    getAttribute(name) {
        return this.attributes.get(name) ?? null;
    }

    hasAttribute(name) {
        return this.attributes.has(name);
    }

    removeAttribute(name) {
        this.attributes.delete(name);
    }

    focus(options) {
        this.focusCalls.push(options);
        this.ownerDocument.activeElement = this;
    }

    click() {
        this.dispatch("click", {
            target: this,
            stopPropagation() {},
        });
    }

    getBoundingClientRect() {
        return this.rect;
    }

    contains(element) {
        for (let node = element; node; node = node.parentElement) {
            if (node === this) return true;
        }
        return false;
    }

    matches(selector) {
        return selector.split(",").some((part) => this.#matchesOne(part.trim()));
    }

    #matchesOne(selector) {
        if (!selector) return false;
        if (selector.includes(" ")) {
            const parts = selector.split(/\s+/);
            return this.#matchesOne(parts.at(-1));
        }
        for (const negated of selector.matchAll(/:not\(([^)]+)\)/g)) {
            if (this.#matchesOne(negated[1])) return false;
        }
        selector = selector.replace(/:not\([^)]+\)/g, "");
        if (selector === ":focus") return this.ownerDocument?.activeElement === this;
        const tag = selector.match(/^[a-zA-Z][\w-]*/)?.[0];
        if (tag && this.tagName !== tag.toUpperCase()) return false;
        const id = selector.match(/#([\w-]+)/)?.[1];
        if (id && this.id !== id) return false;
        for (const [, className] of selector.matchAll(/\.([\w-]+)/g)) {
            if (!this.classList.contains(className)) return false;
        }
        for (const match of selector.matchAll(/\[([\w-]+)(?:([~|^$*]?=)["']?([^\]"']+)["']?)?\]/g)) {
            const [, name, operator, expected] = match;
            let actual;
            if (name === "type") actual = this.type;
            else if (name === "name") actual = this.name;
            else if (name === "hidden") actual = this.hidden ? "" : null;
            else if (name === "disabled") actual = this.disabled ? "" : null;
            else if (name.startsWith("data-")) {
                const key = name.slice(5).replace(/-([a-z])/g, (_, char) => char.toUpperCase());
                actual = this.dataset[key];
            } else actual = this.getAttribute(name);
            if (!operator && actual == null) return false;
            if (operator === "=" && String(actual) !== expected) return false;
        }
        return Boolean(tag || id || selector.includes(".") || selector.includes("[") || selector === "*");
    }

    closest(selector) {
        for (let node = this; node; node = node.parentElement) {
            if (node.matches(selector)) return node;
        }
        return null;
    }

    querySelectorAll(selector) {
        if (this.queryOverrides.has(selector)) return this.queryOverrides.get(selector);
        const matches = [];
        const visit = (node) => {
            for (const child of node.children) {
                if (child.matches(selector)) matches.push(child);
                visit(child);
            }
        };
        visit(this);
        return matches;
    }

    querySelector(selector) {
        return this.querySelectorAll(selector)[0] || null;
    }
}

class FakeDocument extends FakeEventTarget {
    constructor() {
        super();
        this.documentElement = new FakeElement("html");
        this.body = new FakeElement("body");
        this.documentElement.scrollHeight = 1000;
        this.body.scrollHeight = 1000;
        this.documentElement.append(this.body);
        this.documentElement.ownerDocument = this;
        this.body.ownerDocument = this;
        this.activeElement = this.body;
        this.readyState = "loading";
    }

    adopt(node) {
        const visit = (element) => {
            element.ownerDocument = this;
            for (const child of element.children) visit(child);
        };
        visit(node);
        return node;
    }

    getElementById(id) {
        if (this.documentElement.id === id) return this.documentElement;
        return this.documentElement.querySelector(`#${id}`);
    }

    querySelectorAll(selector) {
        return this.documentElement.querySelectorAll(selector);
    }

    querySelector(selector) {
        return this.documentElement.querySelector(selector);
    }
}

function fakeStorage() {
    const values = new Map();
    return {
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, String(value)),
        removeItem: (key) => values.delete(key),
    };
}

function createHarness(options = {}) {
    const document = new FakeDocument();
    const window = new FakeEventTarget();
    Object.assign(window, {
        document,
        innerHeight: 800,
        scrollX: 0,
        scrollY: 0,
        scrollByCalls: [],
        scrollToCalls: [],
        scrollBy(x, y) {
            this.scrollByCalls.push([x, y]);
        },
        scrollTo(x, y) {
            this.scrollToCalls.push([x, y]);
        },
        getComputedStyle: options.getComputedStyle || (() => ({display: "block", visibility: "visible"})),
        matchMedia: () => ({matches: false, addEventListener() {}}),
        confirm: options.confirm || (() => false),
    });
    const localStorage = fakeStorage();
    const sessionStorage = fakeStorage();
    const context = {
        console,
        document,
        window,
        localStorage,
        sessionStorage,
        Intl: options.Intl || Intl,
        setTimeout: (callback) => callback(),
        clearTimeout() {},
    };
    vm.runInNewContext(source, context, {filename: "boardwalkd.js"});
    return {document, window, ...context};
}

function workspace(key, options = {}) {
    const row = new FakeElement("div", {
        classes: ["bw-row", ...(options.rowClasses || [])],
        dataset: {workspaceRow: "", workspaceKey: key},
        rect: {top: options.rowTop ?? 100, bottom: (options.rowTop ?? 100) + 40, height: 40},
    });
    const toggle = new FakeElement("button", {
        type: "button",
        dataset: {rowToggle: "", workspaceKey: key},
        attributes: {"aria-controls": `details-${key}`, "aria-expanded": "false"},
    });
    const checkbox = new FakeElement("input", {
        type: "checkbox",
        name: options.checkboxName || "selected",
        dataset: {
            deleteWorkspace: "",
            workspaceKey: key,
            workspaceStatus: options.status || "done",
        },
        disabled: options.disabled,
        hidden: options.checkboxHidden,
        value: options.name || key,
    });
    row.hidden = Boolean(options.rowHidden);
    row.append(toggle, checkbox);
    const panel = new FakeElement("section", {
        id: `details-${key}`,
        classes: ["bw-row-details", ...(options.expanded ? ["is-expanded"] : [])],
        dataset: {workspaceKey: key},
        hidden: !options.expanded,
        rect: {top: options.panelTop ?? 160, bottom: (options.panelTop ?? 160) + 100, height: 100},
    });
    return {row, toggle, checkbox, panel};
}

function deletionControls(options = {}) {
    const form = new FakeElement("form", {dataset: {bulkDeleteForm: ""}});
    const selectVisibleDone = new FakeElement("button", {
        type: "button",
        dataset: {selectVisibleDone: ""},
    });
    const deleteSelected = new FakeElement("button", {
        type: "submit",
        dataset: {deleteSelected: ""},
        disabled: true,
    });
    const count = new FakeElement("span", {dataset: {deleteCount: ""}, textContent: "0"});
    const countLive = new FakeElement("span", {
        dataset: {deleteCountLive: ""},
        textContent: "Delete selected (0)",
    });
    const result = new FakeElement("div", {
        dataset: {deleteResult: "", ...(options.resultDataset || {})},
        attributes: options.resultAttributes,
        textContent: options.resultText,
    });
    deleteSelected.append(count);
    form.append(selectVisibleDone, deleteSelected, countLive, result);
    return {form, selectVisibleDone, deleteSelected, count, countLive, result};
}

function dashboardContent(harness, workspaces, options = {}) {
    const dashboard = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    const controls = options.edit ? deletionControls(options) : null;
    if (controls) dashboard.append(controls.form);
    for (const item of workspaces) dashboard.append(item.row, item.panel);
    return {dashboard, controls};
}

function dashboardFixture(harness, workspaces, options = {}) {
    const frame = harness.document.adopt(new FakeElement("main", {classes: ["bw-frame"]}));
    const {dashboard, controls} = dashboardContent(harness, workspaces, options);
    frame.append(dashboard);
    harness.document.body.append(frame);
    return {frame, dashboard, controls};
}

function startHarness(harness) {
    harness.document.dispatch("DOMContentLoaded");
}

function eventTime(value, fallback = "—", accessible = null) {
    const attributes = value ? {datetime: value} : {};
    if (accessible) {
        attributes.title = accessible;
        attributes["aria-label"] = accessible;
    }
    return new FakeElement("time", {
        dataset: {eventTime: ""},
        attributes,
        textContent: fallback,
    });
}

function htmxSwap(frame, marker = null, options = {}) {
    const isError = options.isError ?? Boolean(marker);
    const xhr =
        options.xhr ||
        {
            getResponseHeader(name) {
                return name === "X-Boardwalk-Dashboard-Fragment" ? marker : null;
            },
        };
    return {
        target: frame,
        detail: {
            target: frame,
            isError,
            shouldSwap: options.shouldSwap ?? !isError,
            xhr,
        },
    };
}

function htmxAfter(frame, xhr) {
    return {target: frame, detail: {target: frame, xhr}};
}

function settleSwap(harness, frame, replacementDashboard, beforeSwap = htmxSwap(frame)) {
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacementDashboard);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));
}

function changeSelection(checkbox, checked) {
    checkbox.checked = checked;
    checkbox.dispatch("change", {target: checkbox});
}

test("manual eligible deletion selections survive a dashboard refresh", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {name: "Alpha", status: "idle"});
    const oldBeta = workspace("beta", {name: "Beta", status: "done"});
    const {frame, controls} = dashboardFixture(harness, [oldAlpha, oldBeta], {edit: true});
    startHarness(harness);
    changeSelection(oldAlpha.checkbox, true);

    const newAlpha = workspace("alpha", {name: "Alpha", status: "idle"});
    const newBeta = workspace("beta", {name: "Beta", status: "done"});
    const replacement = dashboardContent(harness, [newAlpha, newBeta], {edit: true});
    settleSwap(harness, frame, replacement.dashboard);

    assert.equal(newAlpha.checkbox.checked, true);
    assert.equal(newBeta.checkbox.checked, false);
    assert.equal(replacement.controls.count.textContent, "1");
    assert.equal(replacement.controls.countLive.textContent, "Delete selected (1)");
    assert.equal(replacement.controls.deleteSelected.disabled, false);
    assert.equal(controls.count.textContent, "1");
});

test("absent disabled and hidden deletion rows are pruned during refresh", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {name: "Alpha"});
    const oldBeta = workspace("beta", {name: "Beta"});
    const oldGamma = workspace("gamma", {name: "Gamma"});
    const {frame, controls} = dashboardFixture(harness, [oldAlpha, oldBeta, oldGamma], {edit: true});
    startHarness(harness);
    changeSelection(oldAlpha.checkbox, true);
    changeSelection(oldBeta.checkbox, true);
    changeSelection(oldGamma.checkbox, true);
    assert.equal(controls.count.textContent, "3");

    const disabledBeta = workspace("beta", {name: "Beta", disabled: true});
    const hiddenGamma = workspace("gamma", {name: "Gamma", rowHidden: true});
    const pruned = dashboardContent(harness, [disabledBeta, hiddenGamma], {edit: true});
    settleSwap(harness, frame, pruned.dashboard);
    assert.equal(pruned.controls.count.textContent, "0");
    assert.equal(pruned.controls.deleteSelected.disabled, true);

    const newAlpha = workspace("alpha", {name: "Alpha"});
    const newBeta = workspace("beta", {name: "Beta"});
    const newGamma = workspace("gamma", {name: "Gamma"});
    const reintroduced = dashboardContent(harness, [newAlpha, newBeta, newGamma], {edit: true});
    settleSwap(harness, frame, reintroduced.dashboard);

    assert.equal(newAlpha.checkbox.checked, false);
    assert.equal(newBeta.checkbox.checked, false);
    assert.equal(newGamma.checkbox.checked, false);
    assert.equal(reintroduced.controls.count.textContent, "0");
});

test("leaving edit mode clears deletion selection state", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {name: "Alpha"});
    const {frame, controls} = dashboardFixture(harness, [oldAlpha], {edit: true});
    startHarness(harness);
    changeSelection(oldAlpha.checkbox, true);
    assert.equal(controls.count.textContent, "1");

    const readOnlyAlpha = workspace("alpha", {name: "Alpha"});
    settleSwap(harness, frame, dashboardContent(harness, [readOnlyAlpha]).dashboard);

    const newAlpha = workspace("alpha", {name: "Alpha"});
    const editAgain = dashboardContent(harness, [newAlpha], {edit: true});
    settleSwap(harness, frame, editAgain.dashboard);

    assert.equal(newAlpha.checkbox.checked, false);
    assert.equal(editAgain.controls.count.textContent, "0");
    assert.equal(editAgain.controls.deleteSelected.disabled, true);
});

test("select visible done adds only eligible done rows without clearing manual choices", () => {
    const harness = createHarness();
    const manualIdle = workspace("manual", {name: "Manual idle", status: "idle"});
    const visibleDone = workspace("visible", {name: "Visible done", status: "done"});
    const disabledDone = workspace("disabled", {name: "Disabled done", status: "done", disabled: true});
    const hiddenDone = workspace("hidden", {name: "Hidden done", status: "done", rowHidden: true});
    const visibleRunning = workspace("running", {name: "Visible running", status: "running"});
    const {controls} = dashboardFixture(
        harness,
        [manualIdle, visibleDone, disabledDone, hiddenDone, visibleRunning],
        {edit: true},
    );
    startHarness(harness);
    changeSelection(manualIdle.checkbox, true);

    controls.selectVisibleDone.click();

    assert.equal(manualIdle.checkbox.checked, true);
    assert.equal(visibleDone.checkbox.checked, true);
    assert.equal(disabledDone.checkbox.checked, false);
    assert.equal(hiddenDone.checkbox.checked, false);
    assert.equal(visibleRunning.checkbox.checked, false);
    assert.equal(controls.count.textContent, "2");
    assert.equal(controls.countLive.textContent, "Delete selected (2)");
    assert.equal(controls.deleteSelected.disabled, false);
});

test("selection eligibility rejects CSS-hidden checkbox ancestors", () => {
    const harness = createHarness({
        getComputedStyle(element) {
            return {
                display: element.dataset.computedDisplay || "block",
                visibility: element.dataset.computedVisibility || "visible",
            };
        },
    });
    const displayNone = workspace("display-none", {name: "Display none", status: "done"});
    const visibilityHidden = workspace("visibility-hidden", {name: "Visibility hidden", status: "done"});
    const visibilityCollapse = workspace("visibility-collapse", {name: "Visibility collapse", status: "done"});
    const visible = workspace("visible", {name: "Visible", status: "done"});
    const rows = [displayNone, visibilityHidden, visibilityCollapse, visible];
    const {dashboard, controls} = dashboardFixture(harness, rows, {edit: true});
    const wrappers = [
        harness.document.adopt(new FakeElement("div", {dataset: {computedDisplay: "none"}})),
        harness.document.adopt(new FakeElement("div", {dataset: {computedVisibility: "hidden"}})),
        harness.document.adopt(new FakeElement("div", {dataset: {computedVisibility: "collapse"}})),
        harness.document.adopt(new FakeElement("div")),
    ];
    dashboard.replaceChildren(controls.form, ...wrappers, ...rows.map((row) => row.panel));
    wrappers.forEach((wrapper, index) => wrapper.append(rows[index].row));
    startHarness(harness);

    controls.selectVisibleDone.click();

    assert.equal(displayNone.checkbox.checked, false);
    assert.equal(visibilityHidden.checkbox.checked, false);
    assert.equal(visibilityCollapse.checkbox.checked, false);
    assert.equal(visible.checkbox.checked, true);
    assert.equal(controls.count.textContent, "1");
});

test("delete selected count and disabled state follow every checkbox change", () => {
    const harness = createHarness();
    const alpha = workspace("alpha", {name: "Alpha"});
    const beta = workspace("beta", {name: "Beta"});
    const {controls} = dashboardFixture(harness, [alpha, beta], {edit: true});
    startHarness(harness);

    assert.equal(controls.count.textContent, "0");
    assert.equal(controls.deleteSelected.disabled, true);
    changeSelection(alpha.checkbox, true);
    assert.equal(controls.count.textContent, "1");
    assert.equal(controls.deleteSelected.disabled, false);
    changeSelection(beta.checkbox, true);
    assert.equal(controls.count.textContent, "2");
    changeSelection(alpha.checkbox, false);
    assert.equal(controls.count.textContent, "1");
    changeSelection(beta.checkbox, false);
    assert.equal(controls.count.textContent, "0");
    assert.equal(controls.countLive.textContent, "Delete selected (0)");
    assert.equal(controls.deleteSelected.disabled, true);
});

test("a successful deletion fragment removes keys that disappeared from the dashboard", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {name: "Alpha"});
    const oldBeta = workspace("beta", {name: "Beta"});
    const {frame, controls} = dashboardFixture(harness, [oldAlpha, oldBeta], {edit: true});
    startHarness(harness);
    changeSelection(oldAlpha.checkbox, true);
    assert.equal(controls.count.textContent, "1");

    const remainingBeta = workspace("beta", {name: "Beta"});
    const success = dashboardContent(harness, [remainingBeta], {edit: true});
    settleSwap(harness, frame, success.dashboard);
    assert.equal(success.controls.count.textContent, "0");
    assert.equal(success.controls.countLive.textContent, "Delete selected (0)");
    assert.equal(success.controls.deleteSelected.disabled, true);

    const returnedAlpha = workspace("alpha", {name: "Alpha"});
    const returnedBeta = workspace("beta", {name: "Beta"});
    const laterRefresh = dashboardContent(harness, [returnedAlpha, returnedBeta], {edit: true});
    settleSwap(harness, frame, laterRefresh.dashboard);

    assert.equal(returnedAlpha.checkbox.checked, false);
    assert.equal(laterRefresh.controls.count.textContent, "0");
    assert.equal(laterRefresh.controls.countLive.textContent, "Delete selected (0)");
    assert.equal(laterRefresh.controls.deleteSelected.disabled, true);
});

test("bulk form hx-confirm contains the exact bounded selection copy", () => {
    const harness = createHarness();
    const names = Array.from({length: 12}, (_, index) => `Workspace ${String(index + 1).padStart(2, "0")}`);
    const rows = names.map((name, index) =>
        workspace(`key-${index + 1}`, {name, status: index % 2 ? "idle" : "done"}),
    );
    const {controls} = dashboardFixture(harness, rows, {edit: true});
    startHarness(harness);
    for (const row of rows) changeSelection(row.checkbox, true);

    const expected = [
        "Delete 12 selected workspaces?",
        "",
        ...names.slice(0, 10),
        "and 2 more",
        "",
        "Boardwalk's stored workspace data for these workspaces will be removed. This action cannot be undone.",
    ].join("\n");
    assert.equal(controls.form.getAttribute("hx-confirm"), expected);
});

test("bulk form removes hx-confirm when no eligible selections remain", () => {
    const harness = createHarness();
    const alpha = workspace("alpha", {name: "Alpha"});
    const {controls} = dashboardFixture(harness, [alpha], {edit: true});
    startHarness(harness);
    changeSelection(alpha.checkbox, true);
    assert.match(controls.form.getAttribute("hx-confirm"), /Delete 1 selected workspace\?/);

    changeSelection(alpha.checkbox, false);

    assert.equal(controls.form.hasAttribute("hx-confirm"), false);
    assert.equal(controls.deleteSelected.disabled, true);
});

test("Boardwalk leaves confirmation and cancellation to the shipped HTMX attribute contract", () => {
    let confirmCalls = 0;
    const harness = createHarness({
        confirm() {
            confirmCalls += 1;
            return true;
        },
    });
    const alpha = workspace("alpha", {name: "Alpha"});
    const {controls} = dashboardFixture(harness, [alpha], {edit: true});
    startHarness(harness);
    changeSelection(alpha.checkbox, true);
    const event = {
        detail: {elt: controls.form},
        preventDefaultCalls: 0,
        preventDefault() {
            this.preventDefaultCalls += 1;
        },
    };

    harness.document.body.dispatch("htmx:confirm", event);

    assert.equal(event.preventDefaultCalls, 0);
    assert.equal(confirmCalls, 0);
});

test("shipped HTMX 1.8.2 inherits hx-confirm and cancels before issuing a request", () => {
    assert.match(htmxSource, /version:"1\.8\.2"/);
    assert.match(
        htmxSource,
        /var R=z\(n,"hx-confirm"\);if\(R\)\{if\(!confirm\(R\)\)\{Z\(c\);s\(\);return d\}\}/,
    );
    assert.doesNotMatch(htmxSource, /htmx:confirm|issueRequest/);
});

test("event times localize defensively with compact and accessible full formats", () => {
    const formatOptions = [];
    const compactText = "1:02:03 PM";
    const fullText = "Tuesday, July 14, 2026 at 1:02:03 PM Pacific Daylight Time";
    const harness = createHarness({
        Intl: {
            DateTimeFormat: class {
                constructor(_locales, options) {
                    this.options = options;
                    formatOptions.push({...options});
                }

                format() {
                    return this.options.hour ? compactText : fullText;
                }
            },
        },
    });
    const invalid = eventTime("not-a-date", "—");
    const missing = eventTime(null, "—");
    const valid = eventTime("2026-07-14T20:02:03Z", "20:02:03");
    const {dashboard} = dashboardFixture(harness, []);
    dashboard.append(invalid, missing, valid);

    startHarness(harness);

    assert.equal(invalid.textContent, "—");
    assert.equal(invalid.getAttribute("title"), null);
    assert.equal(invalid.getAttribute("aria-label"), null);
    assert.equal(missing.textContent, "—");
    assert.equal(valid.textContent, compactText);
    assert.equal(valid.getAttribute("title"), fullText);
    assert.equal(valid.getAttribute("aria-label"), fullText);
    assert.deepEqual(formatOptions, [
        {hour: "numeric", minute: "2-digit", second: "2-digit"},
        {dateStyle: "full", timeStyle: "long"},
    ]);
});

test("new event times localize during afterSwap before layout settles", () => {
    const harness = createHarness({
        Intl: {
            DateTimeFormat: class {
                constructor(_locales, options) {
                    this.options = options;
                }

                format() {
                    return this.options.hour ? "4:05:06 PM" : "Tuesday, July 14, 2026 at 4:05:06 PM PDT";
                }
            },
        },
    });
    const {frame} = dashboardFixture(harness, []);
    startHarness(harness);
    const replacement = dashboardContent(harness, []);
    const timestamp = eventTime("2026-07-14T23:05:06Z", "23:05:06");
    replacement.dashboard.append(timestamp);
    const beforeSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement.dashboard);
    assert.equal(timestamp.textContent, "23:05:06");

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(timestamp.textContent, "4:05:06 PM");
    assert.equal(timestamp.getAttribute("aria-label"), "Tuesday, July 14, 2026 at 4:05:06 PM PDT");
});

test("valid event times retain the server fallback when Intl formatting fails", () => {
    const harness = createHarness({
        Intl: {
            DateTimeFormat: class {
                format() {
                    throw new RangeError("formatting unavailable");
                }
            },
        },
    });
    const timestamp = eventTime(
        "2026-07-14T20:02:03Z",
        "20:02:03",
        "Tuesday, July 14, 2026 at 20:02:03 UTC",
    );
    const {dashboard} = dashboardFixture(harness, []);
    dashboard.append(timestamp);

    startHarness(harness);

    assert.equal(timestamp.textContent, "20:02:03");
    assert.equal(timestamp.getAttribute("title"), "Tuesday, July 14, 2026 at 20:02:03 UTC");
    assert.equal(timestamp.getAttribute("aria-label"), "Tuesday, July 14, 2026 at 20:02:03 UTC");
});

test("checkbox focus does not cancel dashboard polling", () => {
    const harness = createHarness();
    const alpha = workspace("alpha");
    const {frame, dashboard} = dashboardFixture(harness, [alpha]);
    harness.document.activeElement = alpha.checkbox;
    const event = {
        target: frame,
        detail: {elt: dashboard},
        preventDefaultCalls: 0,
        preventDefault() {
            this.preventDefaultCalls += 1;
        },
    };

    harness.document.body.dispatch("htmx:beforeRequest", event);

    assert.equal(event.preventDefaultCalls, 0);
});

test("text search and select focus still cancel dashboard polling", () => {
    for (const [label, control] of [
        ["text", new FakeElement("input", {type: "text"})],
        ["search", new FakeElement("input", {type: "search"})],
        ["select", new FakeElement("select")],
    ]) {
        const harness = createHarness();
        const alpha = workspace("alpha");
        const {frame, dashboard} = dashboardFixture(harness, [alpha]);
        alpha.row.append(control);
        harness.document.activeElement = control;
        const event = {
            target: frame,
            detail: {elt: dashboard},
            preventDefaultCalls: 0,
            preventDefault() {
                this.preventDefaultCalls += 1;
            },
        };

        harness.document.body.dispatch("htmx:beforeRequest", event);

        assert.equal(event.preventDefaultCalls, 1, label);
    }
});

test("checkbox focus snapshot restores the same workspace key", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldBeta = workspace("beta");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldBeta.checkbox;
    const newAlpha = workspace("alpha");
    const newBeta = workspace("beta");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    assert.equal(newAlpha.checkbox.focusCalls.length, 0);
    assert.equal(newBeta.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls[0].preventScroll, true);
});

test("missing focused control falls forward to the nearest dashboard control without scrolling", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldBeta = workspace("beta");
    const oldGamma = workspace("gamma");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta, oldGamma]);
    harness.document.activeElement = oldBeta.checkbox;
    const newAlpha = workspace("alpha");
    const newGamma = workspace("gamma");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newGamma.row, newGamma.panel);

    settleSwap(harness, frame, replacement);

    assert.equal(newAlpha.checkbox.focusCalls.length, 0);
    assert.equal(newGamma.checkbox.focusCalls.length, 1);
    assert.equal(newGamma.checkbox.focusCalls[0].preventScroll, true);
});

test("focused checkbox that becomes disabled falls forward to an eligible dashboard control", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldBeta = workspace("beta");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldAlpha.checkbox;
    const newAlpha = workspace("alpha", {disabled: true});
    const newBeta = workspace("beta");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    assert.equal(newAlpha.checkbox.focusCalls.length, 0);
    assert.equal(newBeta.toggle.focusCalls.length, 1);
    assert.equal(newBeta.toggle.focusCalls[0].preventScroll, true);
});

test("overlapping same-frame swaps restore the snapshot owned by each xhr", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldBeta = workspace("beta");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldAlpha.checkbox;
    const alphaSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", alphaSwap);
    harness.document.activeElement = oldBeta.checkbox;
    const betaSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", betaSwap);
    const newAlpha = workspace("alpha");
    const newBeta = workspace("beta");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);
    frame.replaceChildren(replacement);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, alphaSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, alphaSwap.detail.xhr));
    assert.equal(newAlpha.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls.length, 0);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, betaSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, betaSwap.detail.xhr));
    assert.equal(newAlpha.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls.length, 1);
});

test("unnamed buttons restore focus by stable action discriminator", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldRelease = new FakeElement("button", {
        type: "button",
        dataset: {workspaceKey: "alpha"},
        attributes: {"hx-post": "/workspaces/alpha/release"},
    });
    oldAlpha.row.append(oldRelease);
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    harness.document.activeElement = oldRelease;
    const newAlpha = workspace("alpha");
    const newRelease = new FakeElement("button", {
        type: "button",
        dataset: {workspaceKey: "alpha"},
        attributes: {"hx-post": "/workspaces/alpha/release"},
    });
    newAlpha.row.append(newRelease);
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);

    settleSwap(harness, frame, replacement);

    assert.equal(newAlpha.toggle.focusCalls.length, 0);
    assert.equal(newRelease.focusCalls.length, 1);
    assert.equal(newRelease.focusCalls[0].preventScroll, true);
});

test("one swap restores expansion exactly once after layout settles", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const oldAlpha = workspace("alpha", {expanded: true});
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);
    assert.equal(beforeSwap.detail.shouldSwap, true);
    assert.equal(beforeSwap.detail.isError, false);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.equal(newAlpha.panel.hidden, true);
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.equal(newAlpha.panel.hiddenWrites.filter((value) => !value).length, 1);
});

test("initial empty frame load binds controls and restores expansion once after settle", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const frame = harness.document.adopt(new FakeElement("main", {classes: ["bw-frame"]}));
    harness.document.body.append(frame);
    const newAlpha = workspace("alpha");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    assert.equal(newAlpha.toggle.dataset.bound, undefined);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.equal(newAlpha.toggle.dataset.bound, "1");
    assert.equal(newAlpha.panel.hidden, true);
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.equal(newAlpha.panel.hiddenWrites.filter((value) => !value).length, 1);
    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, []);
});

test("unrelated htmx swaps do not capture or restore dashboard viewport state", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const alpha = workspace("alpha");
    const {dashboard} = dashboardFixture(harness, [alpha]);
    harness.document.activeElement = alpha.checkbox;
    const unrelated = harness.document.adopt(new FakeElement("aside", {classes: ["inline-swap"]}));
    dashboard.append(unrelated);

    const beforeSwap = htmxSwap(unrelated);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(unrelated, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(unrelated, beforeSwap.detail.xhr));

    assert.equal(alpha.panel.hidden, true);
    assert.equal(alpha.checkbox.focusCalls.length, 0);
    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, []);
});

test("marked dashboard error fragments opt into htmx swapping while unrelated errors remain errors", () => {
    const markedHarness = createHarness();
    const markedAlpha = workspace("alpha");
    const {frame: markedFrame, controls: markedControls} = dashboardFixture(markedHarness, [markedAlpha], {
        edit: true,
    });
    startHarness(markedHarness);
    changeSelection(markedAlpha.checkbox, true);
    assert.equal(markedControls.count.textContent, "1");
    const marked = htmxSwap(markedFrame, "deletion-error");

    markedHarness.document.body.dispatch("htmx:beforeSwap", marked);

    assert.equal(marked.detail.shouldSwap, true);
    assert.equal(marked.detail.isError, false);
    const serverCopy = "Workspace deletion was not completed: Alpha has a connected worker.";
    const refreshedAlpha = workspace("alpha");
    const markedReplacement = dashboardContent(markedHarness, [refreshedAlpha], {
        edit: true,
        resultDataset: {dashboardError: "workspace-deletion"},
        resultAttributes: {role: "alert", "aria-live": "assertive"},
        resultText: serverCopy,
    });
    const issueList = new FakeElement("ul");
    issueList.append(new FakeElement("li", {textContent: "Alpha has a connected worker."}));
    markedReplacement.controls.result.append(issueList);
    markedFrame.replaceChildren(markedReplacement.dashboard);
    markedHarness.document.body.dispatch("htmx:afterSwap", htmxAfter(markedFrame, marked.detail.xhr));
    markedHarness.document.body.dispatch("htmx:afterSettle", htmxAfter(markedFrame, marked.detail.xhr));

    assert.equal(refreshedAlpha.checkbox.checked, true);
    assert.equal(markedReplacement.controls.count.textContent, "1");
    assert.equal(markedReplacement.controls.countLive.textContent, "Delete selected (1)");
    assert.equal(markedReplacement.controls.deleteSelected.disabled, false);
    assert.equal(markedReplacement.controls.result.textContent, serverCopy);
    assert.equal(markedReplacement.controls.result.getAttribute("role"), "alert");
    assert.equal(markedReplacement.controls.result.children[0], issueList);
    assert.equal(
        markedHarness.document.querySelectorAll('[data-dashboard-error="workspace-deletion"]').length,
        1,
    );

    const unrelatedHarness = createHarness();
    unrelatedHarness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const unrelatedAlpha = workspace("alpha");
    const {frame: unrelatedFrame} = dashboardFixture(unrelatedHarness, [unrelatedAlpha]);
    const unrelated = htmxSwap(unrelatedFrame, null, {shouldSwap: false, isError: true});

    unrelatedHarness.document.body.dispatch("htmx:beforeSwap", unrelated);

    assert.equal(unrelated.detail.shouldSwap, false);
    assert.equal(unrelated.detail.isError, true);
    unrelatedHarness.document.body.dispatch("htmx:afterSwap", htmxAfter(unrelatedFrame, unrelated.detail.xhr));
    unrelatedHarness.document.body.dispatch("htmx:afterSettle", htmxAfter(unrelatedFrame, unrelated.detail.xhr));
    assert.equal(unrelatedAlpha.panel.hidden, true);
});

test("collapsed workspace anchor stays fixed when a row is inserted above it", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {rowTop: 120});
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const inserted = workspace("inserted", {rowTop: 40});
    const newAlpha = workspace("alpha", {rowTop: 215});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(inserted.row, inserted.panel, newAlpha.row, newAlpha.panel);

    settleSwap(harness, frame, replacement);

    const correction = 215 - 120;
    assert.deepEqual(harness.window.scrollByCalls, [[0, correction]]);
    assert.equal(newAlpha.row.getBoundingClientRect().top - correction, 120);
});

test("active workspace anchor wins over the first visible row", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {rowTop: 80});
    const oldBeta = workspace("beta", {rowTop: 180});
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldBeta.checkbox;
    const newAlpha = workspace("alpha", {rowTop: 90});
    const newBeta = workspace("beta", {rowTop: 250});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    const correction = 250 - 180;
    assert.deepEqual(harness.window.scrollByCalls, [[0, correction]]);
    assert.equal(newBeta.row.getBoundingClientRect().top - correction, 180);
});

test("active workspace row anchor remains a row when its details restore", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "beta");
    const oldAlpha = workspace("alpha", {rowTop: 80});
    const oldBeta = workspace("beta", {rowTop: 180, panelTop: 240, expanded: true});
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldBeta.checkbox;
    const newAlpha = workspace("alpha", {rowTop: 90});
    const newBeta = workspace("beta", {rowTop: 250, panelTop: 330});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    const correction = 250 - 180;
    assert.deepEqual(harness.window.scrollByCalls, [[0, correction]]);
    assert.equal(newBeta.row.getBoundingClientRect().top - correction, 180);
});

test("expanded details anchor stays fixed after content above it resizes", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "beta");
    const oldAlpha = workspace("alpha", {rowTop: 40});
    const oldBeta = workspace("beta", {rowTop: 160, panelTop: 220, expanded: true});
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    const newAlpha = workspace("alpha", {rowTop: 40});
    const newBeta = workspace("beta", {rowTop: 230, panelTop: 310});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    const correction = 310 - 220;
    assert.deepEqual(harness.window.scrollByCalls, [[0, correction]]);
    assert.equal(newBeta.panel.getBoundingClientRect().top - correction, 220);
});

test("missing saved anchor part uses absolute fallback instead of another part", () => {
    const harness = createHarness();
    harness.window.scrollX = 20;
    harness.window.scrollY = 450;
    harness.document.documentElement.scrollHeight = 1000;
    harness.document.body.scrollHeight = 900;
    const oldBeta = workspace("beta", {rowTop: 160, panelTop: 220, expanded: true});
    const {frame} = dashboardFixture(harness, [oldBeta]);
    const newBeta = workspace("beta", {rowTop: 300});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newBeta.row);

    settleSwap(harness, frame, replacement);

    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, [[20, 200]]);
});

test("missing workspace anchor falls back to saved clamped scroll position", () => {
    const harness = createHarness();
    harness.window.scrollX = 12;
    harness.window.scrollY = 650;
    harness.document.documentElement.scrollHeight = 1000;
    harness.document.body.scrollHeight = 900;
    const oldAlpha = workspace("alpha", {rowTop: 120});
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newBeta = workspace("beta", {rowTop: 50});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, [[12, 200]]);
});
