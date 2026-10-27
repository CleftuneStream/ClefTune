/* ClefTune site · vanilla JS. Every animation loop pauses when off-screen or hidden. */
(() => {
  "use strict";

  document.documentElement.classList.remove("no-js");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const lerp = (a, b, t) => a + (b - a) * t;

  const REPO = "ettisafxrup/ClefTune";

  /* ---------- toast ---------- */
  const toastEl = $(".toast");
  let toastTimer;
  const toast = (msg) => {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
  };

  const copyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fallback for non-secure contexts
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch { /* ignore */ }
      ta.remove();
      return ok;
    }
  };

  /* ---------- split hero title into letters ---------- */
  let i = 0;
  $$(".title .split").forEach((word) => {
    const text = word.textContent;
    word.textContent = "";
    for (const ch of text) {
      const s = document.createElement("span");
      s.className = "char";
      s.style.setProperty("--i", i++);
      s.textContent = ch;
      word.appendChild(s);
    }
  });

  /* ---------- reveal on scroll ---------- */
  const revealObs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      e.target.classList.add("in");
      revealObs.unobserve(e.target);
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  $$(".reveal").forEach((el) => revealObs.observe(el));

  /* ---------- clef cursor ---------- */
  // Switched on by the first real mouse movement rather than a media query, so it also
  // works on touchscreen laptops and stays off on phones and tablets.
  {
    const cursor = $(".cursor");
    const ring = $(".cursor-ring");
    let mx = 0, my = 0, rx = 0, ry = 0, cx = 0, cy = 0;
    let running = false, on = false;

    const place = () => {
      cursor.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
    };
    const tick = () => {
      // reduced motion: follow the pointer exactly, no trailing
      const k1 = reduced ? 1 : 0.55, k2 = reduced ? 1 : 0.16;
      cx = lerp(cx, mx, k1); cy = lerp(cy, my, k1);
      rx = lerp(rx, mx, k2); ry = lerp(ry, my, k2);
      place();
      // stop the loop once everything has settled
      if (Math.abs(rx - mx) + Math.abs(ry - my) + Math.abs(cx - mx) + Math.abs(cy - my) > 0.3) {
        requestAnimationFrame(tick);
      } else running = false;
    };
    const wake = () => { if (!running) { running = true; requestAnimationFrame(tick); } };
    const show = (v) => { cursor.classList.toggle("hidden", !v); ring.classList.toggle("hidden", !v); };

    addEventListener("pointermove", (e) => {
      if (e.pointerType !== "mouse") {
        // a touch or pen took over: give the system cursor back
        if (on) { on = false; document.body.classList.remove("has-cursor"); }
        return;
      }
      mx = e.clientX; my = e.clientY;
      if (!on) {
        on = true;
        document.body.classList.add("has-cursor");
        cx = rx = mx; cy = ry = my;
        place();
      }
      show(true);
      wake();
    }, { passive: true });

    const interactive = "a, button, summary, .card, .key, .chip, .line, .track";
    document.addEventListener("pointerover", (e) => {
      const hit = !!e.target.closest(interactive);
      cursor.classList.toggle("hover", hit);
      ring.classList.toggle("hover", hit);
    });
    addEventListener("pointerdown", (e) => { if (e.pointerType === "mouse") cursor.classList.add("down"); });
    addEventListener("pointerup", () => cursor.classList.remove("down"));
    // leaving the window: relatedTarget is null when the pointer exits the document
    document.addEventListener("mouseout", (e) => { if (!e.relatedTarget) show(false); });
    addEventListener("blur", () => show(false));
  }

  /* ---------- click feedback: a burst of notes + ripples inside buttons ---------- */
  if (!reduced) {
    const glyphs = ["♪", "♫", "♩", "♬"];
    let live = 0;
    const burst = (x, y) => {
      if (live > 5) return; // cap DOM work during rapid clicking
      live++;
      const el = document.createElement("div");
      el.className = "burst";
      el.style.left = `${x}px`;
      el.style.top = `${y}px`;
      let html = '<i class="burst-ring"></i>';
      const n = 4, base = Math.random() * Math.PI * 2;
      for (let k = 0; k < n; k++) {
        const a = base + (k / n) * Math.PI * 2 + (Math.random() - 0.5) * 0.6;
        const d = 26 + Math.random() * 18;
        html += `<span class="burst-note" style="--dx:${(Math.cos(a) * d).toFixed(1)}px;--dy:${(Math.sin(a) * d - 10).toFixed(1)}px;--r:${((Math.random() - 0.5) * 60) | 0}deg">${glyphs[(Math.random() * glyphs.length) | 0]}</span>`;
      }
      el.innerHTML = html;
      document.body.appendChild(el);
      setTimeout(() => { el.remove(); live--; }, 700);
    };

    const rippleHosts = ".btn, .dl-link, .copy, .menu-btn, .to-top, .controls .play, .faq summary, .key, .tags a";
    addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      burst(e.clientX, e.clientY);
      const host = e.target.closest(rippleHosts);
      if (!host) return;
      const r = host.getBoundingClientRect();
      const size = Math.max(r.width, r.height) * 2;
      const rip = document.createElement("span");
      rip.className = "ripple";
      rip.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
      host.appendChild(rip);
      setTimeout(() => rip.remove(), 600);
    }, { passive: true });
  }

  /* ---------- magnetic buttons ---------- */
  if (finePointer && !reduced) {
    $$(".magnetic").forEach((el) => {
      el.addEventListener("pointermove", (e) => {
        const r = el.getBoundingClientRect();
        const x = (e.clientX - r.left - r.width / 2) * 0.22;
        const y = (e.clientY - r.top - r.height / 2) * 0.3;
        el.style.transform = `translate(${x}px, ${y}px)`;
      });
      el.addEventListener("pointerleave", () => { el.style.transform = ""; });
    });
  }

  /* ---------- card spotlight + tilt ---------- */
  if (finePointer) {
    $$(".card").forEach((card) => {
      card.addEventListener("pointermove", (e) => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;
        const py = (e.clientY - r.top) / r.height;
        card.style.setProperty("--mx", `${px * 100}%`);
        card.style.setProperty("--my", `${py * 100}%`);
        if (!reduced) card.style.transform = `perspective(900px) rotateX(${(0.5 - py) * 6}deg) rotateY(${(px - 0.5) * 8}deg)`;
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
  }

  /* ---------- mobile menu ---------- */
  const nav = $(".nav");
  const menuBtn = $(".menu-btn");
  const setMenu = (open) => {
    nav.classList.toggle("open", open);
    menuBtn.setAttribute("aria-expanded", String(open));
    menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  };
  menuBtn.addEventListener("click", () => setMenu(!nav.classList.contains("open")));
  $$(".nav-links a").forEach((a) => a.addEventListener("click", () => setMenu(false)));
  document.addEventListener("click", (e) => { if (nav.classList.contains("open") && !nav.contains(e.target)) setMenu(false); });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && nav.classList.contains("open")) { setMenu(false); menuBtn.focus(); } });

  /* ---------- scroll: progress bar, auto-hiding nav, back-to-top (one rAF per burst) ---------- */
  const bar = $(".progress");
  const toTop = $(".to-top");
  let lastY = scrollY, scrollQueued = false;
  addEventListener("scroll", () => {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      const max = document.documentElement.scrollHeight - innerHeight;
      bar.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
      if (!nav.classList.contains("open")) nav.classList.toggle("away", y > lastY + 2 && y > 400);
      if (y < lastY - 2) nav.classList.remove("away");
      toTop.classList.toggle("show", y > 1200);
      lastY = y;
      scrollQueued = false;
    });
  }, { passive: true });
  toTop.addEventListener("click", () => scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" }));

  /* ---------- active section in nav ---------- */
  const navMap = new Map($$('.nav-links a[href^="#"]').map((a) => [a.getAttribute("href").slice(1), a]));
  const sectionObs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      navMap.forEach((a, id) => a.classList.toggle("active", id === e.target.id));
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  navMap.forEach((_, id) => { const s = document.getElementById(id); if (s) sectionObs.observe(s); });

  /* ---------- count-up stats ---------- */
  const countObs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      countObs.unobserve(e.target);
      const el = e.target;
      const to = parseFloat(el.dataset.to);
      const dec = +(el.dataset.dec || 0);
      if (reduced || to === 0) { el.textContent = to.toFixed(dec); continue; }
      const t0 = performance.now(), dur = 1400;
      const step = (now) => {
        const p = Math.min(1, (now - t0) / dur);
        el.textContent = (to * (1 - Math.pow(1 - p, 3))).toFixed(dec);
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
  }, { threshold: 0.6 });
  if (!reduced) $$(".count").forEach((el) => { el.textContent = (0).toFixed(+(el.dataset.dec || 0)); countObs.observe(el); });

  /* ---------- hero floating notes (canvas) ---------- */
  const canvas = $(".notes");
  const hero = $(".hero");
  if (canvas && !reduced) {
    const ctx = canvas.getContext("2d");
    const glyphs = ["♪", "♫", "♩", "♬", "𝄞"];
    let w = 0, h = 0, dpr = 1, notes = [], visible = true, raf = 0;

    const spawn = (anywhere) => ({
      x: Math.random() * w,
      y: anywhere ? Math.random() * h : h + 30,
      s: 14 + Math.random() * 22,
      v: 0.18 + Math.random() * 0.45,
      a: Math.random() * Math.PI * 2,
      g: glyphs[(Math.random() * glyphs.length) | 0],
      o: 0.08 + Math.random() * 0.22,
      hot: Math.random() < 0.3,
    });
    const resize = () => {
      dpr = Math.min(devicePixelRatio || 1, 2);
      w = hero.clientWidth; h = hero.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.round(Math.min(26, w / 55));
      notes = Array.from({ length: count }, () => spawn(true));
    };
    let px = -1e4, py = -1e4;
    hero.addEventListener("pointermove", (e) => { const r = hero.getBoundingClientRect(); px = e.clientX - r.left; py = e.clientY - r.top; }, { passive: true });
    hero.addEventListener("pointerleave", () => { px = py = -1e4; });

    const frame = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.textAlign = "center";
      for (const n of notes) {
        n.y -= n.v;
        n.a += 0.012;
        let x = n.x + Math.sin(n.a) * 14;
        // notes drift away from the pointer
        const dx = x - px, dy = n.y - py, d2 = dx * dx + dy * dy;
        if (d2 < 14400) { const f = (1 - Math.sqrt(d2) / 120) * 2.2; n.x += (dx / 120) * f; n.y += (dy / 120) * f; x = n.x + Math.sin(n.a) * 14; }
        if (n.y < -40) Object.assign(n, spawn(false));
        ctx.globalAlpha = n.o;
        ctx.fillStyle = n.hot ? "#f58247" : "#ececf1";
        ctx.font = `${n.s}px "Segoe UI Symbol", "Noto Music", serif`;
        ctx.fillText(n.g, x, n.y);
      }
      ctx.globalAlpha = 1;
      raf = visible && !document.hidden ? requestAnimationFrame(frame) : 0;
    };
    const start = () => { if (!raf && visible && !document.hidden) raf = requestAnimationFrame(frame); };

    new IntersectionObserver(([e]) => { visible = e.isIntersecting; start(); }).observe(hero);
    document.addEventListener("visibilitychange", start);
    let rt, lastW = innerWidth;
    // ignore height-only resizes (mobile URL bar) to avoid re-seeding the notes
    addEventListener("resize", () => { if (innerWidth === lastW) return; lastW = innerWidth; clearTimeout(rt); rt = setTimeout(resize, 150); });
    resize();
    start();
  }

  /* ---------- diagram wire length for pulses ---------- */
  const sizeWires = () => $$(".wire").forEach((wEl) => {
    const vertical = wEl.offsetHeight > wEl.offsetWidth;
    wEl.style.setProperty("--len", `${(vertical ? wEl.offsetHeight : wEl.offsetWidth) - 10}px`);
  });
  sizeWires();
  addEventListener("resize", sizeWires, { passive: true });

  /* ---------- synced lyrics demo ---------- */
  const lyricsEl = $(".lyrics");
  const player = $(".player");
  if (lyricsEl) {
    // Original demo lyrics: [start seconds, line]
    const song = [
      [0.0, "I closed the window, thought the song was gone"],
      [4.0, "but the speakers kept on humming on"],
      [8.0, "no ads to break the chorus in two"],
      [12.0, "just a clef, a queue, and you"],
      [16.0, "word by word the lyrics glow"],
      [20.0, "half a second, here we go"],
      [24.0, "press the space bar, let it ring"],
      [28.0, "open source, and everything"],
    ];
    const total = 32;
    const inner = document.createElement("div");
    inner.className = "lyrics-inner";
    let clock = 0, last = 0, active = -1, raf = 0, inView = false, stopped = reduced;

    const lines = song.map(([t, text], idx) => {
      const div = document.createElement("div");
      div.className = "line";
      const end = idx + 1 < song.length ? song[idx + 1][0] : total;
      const words = text.split(" ");
      words.forEach((wd, k) => {
        const s = document.createElement("span");
        s.className = "w";
        s.textContent = wd + (k < words.length - 1 ? " " : "");
        s.dataset.t = (t + ((end - t) * 0.85 * k) / words.length).toFixed(2);
        div.appendChild(s);
      });
      div.addEventListener("click", () => { clock = t; render(true); });
      inner.appendChild(div);
      return div;
    });
    lyricsEl.appendChild(inner);
    // lines are clickable, so let them receive pointer events despite aria-hidden wrapper
    lyricsEl.removeAttribute("aria-hidden");
    lyricsEl.setAttribute("role", "presentation");

    const fill = $(".fill", player), knob = $(".knob", player), cur = $(".time.cur", player), track = $(".track", player);
    const playBtn = $(".play", player);
    const words = $$(".w", inner);
    const display = 204; // fake 3:24 length shown in the bar

    const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
    const render = (force) => {
      let idx = 0;
      for (let k = 0; k < song.length; k++) if (clock >= song[k][0]) idx = k;
      if (idx !== active || force) {
        active = idx;
        lines.forEach((l, k) => { l.classList.toggle("active", k === idx); l.classList.toggle("past", k < idx); });
        const target = lines[idx];
        inner.style.transform = `translateY(${lyricsEl.clientHeight * 0.36 - target.offsetTop - target.offsetHeight / 2}px)`;
      }
      for (const w of words) w.classList.toggle("on", clock >= +w.dataset.t);
      const p = clock / total;
      fill.style.transform = `scaleX(${p})`;
      knob.style.left = `${p * 100}%`;
      cur.textContent = fmt(p * display);
    };
    const loop = (now) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      clock += dt;
      if (clock >= total) clock = 0;
      render(false);
      raf = inView && !stopped && !document.hidden ? requestAnimationFrame(loop) : 0;
    };
    const play = () => { if (!raf && inView && !stopped && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(loop); } };
    const setStopped = (v) => {
      stopped = v;
      player.classList.toggle("stopped", v);
      playBtn.setAttribute("aria-label", v ? "Play preview" : "Pause preview");
      play();
    };

    playBtn.addEventListener("click", () => setStopped(!stopped));
    track.addEventListener("click", (e) => {
      const r = track.getBoundingClientRect();
      clock = Math.max(0, Math.min(0.999, (e.clientX - r.left) / r.width)) * total;
      render(true);
    });

    new IntersectionObserver(([e]) => {
      inView = e.isIntersecting;
      player.classList.toggle("paused", !inView);
      play();
    }, { threshold: 0.25 }).observe(player);
    document.addEventListener("visibilitychange", play);
    addEventListener("resize", () => render(true), { passive: true });
    if (reduced) { clock = 13; player.classList.add("stopped"); }
    render(true);
  }

  /* ---------- keyboard shortcut board ---------- */
  const keyMap = new Map();
  $$(".key").forEach((el) => el.dataset.k.split(" ").forEach((k) => { if (k) keyMap.set(k, el); }));
  keyMap.set(" ", $('.key[data-k=" "]'));
  const timers = new WeakMap();
  const flash = (el) => {
    el.classList.add("lit");
    clearTimeout(timers.get(el));
    timers.set(el, setTimeout(() => el.classList.remove("lit"), 380));
  };
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.target.closest && e.target.closest("input, textarea, [contenteditable]")) return;
    const el = keyMap.get(e.key.length === 1 ? e.key.toLowerCase() : e.key);
    if (el) flash(el);
  });
  // touch screens have no keyboard: let people tap the keys instead
  if (!finePointer) {
    const hint = $(".keys-hint");
    if (hint) hint.textContent = "Tap a key to try it. On your computer, they light up as you type.";
    $$(".key").forEach((el) => el.addEventListener("pointerdown", () => flash(el)));
  }

  /* ---------- copy buttons ---------- */
  $$(".copy").forEach((btn) => btn.addEventListener("click", async () => {
    if (await copyText(btn.dataset.copy)) {
      btn.classList.add("done");
      btn.innerHTML = '<svg aria-hidden="true"><use href="#i-check"/></svg>';
      toast("Command copied");
      setTimeout(() => { btn.classList.remove("done"); btn.innerHTML = '<svg aria-hidden="true"><use href="#i-copy"/></svg>'; }, 1800);
    }
  }));

  /* ======================================================================
     Downloads: latest release + platform detection
     ====================================================================== */

  // Shipped with the page so links work offline / when the GitHub API is rate-limited.
  const FALLBACK = {
    tag: "v1.0.0",
    date: "2026-10-27T03:07:28Z",
    assets: {
      win: { name: "ClefTune-1.0.0-windows-x64-setup.exe", size: 81455738 },
      "mac-arm": { name: "ClefTune-1.0.0-macos-arm64.pkg", size: 92376767 },
      "mac-intel": { name: "ClefTune-1.0.0-macos-x86_64.pkg", size: 101784361 },
      linux: { name: "ClefTune-1.0.0-linux-x86_64.run", size: 180401871 },
    },
  };
  for (const a of Object.values(FALLBACK.assets)) a.url = `https://github.com/${REPO}/releases/download/${FALLBACK.tag}/${a.name}`;

  const ASSET_PATTERNS = {
    win: /windows-x64-setup\.exe$/i,
    "mac-arm": /macos-arm64\.pkg$/i,
    "mac-intel": /macos-x86_64\.pkg$/i,
    linux: /linux-x86_64\.run$/i,
  };

  const fmtSize = (b) => `${Math.round(b / 1e6)} MB`;
  const fmtDate = (iso) => {
    try { return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }); }
    catch { return iso.slice(0, 10); }
  };

  async function loadRelease() {
    const KEY = "cleftune-release";
    try {
      const cached = JSON.parse(sessionStorage.getItem(KEY) || "null");
      if (cached && Date.now() - cached.at < 36e5) return cached.data;
    } catch { /* storage unavailable */ }

    const ctrl = new AbortController();
    const timeout = setTimeout(() => ctrl.abort(), 5000);
    try {
      const res = await fetch(`https://api.github.com/repos/${REPO}/releases/latest`, {
        headers: { Accept: "application/vnd.github+json" },
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(res.status);
      const json = await res.json();
      const assets = {};
      for (const [key, re] of Object.entries(ASSET_PATTERNS)) {
        const a = json.assets.find((x) => re.test(x.name));
        if (a) assets[key] = { name: a.name, size: a.size, url: a.browser_download_url };
      }
      // only trust the response if every installer is present
      if (Object.keys(assets).length !== Object.keys(ASSET_PATTERNS).length) throw new Error("incomplete release");
      const data = { tag: json.tag_name, date: json.published_at, assets };
      try { sessionStorage.setItem(KEY, JSON.stringify({ at: Date.now(), data })); } catch { /* ignore */ }
      return data;
    } catch {
      return FALLBACK;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function detectPlatform() {
    const ua = navigator.userAgent;
    const uad = navigator.userAgentData;
    const plat = (uad && uad.platform) || navigator.platform || "";
    let os = "unknown", arch = null;

    const isIPadOS = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
    if (/Android|iPhone|iPad|iPod/i.test(ua) || isIPadOS || (uad && uad.mobile)) os = "mobile";
    else if (/CrOS/.test(ua) || /Chrome OS/i.test(plat)) os = "chromeos";
    else if (/^Win/i.test(plat) || /Windows/.test(ua)) os = "windows";
    else if (/^Mac/i.test(plat) || /Mac OS X/.test(ua)) os = "mac";
    else if (/Linux|X11/i.test(plat) || /Linux|X11/.test(ua)) os = "linux";

    // CPU architecture: Chromium tells us directly; elsewhere, peek at the GPU name.
    try {
      if (uad && uad.getHighEntropyValues) {
        const v = await uad.getHighEntropyValues(["architecture"]);
        if (v.architecture) arch = v.architecture === "arm" ? "arm" : "x86";
      }
    } catch { /* not allowed */ }
    if (!arch && os === "mac") {
      try {
        const gl = document.createElement("canvas").getContext("webgl");
        const ext = gl && gl.getExtension("WEBGL_debug_renderer_info");
        const gpu = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : "";
        if (/Intel|AMD|Radeon/i.test(gpu)) arch = "x86";
        else if (/Apple M\d|Apple GPU/i.test(gpu)) arch = "arm";
      } catch { /* ignore */ }
    }
    if (!arch && /aarch64|arm64/i.test(ua)) arch = "arm";
    return { os, arch };
  }

  const STEPS = {
    windows: [
      "<b>Run the setup file.</b> No admin rights needed.",
      "If <b>“Windows protected your PC”</b> appears, click <i>More info → Run anyway</i>. The builds aren't code-signed yet.",
      "Pick <b>its own window</b> (recommended) or <b>your browser</b>, then press play.",
    ],
    mac: [
      "<b>Open the .pkg</b> and follow the installer.",
      "If macOS blocks it, go to <i>System Settings → Privacy &amp; Security</i> and click <b>Open Anyway</b>.",
      "Pick <b>its own window</b> (recommended) or <b>your browser</b>. Find ClefTune in Applications.",
    ],
    linux: [
      'Make it executable and run it. No root needed:<div class="cmd"><code>chmod +x ClefTune-*.run &amp;&amp; ./ClefTune-*.run</code><button class="copy" type="button" data-copy="chmod +x ClefTune-*.run &amp;&amp; ./ClefTune-*.run" aria-label="Copy install command"><svg aria-hidden="true"><use href="#i-copy"/></svg></button></div>',
      "It installs into your home folder (<code>~/.local</code>) and adds a menu entry.",
      "Pick <b>its own window</b> (recommended) or <b>your browser</b>, then press play.",
    ],
  };

  function applyRelease(rel) {
    $$("[data-version]").forEach((el) => { el.textContent = rel.tag; });
    $$("[data-date]").forEach((el) => { el.textContent = `released ${fmtDate(rel.date)}`; });
    $$("[data-asset]").forEach((a) => {
      const asset = rel.assets[a.dataset.asset];
      if (asset) a.href = asset.url;
    });
    $$("[data-size]").forEach((el) => {
      const asset = rel.assets[el.dataset.size];
      if (asset) el.textContent = `${fmtSize(asset.size)} · ${asset.name.split(".").pop()}`;
    });
  }

  function showRecommendation(rel, { os, arch }) {
    const rec = $(".rec");
    const mobile = $(".mobile-note");
    const navLabel = $(".nav-dl-label");
    const heroLabel = $(".hero-dl-label");

    if (os === "mobile") {
      mobile.hidden = false;
      heroLabel.textContent = "Get it for your computer";
      return;
    }

    const plat = os === "chromeos" ? "linux" : os;
    if (!STEPS[plat]) return; // unknown OS: the "All downloads" grid is enough

    const meta = {
      windows: { name: "Windows", icon: "i-win", req: "Windows 10 / 11 · 64-bit", key: "win" },
      mac: arch === "x86"
        ? { name: "macOS", icon: "i-apple", req: "Intel Mac · macOS 11 or newer", key: "mac-intel", label: "Intel" }
        : { name: "macOS", icon: "i-apple", req: "Apple Silicon (M1 and later) · macOS 11 or newer", key: "mac-arm", label: "Apple Silicon" },
      linux: { name: "Linux", icon: "i-linux", req: "x86-64 · any distro", key: "linux" },
    }[plat];
    const asset = rel.assets[meta.key];

    $(".rec-detected", rec).textContent = `Detected: ${os === "chromeos" ? "ChromeOS (Linux)" : meta.name}${meta.label ? ` · ${meta.label}` : ""}`;
    $(".rec-icon use", rec).setAttribute("href", `#${meta.icon}`);
    $(".rec-name", rec).textContent = `ClefTune for ${meta.name}`;
    $(".rec-req", rec).textContent = meta.req;
    const btn = $(".rec-btn", rec);
    btn.href = asset.url;
    $(".rec-btn-label", rec).textContent = `Download for ${meta.name}`;
    $(".rec-btn-size", rec).textContent = fmtSize(asset.size);
    $(".rec-file code", rec).textContent = asset.name;

    const alt = $(".rec-alt", rec);
    alt.innerHTML = "";
    const addAlt = (text, href) => {
      const a = document.createElement("a");
      a.href = href;
      a.textContent = text;
      if (href.startsWith("http")) a.setAttribute("download", "");
      alt.append(a);
    };
    if (plat === "mac") {
      const other = arch === "x86" ? "mac-arm" : "mac-intel";
      alt.append(arch === "x86" ? "On an M-series Mac? " : "On an Intel Mac? ");
      addAlt(`Get the ${arch === "x86" ? "Apple Silicon" : "Intel"} build (${fmtSize(rel.assets[other].size)})`, rel.assets[other].url);
      if (!arch) alt.append(" · Not sure? Apple menu → About This Mac.");
    } else if (plat === "windows" && arch === "arm") {
      alt.append("Windows on ARM runs this x64 build through Windows 11's built-in emulation. ");
    } else if (plat === "linux" && arch === "arm") {
      alt.append("Heads-up: only x86-64 Linux builds exist right now. ");
      addAlt("Run from source instead", `https://github.com/${REPO}#-run-from-source`);
    } else if (os === "chromeos") {
      alt.append("Needs the Linux development environment turned on in ChromeOS settings.");
    }
    if (alt.childNodes.length) alt.append(" ");
    addAlt("Other systems ↓", "#all-downloads");

    const steps = $(".steps", rec);
    steps.innerHTML = STEPS[plat].map((s) => `<li>${s}</li>`).join("");
    $$(".copy", steps).forEach((b) => b.addEventListener("click", async () => {
      if (await copyText(b.dataset.copy)) toast("Command copied");
    }));

    rec.hidden = false;
    $(`.os[data-os="${plat}"]`)?.classList.add("current");
    navLabel.innerHTML = `Download<span class="nav-dl-os"> for ${meta.name}</span>`;
    heroLabel.textContent = `Download for ${meta.name}`;
  }

  // Header and hero buttons scroll to the download section and point at the recommended card.
  $$(".nav-dl, .hero-dl").forEach((a) => a.addEventListener("click", () => {
    const rec = $(".rec");
    if (rec.hidden) return;
    setTimeout(() => {
      rec.classList.remove("flash");
      void rec.offsetWidth;
      rec.classList.add("flash");
    }, reduced ? 0 : 650);
  }));

  // Phones: share or copy the page link so it can be opened on a computer.
  const shareBtn = $(".share-btn");
  if (!navigator.share) shareBtn.hidden = true;
  shareBtn.addEventListener("click", async () => {
    try { await navigator.share({ title: "ClefTune", text: "ClefTune, a free desktop music app. Open this on your computer:", url: location.href.split("#")[0] }); }
    catch { /* dismissed */ }
  });
  $(".copy-link").addEventListener("click", async () => {
    if (await copyText(location.href.split("#")[0])) toast("Link copied. Open it on your computer.");
  });

  Promise.all([loadRelease(), detectPlatform()]).then(([rel, platform]) => {
    applyRelease(rel);
    showRecommendation(rel, platform);
  });
})();
