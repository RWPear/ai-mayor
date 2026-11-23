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

  const control = (body) => api("/live/control", body).then(() => setTimeout(() => poll(true), 300));
  $("lpause").addEventListener("click", () => control({ action: state && state.paused ? "play" : "pause" }));
  $("lspeed").addEventListener("change", (e) => control({ action: "speed", speed: e.target.value }));
  $("lstep").addEventListener("click", () => control({ action: "step" }));
  $("lclose").addEventListener("click", () => { $("lclose").disabled = true; control({ action: "close" }).finally(() => setTimeout(() => { $("lclose").disabled = false; }, 2500)); });
  $("larrive").addEventListener("click", () => control({ action: "arrive" }));
  document.querySelectorAll("#ltabs button").forEach((b) => b.addEventListener("click", () => { tab = b.dataset.tab; render(); }));

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
    $("larrive").hidden = !state.frontier;
    $("lpending").textContent = state.pending ? `(${state.pending})` : "";
  }

  function render() {
    const mine = $("lmine").checked ? me() : "";
    document.querySelectorAll("#ltabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tab === tab)));
    $("lreplies").hidden = tab !== "replies"; $("llog").hidden = tab !== "log";
    if (tab === "replies") {
      const list = replies.filter((r) => !mine || r.to === mine).slice().reverse();
      const order = { pending: 0, approved: 1, rejected: 2 };
      list.sort((a, b) => order[a.status] - order[b.status]);
      $("lreplies").innerHTML = list.length ? list.map((r) => `
        <article class="reply ${r.status}" data-id="${r.id}">
          <header><strong>@${esc(r.to)}</strong> <span class="muted">${esc(r.kind)} · ${esc((r.time || "").split(", ")[1] || "")}</span>
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
      const list = log.filter((m) => !mine || m.who === "@" + mine || (m.text || "").includes("@" + mine)).slice(-250);
      const el = $("llog"), atEnd = el.scrollTop + el.clientHeight >= el.scrollHeight - 30;
      el.innerHTML = list.map((m) => `<div class="lm ${m.comment ? "comment" : ""} ${m.who === "post" ? "post" : ""} ${m.public ? "" : "secret"} d${m.drama}">
        <span class="t">${esc((m.time || "").split(", ")[1] || "")}</span>${m.comment ? `<strong>${esc(m.who)}:</strong> ` : m.public ? "" : "<em>(secret)</em> "}${esc(m.text)}</div>`).join("");
      if (atEnd) el.scrollTop = el.scrollHeight;
    }
  }

  poll(true);
  setInterval(() => poll(false), 1500);
  return { get state() { return state; } };
}
