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
const cssSource = fs.readFileSync(
    new URL("../../src/boardwalkd/static/boardwalkd.css", import.meta.url),
    "utf8",
);
const obsoleteRestorationClass = ["is", "restoring", "dashboard", "state"].join("-");

test("deletion checkboxes use compact theme-aware focus and disabled styles", () => {
    assert.match(
        cssSource,
        /\.bw-delete-checkbox\s*\{[^}]*width:\s*16px;[^}]*height:\s*16px;[^}]*accent-color:\s*var\(--bw-brand\);[^}]*border-radius:\s*4px;/s,
    );
    assert.match(
        cssSource,
        /\.bw-delete-checkbox:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--bw-link\);[^}]*outline-offset:\s*2px;/s,
    );
    assert.match(cssSource, /\.bw-delete-checkbox:disabled\s*\{[^}]*opacity:\s*0\.35;/s);
    assert.match(cssSource, /\.bw-theme-light \.bw-delete-checkbox\s*\{[^}]*color-scheme:\s*light;/s);
    assert.match(cssSource, /\.bw-theme-dark \.bw-delete-checkbox\s*\{[^}]*color-scheme:\s*dark;/s);
});

test("stale row styling does not dim deletion controls through parent opacity", () => {
    const staleRules = Array.from(cssSource.matchAll(/\.bw-row\.status-stale[^\{]*\{([^}]*)\}/g));
    assert.ok(staleRules.length > 0);
    for (const rule of staleRules) assert.doesNotMatch(rule[1], /\bopacity\s*:/);
    assert.match(staleRules[0][1], /background-image:\s*linear-gradient/);
    assert.doesNotMatch(staleRules[0][1], /box-shadow/);
});

test("obsolete dashboard restoration state is absent without removing normal animations", () => {
    assert.doesNotMatch(source, new RegExp(obsoleteRestorationClass));
    assert.doesNotMatch(cssSource, new RegExp(obsoleteRestorationClass));
    assert.match(cssSource, /\.bw-row\s*\{[^}]*transition:\s*background 140ms ease/s);
    assert.match(cssSource, /\.bw-expand span\[aria-hidden="true"\]\s*\{[^}]*transition:\s*transform 160ms ease;/s);
    assert.match(
        cssSource,
        /\.bw-row-details:not\(\[hidden\]\)\s*\{[^}]*background:\s*color-mix\(in srgb, var\(--bw-brand\) 5%, var\(--bw-row-alt\)\);/s,
    );
});

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
        this.toggleCalls = [];
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
        this.toggleCalls.push([value, force]);
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
        this.datasetWrites = [];
        this.dataset = new Proxy(
            {...options.dataset},
            {
                set: (target, key, value) => {
                    this.datasetWrites.push([key, value]);
                    target[key] = value;
                    return true;
                },
            },
        );
        this.classList = new FakeClassList(options.classes);
        this.attributes = new Map(Object.entries(options.attributes || {}));
        this.children = [];
        this.parentElement = null;
        this._hidden = Boolean(options.hidden);
        this.hiddenWrites = [];
        this.open = Boolean(options.open);
        this.checked = Boolean(options.checked);
        this.disabled = Boolean(options.disabled);
        this._textContent = options.textContent || "";
        this.textWrites = [];
        this.value = options.value || "";
        this.rect = options.rect || {top: 0, bottom: 20, height: 20};
        this.scrollWidth = options.scrollWidth;
        this.clientWidth = options.clientWidth;
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

    get isConnected() {
        return Boolean(this.ownerDocument && this.ownerDocument.documentElement.contains(this));
    }

    get textContent() {
        return this._textContent;
    }

    set textContent(value) {
        this._textContent = String(value);
        this.textWrites.push(this._textContent);
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
        dispatchBubbling(this, "click");
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
    const setItemCalls = [];
    const removeItemCalls = [];
    return {
        getItem: (key) => values.get(key) ?? null,
        setItem(key, value) {
            setItemCalls.push([key, String(value)]);
            values.set(key, String(value));
        },
        removeItem(key) {
            removeItemCalls.push(key);
            values.delete(key);
        },
        setItemCalls,
        removeItemCalls,
    };
}

function createHarness(options = {}) {
    const document = new FakeDocument();
    const window = new FakeEventTarget();
    Object.assign(window, {
        document,
        Idiomorph: options.Idiomorph,
        innerHeight: 800,
        scrollX: 0,
        scrollY: 0,
        scrollByCalls: [],
        scrollToCalls: [],
        scrollBy(...args) {
            this.scrollByCalls.push(args.map((arg) => (arg && typeof arg === "object" ? {...arg} : arg)));
        },
        scrollTo(...args) {
            this.scrollToCalls.push(args.map((arg) => (arg && typeof arg === "object" ? {...arg} : arg)));
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
        dataset: {selectVisibleStatus: "done"},
    });
    const selectVisibleStale = new FakeElement("button", {
        type: "button",
        dataset: {selectVisibleStatus: "stale"},
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
    form.append(selectVisibleDone, selectVisibleStale, deleteSelected, countLive, result);
    return {form, selectVisibleDone, selectVisibleStale, deleteSelected, count, countLive, result};
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
    dispatchBubbling(checkbox, "change");
}

function dispatchBubbling(target, type, event = {}) {
    let propagationStopped = false;
    const dispatchedEvent = {
        ...event,
        target: event.target || target,
        stopPropagation() {
            propagationStopped = true;
            if (event.stopPropagation) event.stopPropagation();
        },
    };
    for (let node = target; node; node = node.parentElement) {
        node.dispatch(type, dispatchedEvent);
        if (propagationStopped) break;
    }
    return dispatchedEvent;
}

test("global morph callbacks preserve prior vetoes and project only marked dashboard state", () => {
    const previousCalls = [];
    const previousMorphed = (oldNode) => {
        previousCalls.push(["morphed", oldNode.id]);
        return oldNode.id === "veto-row" ? false : true;
    };
    const previousAdded = (newNode) => {
        previousCalls.push(["added", newNode.id]);
        return newNode.id === "veto-added" ? false : true;
    };
    const Idiomorph = {
        defaults: {
            callbacks: {
                beforeNodeMorphed: previousMorphed,
                beforeNodeAdded: previousAdded,
            },
        },
    };
    const harness = createHarness({Idiomorph});
    assert.notStrictEqual(Idiomorph.defaults.callbacks.beforeNodeMorphed, previousMorphed);
    assert.notStrictEqual(Idiomorph.defaults.callbacks.beforeNodeAdded, previousAdded);

    const oldDashboard = new FakeElement("section", {id: "workspace-dashboard"});
    const oldRow = new FakeElement("article", {
        id: "alpha-row",
        classes: ["status-running", "is-expanded"],
        dataset: {workspaceRow: "", workspaceKey: "alpha"},
    });
    const oldToggle = new FakeElement("button", {
        id: "alpha-toggle",
        dataset: {rowToggle: "", workspaceKey: "alpha"},
        attributes: {"aria-expanded": "true"},
    });
    const oldPanel = new FakeElement("section", {
        id: "alpha-panel",
        classes: ["bw-row-details", "is-expanded"],
        dataset: {workspaceKey: "alpha"},
    });
    oldDashboard.append(oldRow, oldToggle, oldPanel);

    const newDashboard = new FakeElement("section", {id: "workspace-dashboard"});
    const newRow = new FakeElement("article", {
        id: "alpha-row",
        classes: ["status-done"],
        dataset: {workspaceRow: "", workspaceKey: "alpha"},
    });
    const newToggle = new FakeElement("button", {
        id: "alpha-toggle",
        dataset: {rowToggle: "", workspaceKey: "alpha"},
        attributes: {"aria-expanded": "false"},
    });
    const newPanel = new FakeElement("section", {
        id: "alpha-panel",
        classes: ["bw-row-details"],
        dataset: {workspaceKey: "alpha"},
        hidden: true,
    });
    newDashboard.append(newRow, newToggle, newPanel);

    assert.equal(Idiomorph.defaults.callbacks.beforeNodeMorphed(oldRow, newRow), true);
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeMorphed(oldToggle, newToggle), true);
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeMorphed(oldPanel, newPanel), true);
    assert.equal(newRow.classList.contains("status-done"), true);
    assert.equal(newRow.classList.contains("status-running"), false);
    assert.equal(newRow.classList.contains("is-expanded"), true);
    assert.equal(newToggle.getAttribute("aria-expanded"), "true");
    assert.equal(newPanel.hidden, false);
    assert.equal(newPanel.classList.contains("is-expanded"), true);

    const outsideOld = new FakeElement("article", {
        id: "outside-row",
        classes: ["is-expanded"],
        dataset: {workspaceRow: ""},
    });
    const outsideNew = new FakeElement("article", {
        id: "outside-row",
        classes: ["status-done"],
        dataset: {workspaceRow: ""},
    });
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeMorphed(outsideOld, outsideNew), true);
    assert.equal(outsideNew.classList.contains("is-expanded"), false);

    const vetoOld = new FakeElement("article", {
        id: "veto-row",
        classes: ["is-expanded"],
        dataset: {workspaceRow: ""},
    });
    const vetoNew = new FakeElement("article", {
        id: "veto-row",
        dataset: {workspaceRow: ""},
    });
    oldDashboard.append(vetoOld);
    newDashboard.append(vetoNew);
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeMorphed(vetoOld, vetoNew), false);
    assert.equal(vetoNew.classList.contains("is-expanded"), false);

    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "new");
    harness.sessionStorage.setItem("boardwalk.expandedEvents", "new");
    const addedRow = new FakeElement("article", {
        id: "new-row",
        dataset: {workspaceRow: "", workspaceKey: "new"},
    });
    const addedToggle = new FakeElement("button", {
        dataset: {rowToggle: "", workspaceKey: "new"},
        attributes: {"aria-expanded": "false"},
    });
    addedRow.append(addedToggle);
    const addedPanel = new FakeElement("section", {
        id: "new-panel",
        classes: ["bw-row-details"],
        dataset: {workspaceKey: "new"},
        hidden: true,
    });
    const extraEvent = new FakeElement("div", {dataset: {eventExtra: ""}, hidden: true});
    const eventToggle = new FakeElement("button", {dataset: {eventsToggle: ""}});
    addedPanel.append(extraEvent, eventToggle);
    newDashboard.append(addedRow, addedPanel);

    assert.equal(Idiomorph.defaults.callbacks.beforeNodeAdded(addedRow), true);
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeAdded(addedPanel), true);
    assert.equal(addedRow.classList.contains("is-expanded"), true);
    assert.equal(addedToggle.getAttribute("aria-expanded"), "true");
    assert.equal(addedPanel.hidden, false);
    assert.equal(addedPanel.classList.contains("is-expanded"), true);
    assert.equal(extraEvent.hidden, false);
    assert.equal(eventToggle.hidden, true);

    const vetoAdded = new FakeElement("article", {id: "veto-added"});
    newDashboard.append(vetoAdded);
    assert.equal(Idiomorph.defaults.callbacks.beforeNodeAdded(vetoAdded), false);
    assert.ok(previousCalls.some(([type, id]) => type === "morphed" && id === "alpha-row"));
    assert.ok(previousCalls.some(([type, id]) => type === "added" && id === "new-row"));
});

test("delegated retained controls act exactly once after duplicate enhancements", () => {
    const harness = createHarness();
    const themeToggle = harness.document.adopt(
        new FakeElement("button", {type: "button", dataset: {themeToggle: ""}}),
    );
    harness.document.body.append(themeToggle);
    const alpha = workspace("alpha", {name: "Alpha", status: "done"});
    const stale = workspace("stale", {name: "Stale", status: "stale"});
    const events = new FakeElement("div", {classes: ["bw-events"]});
    const extraEvent = new FakeElement("div", {dataset: {eventExtra: ""}, hidden: true});
    const eventsToggle = new FakeElement("button", {
        type: "button",
        dataset: {eventsToggle: ""},
        textContent: "Show more",
    });
    events.append(extraEvent, eventsToggle);
    alpha.panel.append(events);
    const {frame, controls} = dashboardFixture(harness, [alpha, stale], {edit: true});
    startHarness(harness);

    for (let index = 0; index < 10; index += 1) {
        delete themeToggle.dataset.bound;
        delete alpha.toggle.dataset.bound;
        delete alpha.row.dataset.bound;
        delete eventsToggle.dataset.bound;
        delete alpha.checkbox.dataset.deletionBound;
        delete controls.selectVisibleStale.dataset.deletionBound;
        const beforeSwap = htmxSwap(frame);
        harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
        harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
        harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));
    }

    assert.equal(harness.document.body.listeners.get("click")?.length, 1);
    assert.equal(harness.document.body.listeners.get("change")?.length, 1);
    assert.equal(themeToggle.listeners.get("click")?.length || 0, 0);
    assert.equal(alpha.toggle.listeners.get("click")?.length || 0, 0);
    assert.equal(alpha.row.listeners.get("click")?.length || 0, 0);
    assert.equal(eventsToggle.listeners.get("click")?.length || 0, 0);
    assert.equal(alpha.checkbox.listeners.get("change")?.length || 0, 0);
    assert.equal(controls.selectVisibleStale.listeners.get("click")?.length || 0, 0);
    for (const element of [
        themeToggle,
        alpha.toggle,
        alpha.row,
        eventsToggle,
        alpha.checkbox,
        controls.selectVisibleStale,
    ]) {
        assert.equal(element.dataset.bound, undefined);
        assert.equal(element.dataset.deletionBound, undefined);
    }

    alpha.panel.hiddenWrites = [];
    alpha.toggle.click();
    assert.equal(alpha.panel.hiddenWrites.filter((hidden) => !hidden).length, 1);
    alpha.panel.hiddenWrites = [];
    dispatchBubbling(alpha.row, "click");
    assert.deepEqual(alpha.panel.hiddenWrites, [true]);

    extraEvent.hiddenWrites = [];
    eventsToggle.hiddenWrites = [];
    harness.sessionStorage.setItemCalls.length = 0;
    eventsToggle.click();
    assert.deepEqual(extraEvent.hiddenWrites, [false]);
    assert.deepEqual(eventsToggle.hiddenWrites, [true]);
    assert.deepEqual(harness.sessionStorage.setItemCalls, [
        ["boardwalk.expandedEvents", "alpha"],
    ]);

    controls.count.textWrites = [];
    changeSelection(alpha.checkbox, true);
    assert.deepEqual(controls.count.textWrites, ["1"]);

    controls.count.textWrites = [];
    controls.selectVisibleStale.click();
    assert.equal(stale.checkbox.checked, true);
    assert.deepEqual(controls.count.textWrites, ["2"]);

    harness.document.documentElement.classList.toggleCalls = [];
    harness.localStorage.setItemCalls.length = 0;
    themeToggle.click();
    assert.deepEqual(harness.document.documentElement.classList.toggleCalls, [
        ["bw-theme-dark", false],
        ["bw-theme-light", true],
    ]);
    assert.deepEqual(harness.localStorage.setItemCalls, [["boardwalk.theme", "light"]]);
});

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

test("select visible stale adds only eligible stale rows without clearing manual choices", () => {
    const harness = createHarness();
    const manualIdle = workspace("manual", {name: "Manual idle", status: "idle"});
    const visibleStale = workspace("visible", {name: "Visible stale", status: "stale"});
    const disabledStale = workspace("disabled", {name: "Disabled stale", status: "stale", disabled: true});
    const hiddenStale = workspace("hidden", {name: "Hidden stale", status: "stale", rowHidden: true});
    const visibleDone = workspace("done", {name: "Visible done", status: "done"});
    const {controls} = dashboardFixture(
        harness,
        [manualIdle, visibleStale, disabledStale, hiddenStale, visibleDone],
        {edit: true},
    );
    startHarness(harness);
    changeSelection(manualIdle.checkbox, true);

    controls.selectVisibleStale.click();

    assert.equal(manualIdle.checkbox.checked, true);
    assert.equal(visibleStale.checkbox.checked, true);
    assert.equal(disabledStale.checkbox.checked, false);
    assert.equal(hiddenStale.checkbox.checked, false);
    assert.equal(visibleDone.checkbox.checked, false);
    assert.equal(controls.count.textContent, "2");
    assert.equal(controls.countLive.textContent, "Delete selected (2)");
    assert.equal(controls.deleteSelected.disabled, false);
});

test("focused visible-status shortcut restores the same status after refresh", () => {
    const harness = createHarness();
    const oldStale = workspace("stale", {status: "stale"});
    const {frame, controls} = dashboardFixture(harness, [oldStale], {edit: true});
    startHarness(harness);
    harness.document.activeElement = controls.selectVisibleStale;
    const newStale = workspace("stale", {status: "stale"});
    const replacement = dashboardContent(harness, [newStale], {edit: true});

    settleSwap(harness, frame, replacement.dashboard);

    assert.equal(replacement.controls.selectVisibleDone.focusCalls.length, 0);
    assert.equal(replacement.controls.selectVisibleStale.focusCalls.length, 1);
    assert.equal(replacement.controls.selectVisibleStale.focusCalls[0].preventScroll, true);
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

test("shipped HTMX 2.0.10 inherits hx-confirm and cancels before issuing a request", () => {
    assert.match(htmxSource, /version:"2\.0\.10"/);
    assert.match(htmxSource, /const a=ne\(r,"hx-confirm"\)/);
    assert.match(htmxSource, /if\(a&&!k\)\{if\(!confirm\(a\)\)\{re\(s\);m\(\);return e\}\}/);
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

test("afterSwap runs timestamp localization and name fitting once per response", () => {
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
    const replacement = dashboardContent(harness, []);
    const timestamp = eventTime("2026-07-14T23:05:06Z", "23:05:06");
    const fittedName = new FakeElement("span", {
        dataset: {fitName: ""},
        scrollWidth: 40,
        clientWidth: 40,
    });
    replacement.dashboard.append(timestamp, fittedName);
    const beforeSwap = htmxSwap(frame);

    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement.dashboard);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.deepEqual(timestamp.textWrites, ["4:05:06 PM"]);
    assert.deepEqual(fittedName.datasetWrites, [["fit", "normal"]]);
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

test("afterSwap focus fallback restores the same workspace key exactly once", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha");
    const oldBeta = workspace("beta");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldBeta.checkbox;
    const newAlpha = workspace("alpha");
    const newBeta = workspace("beta");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    const beforeSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.checkbox.focusCalls.length, 0);
    assert.equal(newBeta.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls[0].preventScroll, true);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.equal(newBeta.checkbox.focusCalls.length, 1);
});

test("afterSwap never refocuses or overwrites a retained active node", () => {
    const harness = createHarness();
    const alpha = workspace("alpha");
    const filter = new FakeElement("input", {
        type: "search",
        name: "filter",
        value: "operator draft",
    });
    alpha.row.append(filter);
    const {frame} = dashboardFixture(harness, [alpha]);
    harness.document.activeElement = filter;
    const beforeSwap = htmxSwap(frame);

    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    filter.value = "server-authoritative filter";
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(filter.value, "server-authoritative filter");
    assert.deepEqual(filter.focusCalls, []);
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

test("overlapping same-frame swaps apply the snapshot owned by each xhr without restoration state", () => {
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
    assert.equal(frame.classList.contains(obsoleteRestorationClass), false);
    const newAlpha = workspace("alpha");
    const newBeta = workspace("beta");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);
    frame.replaceChildren(replacement);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, alphaSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, alphaSwap.detail.xhr));
    assert.equal(newAlpha.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls.length, 0);
    assert.equal(frame.classList.contains(obsoleteRestorationClass), false);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, betaSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, betaSwap.detail.xhr));
    assert.equal(newAlpha.checkbox.focusCalls.length, 1);
    assert.equal(newBeta.checkbox.focusCalls.length, 1);
    assert.equal(frame.classList.contains(obsoleteRestorationClass), false);
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

test("afterSwap leaves morph-projected expansion untouched", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const oldAlpha = workspace("alpha", {expanded: true});
    oldAlpha.row.classList.add("is-expanded");
    oldAlpha.toggle.setAttribute("aria-expanded", "true");
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha", {expanded: true});
    newAlpha.row.classList.add("is-expanded");
    newAlpha.toggle.setAttribute("aria-expanded", "true");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);
    assert.equal(beforeSwap.detail.shouldSwap, true);
    assert.equal(beforeSwap.detail.isError, false);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    assert.equal(newAlpha.panel.hidden, false);
    assert.deepEqual(newAlpha.panel.hiddenWrites, []);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.equal(newAlpha.panel.hidden, false);
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.deepEqual(newAlpha.panel.hiddenWrites, []);
});

test("afterSwap restores stored row expansion when a plain replacement loses morph state", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const oldAlpha = workspace("alpha", {expanded: true});
    oldAlpha.row.classList.add("is-expanded");
    oldAlpha.toggle.setAttribute("aria-expanded", "true");
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);

    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    assert.equal(newAlpha.panel.hidden, true);
    assert.equal(newAlpha.toggle.getAttribute("aria-expanded"), "false");
    assert.equal(newAlpha.row.classList.contains("is-expanded"), false);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.equal(newAlpha.panel.classList.contains("is-expanded"), true);
    assert.equal(newAlpha.toggle.getAttribute("aria-expanded"), "true");
    assert.equal(newAlpha.row.classList.contains("is-expanded"), true);
});

test("afterSwap restores stored recent-event expansion after a plain replacement", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedEvents", "alpha");
    const oldAlpha = workspace("alpha");
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha");
    const extraEvent = new FakeElement("div", {dataset: {eventExtra: ""}, hidden: true});
    const eventsToggle = new FakeElement("button", {dataset: {eventsToggle: ""}});
    newAlpha.panel.append(extraEvent, eventsToggle);
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);

    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    assert.equal(extraEvent.hidden, true);
    assert.equal(eventsToggle.hidden, false);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(extraEvent.hidden, false);
    assert.equal(eventsToggle.hidden, true);
});

test("response swap and abort error cleanup discard refresh transactions", () => {
    for (const eventType of ["htmx:responseError", "htmx:swapError", "htmx:sendAbort"]) {
        const harness = createHarness();
        const oldAlpha = workspace("alpha", {rowTop: 100});
        const {frame} = dashboardFixture(harness, [oldAlpha]);
        harness.document.activeElement = oldAlpha.checkbox;
        const beforeSwap = htmxSwap(frame);
        harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
        harness.document.body.dispatch(eventType, htmxAfter(frame, beforeSwap.detail.xhr));

        const newAlpha = workspace("alpha", {rowTop: 220});
        const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
        replacement.append(newAlpha.row, newAlpha.panel);
        frame.replaceChildren(replacement);
        harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

        assert.equal(frame.classList.contains(obsoleteRestorationClass), false, eventType);
        assert.deepEqual(newAlpha.checkbox.focusCalls, [], eventType);
        assert.deepEqual(harness.window.scrollByCalls, [], eventType);
        assert.deepEqual(harness.window.scrollToCalls, [], eventType);
    }
});

test("expanded anchor correction is instant once before settle can paint", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const originalPanelTop = -80;
    const clampedPanelTop = 188;
    const oldAlpha = workspace("alpha", {expanded: true, panelTop: originalPanelTop});
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha", {expanded: true, panelTop: clampedPanelTop});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);

    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.deepEqual(harness.window.scrollByCalls, [
        [{behavior: "instant", left: 0, top: clampedPanelTop - originalPanelTop}],
    ]);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.deepEqual(harness.window.scrollByCalls, [
        [{behavior: "instant", left: 0, top: clampedPanelTop - originalPanelTop}],
    ]);
});

test("zero anchor delta does not move the viewport", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {rowTop: 120});
    const {frame} = dashboardFixture(harness, [oldAlpha]);
    const newAlpha = workspace("alpha", {rowTop: 120});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);

    settleSwap(harness, frame, replacement);

    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, []);
});

test("initial empty frame afterSwap enhances morph-projected controls without viewport work", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "alpha");
    const frame = harness.document.adopt(new FakeElement("main", {classes: ["bw-frame"]}));
    harness.document.body.append(frame);
    const newAlpha = workspace("alpha", {expanded: true});
    newAlpha.row.classList.add("is-expanded");
    newAlpha.toggle.setAttribute("aria-expanded", "true");
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel);
    const beforeSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    assert.equal(newAlpha.toggle.dataset.bound, undefined);

    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    assert.equal(newAlpha.toggle.dataset.bound, undefined);
    assert.equal(harness.document.body.listeners.get("click")?.length, 1);
    assert.equal(newAlpha.panel.hidden, false);
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.equal(newAlpha.panel.hidden, false);
    assert.deepEqual(newAlpha.panel.hiddenWrites, []);
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
    assert.deepEqual(harness.window.scrollByCalls, [[{behavior: "instant", left: 0, top: correction}]]);
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
    assert.deepEqual(harness.window.scrollByCalls, [[{behavior: "instant", left: 0, top: correction}]]);
    assert.equal(newBeta.row.getBoundingClientRect().top - correction, 180);
});

test("offscreen active workspace anchor yields to the first visible expanded panel", () => {
    const harness = createHarness();
    const oldAlpha = workspace("alpha", {rowTop: 900});
    const oldBeta = workspace("beta", {expanded: true, rowTop: 140, panelTop: 200});
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    harness.document.activeElement = oldAlpha.checkbox;
    const newAlpha = workspace("alpha", {rowTop: 1040});
    const newBeta = workspace("beta", {expanded: true, rowTop: 180, panelTop: 260});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    const visiblePanelCorrection = 260 - 200;
    assert.deepEqual(harness.window.scrollByCalls, [
        [{behavior: "instant", left: 0, top: visiblePanelCorrection}],
    ]);
    assert.equal(newBeta.panel.getBoundingClientRect().top - visiblePanelCorrection, 200);
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
    assert.deepEqual(harness.window.scrollByCalls, [[{behavior: "instant", left: 0, top: correction}]]);
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
    assert.deepEqual(harness.window.scrollByCalls, [[{behavior: "instant", left: 0, top: correction}]]);
    assert.equal(newBeta.panel.getBoundingClientRect().top - correction, 220);
});

test("visible details remain the viewport anchor after htmx settles their classes", () => {
    const harness = createHarness();
    harness.sessionStorage.setItem("boardwalk.expandedWorkspace", "beta");
    const oldAlpha = workspace("alpha", {rowTop: 40});
    const oldBeta = workspace("beta", {rowTop: 160, panelTop: 220, expanded: true});
    oldBeta.panel.classList.remove("is-expanded");
    const {frame} = dashboardFixture(harness, [oldAlpha, oldBeta]);
    const newAlpha = workspace("alpha", {rowTop: 40});
    const newBeta = workspace("beta", {rowTop: 230, panelTop: 310});
    const replacement = harness.document.adopt(new FakeElement("div", {classes: ["bw-dashboard"]}));
    replacement.append(newAlpha.row, newAlpha.panel, newBeta.row, newBeta.panel);

    settleSwap(harness, frame, replacement);

    const correction = 310 - 220;
    assert.deepEqual(harness.window.scrollByCalls, [[{behavior: "instant", left: 0, top: correction}]]);
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
    assert.deepEqual(harness.window.scrollToCalls, [[{behavior: "instant", left: 0, top: 200}]]);
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

    const beforeSwap = htmxSwap(frame);
    harness.document.body.dispatch("htmx:beforeSwap", beforeSwap);
    frame.replaceChildren(replacement);
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSwap", htmxAfter(frame, beforeSwap.detail.xhr));
    harness.document.body.dispatch("htmx:afterSettle", htmxAfter(frame, beforeSwap.detail.xhr));

    assert.deepEqual(harness.window.scrollByCalls, []);
    assert.deepEqual(harness.window.scrollToCalls, [[{behavior: "instant", left: 0, top: 200}]]);
});
