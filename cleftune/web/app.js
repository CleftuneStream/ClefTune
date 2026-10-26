"use strict";

/* ============================================================
 * ClefTune UI. Plain DOM, no framework, no build step.
 * Text from YouTube is only ever inserted via textContent.
 * ============================================================ */

const TOKEN = document.querySelector('meta[name="token"]').content;
const $ = (sel, root = document) => root.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";

// Material Design icons (Apache 2.0)
const ICONS = {
  play: "M8 5v14l11-7z",
  pause: "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
  next: "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z",
  prev: "M6 6h2v12H6zm3.5 6l8.5 6V6z",
  shuffle: "M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z",
  repeat: "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z",
  repeatOne: "M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z",
  heart: "M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z",
  heartOutline: "M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z",
  more: "M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z",
  search: "M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z",
  home: "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
  explore: "M12 10.9c-.61 0-1.1.49-1.1 1.1s.49 1.1 1.1 1.1c.61 0 1.1-.49 1.1-1.1s-.49-1.1-1.1-1.1zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm2.19 12.19L6 18l3.81-8.19L18 6l-3.81 8.19z",
  library: "M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 5h-3v5.5c0 1.38-1.12 2.5-2.5 2.5S10 13.88 10 12.5s1.12-2.5 2.5-2.5c.57 0 1.08.19 1.5.51V5h4v2zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z",
  download: "M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z",
  downloadDone: "M5 18h14v2H5v-2zm4.6-2.7L5 10.7l2-1.9 2.6 2.6L17 4l2 2-9.4 9.3z",
  settings: "M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z",
  queue: "M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z",
  lyrics: "M14 17H4v2h10v-2zm6-8H4v2h16V9zM4 15h16v-2H4v2zM4 5v2h16V5H4z",
  volume: "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z",
  mute: "M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z",
  close: "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
  back: "M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z",
  forward: "M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8z",
  add: "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
  playlistAdd: "M14 10H2v2h12v-2zm0-4H2v2h12V6zm4 8v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM2 16h8v-2H2v2z",
  playNext: "M3 10h11v2H3zm0-4h11v2H3zm0 8h7v2H3zm13-1v8l6-4z",
  radio: "M3.24 6.15C2.51 6.43 2 7.17 2 8v12c0 1.1.89 2 2 2h16c1.11 0 2-.9 2-2V8c0-1.11-.89-2-2-2H8.3l8.26-3.34L15.88 1 3.24 6.15zM7 20c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm13-8h-2v-2h-2v2H4V8h16v4z",
  timer: "M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61l1.42-1.42c-.43-.51-.9-.99-1.41-1.41l-1.42 1.42C16.07 4.74 14.12 4 12 4c-4.97 0-9 4.03-9 9s4.02 9 9 9 9-4.03 9-9c0-2.12-.74-4.07-1.97-5.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z",
  trash: "M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z",
  folder: "M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z",
  history: "M13 3c-4.97 0-9 4.03-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42C8.27 19.99 10.51 21 13 21c4.97 0 9-4.03 9-9s-4.03-9-9-9zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z",
  check: "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
  libraryAdd: "M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-1 9h-4v4h-2v-4H9V9h4V5h2v4h4v2z",
  libraryCheck: "M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7.53 12L9 10.5l1.4-1.41 2.07 2.08L17.6 6 19 7.41 12.47 14zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z",
  person: "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z",
  up: "M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z",
  down: "M20 12l-1.41-1.41L13 16.17V4h-2v12.17l-5.58-5.59L4 12l8 8 8-8z",
  link: "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z",
  album: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z",
  note: "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z",
  power: "M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z",
  stats: "M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z",
  edit: "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z",
  expand: "M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z",
};

/* ---------- tiny DOM helpers ---------- */
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "style") el.style.cssText = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "dataset") Object.assign(el.dataset, v);
      else el.setAttribute(k, v === true ? "" : v);
    }
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : String(kid));
  }
  return el;
}

function icon(name, size) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon");
  if (size) { svg.style.width = size + "px"; svg.style.height = size + "px"; }
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", ICONS[name] || ICONS.note);
  svg.append(path);
  return svg;
}

function setIcon(el, name) { el.replaceChildren(icon(name)); }

function img(src, cls = "", fallback = "note") {
  if (!src) return h("div", { class: "placeholder-art " + cls }, icon(fallback));
  const el = h("img", { src, class: cls, loading: "lazy", referrerpolicy: "no-referrer", alt: "", draggable: "false" });
  el.addEventListener("error", () => el.replaceWith(h("div", { class: "placeholder-art " + cls }, icon(fallback))), { once: true });
  return el;
}

function fmt(sec) {
  if (sec == null || !isFinite(sec)) return "–:––";
  sec = Math.max(0, Math.floor(sec));
  const hrs = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = String(sec % 60).padStart(2, "0");
  return hrs ? `${hrs}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function toast(message, kind = "") {
  const el = h("div", { class: "toast " + kind }, message);
  $("#toasts").append(el);
  setTimeout(() => el.remove(), kind === "error" ? 5000 : 2600);
}

/* ---------- backend ---------- */
async function call(name, params = {}) {
  const res = await fetch(`/api/call/${name}`, {
    method: "POST",
    headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  let data;
  try { data = await res.json(); } catch { throw new Error(`Server error (${res.status})`); }
  if (!data.ok) throw new Error(data.error || "Request failed");
  return data.result;
}

function act(name, params, okMessage) {
  return call(name, params).then(r => { if (okMessage) toast(okMessage); return r; })
    .catch(e => { toast(e.message, "error"); throw e; });
}

/* ---------- global state ---------- */
const S = {
  state: null,
  queue: { items: [], index: -1, version: 0, title: "" },
  pos: 0, dur: 0, playing: false, posAt: performance.now(),
  liked: new Set(),
  downloaded: new Set(),
  lyrics: null, lyricsFor: null, lyricIndex: -1, lyricsFollowAt: 0,
  panel: null,
  settings: {},
  about: {},
  seeking: false,
  volumeBeforeMute: 80,
};

/* ============================================================
 * Web audio engine: the backend sends commands, we report back.
 * ============================================================ */
const audio = $("#audio");
const BOOT_TIME = Date.now() / 1000;
const engine = { src: null, pendingStart: 0 };

function engineReport(event, extra = {}) {
  if (!engine.src) return;
  call("engine_report", {
    event, src: engine.src, pos: audio.currentTime || 0,
    duration: isFinite(audio.duration) ? audio.duration : 0, paused: audio.paused, ...extra,
  }).catch(() => {});
}

function handleEngine(cmd) {
  if (S.state && S.state.engine && S.state.engine !== "web") return;
  switch (cmd.cmd) {
    case "load": {
      engine.src = cmd.src;
      // a command older than this page is a replay after a UI reload: restore paused at the last position
      const resume = (cmd.ts || 0) < BOOT_TIME;
      engine.pendingStart = resume ? (S.pos || cmd.start || 0) : (cmd.start || 0);
      audio.src = cmd.src;
      audio.volume = (cmd.volume ?? 80) / 100;
      if (!cmd.paused && !resume) {
        audio.play().catch(err => {
          if (err.name === "NotAllowedError") toast("Click play to start audio");
          engineReport("position");
        });
      }
      break;
    }
    case "play": audio.play().catch(() => engineReport("position")); break;
    case "pause": audio.pause(); break;
    case "seek": if (engine.src) audio.currentTime = cmd.pos; break;
    case "volume": audio.volume = cmd.volume / 100; break;
    case "loop": audio.loop = !!cmd.enabled; break;
    case "stop":
      engine.src = null;
      audio.pause();
      audio.removeAttribute("src");
      audio.load();
      break;
  }
}

audio.addEventListener("loadedmetadata", () => {
  if (engine.pendingStart > 0) { audio.currentTime = engine.pendingStart; engine.pendingStart = 0; }
  engineReport("position");
});
for (const ev of ["play", "pause", "seeked", "durationchange"]) audio.addEventListener(ev, () => engineReport("position"));
audio.addEventListener("ended", () => engineReport("ended"));
audio.addEventListener("error", () => {
  if (!engine.src || !audio.error) return;
  const codes = { 1: "aborted", 2: "network error", 3: "decode error", 4: "format not supported" };
  engineReport("error", { message: `Audio ${codes[audio.error.code] || "error"}${audio.error.code === 4 ? " (try 'Prefer AAC streams' in Settings)" : ""}` });
});
setInterval(() => { if (!audio.paused && engine.src) engineReport("position"); }, 500);

/* Media Session: OS media keys + Windows/ChromeOS media flyout for the web engine */
function updateMediaSession() {
  if (!("mediaSession" in navigator) || S.state?.engine !== "web") return;
  const cur = S.state?.current;
  if (!cur) { navigator.mediaSession.metadata = null; return; }
  navigator.mediaSession.metadata = new MediaMetadata({
    title: cur.title, artist: cur.artist, album: cur.album?.name || "",
    artwork: cur.thumbnail ? [{ src: cur.thumbnail, sizes: "544x544" }] : [],
  });
  navigator.mediaSession.playbackState = S.playing ? "playing" : "paused";
}
if ("mediaSession" in navigator) {
  const ms = navigator.mediaSession;
  ms.setActionHandler("play", () => call("toggle"));
  ms.setActionHandler("pause", () => call("toggle"));
  ms.setActionHandler("nexttrack", () => call("next"));
  ms.setActionHandler("previoustrack", () => call("previous"));
  try { ms.setActionHandler("seekto", d => call("seek", { pos: d.seekTime })); } catch {}
}

/* ============================================================
 * Server-Sent Events
 * ============================================================ */
function connectEvents() {
  const es = new EventSource(`/api/events?token=${encodeURIComponent(TOKEN)}`);
  const on = (name, fn) => es.addEventListener(name, e => { try { fn(JSON.parse(e.data)); } catch (err) { console.error(err); } });
  on("state", st => {
    const prevId = S.state?.current?.videoId;
    S.state = st;
    S.playing = st.playing;
    if (st.current?.videoId !== prevId) { S.pos = st.pos || 0; S.posAt = performance.now(); }
    S.dur = st.duration || 0;
    if (st.current) S.liked[st.liked ? "add" : "delete"](st.current.videoId);
    renderPlayerBar();
    if (st.current?.videoId !== prevId) onTrackChanged();
    markPlayingRows();
    updateMediaSession();
  });
  on("queue", q => { S.queue = q; if (S.panel === "queue") renderPanel(); markPlayingRows(); });
  on("queue-index", d => { S.queue.index = d.index; if (S.panel === "queue") renderPanel(); });
  on("position", p => {
    if (S.state && p.gen != null && S.state.gen != null && p.gen !== S.state.gen) return;
    S.pos = p.pos; S.dur = p.duration || S.dur; S.playing = p.playing; S.posAt = performance.now();
    if (S.state) S.state.playing = p.playing;
    renderPlayButton();
  });
  on("engine", handleEngine);
  on("toast", t => toast(t.message, t.kind || ""));
  on("login", ev => loginWatch.onEvent?.(ev));
  on("account", () => { renderAccountChip(); if (/^#\/(settings|library)/.test(location.hash)) route(); });
  on("cache", () => { if (location.hash.startsWith("#/cache")) route(); });
  on("downloads", () => {
    refreshDownloadedIds();
    if (location.hash.startsWith("#/downloads")) route();
  });
}

/* ============================================================
 * Player bar
 * ============================================================ */
function renderPlayButton() {
  const btn = $("#pb-play");
  const loading = S.state?.loading;
  const want = loading ? "loading" : S.playing ? "pause" : "play";
  if (btn.dataset.mode === want) return;
  btn.dataset.mode = want;
  btn.replaceChildren(loading ? h("div", { class: "spinner" }) : icon(S.playing ? "pause" : "play", 28));
  document.body.classList.toggle("paused", !S.playing);
  renderNowPlayingControls();
  updateMediaSession();
}

function renderPlayerBar() {
  const st = S.state;
  const cur = st?.current;
  const art = $("#pb-art");
  const artKey = cur?.thumbnail || "";
  if (art.dataset.src !== artKey) { art.dataset.src = artKey; art.replaceChildren(img(cur?.thumbnail)); applyDynamicColor(cur?.thumbnail); }
  $("#pb-title").textContent = cur ? cur.title : "Nothing playing";
  $("#pb-title").title = cur ? cur.title : "";
  $("#pb-artist").replaceChildren(...(cur ? artistLinks(cur) : []));
  setIcon($("#pb-like"), cur && S.liked.has(cur.videoId) ? "heart" : "heartOutline");
  $("#pb-like").classList.toggle("on", !!(cur && S.liked.has(cur.videoId)));
  $("#pb-like").disabled = !cur;
  $("#pb-shuffle").classList.toggle("on", !!st?.shuffle);
  setIcon($("#pb-repeat"), st?.repeat === "one" ? "repeatOne" : "repeat");
  $("#pb-repeat").classList.toggle("on", st && st.repeat !== "off");
  $("#pb-repeat").title = `Repeat: ${st?.repeat || "off"} (R)`;
  $("#pb-sleep").classList.toggle("on", st?.sleep != null);
  $("#pb-sleep").title = st?.sleep == null ? "Sleep timer" : st.sleep === "end" ? "Sleep: end of song" : `Sleep in ${Math.ceil(st.sleep / 60)} min`;
  $("#pb-stream").textContent = st?.stream || "";
  const vol = st?.volume ?? 80;
  const volEl = $("#pb-volume");
  if (document.activeElement !== volEl) { volEl.value = vol; volEl.style.setProperty("--p", vol + "%"); }
  setIcon($("#pb-mute"), vol === 0 ? "mute" : "volume");
  if (st?.error) $("#pb-artist").replaceChildren(h("span", { style: "color:#e5484d" }, st.error));
  $("#pb-title").title = cur ? (cur.album?.id ? `${cur.title} — open the album` : cur.title) : "";
  renderPlayButton();
  renderNowPlayingControls();
}

function currentPos() {
  let p = S.pos;
  if (S.playing) p += (performance.now() - S.posAt) / 1000;
  return S.dur ? Math.min(p, S.dur) : p;
}

function tick() {
  const pos = currentPos();
  if (!S.seeking) {
    const pct = S.dur ? (pos / S.dur) * 100 : 0;
    for (const [barSel, timeSel] of [["#pb-seekbar", "#pb-time"], ["#np-seekbar", "#np-time"]]) {
      const bar = $(barSel);
      if (!bar) continue;
      bar.value = Math.round(pct * 10);
      bar.style.setProperty("--p", pct + "%");
      $(timeSel).textContent = fmt(pos);
    }
  }
  $("#pb-dur").textContent = fmt(S.dur);
  const npDur = $("#np-dur");
  if (npDur) npDur.textContent = fmt(S.dur);
  updateLyricHighlight(pos);
  requestAnimationFrame(tick);
}

function artistLinks(track) {
  const out = [];
  (track.artists || []).forEach((a, i) => {
    if (i) out.push(", ");
    out.push(a.id ? h("span", { class: "link", onclick: e => { e.stopPropagation(); go(`/artist/${a.id}`); } }, a.name) : a.name);
  });
  if (!out.length && track.artist) out.push(track.artist);
  return out;
}

function setupPlayerBar() {
  setIcon($("#pb-shuffle"), "shuffle");
  setIcon($("#pb-prev"), "prev");
  setIcon($("#pb-next"), "next");
  setIcon($("#pb-repeat"), "repeat");
  setIcon($("#pb-sleep"), "timer");
  setIcon($("#pb-lyrics"), "lyrics");
  setIcon($("#pb-queue"), "queue");
  setIcon($("#pb-mute"), "volume");
  setIcon($("#pb-like"), "heartOutline");
  $("#pb-art").replaceChildren(img(null));

  $("#pb-play").onclick = () => call("toggle");
  $("#pb-next").onclick = () => call("next");
  $("#pb-prev").onclick = () => call("previous");
  $("#pb-shuffle").onclick = () => call("shuffle", { enabled: !S.state?.shuffle });
  $("#pb-repeat").onclick = () => {
    const order = ["off", "all", "one"];
    call("repeat", { mode: order[(order.indexOf(S.state?.repeat || "off") + 1) % 3] });
  };
  $("#pb-like").onclick = () => S.state?.current && toggleLike(S.state.current);
  // artwork: full-screen player with lyrics (click again to go back); title: the album; artist: their page
  const openNowPlaying = () => {
    if (!S.state?.current) return;
    if (location.hash.startsWith("#/nowplaying")) history.back(); else go("/nowplaying");
  };
  $("#pb-art").onclick = openNowPlaying;
  $("#pb-title").onclick = () => {
    const album = S.state?.current?.album;
    if (album?.id) go(`/album/${album.id}`); else openNowPlaying();   // videos/uploads have no album
  };
  $("#pb-title").classList.add("link");
  $("#pb-title").setAttribute("role", "button");
  $("#pb-queue").onclick = () => togglePanel("queue");
  $("#pb-lyrics").onclick = () => togglePanel("lyrics");
  $("#pb-sleep").onclick = e => openMenu(e.currentTarget, [
    { label: "Sleep timer", heading: true },
    ...[5, 10, 15, 30, 45, 60, 90].map(m => ({ label: `${m} minutes`, icon: "timer", run: () => call("sleep", { minutes: m }).then(() => toast(`Pausing in ${m} minutes`)) })),
    { label: "End of current song", icon: "note", run: () => call("sleep", { minutes: -1 }).then(() => toast("Stopping after this song")) },
    S.state?.sleep != null && { label: "Turn off", icon: "close", run: () => call("sleep", { minutes: 0 }).then(() => toast("Sleep timer off")) },
  ], "up");

  bindSeekbar($("#pb-seekbar"), "#pb-time");

  const vol = $("#pb-volume");
  const sendVol = debounce(v => call("volume", { volume: v }), 60);
  vol.addEventListener("input", () => { vol.style.setProperty("--p", vol.value + "%"); sendVol(+vol.value); });
  $("#pb-mute").onclick = () => {
    const v = S.state?.volume ?? 80;
    if (v > 0) { S.volumeBeforeMute = v; call("volume", { volume: 0 }); } else call("volume", { volume: S.volumeBeforeMute || 80 });
  };
}

/* dynamic accent colour sampled from album art (needs CORS-enabled images; silently skipped otherwise) */
function applyDynamicColor(src) {
  const root = document.documentElement;
  if (!S.settings.dynamic_color || !src) { root.style.removeProperty("--accent"); root.style.removeProperty("--accent-ink"); return; }
  const im = new Image();
  im.crossOrigin = "anonymous";
  im.referrerPolicy = "no-referrer";
  im.onload = () => {
    try {
      const c = document.createElement("canvas");
      c.width = c.height = 24;
      const ctx = c.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(im, 0, 0, 24, 24);
      const d = ctx.getImageData(0, 0, 24, 24).data;
      let best = null, bestScore = -1;
      for (let i = 0; i < d.length; i += 4) {
        const [r, g, b] = [d[i], d[i + 1], d[i + 2]];
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        const sat = max ? (max - min) / max : 0;
        const score = sat * (max / 255) * (max > 60 ? 1 : 0.2);
        if (score > bestScore) { bestScore = score; best = [r, g, b]; }
      }
      if (!best || bestScore < 0.12) { root.style.removeProperty("--accent"); root.style.removeProperty("--accent-ink"); return; }
      let [r, g, b] = best;
      const light = document.documentElement.dataset.theme === "light";
      const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
      const target = light ? 0.42 : 0.68;              // keep contrast with the background
      const k = lum ? target / lum : 1;
      [r, g, b] = [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v * k))));
      root.style.setProperty("--accent", `rgb(${r},${g},${b})`);
      root.style.setProperty("--accent-ink", light ? "#fff" : "#0b0b10");
    } catch { /* tainted canvas: no CORS on this image */ }
  };
  im.src = src;
}

/* ============================================================
 * Likes / downloads bookkeeping
 * ============================================================ */
async function refreshLikedIds() { try { S.liked = new Set(await call("liked_ids")); } catch {} }
async function refreshDownloadedIds() { try { S.downloaded = new Set(await call("download_ids")); } catch {} }

async function toggleLike(track) {
  const liked = !S.liked.has(track.videoId);
  S.liked[liked ? "add" : "delete"](track.videoId);
  document.querySelectorAll(`[data-like="${CSS.escape(track.videoId)}"]`).forEach(b => {
    b.classList.toggle("on", liked); setIcon(b, liked ? "heart" : "heartOutline");
  });
  if (S.state?.current?.videoId === track.videoId) renderPlayerBar();
  renderNowPlayingControls();
  await act("like", { track: clean(track), liked }, liked ? "Added to Liked songs" : "Removed from Liked songs");
}

const clean = t => { const { qid, plays, playedAt, status, progress, path, error, ...rest } = t; return rest; };
const cleanAll = list => list.map(clean);

/* ============================================================
 * Menus and dialogs
 * ============================================================ */
let menuCleanup = null;
function openMenu(anchor, items, dir = "down", point = null) {
  closeMenu();
  const menu = $("#menu");
  menu.replaceChildren(...items.filter(Boolean).map(it => {
    if (it === "-") return h("hr");
    if (it.heading) return h("div", { class: "menu-label" }, it.label);
    return h("button", { onclick: () => { closeMenu(); it.run(); } }, it.icon ? icon(it.icon) : null, h("span", null, it.label));
  }));
  menu.hidden = false;
  const r = point ? { left: point.x, right: point.x, top: point.y, bottom: point.y } : anchor.getBoundingClientRect();
  const mw = menu.offsetWidth, mh = menu.offsetHeight;
  let x = Math.min(r.left, innerWidth - mw - 8);
  let y = dir === "up" ? r.top - mh - 6 : r.bottom + 4;
  if (y + mh > innerHeight - 8) y = Math.max(8, r.top - mh - 4);
  if (y < 8) y = 8;
  menu.style.left = Math.max(8, x) + "px";
  menu.style.top = y + "px";
  const away = e => { if (!menu.contains(e.target)) closeMenu(); };
  const esc = e => { if (e.key === "Escape") closeMenu(); };
  setTimeout(() => { document.addEventListener("mousedown", away); document.addEventListener("keydown", esc); });
  menuCleanup = () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
}
function closeMenu() { $("#menu").hidden = true; if (menuCleanup) { menuCleanup(); menuCleanup = null; } }

function dialog(title, body, actions) {
  const backdrop = $("#modal-backdrop");
  const close = () => { backdrop.hidden = true; document.removeEventListener("keydown", esc); };
  const esc = e => { if (e.key === "Escape") close(); };
  $("#modal").replaceChildren(h("h3", null, title), body,
    h("div", { class: "btn-row" }, actions.map(a => h("button", {
      class: "btn" + (a.primary ? " primary" : ""), onclick: async () => { if ((await a.run?.()) !== false) close(); },
    }, a.label))));
  backdrop.hidden = false;
  backdrop.onclick = e => { if (e.target === backdrop) close(); };
  document.addEventListener("keydown", esc);
  const input = $("#modal input, #modal textarea");
  if (input) setTimeout(() => input.focus(), 30);
  return close;
}

function promptText(title, value = "", okLabel = "Save") {
  return new Promise(resolve => {
    const input = h("input", { class: "text-input", value, maxlength: "120" });
    let done = false;
    const finish = v => { if (!done) { done = true; resolve(v); } };
    const close = dialog(title, input, [
      { label: "Cancel", run: () => finish(null) },
      { label: okLabel, primary: true, run: () => finish(input.value.trim() || null) },
    ]);
    input.addEventListener("keydown", e => { if (e.key === "Enter") { finish(input.value.trim() || null); close(); } });
  });
}

async function addToPlaylistMenu(anchor, tracks, point) {
  let lists = [];
  try { lists = await call("playlists"); } catch {}
  openMenu(anchor, [
    { label: "Add to playlist", heading: true },
    { label: "New playlist…", icon: "add", run: async () => {
        const name = await promptText("New playlist", "", "Create");
        if (name) { await act("playlist_create", { name, tracks: cleanAll(tracks) }, `Created “${name}”`); refreshSidebar(); }
      } },
    lists.length ? "-" : null,
    ...lists.map(p => ({ label: p.title, icon: "queue", run: () => act("playlist_add", { id: p.id, tracks: cleanAll(tracks) }, `Added to “${p.title}”`).then(refreshSidebar) })),
  ], "down", point);
}

function trackMenu(anchor, track, ctx = {}, point = null) {
  const downloaded = S.downloaded.has(track.videoId);
  openMenu(anchor, [
    { label: "Play next", icon: "playNext", run: () => act("add_next", { tracks: [clean(track)] }, "Playing next") },
    { label: "Add to queue", icon: "queue", run: () => act("add_queue", { tracks: [clean(track)] }, "Added to queue") },
    { label: "Start radio", icon: "radio", run: () => call("play_radio", { track: clean(track) }) },
    "-",
    { label: S.liked.has(track.videoId) ? "Remove from Liked songs" : "Add to Liked songs", icon: S.liked.has(track.videoId) ? "heart" : "heartOutline", run: () => toggleLike(track) },
    { label: "Add to playlist…", icon: "playlistAdd", run: () => addToPlaylistMenu(anchor, [track], point) },
    downloaded
      ? { label: "Remove download", icon: "trash", run: () => act("download_delete", { videoId: track.videoId }, "Download removed").then(refreshDownloadedIds) }
      : { label: "Download", icon: "download", run: () => act("download", { tracks: [clean(track)] }, "Downloading…") },
    "-",
    track.album?.id && { label: "Go to album", icon: "album", run: () => go(`/album/${track.album.id}`) },
    ...(track.artists || []).filter(a => a.id).slice(0, 3).map(a => ({ label: `Go to ${a.name}`, icon: "person", run: () => go(`/artist/${a.id}`) })),
    { label: "Copy link", icon: "link", run: () => copy(`https://music.youtube.com/watch?v=${track.videoId}`) },
    ctx.onRemove && "-",
    ctx.onRemove && { label: ctx.removeLabel || "Remove", icon: "trash", run: ctx.onRemove },
  ], "down", point);
}

function copy(text) {
  navigator.clipboard?.writeText(text).then(() => toast("Link copied"), () => toast(text));
}

/* ============================================================
 * Building blocks: track rows, cards, shelves
 * ============================================================ */
function trackRows(tracks, ctx = {}) {
  // ctx: { title, play: (index) => void, numbered, compact, onRemove(index), removeLabel }
  const play = ctx.play || (i => call("play_tracks", { tracks: cleanAll(tracks), index: i, title: ctx.title || "" }));
  return h("div", { class: "tracks" }, tracks.map((t, i) => {
    const likeBtn = h("button", { class: "icon-btn like" + (S.liked.has(t.videoId) ? " on" : ""), dataset: { like: t.videoId }, title: "Like",
      onclick: e => { e.stopPropagation(); toggleLike(t); } }, icon(S.liked.has(t.videoId) ? "heart" : "heartOutline"));
    const lead = ctx.numbered
      ? h("div", { class: "t-lead" }, h("span", { class: "num" }, i + 1), h("div", { class: "t-overlay" }, icon("play")))
      : h("div", { class: "t-lead" }, img(t.thumbnail), h("div", { class: "t-overlay" }, icon("play")));
    const rowCtx = { onRemove: ctx.onRemove && (() => ctx.onRemove(i)), removeLabel: ctx.removeLabel };
    const row = h("div", {
      class: "track" + (ctx.compact ? " compact" : ""), dataset: { vid: t.videoId },
      onmouseenter: () => hoverPrefetch(t.videoId), onmouseleave: cancelHoverPrefetch,
      ondblclick: () => play(i),
      oncontextmenu: e => { e.preventDefault(); trackMenu(row, t, rowCtx, { x: e.clientX, y: e.clientY }); },
    },
      lead,
      h("div", { class: "t-main" },
        h("div", { class: "t-title" }, h("span", { title: t.title }, t.title),
          t.explicit ? h("span", { class: "badge", title: "Explicit" }, "E") : null,
          S.downloaded.has(t.videoId) ? h("span", { class: "badge dl", title: "Downloaded" }, "↓") : null),
        h("div", { class: "t-sub" }, artistLinks(t), t.isVideo ? h("span", { class: "faint" }, " • Video") : null)),
      ctx.compact ? null : h("div", { class: "t-album" }, t.album?.id
        ? h("span", { class: "link", onclick: () => go(`/album/${t.album.id}`) }, t.album.name) : (t.album?.name || "")),
      h("div", { class: "t-dur" }, t.duration ? fmt(t.duration) : ""),
      likeBtn,
      h("button", { class: "icon-btn", title: "More", onclick: e => { e.stopPropagation(); trackMenu(e.currentTarget, t, rowCtx); } }, icon("more")),
    );
    lead.querySelector(".t-overlay").addEventListener("click", () => play(i));
    return row;
  }));
}

/* Start resolving a song while the pointer rests on it: by the time it's clicked it's often ready. */
let hoverTimer = null;
const prefetched = new Set();
function hoverPrefetch(videoId, delay = 250) {
  clearTimeout(hoverTimer);
  if (prefetched.has(videoId) || S.downloaded.has(videoId)) return;
  const go = () => { prefetched.add(videoId); call("prefetch", { videoIds: [videoId] }).catch(() => {}); };
  if (delay) hoverTimer = setTimeout(go, delay); else go();
}
function cancelHoverPrefetch() { clearTimeout(hoverTimer); }

function markPlayingRows() {
  const vid = S.state?.current?.videoId;
  document.querySelectorAll(".track").forEach(r => {
    const on = r.dataset.vid === vid;
    r.classList.toggle("playing", on);
    const lead = r.querySelector(".t-lead");
    const playing = lead.querySelector(".t-playing");
    if (on && !playing) lead.append(h("div", { class: "t-playing" }, h("div", { class: "eq" }, h("i"), h("i"), h("i"))));
    if (!on && playing) playing.remove();
  });
}

function cardFor(item) {
  if (item.type === "song") {
    return h("div", { class: "card song", onclick: () => call("play_radio", { track: clean(item) }),
      onmouseenter: () => hoverPrefetch(item.videoId), onmouseleave: cancelHoverPrefetch,
      oncontextmenu: e => { e.preventDefault(); trackMenu(e.currentTarget, item, {}, { x: e.clientX, y: e.clientY }); } },
      h("div", { class: "card-art" }, img(item.thumbnail), h("div", { class: "card-play" }, icon("play"))),
      h("div", { class: "card-title", title: item.title }, item.title),
      h("div", { class: "card-sub" }, (item.isVideo ? "Video • " : "Song • ") + (item.artist || "")));
  }
  const path = item.type === "album" ? `/album/${item.id}` : item.type === "artist" ? `/artist/${item.id}`
    : `/playlist/${encodeURIComponent(item.id)}?t=${encodeURIComponent(item.title || "")}`;
  const playBtn = h("div", { class: "card-play", title: "Play", onclick: e => { e.stopPropagation(); playCollection(item); } }, icon("play"));
  return h("div", { class: `card ${item.type === "local-playlist" ? "playlist" : item.type}`, onclick: () => go(path),
    oncontextmenu: e => { e.preventDefault(); collectionMenu(e.currentTarget, item, { x: e.clientX, y: e.clientY }); } },
    h("div", { class: "card-art" }, img(item.thumbnail, "", item.type === "artist" ? "person" : item.type === "album" ? "album" : "queue"), playBtn),
    h("div", { class: "card-title", title: item.title }, item.title),
    item.subtitle ? h("div", { class: "card-sub" }, item.subtitle) : null);
}

async function loadCollection(item) {
  if (item.type === "album") return (await call("album", { id: item.id })).tracks;
  if (item.type === "artist") return (await call("artist", { id: item.id })).songs;
  return (await call("playlist", { id: item.id, title: item.title })).tracks;
}

async function playCollection(item, shuffle = false) {
  try {
    if (item.type === "playlist" && isMixId(item.id)) return call("play_playlist_radio", { playlist_id: item.id, title: item.title });
    const tracks = await loadCollection(item);
    if (!tracks.length) return toast("Nothing to play here");
    await call("play_tracks", { tracks: cleanAll(tracks), title: item.title, shuffle });
  } catch (e) { toast(e.message, "error"); }
}

const isMixId = id => /^RD/.test(id) && !/^RDCLAK/.test(id);

function collectionMenu(anchor, item, point) {
  const saveable = ["album", "artist", "playlist"].includes(item.type);
  openMenu(anchor, [
    { label: "Play", icon: "play", run: () => playCollection(item) },
    item.type !== "artist" && { label: "Shuffle", icon: "shuffle", run: () => playCollection(item, true) },
    { label: "Play next", icon: "playNext", run: async () => act("add_next", { tracks: cleanAll(await loadCollection(item)) }, "Playing next") },
    { label: "Add to queue", icon: "queue", run: async () => act("add_queue", { tracks: cleanAll(await loadCollection(item)) }, "Added to queue") },
    { label: "Download all", icon: "download", run: async () => act("download", { tracks: cleanAll(await loadCollection(item)) }, "Downloading…") },
    saveable && "-",
    saveable && { label: "Save to library", icon: "libraryAdd", run: () => act("save", { item, saved: true }, "Saved to library") },
  ], "down", point);
}

function shelfEl(shelf, grid = false) {
  return h("section", null,
    shelf.title ? h("h2", { class: "shelf-title" }, shelf.title) : null,
    h("div", { class: grid ? "grid" : "shelf" }, shelf.items.map(cardFor)));
}

function pageHead(page, { kind, actions, artistLinksFor }) {
  const desc = page.description ? h("div", { class: "desc", title: "Click to expand", onclick: e => e.currentTarget.classList.toggle("open") }, page.description) : null;
  return h("div", { class: "page-head " + (page.type || "") },
    h("div", { class: "art" }, img(page.thumbnail, "", page.type === "artist" ? "person" : "album")),
    h("div", { style: "min-width:0" },
      h("div", { class: "kind" }, kind),
      h("h1", null, page.title || ""),
      artistLinksFor ? h("div", { class: "muted", style: "font-weight:600;margin-bottom:4px" }, artistLinks(artistLinksFor)) : null,
      h("div", { class: "muted" }, page.subtitle || ""),
      desc,
      h("div", { class: "btn-row", style: "margin-top:16px" }, actions)));
}

function saveButton(page) {
  let saved = !!page.saved;
  const btn = h("button", { class: "btn" });
  const paint = () => btn.replaceChildren(icon(saved ? "libraryCheck" : "libraryAdd"), saved ? "Saved" : "Save");
  paint();
  btn.onclick = async () => {
    saved = !saved; paint();
    await act("save", { item: { type: page.type, id: page.id, title: page.title, subtitle: page.subtitle, thumbnail: page.thumbnail }, saved },
      saved ? "Saved to library" : "Removed from library");
    refreshSidebar();
  };
  return btn;
}

/* ============================================================
 * Router & views
 * ============================================================ */
const view = $("#view");
let routeToken = 0;

function go(path) { if (location.hash !== "#" + path) location.hash = path; else route(); }

function loading() { view.replaceChildren(h("div", { class: "center-msg" }, h("div", { class: "spinner" }))); }

function errorView(err, retry) {
  view.replaceChildren(h("div", { class: "center-msg" },
    h("div", { style: "font-size:18px;font-weight:600" }, "Something went wrong"),
    h("div", { class: "faint", style: "max-width:560px" }, err.message || String(err)),
    h("button", { class: "btn", onclick: retry }, "Try again")));
}

async function route() {
  closeMenu();
  const token = ++routeToken;
  const hash = location.hash.slice(1) || "/home";
  const [path, qs] = hash.split("?");
  const query = new URLSearchParams(qs || "");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  const [name, arg] = parts;
  document.querySelectorAll(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.route === name));
  if (name !== "search") $("#search").value = "";
  view.classList.toggle("np-mode", name === "nowplaying");
  view.scrollTop = 0;
  const views = { home: homeView, explore: exploreView, search: searchView, album: albumView, artist: artistView,
    playlist: playlistView, mood: moodView, library: libraryView, downloads: downloadsView, settings: settingsView, cache: cacheView,
    nowplaying: nowPlayingView };
  const fn = views[name] || homeView;
  loading();
  try {
    const content = await fn(arg, query, () => token === routeToken);
    if (token !== routeToken) return;
    if (content) view.replaceChildren(content);
    markPlayingRows();
  } catch (err) {
    if (token === routeToken) errorView(err, route);
  }
}

async function homeView() {
  const shelves = await call("home");
  return h("div", null, h("h1", { class: "page-title" }, greeting()), shelves.map(s => shelfEl(s)));
}

function greeting() {
  const hr = new Date().getHours();
  return hr < 5 ? "Good night" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}

async function exploreView() {
  const data = await call("explore");
  return h("div", null,
    h("h1", { class: "page-title" }, "Explore"),
    data.shelves.map(s => shelfEl(s)),
    data.moods.map(group => h("section", null,
      h("h2", { class: "shelf-title" }, group.title),
      h("div", { class: "mood-grid" }, group.items.map(m =>
        h("button", { class: "mood", onclick: () => go(`/mood/${encodeURIComponent(m.params)}?t=${encodeURIComponent(m.title)}`) }, m.title))))));
}

async function moodView(params, query) {
  const title = query.get("t") || "Mood";
  const data = await call("mood", { params, title });
  return h("div", null, h("h1", { class: "page-title" }, title), h("div", { class: "grid" }, data.items.map(cardFor)));
}

const SEARCH_FILTERS = [["", "All"], ["songs", "Songs"], ["videos", "Videos"], ["albums", "Albums"], ["artists", "Artists"], ["playlists", "Playlists"]];

async function searchView(_, query) {
  const q = query.get("q") || "";
  const kind = query.get("f") || "";
  $("#search").value = q;
  if (!q) return h("div", { class: "center-msg" }, icon("search", 48), h("div", null, "Search for songs, albums, artists and playlists"));
  const chips = h("div", { class: "chips" }, SEARCH_FILTERS.map(([k, label]) =>
    h("button", { class: "chip" + (k === kind ? " active" : ""), onclick: () => go(`/search?q=${encodeURIComponent(q)}${k ? "&f=" + k : ""}`) }, label)));
  const res = await call("search", { query: q, kind });
  // get the most likely click ready in the background
  const likely = res.top?.type === "song" ? res.top : res.songs[0];
  if (likely) hoverPrefetch(likely.videoId, 0);
  const out = h("div", null, chips);
  if (!res.top && !res.songs.length && !res.cards.length) {
    out.append(h("div", { class: "center-msg" }, `No results for “${q}”`));
    return out;
  }
  if (res.top || res.songs.length) {
    const top = res.top;
    const topCard = top && (top.type === "song"
      ? h("div", { class: "top-card", onclick: () => call("play_radio", { track: clean(top) }) },
          img(top.thumbnail), h("div", { class: "tt" }, top.title), h("div", { class: "muted" }, (top.isVideo ? "Video • " : "Song • ") + top.artist),
          h("div", null, h("button", { class: "btn primary", onclick: e => { e.stopPropagation(); call("play_radio", { track: clean(top) }); } }, icon("play"), "Play")))
      : h("div", { class: "top-card " + top.type, onclick: () => cardFor(top).click() },
          img(top.thumbnail, "", top.type === "artist" ? "person" : "album"), h("div", { class: "tt" }, top.title), h("div", { class: "muted" }, top.subtitle),
          h("div", null, h("button", { class: "btn primary", onclick: e => { e.stopPropagation(); playCollection(top); } }, icon("play"), top.type === "artist" ? "Shuffle" : "Play"))));
    const songs = kind ? res.songs : res.songs.slice(0, 6);
    out.append(h("div", { class: kind || !topCard ? "" : "top-result" },
      topCard ? h("div", null, h("h2", { class: "shelf-title" }, "Top result"), topCard) : null,
      songs.length ? h("div", { style: "min-width:0" }, h("h2", { class: "shelf-title" }, kind === "videos" ? "Videos" : "Songs"),
        trackRows(songs, { compact: !kind, play: i => call("play_radio", { track: clean(songs[i]) }) })) : null));
  }
  if (res.cards.length) {
    if (kind) out.append(h("div", { class: "grid", style: "margin-top:12px" }, res.cards.map(cardFor)));
    else {
      for (const [type, title] of [["artist", "Artists"], ["album", "Albums"], ["playlist", "Playlists"]]) {
        const items = res.cards.filter(c => c.type === type);
        if (items.length) out.append(shelfEl({ title, items }));
      }
    }
  }
  return out;
}

async function albumView(id) {
  const a = await call("album", { id });
  if (a.tracks[0]) hoverPrefetch(a.tracks[0].videoId, 0);
  const play = (shuffle = false) => call("play_tracks", { tracks: cleanAll(a.tracks), title: a.title, shuffle });
  return h("div", null,
    pageHead(a, { kind: "Album", artistLinksFor: { artists: a.artists }, actions: [
      h("button", { class: "btn primary", onclick: () => play() }, icon("play"), "Play"),
      h("button", { class: "btn", onclick: () => play(true) }, icon("shuffle"), "Shuffle"),
      saveButton(a),
      h("button", { class: "btn", onclick: () => act("download", { tracks: cleanAll(a.tracks) }, "Downloading album…") }, icon("download"), "Download"),
      h("button", { class: "icon-btn", title: "More", onclick: e => openMenu(e.currentTarget, [
        { label: "Play next", icon: "playNext", run: () => act("add_next", { tracks: cleanAll(a.tracks) }, "Playing next") },
        { label: "Add to queue", icon: "queue", run: () => act("add_queue", { tracks: cleanAll(a.tracks) }, "Added to queue") },
        { label: "Add to playlist…", icon: "playlistAdd", run: () => addToPlaylistMenu(e.target, a.tracks) },
        { label: "Copy link", icon: "link", run: () => copy(`https://music.youtube.com/browse/${a.id}`) },
      ]) }, icon("more")),
    ] }),
    trackRows(a.tracks, { title: a.title, numbered: true }),
    a.related?.length ? shelfEl({ title: "Other versions", items: a.related }) : null);
}

async function artistView(id) {
  const a = await call("artist", { id });
  const actions = [
    a.songs.length ? h("button", { class: "btn primary", onclick: () => call("play_tracks", { tracks: cleanAll(a.songs), title: a.title, shuffle: true }) }, icon("shuffle"), "Shuffle") : null,
    a.radioId ? h("button", { class: "btn", onclick: () => call("play_playlist_radio", { playlist_id: a.radioId, title: `${a.title} radio` }) }, icon("radio"), "Radio") : null,
    saveButton(a),
  ];
  return h("div", null,
    pageHead(a, { kind: "Artist", actions }),
    a.songs.length ? h("section", null,
      h("h2", { class: "shelf-title" }, "Top songs",
        a.songsPlaylistId ? h("button", { class: "btn small", onclick: () => go(`/playlist/${encodeURIComponent(a.songsPlaylistId)}?t=${encodeURIComponent(a.title + " – songs")}`) }, "See all") : null),
      trackRows(a.songs, { title: a.title })) : null,
    a.shelves.map(s => shelfEl(s)));
}

async function playlistView(id, query) {
  const local = /^\d+$/.test(id);
  const p = await call("playlist", { id, title: query.get("t") || "" });
  const title = p.title || query.get("t") || "Playlist";
  const play = (shuffle = false) => call("play_tracks", { tracks: cleanAll(p.tracks), title, shuffle });
  const actions = [
    h("button", { class: "btn primary", onclick: () => play() }, icon("play"), "Play"),
    h("button", { class: "btn", onclick: () => play(true) }, icon("shuffle"), "Shuffle"),
    local ? null : saveButton({ ...p, title }),
    h("button", { class: "btn", onclick: () => act("download", { tracks: cleanAll(p.tracks) }, "Downloading playlist…") }, icon("download"), "Download"),
  ];
  if (local) {
    actions.push(h("button", { class: "icon-btn", title: "More", onclick: e => openMenu(e.currentTarget, [
      { label: "Rename", icon: "edit", run: async () => {
          const name = await promptText("Rename playlist", title);
          if (name) { await act("playlist_rename", { id, name }); refreshSidebar(); route(); }
        } },
      { label: "Delete playlist", icon: "trash", run: () => dialog("Delete playlist?", h("p", { class: "muted" }, `“${title}” will be removed. Songs stay in your library.`), [
          { label: "Cancel" },
          { label: "Delete", primary: true, run: async () => { await act("playlist_delete", { id }, "Playlist deleted"); refreshSidebar(); go("/library/playlists"); } },
        ]) },
    ]) }, icon("more")));
  }
  return h("div", null,
    pageHead({ ...p, title }, { kind: local ? "Your playlist" : "Playlist", actions }),
    p.tracks.length ? trackRows(p.tracks, {
      title,
      onRemove: local ? async i => { await act("playlist_remove", { id, index: i }, "Removed from playlist"); route(); refreshSidebar(); } : null,
      removeLabel: "Remove from this playlist",
    }) : h("div", { class: "center-msg" }, "This playlist is empty. Add songs from their ⋮ menu."));
}

async function libraryView(tab = "liked") {
  const tabs = [["liked", "Liked songs"], ["playlists", "Playlists"], ["saved", "Saved"], ["history", "History"], ["stats", "Stats"], ["account", "YouTube Music"]];
  const head = h("div", null, h("h1", { class: "page-title" }, "Library"),
    h("div", { class: "tabs" }, tabs.map(([k, label]) => h("button", { class: k === tab ? "active" : "", onclick: () => go(`/library/${k}`) }, label))));
  const body = h("div");
  const lib = await call("library");
  if (tab === "liked") {
    body.append(lib.liked.length
      ? h("div", null,
          h("div", { class: "btn-row", style: "margin-bottom:14px" },
            h("button", { class: "btn primary", onclick: () => call("play_tracks", { tracks: cleanAll(lib.liked), title: "Liked songs" }) }, icon("play"), "Play"),
            h("button", { class: "btn", onclick: () => call("play_tracks", { tracks: cleanAll(lib.liked), title: "Liked songs", shuffle: true }) }, icon("shuffle"), "Shuffle"),
            h("button", { class: "btn", onclick: () => act("download", { tracks: cleanAll(lib.liked) }, "Downloading…") }, icon("download"), "Download all"),
            h("span", { class: "faint" }, `${lib.liked.length} songs`)),
          trackRows(lib.liked, { title: "Liked songs" }))
      : h("div", { class: "center-msg" }, icon("heartOutline", 44), "Songs you like appear here."));
  } else if (tab === "playlists") {
    const newCard = h("div", { class: "card", onclick: async () => {
        const name = await promptText("New playlist", "", "Create");
        if (name) { const id = await act("playlist_create", { name }); refreshSidebar(); go(`/playlist/${id}`); }
      } },
      h("div", { class: "card-art", style: "display:grid;place-items:center;border:2px dashed var(--line);background:none" }, icon("add", 48)),
      h("div", { class: "card-title" }, "New playlist"));
    body.append(h("div", { class: "grid" }, newCard, lib.playlists.map(cardFor)));
  } else if (tab === "saved") {
    body.append(lib.saved.length ? h("div", { class: "grid" }, lib.saved.map(cardFor))
      : h("div", { class: "center-msg" }, icon("libraryAdd", 44), "Albums, artists and playlists you save appear here."));
  } else if (tab === "history") {
    const items = await call("history");
    body.append(items.length
      ? h("div", null,
          h("div", { class: "btn-row", style: "margin-bottom:14px" },
            h("button", { class: "btn", onclick: () => dialog("Clear listening history?", h("p", { class: "muted" }, "This also resets your stats."), [
              { label: "Cancel" }, { label: "Clear", primary: true, run: async () => { await act("history_clear"); route(); } }]) }, icon("trash"), "Clear history")),
          trackRows(items, { title: "History" }))
      : h("div", { class: "center-msg" }, icon("history", 44), "Nothing played yet."));
  } else if (tab === "stats") {
    body.append(await statsBlock());
  } else if (tab === "account") {
    body.append(await accountLibraryBlock(lib.account));
  }
  return h("div", null, head, body);
}

async function statsBlock() {
  const st = await call("stats", { days: 30 });
  if (!st.plays) return h("div", { class: "center-msg" }, icon("stats", 44), "Play some music and your stats will show up here.");
  const maxA = Math.max(...st.artists.map(a => a.plays), 1);
  return h("div", null,
    h("div", { class: "stat-tiles" },
      h("div", { class: "stat-tile" }, h("div", { class: "v" }, st.plays), h("div", { class: "l" }, "plays in the last 30 days")),
      h("div", { class: "stat-tile" }, h("div", { class: "v" }, st.minutes), h("div", { class: "l" }, "minutes listened")),
      h("div", { class: "stat-tile" }, h("div", { class: "v" }, st.artists.length), h("div", { class: "l" }, "artists"))),
    h("h2", { class: "shelf-title" }, "Top artists"),
    h("div", { class: "bar-list" }, st.artists.map(a => h("div", { class: "bar-row" },
      h("span", { class: a.id ? "link" : "", onclick: () => a.id && go(`/artist/${a.id}`), style: "white-space:nowrap;overflow:hidden;text-overflow:ellipsis" }, a.name),
      h("div", null, h("div", { class: "bar", style: `width:${(a.plays / maxA) * 100}%` })),
      h("span", { class: "faint" }, a.plays)))),
    h("h2", { class: "shelf-title" }, "Top songs"),
    trackRows(st.songs, { title: "Your top songs" }));
}

async function accountLibraryBlock(signedIn) {
  if (!signedIn) {
    return h("div", { class: "center-msg" }, icon("person", 44),
      h("div", null, "Sign in to see your YouTube Music likes and playlists."),
      h("button", { class: "btn primary", onclick: () => go("/settings") }, "Sign in in Settings"));
  }
  const data = await call("account_library");
  return h("div", null,
    data.playlists.length ? shelfEl({ title: "Your playlists", items: data.playlists }) : null,
    h("h2", { class: "shelf-title" }, "Liked on YouTube Music",
      data.liked.length ? h("button", { class: "btn small", onclick: () => call("play_tracks", { tracks: cleanAll(data.liked), title: "Liked on YouTube Music", shuffle: true }) }, "Shuffle") : null),
    trackRows(data.liked, { title: "Liked on YouTube Music" }));
}

async function downloadsView() {
  const d = await call("downloads");
  const done = d.items.filter(x => x.status === "done");
  const head = h("div", null,
    h("h1", { class: "page-title" }, "Downloads"),
    h("div", { class: "btn-row", style: "margin-bottom:16px" },
      done.length ? h("button", { class: "btn primary", onclick: () => call("play_tracks", { tracks: cleanAll(done), title: "Downloads" }) }, icon("play"), "Play all") : null,
      done.length ? h("button", { class: "btn", onclick: () => call("play_tracks", { tracks: cleanAll(done), title: "Downloads", shuffle: true }) }, icon("shuffle"), "Shuffle") : null,
      h("button", { class: "btn", onclick: () => call("open_downloads") }, icon("folder"), "Open folder"),
      h("span", { class: "faint" }, d.folder)),
    d.ffmpeg ? null : h("div", { class: "notice", style: "margin-bottom:16px" },
      "Install ffmpeg to have downloads tagged with title, artist and cover art. Files still play without it."));
  if (!d.items.length) return h("div", null, head, h("div", { class: "center-msg" }, icon("download", 44), "Downloaded songs play offline and appear here."));
  const rows = d.items.map(item => {
    const status = item.status === "done" ? null
      : h("div", { class: "faint", style: "font-size:12px" },
          item.status === "error" ? h("span", { style: "color:#e5484d" }, "Failed: " + (item.error || "")) : item.status === "queued" ? "Waiting…" : `Downloading ${Math.round(item.progress * 100)}%`,
          item.status === "downloading" ? h("div", { class: "progress" }, h("i", { style: `width:${Math.round(item.progress * 100)}%` })) : null);
    const row = trackRows([item], { title: "Downloads", compact: true, play: () => call("play_tracks", { tracks: cleanAll(done), index: Math.max(0, done.findIndex(x => x.videoId === item.videoId)), title: "Downloads" }) }).firstChild;
    if (status) row.querySelector(".t-main").append(status);
    const del = h("button", { class: "icon-btn", title: item.status === "done" ? "Delete file" : "Cancel", onclick: async () => { await act("download_delete", { videoId: item.videoId }); refreshDownloadedIds(); route(); } }, icon("trash"));
    row.replaceChild(del, row.lastChild);
    return row;
  });
  return h("div", null, head, h("div", { class: "tracks" }, rows));
}

/* ---------- cache ---------- */
function fmtBytes(n) {
  if (!n) return "0 MB";
  return n > 1e9 ? `${(n / 1e9).toFixed(1)} GB` : `${Math.max(1, Math.round(n / 1e6))} MB`;
}

async function cacheView() {
  const c = await call("cache");
  const limitSelect = selectInput(String(c.limit), [["25", "25 songs"], ["50", "50 songs"], ["100", "100 songs"], ["200", "200 songs"]],
    v => saveSetting({ cache_songs: Number(v) }).then(route));
  const head = h("div", null,
    h("h1", { class: "page-title" }, "Cache"),
    h("p", { class: "muted", style: "max-width:720px;margin-top:-8px" },
      "Your most recently played songs are kept on this computer, so they start instantly and keep working when you're offline."),
    h("div", { class: "btn-row", style: "margin:14px 0 18px" },
      c.items.length ? h("button", { class: "btn primary", onclick: () => call("play_tracks", { tracks: cleanAll(c.items), title: "Cache" }) }, icon("play"), "Play") : null,
      c.items.length ? h("button", { class: "btn", onclick: () => call("play_tracks", { tracks: cleanAll(c.items), title: "Cache", shuffle: true }) }, icon("shuffle"), "Shuffle") : null,
      h("span", { class: "faint" }, `${c.count} songs • ${fmtBytes(c.bytes)}`),
      h("span", { style: "flex:1" }),
      h("span", { class: "muted" }, "Keep"), limitSelect,
      switchInput(c.enabled, v => saveSetting({ cache_enabled: v }).then(route)),
      c.items.length ? h("button", { class: "btn small", onclick: () => dialog("Clear the cache?", h("p", { class: "muted" }, "Cached songs will need the internet again. Your downloads aren't affected."),
        [{ label: "Cancel" }, { label: "Clear", primary: true, run: async () => { await act("cache_clear", {}, "Cache cleared"); route(); } }]) }, icon("trash"), "Clear") : null));
  if (!c.enabled) return h("div", null, head, h("div", { class: "center-msg" }, icon("history", 44), "The cache is turned off."));
  if (!c.items.length) return h("div", null, head, h("div", { class: "center-msg" }, icon("history", 44), "Songs you play are cached here automatically."));
  return h("div", null, head, trackRows(c.items, { title: "Cache" }));
}

/* ---------- settings ---------- */
const loginWatch = { onEvent: null };   // the open Settings page listens for browser sign-in results

function switchInput(checked, onchange) {
  const input = h("input", { type: "checkbox" });
  input.checked = !!checked;
  input.addEventListener("change", () => onchange(input.checked));
  return h("label", { class: "switch" }, input, h("span"));
}

function selectInput(value, options, onchange) {
  const sel = h("select", null, options.map(([v, label]) => h("option", { value: v }, label)));
  sel.value = value;
  sel.addEventListener("change", () => onchange(sel.value));
  return sel;
}

function setRow(label, hint, control) {
  return h("div", { class: "set-row" }, h("div", null, h("div", { class: "lbl" }, label), hint ? h("div", { class: "hint" }, hint) : null), control);
}

async function saveSetting(patch) {
  try {
    const res = await call("settings_set", { patch });
    S.settings = res.settings;
    applyTheme();
    if (res.restartRequired) toast("Restart the app to switch the audio engine");
    else toast("Saved");
  } catch (e) { toast(e.message, "error"); }
}

async function settingsView() {
  const [settings, about, account] = await Promise.all([call("settings"), call("about"), call("account")]);
  S.settings = settings; S.about = about;
  const set = (key) => v => saveSetting({ [key]: v });

  const accountBlock = account.signedIn
    ? h("div", { class: "set-row" },
        h("div", { style: "display:flex;gap:12px;align-items:center" },
          account.photo ? h("img", { class: "avatar", src: account.photo, referrerpolicy: "no-referrer" }) : icon("person"),
          h("div", null, h("div", { class: "lbl" }, account.name || "Signed in"), h("div", { class: "hint" }, account.handle || account.error || ""))),
        h("button", { class: "btn", onclick: async () => { await act("logout", {}, "Signed out"); renderAccountChip(); route(); } }, "Sign out"))
    : (() => {
        const ta = h("textarea", { class: "text-input", placeholder: "Paste the request headers here…" });
        const signedIn = info => { toast(`Signed in as ${info?.name || "you"}`); renderAccountChip(); route(); };
        const status = h("div", { class: "login-status", hidden: true });
        const showWaiting = label => {
          status.hidden = false;
          status.replaceChildren(h("div", { class: "spinner small" }),
            h("div", null, h("div", { class: "lbl" }, `Finish signing in in ${label}`),
              h("div", { class: "hint" }, `Google's sign-in page opened in ${label}. ClefTune signs in by itself as soon as you're done there.`)),
            h("button", { class: "btn small", onclick: () => { call("login_cancel"); status.hidden = true; } }, "Cancel"));
        };
        const start = async (btn, browserId = "") => {
          btn.disabled = true;
          try {
            const res = await call("login_start", { browser: browserId });
            if (res.status === "signed-in") signedIn(res); else showWaiting(res.browser);
          } catch (err) { toast(err.message, "error"); }
          btn.disabled = false;
        };
        loginWatch.onEvent = ev => {
          if (ev.status === "signed-in") signedIn(ev);
          else { status.hidden = true; if (ev.message) toast(ev.message, "error"); }
        };
        const primary = h("button", { class: "btn primary google", onclick: e => start(e.currentTarget) }, icon("person"), "Sign in with Google");
        const browsersRow = h("div", { class: "btn-row" }, h("span", { class: "faint" }, "Looking for browsers…"));
        call("login_browsers").then(list => {
          const def = list.find(b => b.default) || list[0];
          if (def) primary.replaceChildren(icon("person"), "Sign in with Google", h("span", { class: "via" }, `via ${def.label}`));
          else primary.disabled = true;
          const others = list.filter(b => b !== def);
          browsersRow.replaceChildren(...(others.length
            ? [h("span", { class: "faint" }, "Or use:"), ...others.map(b => h("button", { class: "btn small", onclick: e => start(e.currentTarget, b.id) }, b.label))]
            : list.length ? [] : [h("span", { class: "faint" }, "No supported browser found. Use the advanced option below.")]));
        }).catch(() => browsersRow.replaceChildren());
        const advanced = h("details", { class: "advanced" },
          h("summary", null, "Advanced: paste request headers"),
          h("ol", { class: "steps" },
            h("li", null, "Open music.youtube.com in your browser and sign in."),
            h("li", null, "Press F12 → Network tab, then click Library or Home."),
            h("li", null, "Pick a request named “browse”, and copy its Request Headers."),
            h("li", null, "Paste below and press Sign in.")),
          ta,
          h("div", { class: "btn-row", style: "margin-top:10px" },
            h("button", { class: "btn", onclick: async () => {
              try { const info = await call("login", { headers: ta.value }); toast(`Signed in as ${info.name || "you"}`); renderAccountChip(); route(); }
              catch (e) { toast(e.message, "error"); }
            } }, "Sign in")));
        return h("div", { class: "set-row", style: "flex-direction:column;align-items:stretch;gap:12px" },
          h("div", null,
            h("div", { class: "lbl" }, "Sign in to YouTube Music (optional)"),
            h("div", { class: "hint" }, "Brings your YouTube Music likes, playlists and history into ClefTune. Your login stays on this computer.")),
          h("div", { class: "hint" }, "Signs in through your web browser, so Google sees a normal, trusted sign-in. If you're already signed in to YouTube there, it takes a second."),
          h("div", { class: "btn-row" }, primary), browsersRow, status,
          advanced);
      })();

  const uiSelect = selectInput(settings.ui_mode, [["window", "Its own window"], ["browser", "My web browser"]], async mode => {
    try {
      const res = await call("set_ui_mode", { mode });
      if (!res.ok) { uiSelect.value = settings.ui_mode; dialog("Separate window not installed", h("p", { class: "muted" }, res.message), [{ label: "OK", primary: true }]); return; }
      settings.ui_mode = mode;
      if (mode === "window" && about.window === "browser") toast("Opened in its own window. You can close this browser tab.");
      else toast(mode === "window" ? "Using its own window" : "Opened in your web browser");
    } catch (e) { toast(e.message, "error"); uiSelect.value = settings.ui_mode; }
  });
  const engineBox = h("div", { class: "faint" }, "…");
  call("engine_status").then(st => engineBox.replaceChildren(
    `yt-dlp ${st.version}${st.updated ? " (updated)" : " (bundled)"}${st.staged && st.staged !== st.version ? ` • ${st.staged} ready after restart` : ""}`)).catch(() => {});
  const engineButtons = h("div", { class: "btn-row", style: "margin-top:10px" },
    h("button", { class: "btn small", onclick: async e => {
      const btn = e.currentTarget; btn.disabled = true; btn.textContent = "Checking…";
      try { const r = await call("engine_update"); toast(r.message); route(); }
      catch (err) { toast(err.message, "error"); btn.disabled = false; btn.textContent = "Update YouTube engine"; }
    } }, "Update YouTube engine"),
    h("button", { class: "btn small", onclick: () => act("engine_reset").then(r => { toast(r.message); route(); }) }, "Use bundled engine"));

  return h("div", null,
    h("h1", { class: "page-title" }, "Settings"),
    h("div", { class: "settings" },
      h("div", { class: "set-group" }, h("h2", null, "Window"),
        setRow("Open ClefTune in", about.windowAvailable
          ? "Switch any time. Audio follows the window you choose."
          : `The separate window isn't installed, so it opens in your browser. ${about.windowHint}`, uiSelect),
        setRow("Keep playing when the window is closed", "Closing the window or browser tab doesn't stop the music. Use Quit in the sidebar (or the tray icon) to stop.",
          switchInput(settings.close_to_background, set("close_to_background")))),
      h("div", { class: "set-group" }, h("h2", null, "Playback"),
        setRow("Audio quality", "Higher quality uses more data.", selectInput(settings.audio_quality, [["high", "High (best available)"], ["medium", "Medium (~128 kbps)"], ["low", "Low (data saver)"]], set("audio_quality"))),
        setRow("Audio engine", `Current: ${about.engine}. Native plays inside the app and keeps going with the window closed. Takes effect after restart.`,
          selectInput(settings.engine, [["auto", "Automatic (native)"], ["native", "Native"], ["mpv", "mpv (if installed)"], ["web", "In the window (stops when closed)"]], set("engine"))),
        setRow("Prefer AAC streams", "Use if songs fail with a 'format not supported' error.", switchInput(settings.prefer_m4a, set("prefer_m4a"))),
        setRow("Loudness normalization", "Evens out volume between songs (mpv engine only).", switchInput(settings.normalize, set("normalize"))),
        setRow("Autoplay", "Keep playing similar songs when the queue ends.", switchInput(settings.autoplay, set("autoplay"))),
        setRow("Skip unplayable songs", null, switchInput(settings.skip_on_error, set("skip_on_error"))),
        setRow("Resume where you left off", "Restore the queue on startup.", switchInput(settings.restore_session, set("restore_session")))),
      h("div", { class: "set-group" }, h("h2", null, "Appearance"),
        setRow("Theme", null, selectInput(settings.theme, [["dark", "Dark"], ["light", "Light"], ["system", "System"]], set("theme"))),
        setRow("Colors from album art", "Accent color follows the current song.", switchInput(settings.dynamic_color, v => { saveSetting({ dynamic_color: v }).then(() => applyDynamicColor(S.state?.current?.thumbnail)); }))),
      h("div", { class: "set-group" }, h("h2", null, "Content"),
        setRow("Language", "Language of YouTube Music pages.", selectInput(settings.language, [["en", "English"], ["hi", "हिन्दी"], ["es", "Español"], ["fr", "Français"], ["de", "Deutsch"], ["pt", "Português"], ["it", "Italiano"], ["ja", "日本語"], ["ko", "한국어"], ["ru", "Русский"], ["tr", "Türkçe"], ["ar", "العربية"], ["nl", "Nederlands"], ["ur", "اردو"], ["zh_CN", "中文 (简体)"], ["zh_TW", "中文 (繁體)"]], set("language"))),
        setRow("Region", "Two-letter country code for charts and recommendations (empty = automatic).",
          (() => { const i = h("input", { class: "text-input", value: settings.location, maxlength: "2", style: "width:80px;min-width:0;text-transform:uppercase" });
                   i.addEventListener("change", () => saveSetting({ location: i.value.trim().toUpperCase() })); return i; })())),
      h("div", { class: "set-group" }, h("h2", null, "Downloads"),
        setRow("Download folder", "Leave empty for Music/ClefTune.",
          (() => { const i = h("input", { class: "text-input", value: settings.download_dir, placeholder: "Music/ClefTune", style: "width:280px" });
                   i.addEventListener("change", () => saveSetting({ download_dir: i.value.trim() })); return i; })())),
      h("div", { class: "set-group" }, h("h2", null, "Account"),
        accountBlock,
        account.signedIn ? setRow("Use account for playback", "Needed for age-restricted songs and Premium audio quality.", switchInput(settings.use_account_for_playback, set("use_account_for_playback"))) : null),
      h("div", { class: "set-group" }, h("h2", null, "About"),
        h("div", { class: "set-row", style: "display:block" },
          h("div", { class: "kv" },
            ...[["Version", about.version], ["Audio engine", about.engine], ["Showing in", about.window === "window" ? "its own window" : "web browser"],
              ["Separate window", about.windowAvailable ? "installed" : "not installed"], ["JavaScript runtime", about.jsRuntime || "none found, some songs may fail"],
              ["ffmpeg", about.ffmpeg ? "found" : "not found"], ["Media keys (MPRIS)", about.mpris ? "on" : "off"], ["yt-dlp", about.ytdlp], ["ytmusicapi", about.ytmusicapi],
              ["Python", about.python], ["System", about.os]].flatMap(([k, v]) => [h("div", { class: "k" }, k), h("div", null, String(v ?? ""))])),
          h("div", { class: "btn-row", style: "margin-top:14px" },
            h("button", { class: "btn small", onclick: () => act("clear_cache", {}, "Cache cleared") }, "Clear cache"))),
        h("div", { class: "set-row", style: "flex-direction:column;align-items:stretch" },
          h("div", { class: "lbl" }, "YouTube engine"),
          h("div", { class: "hint" }, "If songs stop loading, YouTube probably changed something. Updating the engine usually fixes it without reinstalling."),
          engineBox, engineButtons),
        h("div", { class: "notice", style: "margin-top:12px" },
          "Unofficial client, not affiliated with YouTube, Google or the Metrolist Android project. For personal use; respect YouTube's Terms of Service and artists' rights."))));
}

/* ---------- now playing ---------- */
const bigArt = src => src?.replace(/=w\d+-h\d+/, "=w1080-h1080");

async function nowPlayingView() {
  const cur = S.state?.current;
  if (!cur) return h("div", { class: "center-msg" }, icon("note", 44), "Nothing is playing.",
    h("button", { class: "btn", onclick: () => go("/home") }, "Find something to play"));
  const lyricsBox = h("div", { class: "np-right", id: "np-lyrics" }, lyricsSkeleton());
  const btn = (id, ic, title, run) => h("button", { class: "icon-btn", id, title, onclick: run }, icon(ic));
  const seek = h("input", { id: "np-seekbar", type: "range", min: "0", max: "1000", value: "0", "aria-label": "Seek" });
  bindSeekbar(seek, "#np-time");
  const out = h("div", { class: "np" },
    h("div", { class: "np-bg", "aria-hidden": "true" }, cur.thumbnail ? h("img", { src: bigArt(cur.thumbnail), alt: "", referrerpolicy: "no-referrer" }) : null),
    h("div", { class: "np-left" },
      h("div", { class: "np-art" + (S.playing ? "" : " paused"), id: "np-art", title: "Back (Esc)", onclick: () => history.back() }, img(bigArt(cur.thumbnail))),
      h("div", { class: "np-meta" },
        h("div", { class: "np-title" + (cur.album?.id ? " link" : ""), title: cur.album?.id ? `Open the album “${cur.album.name}”` : cur.title,
          onclick: () => cur.album?.id && go(`/album/${cur.album.id}`) }, cur.title),
        h("div", { class: "np-artist" }, artistLinks(cur)),
        cur.album?.name ? h("div", { class: "np-album faint" }, cur.album.name) : null),
      h("div", { class: "np-seek" },
        h("span", { class: "time", id: "np-time" }, fmt(currentPos())), seek, h("span", { class: "time", id: "np-dur" }, fmt(S.dur))),
      h("div", { class: "np-controls" },
        btn("np-shuffle", "shuffle", "Shuffle (S)", () => $("#pb-shuffle").click()),
        btn("np-prev", "prev", "Previous (Shift+←)", () => call("previous")),
        h("button", { class: "play-btn big", id: "np-play", title: "Play/Pause (Space)", onclick: () => call("toggle") }),
        btn("np-next", "next", "Next (Shift+→)", () => call("next")),
        btn("np-repeat", "repeat", "Repeat (R)", () => $("#pb-repeat").click())),
      h("div", { class: "np-actions" },
        h("button", { class: "btn small", id: "np-like", onclick: () => toggleLike(cur) }),
        h("button", { class: "btn small", onclick: e => trackMenu(e.currentTarget, cur) }, icon("more"), "More"),
        h("button", { class: "btn small", onclick: () => togglePanel("queue") }, icon("queue"), "Up next"))),
    h("div", { class: "np-lyrics-col" }, h("div", { class: "lyrics-head-slot" }), lyricsBox));
  ensureLyrics().then(() => { if (S.state?.current?.videoId === cur.videoId) renderLyricsInto(lyricsBox); });
  queueMicrotask(renderNowPlayingControls);
  return out;
}

function lyricsSkeleton() {
  return h("div", { class: "lyrics-skeleton" }, [78, 62, 90, 54, 70, 84, 48].map(w => h("i", { style: `width:${w}%` })));
}

/* keeps the big player's buttons in step with the player bar */
function renderNowPlayingControls() {
  const play = $("#np-play");
  if (!play) return;
  const st = S.state, cur = st?.current;
  const want = st?.loading ? "loading" : S.playing ? "pause" : "play";
  if (play.dataset.mode !== want) {
    play.dataset.mode = want;
    play.replaceChildren(st?.loading ? h("div", { class: "spinner" }) : icon(S.playing ? "pause" : "play", 34));
  }
  $("#np-art")?.classList.toggle("paused", !S.playing);
  $("#np-shuffle")?.classList.toggle("on", !!st?.shuffle);
  const rep = $("#np-repeat");
  if (rep) { setIcon(rep, st?.repeat === "one" ? "repeatOne" : "repeat"); rep.classList.toggle("on", !!st && st.repeat !== "off"); }
  const like = $("#np-like");
  if (like && cur) {
    const liked = S.liked.has(cur.videoId);
    like.classList.toggle("on", liked);
    like.replaceChildren(icon(liked ? "heart" : "heartOutline"), liked ? "Liked" : "Like");
  }
}

function bindSeekbar(bar, timeSel) {
  bar.addEventListener("input", () => {
    S.seeking = true;
    const pct = bar.value / 10;
    bar.style.setProperty("--p", pct + "%");
    $(timeSel).textContent = fmt((pct / 100) * S.dur);
  });
  bar.addEventListener("change", () => {
    const pos = (bar.value / 1000) * S.dur;
    S.pos = pos; S.posAt = performance.now(); S.seeking = false;
    call("seek", { pos });
  });
}

/* ============================================================
 * Right panel: queue & lyrics
 * ============================================================ */
function togglePanel(tab) {
  S.panel = S.panel === tab ? null : tab;
  try { localStorage.setItem("panel", S.panel || ""); } catch {}
  renderPanel();
}

function renderPanel() {
  const panel = $("#panel");
  panel.hidden = !S.panel;
  $("#pb-queue").classList.toggle("on", S.panel === "queue");
  $("#pb-lyrics").classList.toggle("on", S.panel === "lyrics");
  document.querySelectorAll(".panel-tabs .tab").forEach(t => t.classList.toggle("active", t.dataset.tab === S.panel));
  if (!S.panel) return;
  const body = $("#panel-body");
  if (S.panel === "queue") renderQueue(body);
  else { body.replaceChildren(lyricsSkeleton()); ensureLyrics().then(() => S.panel === "lyrics" && renderLyricsInto(body)); }
}

let dragFrom = null;
function renderQueue(body) {
  const q = S.queue;
  const keepScroll = body.scrollTop;
  if (!q.items.length) { body.replaceChildren(h("div", { class: "center-msg" }, icon("queue", 40), "Your queue is empty.")); return; }
  const items = q.items.map((t, i) => {
    const el = h("div", { class: "q-item" + (i === q.index ? " current" : i < q.index ? " past" : ""), draggable: "true",
      onclick: () => call("queue_jump", { index: i }),
      oncontextmenu: e => { e.preventDefault(); trackMenu(el, t, { onRemove: () => call("queue_remove", { index: i }), removeLabel: "Remove from queue" }, { x: e.clientX, y: e.clientY }); },
      ondragstart: e => { dragFrom = i; el.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; },
      ondragend: () => { el.classList.remove("dragging"); document.querySelectorAll(".drop-target").forEach(x => x.classList.remove("drop-target")); },
      ondragover: e => { e.preventDefault(); el.classList.add("drop-target"); },
      ondragleave: () => el.classList.remove("drop-target"),
      ondrop: e => { e.preventDefault(); el.classList.remove("drop-target"); if (dragFrom != null && dragFrom !== i) call("queue_move", { src: dragFrom, dst: i }); dragFrom = null; } },
      h("div", { class: "t-lead" }, img(t.thumbnail)),
      h("div", { class: "t-main" }, h("div", { class: "t-title" }, h("span", null, t.title)), h("div", { class: "t-sub" }, t.artist)),
      h("div", { class: "q-actions" },
        h("button", { class: "icon-btn", title: "Remove", onclick: e => { e.stopPropagation(); call("queue_remove", { index: i }); } }, icon("close"))));
    return el;
  });
  body.replaceChildren(
    h("div", { class: "q-head" },
      h("div", { style: "min-width:0" }, h("div", { class: "faint", style: "font-size:12px" }, "Playing from"), h("div", { class: "q-title" }, q.title || "Queue")),
      h("button", { class: "btn small", title: "Remove everything except the current song", onclick: () => call("queue_clear") }, "Clear")),
    ...items);
  body.scrollTop = keepScroll;
  if (!renderQueue.scrolledFor || renderQueue.scrolledFor !== q.index) {
    renderQueue.scrolledFor = q.index;
    body.querySelector(".q-item.current")?.scrollIntoView({ block: "center" });
  }
}

/* ---------- lyrics ---------- */
async function ensureLyrics() {
  const cur = S.state?.current;
  if (!cur) { S.lyrics = null; return; }
  if (S.lyricsFor === cur.videoId && S.lyrics) return;
  S.lyricsFor = cur.videoId; S.lyrics = null; S.lyricIndex = -1;
  try {
    const res = await call("lyrics", { track: clean(cur) });
    if (S.lyricsFor === cur.videoId) S.lyrics = res;
  } catch (e) {
    if (S.lyricsFor === cur.videoId) S.lyrics = { error: e.message, lines: [], text: "" };
  }
}

const LYRIC_LEAD = 0.1;   // like ClefTune: a line lights up 100 ms before it's sung

function renderLyricsInto(container) {
  const L = S.lyrics;
  S.lyricIndex = -1; S.wordIndex = -1;
  if (!L || L.error || (!L.lines?.length && !L.text)) {
    container.replaceChildren(h("div", { class: "center-msg" }, icon("lyrics", 40), L?.error ? "Couldn't load lyrics." : "No lyrics found for this song."));
    return;
  }
  const lineEl = (ln, i) => h("div", { class: "line" + (ln.text ? "" : " blank") + (ln.words ? " has-words" : ""), dataset: { i },
      onclick: () => { const pos = Math.max(0, ln.t - (S.lyrics.offset || 0)); S.pos = pos; S.posAt = performance.now(); call("seek", { pos }); } },
    ln.words ? ln.words.map(w => h("span", { class: "word" }, w.text)) : (ln.text || "♪"));
  const box = L.synced
    ? h("div", { class: "lyrics synced" }, L.lines.map(lineEl))
    : h("div", { class: "lyrics plain" }, L.text.split("\n").map(t => h("div", { class: "line" + (t.trim() ? "" : " blank") }, t)));
  const offsetLabel = h("span", { class: "faint" });
  const paintOffset = () => { offsetLabel.textContent = L.offset ? `${L.offset > 0 ? "+" : ""}${L.offset.toFixed(2)} s` : "in sync"; };
  const nudge = async delta => {
    const want = delta === 0 ? 0 : Math.round(((L.offset || 0) + delta) * 100) / 100;
    try { L.offset = await call("lyrics_offset", { videoId: S.lyricsFor, offset: want }); paintOffset(); updateLyricHighlight(currentPos(), true); }
    catch (e) { toast(e.message, "error"); }
  };
  paintOffset();
  const head = h("div", { class: "lyrics-head" },
    L.source ? h("span", { class: "lyrics-src" }, `Lyrics from ${L.source}`) : h("span"),
    L.synced ? h("span", { class: "lyrics-offset", title: "If the words are early or late, shift them" },
      h("button", { class: "btn small", title: "Lyrics are early: delay them", onclick: () => nudge(-0.25) }, "−0.25s"),
      offsetLabel,
      h("button", { class: "btn small", title: "Lyrics are late: show them sooner", onclick: () => nudge(0.25) }, "+0.25s"),
      L.offset ? h("button", { class: "btn small", onclick: () => nudge(0) }, "Reset") : null) : null);
  const resync = h("button", { class: "btn small lyrics-resync", hidden: true,
    onclick: () => { S.lyricsFollowAt = 0; resync.hidden = true; updateLyricHighlight(currentPos(), true); } }, icon("down"), "Back to current line");
  // the big player keeps the header outside its faded scroll area
  const slot = container.previousElementSibling?.classList.contains("lyrics-head-slot") ? container.previousElementSibling : null;
  if (slot) slot.replaceChildren(head);
  container.replaceChildren(...[slot ? null : head, box, L.synced ? resync : null].filter(Boolean));
  // scrolling the lyrics yourself pauses auto-scroll for a few seconds
  if (L.synced && !container.dataset.follow) {
    container.dataset.follow = "1";
    const pause = () => { S.lyricsFollowAt = performance.now() + 5000; const r = container.querySelector(".lyrics-resync"); if (r) r.hidden = false; };
    container.addEventListener("wheel", pause, { passive: true });
    container.addEventListener("touchmove", pause, { passive: true });
  }
  S.lyricsFollowAt = 0;
  updateLyricHighlight(currentPos(), true);
}

function updateLyricHighlight(pos, force = false) {
  const L = S.lyrics;
  if (!L?.synced || !L.lines?.length) return;
  const t = pos + (L.offset || 0) + LYRIC_LEAD;
  let idx = -1;
  let lo = 0, hi = L.lines.length - 1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (L.lines[mid].t <= t) { idx = mid; lo = mid + 1; } else hi = mid - 1; }
  const words = idx >= 0 ? L.lines[idx].words : null;
  const wordIdx = words ? words.filter(w => w.t <= t).length - 1 : -1;
  if (idx === S.lyricIndex && wordIdx === S.wordIndex && !force) return;
  const lineChanged = idx !== S.lyricIndex || force;
  S.lyricIndex = idx; S.wordIndex = wordIdx;
  document.querySelectorAll(".lyrics.synced").forEach(box => {
    if (lineChanged) {
      box.querySelectorAll(".line").forEach((el, i) => { el.classList.toggle("active", i === idx); el.classList.toggle("past", i < idx); });
    }
    const active = box.querySelector(".line.active");
    if (active && words) active.querySelectorAll(".word").forEach((w, i) => w.classList.toggle("sung", i <= wordIdx));
    if (active && lineChanged) {
      // centre the active line inside its own scroller (never scrolls the whole page)
      const scroller = box.closest("#panel-body, .np-right");
      const following = force || !S.lyricsFollowAt || performance.now() > S.lyricsFollowAt;
      if (following) scroller?.querySelector(".lyrics-resync")?.setAttribute("hidden", "");
      if (scroller && following) {
        const target = active.offsetTop - scroller.clientHeight / 2 + active.clientHeight / 2;
        scroller.scrollTo({ top: target, behavior: force ? "auto" : "smooth" });
      }
    }
  });
}

function onTrackChanged() {
  S.lyrics = null; S.lyricsFor = null; S.lyricIndex = -1;
  if (S.panel === "lyrics") renderPanel();
  if (location.hash.startsWith("#/nowplaying")) route();
  if (S.panel === "queue") renderPanel();
}

/* ============================================================
 * Sidebar, search box, account chip, theme, shortcuts
 * ============================================================ */
function setupSidebar() {
  const nav = [["home", "Home", "home"], ["explore", "Explore", "explore"], ["library", "Library", "library"], ["cache", "Cache", "history"], ["downloads", "Downloads", "download"], ["settings", "Settings", "settings"]];
  $("#nav").replaceChildren(...nav.map(([r, label, ic]) => h("button", { class: "nav-item", dataset: { route: r }, onclick: () => go("/" + r) }, icon(ic), h("span", null, label))));
  refreshSidebar();
}

async function refreshSidebar() {
  try {
    const lists = await call("playlists");
    $("#sidebar-playlists").replaceChildren(
      h("div", { class: "sb-heading" }, "Your playlists"),
      h("button", { class: "sb-pl", onclick: () => go("/library/liked") }, "♥ Liked songs"),
      ...lists.map(p => h("button", { class: "sb-pl", title: p.title, onclick: () => go(`/playlist/${p.id}`) }, p.title)));
  } catch {}
  // closing the window/tab keeps the music playing, so quitting is an explicit action
  $("#sidebar-foot").replaceChildren(
    h("button", { class: "nav-item", title: "Stop the music and close ClefTune", onclick: () => dialog("Quit ClefTune?",
        h("p", { class: "muted" }, "The music stops and the app closes completely."),
        [{ label: "Cancel" }, { label: "Quit", primary: true, run: async () => { await call("quit"); document.body.replaceChildren(h("div", { class: "center-msg" }, "ClefTune has quit. You can close this window.")); } }]) },
      icon("power"), h("span", null, "Quit")));
}

async function renderAccountChip() {
  const chip = $("#account-chip");
  try {
    const acc = await call("account");
    chip.replaceChildren(acc.signedIn
      ? h("button", { title: acc.name || "Account", onclick: () => go("/library/account") }, acc.photo ? h("img", { class: "avatar", src: acc.photo, referrerpolicy: "no-referrer" }) : icon("person"))
      : h("button", { class: "btn small", onclick: () => go("/settings") }, icon("person"), "Sign in"));
  } catch { chip.replaceChildren(); }
}

function setupSearch() {
  const input = $("#search");
  const list = $("#suggestions");
  $("#search-icon").replaceChildren(icon("search"));
  let sel = -1;
  const submit = q => { list.hidden = true; if (q.trim()) go(`/search?q=${encodeURIComponent(q.trim())}`); };
  const suggest = debounce(async q => {
    if (!q.trim() || document.activeElement !== input) { list.hidden = true; return; }
    try {
      const items = await call("suggestions", { query: q });
      if (input.value !== q) return;
      sel = -1;
      list.replaceChildren(...items.map(s => h("li", { onmousedown: e => { e.preventDefault(); input.value = s; submit(s); } }, icon("search"), h("span", null, s))));
      list.hidden = !items.length;
    } catch { list.hidden = true; }
  }, 180);
  input.addEventListener("input", () => suggest(input.value));
  input.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 120));
  input.addEventListener("keydown", e => {
    const lis = [...list.children];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (list.hidden || !lis.length) return;
      e.preventDefault();
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + lis.length) % lis.length;
      lis.forEach((li, i) => li.classList.toggle("sel", i === sel));
      input.value = lis[sel].textContent;
    } else if (e.key === "Enter") submit(input.value);
    else if (e.key === "Escape") { list.hidden = true; input.blur(); }
  });
  setIcon($("#nav-back"), "back");
  setIcon($("#nav-forward"), "forward");
  $("#nav-back").onclick = () => history.back();
  $("#nav-forward").onclick = () => history.forward();
  setIcon($("#panel-close"), "close");
  $("#panel-close").onclick = () => togglePanel(S.panel);
  document.querySelectorAll(".panel-tabs .tab").forEach(t => (t.onclick = () => { S.panel = t.dataset.tab; renderPanel(); }));
}

function applyTheme() {
  const pref = S.settings.theme || "dark";
  const dark = pref === "system" ? matchMedia("(prefers-color-scheme: dark)").matches : pref === "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);

function setupShortcuts() {
  document.addEventListener("keydown", e => {
    const t = e.target;
    if (t.matches("input, textarea, select") && !(t.type === "range")) return;
    if (e.ctrlKey && e.key.toLowerCase() === "f" || e.key === "/") { e.preventDefault(); $("#search").focus(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (k === " ") { e.preventDefault(); call("toggle"); }
    else if (k === "ArrowRight" && e.shiftKey) call("next");
    else if (k === "ArrowLeft" && e.shiftKey) call("previous");
    else if (k === "ArrowRight") call("seek", { pos: currentPos() + 5 });
    else if (k === "ArrowLeft") call("seek", { pos: Math.max(0, currentPos() - 5) });
    else if (k === "ArrowUp") { e.preventDefault(); call("volume", { volume: Math.min(100, (S.state?.volume ?? 80) + 5) }); }
    else if (k === "ArrowDown") { e.preventDefault(); call("volume", { volume: Math.max(0, (S.state?.volume ?? 80) - 5) }); }
    else if (k === "m") $("#pb-mute").click();
    else if (k === "l" && S.state?.current) toggleLike(S.state.current);
    else if (k === "s") $("#pb-shuffle").click();
    else if (k === "r") $("#pb-repeat").click();
    else if (k === "q") togglePanel("queue");
    else if (k === "y") togglePanel("lyrics");
    else if (k === "Escape" && location.hash.startsWith("#/nowplaying")) history.back();
    else return;
  });
}

/* ============================================================
 * Boot
 * ============================================================ */
async function boot() {
  try {
    [S.settings, S.about] = await Promise.all([call("settings"), call("about")]);
  } catch (e) { toast(e.message, "error"); }
  applyTheme();
  setupSidebar();
  setupSearch();
  setupPlayerBar();
  setupShortcuts();
  renderAccountChip();
  refreshLikedIds();
  refreshDownloadedIds();
  try {
    const st = await call("state");
    S.state = st.state; S.queue = st.queue; S.pos = st.state.pos || 0; S.dur = st.state.duration || 0;
    renderPlayerBar();
  } catch {}
  try { S.panel = localStorage.getItem("panel") || null; } catch {}
  renderPanel();
  connectEvents();
  window.addEventListener("hashchange", route);
  route();
  requestAnimationFrame(tick);
}

boot();
