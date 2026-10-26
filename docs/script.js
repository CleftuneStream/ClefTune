/* ClefTune site · vanilla JS. Every animation loop pauses when off-screen or hidden. */
(() => {
  "use strict";

  document.documentElement.classList.remove("no-js");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const lerp = (a, b, t) => a + (b - a) * t;

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
  if (finePointer && !reduced) {
    const cursor = $(".cursor");
    const ring = $(".cursor-ring");
    let mx = innerWidth / 2, my = innerHeight / 2, rx = mx, ry = my, cx = mx, cy = my;
    let running = false;

    const tick = () => {
      cx = lerp(cx, mx, 0.55);
      cy = lerp(cy, my, 0.55);
      rx = lerp(rx, mx, 0.16);
      ry = lerp(ry, my, 0.16);
      cursor.style.transform = `translate3d(${cx}px, ${cy}px, 0)`;
      ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
      // stop the loop once everything has settled
      if (Math.abs(rx - mx) + Math.abs(ry - my) + Math.abs(cx - mx) + Math.abs(cy - my) > 0.3) {
        requestAnimationFrame(tick);
      } else running = false;
    };
    const wake = () => { if (!running) { running = true; requestAnimationFrame(tick); } };

    addEventListener("pointermove", (e) => {
      mx = e.clientX; my = e.clientY;
      if (!document.body.classList.contains("has-cursor")) {
        document.body.classList.add("has-cursor");
        cx = rx = mx; cy = ry = my;
      }
      wake();
    }, { passive: true });

    const interactive = "a, button, .card, .key, .chip, .os, .line";
    document.addEventListener("pointerover", (e) => {
      const on = !!e.target.closest(interactive);
      cursor.classList.toggle("hover", on);
      ring.classList.toggle("hover", on);
    });
    addEventListener("pointerdown", () => cursor.classList.add("down"));
    addEventListener("pointerup", () => cursor.classList.remove("down"));
    document.addEventListener("pointerleave", () => { cursor.classList.add("hidden"); ring.classList.add("hidden"); });
    document.addEventListener("pointerenter", () => { cursor.classList.remove("hidden"); ring.classList.remove("hidden"); });
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

  /* ---------- scroll progress + auto-hiding nav (one rAF per scroll burst) ---------- */
  const bar = $(".progress");
  const nav = $(".nav");
  let lastY = scrollY, scrollQueued = false;
  addEventListener("scroll", () => {
    if (scrollQueued) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      const y = scrollY;
      const max = document.documentElement.scrollHeight - innerHeight;
      bar.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
      nav.classList.toggle("away", y > lastY && y > 400);
      lastY = y;
      scrollQueued = false;
    });
  }, { passive: true });

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
  $$(".count").forEach((el) => countObs.observe(el));

  /* ---------- hero floating notes (canvas) ---------- */
  const canvas = $(".notes");
  const hero = $(".hero");
  if (canvas && !reduced) {
    const ctx = canvas.getContext("2d");
    const glyphs = ["♪", "♫", "♩", "♬", "𝄞"];
    let w = 0, h = 0, dpr = 1, notes = [], visible = true, raf = 0;

    const resize = () => {
      dpr = Math.min(devicePixelRatio || 1, 2);
      w = hero.clientWidth; h = hero.clientHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.round(Math.min(26, w / 55));
      notes = Array.from({ length: count }, () => spawn(true));
    };
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
    let rt;
    addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(resize, 150); });
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
      div.dataset.t = t;
      div.addEventListener("click", () => { clock = t; render(true); });
      inner.appendChild(div);
      return div;
    });
    lyricsEl.appendChild(inner);

    const fill = $(".fill", player), knob = $(".knob", player), cur = $(".time.cur", player), track = $(".track", player);
    const words = $$(".w", inner);
    const display = 204; // fake 3:24 length shown in the bar
    let clock = 0, last = 0, active = -1, raf = 0, inView = false;

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
      if (clock >= total) { clock = 0; for (const w of words) w.classList.remove("on"); }
      render(false);
      raf = inView && !document.hidden ? requestAnimationFrame(loop) : 0;
    };
    const play = () => { if (!raf && inView && !document.hidden && !reduced) { last = performance.now(); raf = requestAnimationFrame(loop); } };

    track.addEventListener("click", (e) => {
      const r = track.getBoundingClientRect();
      clock = Math.max(0, Math.min(0.999, (e.clientX - r.left) / r.width)) * total;
      for (const w of words) w.classList.remove("on");
      render(true);
    });

    new IntersectionObserver(([e]) => {
      inView = e.isIntersecting;
      player.classList.toggle("paused", !inView);
      play();
    }, { threshold: 0.25 }).observe(player);
    document.addEventListener("visibilitychange", play);
    addEventListener("resize", () => render(true), { passive: true });
    if (reduced) { clock = 13; }
    render(true);
  }

  /* ---------- keyboard shortcut board ---------- */
  const keyMap = new Map();
  $$(".key").forEach((el) => el.dataset.k.split(" ").forEach((k) => keyMap.set(k || " ", el)));
  keyMap.set(" ", $('.key[data-k=" "]'));
  const timers = new WeakMap();
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const el = keyMap.get(e.key.length === 1 ? e.key.toLowerCase() : e.key);
    if (!el) return;
    el.classList.add("lit");
    clearTimeout(timers.get(el));
    timers.set(el, setTimeout(() => el.classList.remove("lit"), 380));
  });
})();
