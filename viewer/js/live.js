// The live panel (./kingdom play): comment as any follower, approve the kingdom's replies, run the clock.
// It talks to the server (city/play.py) and tells main.js when there's a new scene or a new clock.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } } };

const EXAMPLES = ["I chop wood all morning", "I want to start a vegetable garden behind my house", "I become a thief",
  "I steal bread from the stores", "I send Aldric an axe", "I challenge @someone to a duel", "WORK", "STATUS",
  "I sing for the settlers by the fire", "I ask the king to build a bridge"];

export async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export function startLive({ onScene, onState }) {
  const panel = $("live");
  panel.hidden = false;
  document.body.classList.add("live");
  let version = -1, logN = 0, state = null, replies = [], log = [], tab = "replies", busy = false;
  const me = () => $("lhandle").value.trim().replace(/^@/, "").toLowerCase();
  $("lhandle").value = store.get("kingdom.handle", "");
  $("ltext").placeholder = EXAMPLES.slice(0, 3).join(" · ");
  $("lexamples").innerHTML = EXAMPLES.map((t) => `<button type="button" class="ex">${esc(t)}</button>`).join("");
  document.querySelectorAll("#lexamples .ex").forEach((b) => b.addEventListener("click", () => { $("ltext").value = b.textContent; $("ltext").focus(); }));

  $("lform").addEventListener("submit", async (e) => {
    e.preventDefault();
    const handle = me(), text = $("ltext").value.trim();
    if (!handle) { $("lsent").textContent = "Pick a handle first."; $("lhandle").focus(); return; }
    if (!text) return;
    store.set("kingdom.handle", handle);
    $("lsent").textContent = "Sending...";
    try {
      const r = await api("/live/comment", { handle, text });
      $("lsent").textContent = r.ok ? `Sent as @${handle}. It plays out within the game hour.` : r.why;
      if (r.ok) $("ltext").value = "";
      poll(true);
    } catch (err) { $("lsent").textContent = `Couldn't send: ${err.message}`; }
  });
  $("ltext").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("lform").requestSubmit(); } });
  $("lhandle").addEventListener("change", () => { store.set("kingdom.handle", me()); render(); });
  $("lmine").addEventListener("change", render);
  $("llittle").addEventListener("change", render);

  const control = (body) => api("/live/control", body).then(() => setTimeout(() => poll(true), 300));
  $("lpause").addEventListener("click", () => control({ action: state && state.paused ? "play" : "pause" }));
  $("lspeed").addEventListener("change", (e) => control({ action: "speed", speed: e.target.value }));
  $("lstep").addEventListener("click", () => control({ action: "step" }));
  $("lclose").addEventListener("click", () => { $("lclose").disabled = true; control({ action: "close" }).finally(() => setTimeout(() => { $("lclose").disabled = false; }, 2500)); });
  document.querySelectorAll("#ltabs button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.tab; render(); if (tab === "mind") pollMind(); }));

  async function poll(force) {
    if (busy) return;
    busy = true;
    try {
      state = await api("/live/state");
      onState(state);
      showState();
      if (state.version !== version || force) {
        const [scene, feed] = await Promise.all([api("/live/scene"), api(`/live/feed?since=${logN}`)]);
        version = state.version;
        if (scene) onScene(scene);
        log = log.concat(feed.log.filter((m) => m.n >= logN));
        logN = log.length ? log[log.length - 1].n + 1 : logN;
        log = log.slice(-600);
        replies = feed.replies;
        $("lhandles").innerHTML = feed.handles.map((h) => `<option value="${esc(h)}">`).join("");
        render();
      }
      $("lerror").hidden = !state.error;
      $("lerror").textContent = state.error || "";
    } catch (err) {
      $("lerror").hidden = false;
      $("lerror").textContent = `The kingdom isn't answering (${err.message}). Is ./kingdom play still running?`;
    } finally { busy = false; }
  }

  function showState() {
    $("lclock").textContent = `${state.time[0].toUpperCase()}${state.time.slice(1)} · post ${state.day} closes ${state.post_closes.split(", ")[1]}`;
    $("lstatus").textContent = state.status;
    $("lwords").innerHTML = state.words.length ? "Today's words: " + state.words.map((w) => `<span class="chip">${esc(w)}</span>`).join(" ") : "";
    $("lpause").textContent = state.paused ? "Play" : "Pause";
    $("lpause").setAttribute("aria-pressed", String(state.paused));
    $("lstep").disabled = !state.paused;
    const sp = Object.entries(state.speeds).find(([, v]) => v === state.tick_s);
    if (sp && $("lspeed").value !== sp[0]) $("lspeed").value = sp[0];
    $("lpending").textContent = state.pending ? `(${state.pending})` : "";
    const m = state.model || {};
    $("lmodel").hidden = !!m.off;
    $("lmodel").classList.toggle("ok", !!m.ok);
    $("lmodel").textContent = m.off ? "" : m.ok ? `Thinking with ${m.model}` : `⚠ ${m.error} Aldric is running on rules until it answers.`;
  }

  function render() {
    const mine = $("lmine").checked ? me() : "";
    document.querySelectorAll("#ltabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tab === tab)));
    $("lreplies").hidden = tab !== "replies"; $("llog").hidden = tab !== "log"; $("lmind").hidden = tab !== "mind";
    if (tab === "mind") { renderMind(); return; }
    if (tab === "replies") {
      const list = replies.filter((r) => !mine || r.to === mine).slice().reverse();
      const order = { pending: 0, approved: 1, rejected: 2 };
      list.sort((a, b) => order[a.status] - order[b.status]);
      $("lreplies").innerHTML = list.length ? list.map((r) => `
        <article class="reply ${r.status}" data-id="${r.id}">
          <header><strong>@${esc(r.to)}</strong> <span class="muted">${esc(r.kinds ? (r.kind.startsWith("later") ? "later: " : "") + r.kinds.join(" + ") : r.kind)} · ${esc((r.time || "").split(", ")[1] || "")}${r.by ? ` · <span title="Who understood the comment and who wrote this reply" style="${/rules/.test(r.by) ? "color:var(--danger)" : ""}">${esc(r.by)}</span>` : ""}</span>
            <span class="badge">${r.status}${r.edited ? ", edited" : ""}</span></header>
          <p>${esc(r.text)}</p>
          ${r.status === "pending" ? `<div class="row"><button type="button" data-act="approved">Approve</button><button type="button" data-act="rejected">Reject</button><button type="button" data-act="edit">Edit</button></div>` : `<div class="row"><button type="button" data-act="pending">Undo</button></div>`}
        </article>`).join("") : `<p class="muted">No replies yet. Comment as someone and the kingdom answers here; nothing is posted until you approve it (and in this test, nothing is posted at all).</p>`;
      document.querySelectorAll("#lreplies .reply button").forEach((b) => b.addEventListener("click", async () => {
        const card = b.closest(".reply"), id = card.dataset.id, act = b.dataset.act;
        if (act === "edit") {
          const p = card.querySelector("p"), r = replies.find((x) => x.id === id);
          p.outerHTML = `<textarea rows="4">${esc(r.text)}</textarea>`;
          b.textContent = "Save"; b.dataset.act = "save";
          return;
        }
        const body = act === "save" ? { id, status: "approved", text: card.querySelector("textarea").value } : { id, status: act };
        const res = await api("/live/reply", body);
        if (res.ok) { const i = replies.findIndex((x) => x.id === id); replies[i] = res.reply; render(); }
      }));
    } else {
      const little = $("llittle") ? $("llittle").checked : true;
      const list = log.filter((m) => (little || !m.small) && (!mine || m.who === "@" + mine || (m.text || "").includes("@" + mine))).slice(-300);
      const el = $("llog"), atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
      el.innerHTML = list.map((m) => `<div class="lm ${m.small ? "small" : ""} ${m.comment ? "comment" : ""} ${m.who === "post" ? "post" : ""} ${m.public ? "" : "secret"} d${m.drama}">
        <span class="t">${esc((m.time || "").split(", ")[1] || "")}</span>${m.comment ? `<strong>${esc(m.who)}:</strong> ` : m.public ? "" : "<em>(secret)</em> "}${esc(m.text)}</div>`).join("");
      if (atEnd) el.scrollTop = el.scrollHeight;
    }
  }

  // ---------------------------------------------------------------- inside his head
  let mind = null, mindBusy = false;
  async function pollMind() {
    if (tab !== "mind" || mindBusy) return;
    mindBusy = true;
    try { mind = await api("/live/mind"); renderMind(); } catch (e) { /* next time */ } finally { mindBusy = false; }
  }
  const openState = new Set();
  function renderMind() {
    const el = $("lmind");
    if (!mind) { el.innerHTML = `<p class="muted">Reading his mind...</p>`; pollMind(); return; }
    el.querySelectorAll("details[data-k]").forEach((d) => { const want = d.dataset.k[0] === "u" ? d.open : !d.open; if (want) openState.add(d.dataset.k); else openState.delete(d.dataset.k); });
    const k = mind.king, top = el.scrollTop;
    const decs = mind.decisions.filter((d) => d.who === "king").slice().reverse();
    const calls = mind.calls.slice().reverse();
    el.innerHTML = `
      <div class="mcard">
        <div><strong>${esc(k.name)}</strong> <span class="k">· ${esc(k.brain === "model" ? "thinking with the model" : k.brain === "rules" ? "running on rules (started without --king llm)" : "the model isn't answering - running on rules")} · at ${esc(k.location || "")}</span></div>
        ${k.character ? `<div><span class="k">Who he was before:</span> ${esc(k.character)}</div>` : ""}
        <div><span class="k">Goal:</span> ${esc(k.goal || "")}${k.goals.length ? ` · <span class="k">his own:</span> ${esc(k.goals.join("; "))}` : ""}</div>
        ${k.who ? `<div><span class="k">Who he's becoming:</span> ${esc(k.who)}</div>` : ""}
        ${k.thought ? `<div><span class="k">Last thought:</span> <em>${esc(k.thought)}</em></div>` : ""}
        <div class="k">Choices so far: <strong>${mind.tally.model}</strong> by the model, <strong style="${mind.tally.rules ? "color:var(--danger)" : ""}">${mind.tally.rules}</strong> by rules${mind.tally.rules ? ` (${esc(mind.tally.why)})` : ""} · model calls that failed: ${mind.tally.failed}</div>
        <div class="k">Needs: ${Object.entries(k.needs).map(([a, b]) => `${esc(a)} ${Math.round(b * 100)}%`).join(" · ")}</div>
      </div>
      <h3>What he chose</h3>
      ${decs.length ? decs.slice(0, 40).map((d) => `<div class="dec ${d.brain === "model" ? "model" : ""}"><span class="t muted">${esc((d.time || "").split(", ")[1] || "")}</span>
        <span class="b">${esc(d.brain)}</span><strong>${esc(d.tool)}</strong>(${esc(Object.entries(d.args).map(([a, b]) => `${a}: ${b}`).join(", "))})
        ${d.thought ? `<div class="th">"${esc(d.thought)}"</div>` : ""}</div>`).join("") : `<p class="muted">Nothing yet.</p>`}
      <h3>What the model was asked, and what it said</h3>
      ${calls.length ? calls.map((c) => `<div class="call ${c.error ? "err" : ""}">
        <div><strong>${esc(c.who)}</strong> <span class="muted">· ${esc((c.time || "").split(", ")[1] || "")} · ${c.ms} ms · ${esc(c.model)} · temp ${c.temperature}</span></div>
        <details data-k="u${c.n}" ${openState.has(`u${c.n}`) ? "open" : ""}><summary>What it was told (${(c.system.length + c.user.length).toLocaleString()} characters)</summary><pre>${esc(c.system)}</pre><pre>${esc(c.user)}</pre></details>
        <details data-k="r${c.n}" ${openState.has(`r${c.n}`) ? "" : "open"}><summary>What it said</summary>${c.error ? `<pre style="color:var(--danger)">${esc(c.error)}</pre>` : ""}${c.response ? `<pre>${esc(c.response)}</pre>` : ""}</details>
      </div>`).join("") : `<p class="muted">No calls to the model yet. ${k.brain === "rules" ? "Start it with --king llm to see them." : ""}</p>`}`;
    el.scrollTop = top;
  }

  poll(true);
  setInterval(() => poll(false), 1500);
  setInterval(pollMind, 4000);
  return { get state() { return state; } };
}
