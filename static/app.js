/* Field Day Logger front-end.
 * One small namespace, no framework. Pages call FieldDay.initX() on load. */
const FieldDay = (() => {
  let META = null;
  const LS = window.localStorage;

  // ---- helpers ----------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const api = async (url, opts) => {
    const r = await fetch(url, opts);
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || r.statusText);
    return body;
  };
  const esc = (s) =>
    (s ?? "").toString().replace(/[&<>"]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function loadMeta() {
    if (META) return META;
    META = await api("/api/meta");
    // Populate any section datalists on the page.
    document.querySelectorAll("#section-list").forEach((dl) => {
      dl.innerHTML = META.sections.map((s) => `<option value="${s}">`).join("");
    });
    return META;
  }

  function fillBandMode(bandSel, modeSel) {
    if (bandSel)
      bandSel.innerHTML = META.bands.map((b) => `<option>${b}</option>`).join("");
    if (modeSel)
      modeSel.innerHTML = META.modes
        .map((m) => `<option value="${m.code}">${m.label}</option>`)
        .join("");
  }

  // ---- Server-Sent Events ----------------------------------------------
  const listeners = {};
  function on(ev, fn) {
    (listeners[ev] = listeners[ev] || []).push(fn);
  }
  function connectSSE() {
    const conn = $("conn");
    const es = new EventSource("/stream");
    es.onopen = () => {
      if (conn) { conn.textContent = "live"; conn.className = "conn live"; }
    };
    es.onerror = () => {
      if (conn) { conn.textContent = "reconnecting…"; conn.className = "conn down"; }
    };
    es.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      (listeners[msg.event] || []).forEach((fn) => fn(msg.data));
    };
  }

  // ---- Score strip ------------------------------------------------------
  function renderScore(s) {
    const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
    set("s-total", s.total);
    set("s-cw", s.by_mode.CW || 0);
    set("s-ph", s.by_mode.PH || 0);
    set("s-dg", s.by_mode.DG || 0);
    set("s-sect", s.sections);
    set("s-pts", s.qso_points);
    set("s-score", s.claimed_score.toLocaleString());
  }

  // ---- Log row ----------------------------------------------------------
  function logRow(c, opts = {}) {
    const tr = document.createElement("tr");
    if (c.is_dupe) tr.classList.add("dupe-row");
    if (opts.flash) tr.classList.add("flash");
    tr.dataset.id = c.id;
    tr.innerHTML =
      `<td>${esc(c.qso_time)}</td>` +
      `<td class="call">${esc(c.call)}</td>` +
      `<td>${esc(c.band)}</td>` +
      `<td class="mode-${esc(c.mode)}">${esc(c.mode)}</td>` +
      `<td>${esc(c.their_class)}</td>` +
      `<td>${esc(c.their_section)}</td>` +
      `<td>${esc(c.operator)}</td>` +
      `<td><button class="danger" data-del="${c.id}">✕</button></td>`;
    return tr;
  }

  // =======================================================================
  //  MAIN LOGGER PAGE
  // =======================================================================
  async function initLogger() {
    await loadMeta();
    connectSSE();

    const form = $("entryForm");
    const callEl = $("f-call");
    const bandEl = $("f-band");
    const modeEl = $("f-mode");
    const classEl = $("f-class");
    const sectEl = $("f-section");
    const opEl = $("f-op");
    const stationEl = $("f-station");
    const callout = $("callout");
    const body = $("logBody");

    fillBandMode(bandEl, modeEl);

    // Restore sticky per-position settings.
    const sticky = { band: "f-band", mode: "f-mode", op: "f-op", station: "f-station" };
    for (const [k, id] of Object.entries(sticky)) {
      const v = LS.getItem("fd_" + k);
      if (v) $(id).value = v;
    }
    const saveSticky = () => {
      LS.setItem("fd_band", bandEl.value);
      LS.setItem("fd_mode", modeEl.value);
      LS.setItem("fd_op", opEl.value);
      LS.setItem("fd_station", stationEl.value);
    };
    [bandEl, modeEl, opEl, stationEl].forEach((el) =>
      el.addEventListener("change", saveSticky));

    // Load score + recent contacts.
    renderScore(await api("/api/score"));
    const recent = await api("/api/contacts?limit=100");
    recent.forEach((c) => body.appendChild(logRow(c)));
    updateLiveCount();

    // Live updates.
    on("stats", renderScore);
    on("contact", (c) => {
      body.prepend(logRow(c, { flash: true }));
      updateLiveCount();
    });
    on("delete", (d) => {
      const row = body.querySelector(`tr[data-id="${d.id}"]`);
      if (row) row.remove();
      updateLiveCount();
    });

    function updateLiveCount() {
      const lc = $("livecount");
      if (lc) lc.textContent = body.children.length + " shown";
    }

    // Delete from the live log.
    body.addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del]");
      if (!del) return;
      if (confirm("Delete this contact?")) {
        try { await api("/api/contacts/" + del.dataset.del, { method: "DELETE" }); }
        catch (err) { setCallout("dupe", "✕ " + esc(err.message)); }
      }
    });

    // ---- Dupe / history check as you type --------------------------------
    let checkTimer = null;
    const doCheck = async () => {
      const call = callEl.value.trim().toUpperCase();
      if (!call) { setCallout("info", "Enter a callsign to begin. Time is stamped automatically in UTC."); callEl.className = "call-input"; return; }
      try {
        const r = await api(
          `/api/check?call=${encodeURIComponent(call)}&band=${encodeURIComponent(bandEl.value)}&mode=${encodeURIComponent(modeEl.value)}`
        );
        if (r.dupe) {
          setCallout("dupe", `⚠ DUPE — ${call} already worked on ${bandEl.value} ${modeEl.value}.`);
          callEl.className = "call-input bad";
        } else {
          callEl.className = "call-input good";
          let msg = `${call} — new on ${bandEl.value} ${modeEl.value}.`;
          if (r.worked.length) {
            const chips = r.worked.map((w) => `<span class="bandchip">${w.band} ${w.mode}</span>`).join("");
            msg += ` Worked before: ${chips}`;
          }
          setCallout("ok", msg);
          // Prefill last-known exchange if fields are empty.
          if (r.last_exchange) {
            if (!classEl.value) classEl.value = r.last_exchange.class;
            if (!sectEl.value) sectEl.value = r.last_exchange.section;
          }
        }
      } catch (e) { /* ignore transient */ }
    };
    function setCallout(kind, html) {
      callout.className = "callout " + kind;
      callout.innerHTML = html;
    }
    callEl.addEventListener("input", () => {
      clearTimeout(checkTimer);
      checkTimer = setTimeout(doCheck, 150);
    });
    bandEl.addEventListener("change", doCheck);
    modeEl.addEventListener("change", doCheck);

    // ---- Submit ----------------------------------------------------------
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        call: callEl.value,
        band: bandEl.value,
        mode: modeEl.value,
        their_class: classEl.value,
        their_section: sectEl.value,
        rst_sent: $("f-rsts").value,
        rst_rcvd: $("f-rstr").value,
        freq: $("f-freq").value,
        operator: opEl.value,
        station: stationEl.value,
        notes: $("f-notes").value,
      };
      try {
        const saved = await api("/api/contacts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        // Reset for next QSO; keep band/mode/op/station sticky.
        callEl.value = ""; classEl.value = ""; sectEl.value = "";
        $("f-rsts").value = ""; $("f-rstr").value = ""; $("f-freq").value = ""; $("f-notes").value = "";
        callEl.className = "call-input";
        setCallout("ok", `✓ Logged ${esc(saved.call)} — ${esc(saved.band)} ${esc(saved.mode)} at ${esc(saved.qso_time)}Z`);
        callEl.focus();
      } catch (err) {
        setCallout("dupe", "✕ " + esc(err.message));
      }
    });

    callEl.focus();
  }

  // =======================================================================
  //  FULL LOG PAGE
  // =======================================================================
  async function initFullLog() {
    await loadMeta();
    connectSSE();
    const body = $("fullBody");
    const search = $("search");
    const countEl = $("count");

    fillBandMode($("e-band"), $("e-mode"));

    async function reload() {
      const q = search.value.trim();
      const rows = await api("/api/contacts" + (q ? `?search=${encodeURIComponent(q)}` : ""));
      body.innerHTML = "";
      rows.forEach((c, i) => body.appendChild(fullRow(c, rows.length - i)));
      countEl.textContent = rows.length + " contacts";
    }

    function fullRow(c, num) {
      const tr = document.createElement("tr");
      tr.dataset.id = c.id;
      tr.innerHTML =
        `<td>${num}</td>` +
        `<td>${esc(c.qso_date)}</td>` +
        `<td>${esc(c.qso_time)}</td>` +
        `<td class="call">${esc(c.call)}</td>` +
        `<td>${esc(c.band)}</td>` +
        `<td class="mode-${esc(c.mode)}">${esc(c.mode)}</td>` +
        `<td>${esc(c.their_class)}</td>` +
        `<td>${esc(c.their_section)}</td>` +
        `<td>${esc(c.rst_sent)}/${esc(c.rst_rcvd)}</td>` +
        `<td>${esc(c.operator)}</td>` +
        `<td>${esc(c.station)}</td>` +
        `<td><button class="secondary" data-edit="${c.id}" style="padding:.2rem .5rem;font-size:.78rem">edit</button> ` +
        `<button class="danger" data-del="${c.id}">✕</button></td>`;
      return tr;
    }

    search.addEventListener("input", () => { clearTimeout(search._t); search._t = setTimeout(reload, 200); });
    on("contact", reload);
    on("delete", reload);
    on("update", reload);

    // Edit / delete via event delegation.
    const dlg = $("editDlg");
    body.addEventListener("click", async (e) => {
      const del = e.target.closest("[data-del]");
      if (del) {
        if (confirm("Delete this contact?")) {
          await api("/api/contacts/" + del.dataset.del, { method: "DELETE" });
          reload();
        }
        return;
      }
      const edit = e.target.closest("[data-edit]");
      if (edit) {
        const rows = await api("/api/contacts");
        const c = rows.find((x) => x.id == edit.dataset.edit);
        if (c) openEdit(c, dlg);
      }
    });

    $("e-cancel").addEventListener("click", () => dlg.close());
    $("editForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        call: $("e-call").value, qso_date: $("e-date").value, qso_time: $("e-time").value,
        band: $("e-band").value, mode: $("e-mode").value,
        their_class: $("e-class").value, their_section: $("e-section").value,
        rst_sent: $("e-rsts").value, rst_rcvd: $("e-rstr").value, operator: $("e-op").value,
      };
      try {
        await api("/api/contacts/" + $("e-id").value, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        dlg.close();
        reload();
      } catch (err) {
        const ee = $("e-err");
        ee.className = "callout dupe";
        ee.textContent = err.message;
      }
    });

    reload();
  }

  function openEdit(c, dlg) {
    $("e-id").value = c.id;
    $("e-call").value = c.call; $("e-date").value = c.qso_date; $("e-time").value = c.qso_time;
    $("e-band").value = c.band; $("e-mode").value = c.mode;
    $("e-class").value = c.their_class; $("e-section").value = c.their_section;
    $("e-rsts").value = c.rst_sent; $("e-rstr").value = c.rst_rcvd; $("e-op").value = c.operator;
    $("e-err").className = "callout info hidden";
    dlg.showModal();
  }

  // =======================================================================
  //  SETUP PAGE
  // =======================================================================
  async function initSetup() {
    await loadMeta();
    connectSSE();
    const form = $("setupForm");
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const data = Object.fromEntries(new FormData(form).entries());
      await api("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const msg = $("savedMsg");
      msg.classList.add("show");
      setTimeout(() => msg.classList.remove("show"), 1800);
    });
  }

  return { initLogger, initFullLog, initSetup };
})();
