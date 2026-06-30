"use strict";

const $ = (sel) => document.querySelector(sel);
let JOB = null; // latest job payload

// ---------------------------------------------------------------------------
// Init: Zotero status, styles, collections
// ---------------------------------------------------------------------------
async function init() {
  // Styles
  try {
    const { styles } = await (await fetch("/api/styles")).json();
    const sel = $("#style");
    sel.innerHTML = styles.map((s) => `<option value="${s}">${s}</option>`).join("");
  } catch (_) {}

  // Zotero status
  const statusEl = $("#zotero-status");
  try {
    const st = await (await fetch("/api/zotero/status")).json();
    statusEl.textContent = st.ok ? "✓ " + st.detail : "✗ " + st.detail;
    statusEl.className = "status " + (st.ok ? "ok" : "bad");
    if (st.ok) loadCollections();
  } catch (_) {
    statusEl.textContent = "✗ Could not contact the local server.";
    statusEl.className = "status bad";
  }
}

async function loadCollections() {
  try {
    const { collections } = await (await fetch("/api/zotero/collections")).json();
    const sel = $("#collection");
    for (const c of collections) {
      const o = document.createElement("option");
      o.value = c.key; o.textContent = c.name;
      sel.appendChild(o);
    }
  } catch (_) {}
}

// ---------------------------------------------------------------------------
// Step 1 -> analyze
// ---------------------------------------------------------------------------
$("#analyze").addEventListener("click", async () => {
  const file = $("#file").files[0];
  const msg = $("#setup-msg");
  if (!file) { msg.textContent = "Please choose a .docx file."; msg.className = "msg error"; return; }

  const fd = new FormData();
  fd.append("file", file);
  fd.append("style", $("#style").value);
  fd.append("collection", $("#collection").value);
  const lib = $("#library_file").files[0];
  if (lib) fd.append("library_file", lib);

  $("#analyze").disabled = true;
  msg.textContent = "Analyzing… this can take a moment for large libraries.";
  msg.className = "msg";
  try {
    const res = await fetch("/api/jobs", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    JOB = await res.json();
    renderReview();
  } catch (e) {
    msg.textContent = "Error: " + e.message;
    msg.className = "msg error";
  } finally {
    $("#analyze").disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Step 2 -> review
// ---------------------------------------------------------------------------
function citationsById() {
  const map = {};
  for (const c of JOB.citations) map[c.id] = c;
  return map;
}

function renderReview() {
  const cites = citationsById();
  const s = JOB.summary;
  $("#summary").innerHTML =
    `<span class="pill ok">${s.confident} auto-included</span>` +
    `<span class="pill warn">${s.ambiguous} to review</span>` +
    `<span class="pill bad">${s.none} no match</span>`;

  const auto = [], none = [], ambiguous = [];
  for (const r of Object.values(JOB.results)) {
    if (r.status === "confident") auto.push(r);
    else if (r.status === "none") none.push(r);
    else ambiguous.push(r);
  }

  $("#auto-list").innerHTML = auto.length
    ? auto.map((r) => {
        const c = cites[r.citation_id];
        const cand = r.candidates[0];
        return `<li><span class="raw">${esc(c.raw_text)}</span> → ${esc(cand ? cand.display : "")}</li>`;
      }).join("")
    : `<li class="empty">None.</li>`;

  $("#none-list").innerHTML = none.length
    ? none.map((r) => `<li><span class="raw">${esc(cites[r.citation_id].raw_text)}</span></li>`).join("")
    : `<li class="empty">None.</li>`;

  const rl = $("#review-list");
  if (!ambiguous.length) {
    rl.innerHTML = `<p class="empty">Nothing to review.</p>`;
  } else {
    rl.innerHTML = ambiguous.map((r) => {
      const c = cites[r.citation_id];
      const opts = r.candidates.map((cand) =>
        `<label><input type="radio" name="res_${r.citation_id}" value="${esc(cand.item_key)}">
           ${esc(cand.display)} <span class="score">(${cand.score})</span></label>`).join("");
      return `<div class="review-item">
        <div>For <span class="raw">${esc(c.raw_text)}</span>:</div>
        <div class="cands">${opts}
          <label><input type="radio" name="res_${r.citation_id}" value="" checked>
            Skip / none of these (flag it)</label>
        </div></div>`;
    }).join("");
  }

  show("#review");
}

// ---------------------------------------------------------------------------
// Step 2 -> generate
// ---------------------------------------------------------------------------
$("#generate").addEventListener("click", async () => {
  const msg = $("#review-msg");
  const resolutions = {};
  for (const r of Object.values(JOB.results)) {
    if (r.status !== "ambiguous") continue;
    const picked = document.querySelector(`input[name="res_${r.citation_id}"]:checked`);
    resolutions[r.citation_id] = picked ? (picked.value || null) : null;
  }

  $("#generate").disabled = true;
  msg.textContent = "Generating…"; msg.className = "msg";
  try {
    await fetch(`/api/jobs/${JOB.id}/resolutions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolutions }),
    });
    const res = await fetch(`/api/jobs/${JOB.id}/generate`, { method: "POST" });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const { stats } = await res.json();
    renderDone(stats);
  } catch (e) {
    msg.textContent = "Error: " + e.message; msg.className = "msg error";
  } finally {
    $("#generate").disabled = false;
  }
});

function renderDone(stats) {
  const fidelity = stats.engine === "citeproc"
    ? "" : " <em>(rendered with the built-in fallback formatter — install a CSL style for full fidelity)</em>";
  $("#done-stats").innerHTML =
    `<p>${stats.entries} reference(s) in the bibliography. ` +
    `${stats.comments_anchored} comment(s) added for flagged citations.` +
    (stats.unanchored ? ` ${stats.unanchored} issue(s) listed at the end of the document.` : "") +
    fidelity + `</p>`;
  $("#download").href = `/api/jobs/${JOB.id}/download`;
  show("#done");
  $("#done").scrollIntoView({ behavior: "smooth" });
}

// ---------------------------------------------------------------------------
function show(sel) { $(sel).classList.remove("hidden"); }
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

init();
