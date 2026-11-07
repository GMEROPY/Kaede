const $ = (id) => document.getElementById(id);
const screens = ["home", "loading", "result"];
const show = (n) => screens.forEach((s) => $(s).classList.toggle("active", s === n));
const NS = "http://www.w3.org/2000/svg";

// ---- dekorasi: ranting maple & daun jatuh ----
function leaves(svg, n, w, h, flip) {
  for (let i = 0; i < n; i++) {
    const t = Math.random(), s = 40 + Math.random() * 55;
    const x = (flip ? 0.1 : 0) * w + t * w * 0.85 * Math.random() + Math.random() * 50;
    const y = Math.random() * h * (1 - t * 0.7);
    const u = document.createElementNS(NS, "use");
    u.setAttribute("href", "#leaf");
    u.setAttribute("x", x); u.setAttribute("y", y);
    u.setAttribute("width", s); u.setAttribute("height", s);
    u.setAttribute("transform", `rotate(${Math.random() * 360} ${x + s / 2} ${y + s / 2})`);
    u.style.opacity = 0.75 + Math.random() * 0.25;
    svg.appendChild(u);
  }
}
leaves($("branch"), 70, 400, 300);
leaves($("branchR"), 30, 300, 220, true);
for (let i = 0; i < 14; i++) {
  const el = document.createElement("i");
  el.innerHTML = '<svg viewBox="0 0 100 100"><use href="#leaf"/></svg>';
  el.style.left = Math.random() * 100 + "%";
  el.style.setProperty("--s", 12 + Math.random() * 16 + "px");
  el.style.setProperty("--dx", Math.random() * 120 - 60 + "px");
  el.style.animationDuration = 12 + Math.random() * 14 + "s";
  el.style.animationDelay = -Math.random() * 20 + "s";
  $("falling").appendChild(el);
}

// ---- alur utama ----
let timer;
$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = $("url").value.trim();
  $("error").textContent = "";
  $("urlShown").textContent = url;
  show("loading");
  const msgs = ["Mengambil konten...", "Menganalisis media...", "Menyiapkan hasil..."];
  let k = 0;
  $("status").textContent = msgs[0];
  timer = setInterval(() => ($("status").textContent = msgs[++k % msgs.length]), 2200);
  try {
    const r = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || "Terjadi kesalahan");
    render(data, url);
  } catch (err) {
    show("home");
    $("error").textContent = err.message;
  } finally {
    clearInterval(timer);
  }
});

let items = [], idx = 0;
function render(d, url) {
  items = d.items; idx = 0;
  $("urlShown2").textContent = url;
  $("title").textContent = d.title;
  $("note").textContent = d.note || "";
  const pdf = $("pdf");
  pdf.style.display = d.pdf ? "flex" : "none";
  if (d.pdf) { pdf.href = d.pdf; $("pages").textContent = items.length + " Halaman"; }
  $("list").innerHTML = items
    .map((it, i) => `<li><a href="${it.dl}" download><span>Unduh ${i + 1}</span><b>${it.kind === "video" ? "VIDEO" : "FOTO"}</b></a></li>`)
    .join("");
  const multi = items.length > 1;
  ["prev", "next", "count"].forEach((id) => ($(id).style.display = multi ? "" : "none"));
  slide(0, 0);
  show("result");
}

function slide(i, dir = 0) {
  idx = (i + items.length) % items.length;
  const it = items[idx];
  $("stage").querySelector("img,video")?.remove();
  const m = document.createElement(it.kind === "video" ? "video" : "img");
  m.src = it.src;
  m.style.setProperty("--from", dir * 40 + "px");
  if (it.kind === "video") { m.controls = true; m.playsInline = true; m.preload = "metadata"; }
  $("stage").prepend(m);
  $("count").textContent = `${idx + 1}/${items.length}`;
}
$("prev").onclick = () => slide(idx - 1, -1);
$("next").onclick = () => slide(idx + 1, 1);
let sx = null;  // geser jari untuk ganti foto
$("stage").addEventListener("touchstart", (e) => (sx = e.touches[0].clientX), { passive: true });
$("stage").addEventListener("touchend", (e) => {
  if (sx === null || items.length < 2) return;
  const d = e.changedTouches[0].clientX - sx;
  if (Math.abs(d) > 50) slide(idx + (d < 0 ? 1 : -1), d < 0 ? 1 : -1);
  sx = null;
});
$("reset").onclick = () => {
  $("stage").querySelector("video")?.pause();
  $("url").value = "";
  show("home");
};

// efek riak pada tombol
document.querySelector(".go").addEventListener("pointerdown", (e) => {
  const b = e.currentTarget, r = b.getBoundingClientRect();
  const s = document.createElement("span");
  s.className = "ripple";
  s.style.left = e.clientX - r.left + "px";
  s.style.top = e.clientY - r.top + "px";
  b.appendChild(s);
  setTimeout(() => s.remove(), 700);
});

// parallax halus (mouse / kemiringan HP), berhenti sendiri saat diam
if (!matchMedia("(prefers-reduced-motion:reduce)").matches) {
  const sc = document.querySelector(".scene");
  let tx = 0, ty = 0, cx = 0, cy = 0, run = false;
  const tick = () => {
    cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
    sc.style.setProperty("--px", cx.toFixed(3));
    sc.style.setProperty("--py", cy.toFixed(3));
    if (Math.abs(tx - cx) > 0.002 || Math.abs(ty - cy) > 0.002) requestAnimationFrame(tick);
    else run = false;
  };
  const set = (x, y) => { tx = x; ty = y; if (!run) { run = true; requestAnimationFrame(tick); } };
  const clamp = (v) => Math.max(-1, Math.min(1, v));
  addEventListener("pointermove", (e) => set((e.clientX / innerWidth - 0.5) * 2, (e.clientY / innerHeight - 0.5) * 2));
  addEventListener("deviceorientation", (e) => {
    if (e.gamma == null) return;
    set(clamp(e.gamma / 25), clamp(((e.beta || 0) - 45) / 25));
  });
}
