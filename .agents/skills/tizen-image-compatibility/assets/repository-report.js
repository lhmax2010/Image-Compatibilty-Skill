"use strict";

const byId = id => document.getElementById(id);
const next = byId("next");
const status = byId("status");
let query = null;
let after = null;

async function read(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

async function show(cursor) {
    next.disabled = true;
    status.textContent = "Loading…";
    try {
        const params = new URLSearchParams({after: cursor, package: query.package});
        const result = await read(`/api/${query.table}?${params}`);
        const cols = Object.keys(result.rows[0] || {});
        const fillRow = (values, tag) => {
            const row = document.createElement("tr");
            for (const value of values) {
                const cell = document.createElement(tag);
                cell.textContent = value;
                row.append(cell);
            }
            return row;
        };
        byId("heading").replaceChildren(fillRow(cols, "th"));
        byId("rows").replaceChildren(...result.rows.map(obj => fillRow(cols.map(key => obj[key]), "td")));
        after = result.next_after;
        next.disabled = after === null;
        status.textContent = result.rows.length ? `${result.rows.length} rows` : "No rows";
    } catch (error) {
        status.textContent = error.message;
    }
}

function search() {
    query = {table: byId("table").value, package: byId("package").value};
    show(0);
}

byId("search").addEventListener("click", search);
next.addEventListener("click", () => show(after));
read("/api/overview").then(data => {
    byId("scope").textContent = data.scope;
    search();
}).catch(error => { status.textContent = error.message; });
