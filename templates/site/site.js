// The search box: search.js (titles, aliases, events) loads on first focus.
(() => {
  const q = document.getElementById("q");
  const hits = document.getElementById("hits");
  let entries = null;
  let active = -1;

  const norm = s => s.toLowerCase().replace(/ё/g, "е");
  const esc = s => s.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

  function load() {
    if (entries || document.getElementById("search-data")) return;
    const s = document.createElement("script");
    s.id = "search-data";
    s.src = ROOT + "search.js";
    s.onload = () => {
      entries = window.SEARCH.map(e => ({ ...e, nt: norm(e.t), na: norm(e.a || "") }));
      render();
    };
    document.head.appendChild(s);
  }

  function score(e, words) {
    let total = 0;
    for (const w of words) {
      if (e.nt.startsWith(w)) total += 4;
      else if (e.nt.includes(" " + w)) total += 3;
      else if (e.nt.includes(w)) total += 2;
      else if (e.na.includes(w)) total += 1;
      else return 0;
    }
    // Notes before events, when the words match equally.
    return total + (e.k.startsWith("событие") ? 0 : 0.5);
  }

  function render() {
    const words = norm(q.value).split(/\s+/).filter(Boolean);
    active = -1;
    if (!words.length) { hits.hidden = true; return; }
    if (!entries) { hits.innerHTML = '<li class="empty">Загрузка…</li>'; hits.hidden = false; return; }
    const found = entries.map(e => [score(e, words), e]).filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0] || a[1].t.length - b[1].t.length).slice(0, 25);
    hits.innerHTML = found.length
      ? found.map(([, e]) => `<li><a href="${ROOT + e.u}">${esc(e.t)}<small>${esc(e.k)}</small></a></li>`).join("")
      : '<li class="empty">Ничего не найдено</li>';
    hits.hidden = false;
  }

  function move(step) {
    const links = hits.querySelectorAll("a");
    if (!links.length) return;
    links[active]?.classList.remove("active");
    active = (active + step + links.length) % links.length;
    links[active].classList.add("active");
    links[active].scrollIntoView({ block: "nearest" });
  }

  q.addEventListener("focus", load);
  q.addEventListener("input", render);
  q.addEventListener("keydown", ev => {
    if (ev.key === "ArrowDown") { ev.preventDefault(); move(1); }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); move(-1); }
    else if (ev.key === "Enter") {
      const link = hits.querySelectorAll("a")[Math.max(active, 0)];
      if (link) location.href = link.href;
    } else if (ev.key === "Escape") { hits.hidden = true; q.blur(); }
  });
  document.addEventListener("click", ev => {
    if (!ev.target.closest(".search")) hits.hidden = true;
  });
  document.addEventListener("keydown", ev => {
    if (ev.key === "/" && document.activeElement !== q) { ev.preventDefault(); q.focus(); }
  });
})();
