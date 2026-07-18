/* ============================================================
   SEARCH AI — frontend application
   ============================================================ */
"use strict";

const API = "";
const $ = (id) => document.getElementById(id);

const state = {
  topic: "",
  analysis: null,
  outline: null,          // {layout,title,sections:[{id,title,goal,subpoints}]}
  article: null,
  diagnostics: null,
  busy: false,
};

/* ---------------------------- boot ---------------------------- */
function forceHide(el) { el.hidden = true; el.style.display = "none"; }
function forceShow(el, disp) { el.hidden = false; el.style.display = disp; }

document.addEventListener("DOMContentLoaded", () => {
  const syncGen = () => {
    $("btnGenerate").disabled = !$("topicInput").value.trim();
  };
  $("topicInput").addEventListener("input", syncGen);
  setTimeout(syncGen, 0);
  // Belt-and-braces: close every overlay with inline styles, which beat
  // any stylesheet — even a stale cached one.
  ["lightbox", "statusBar", "errorBar"].forEach((id) => forceHide($(id)));
  if (location.search.includes("boot=")) {
    // fresh launcher boot: overwrite any ancient cached copies of the
    // plain URLs so old ghost pages can never be served again
    ["/", "/style.css", "/app.js"].forEach((u) => {
      try { fetch(u, { cache: "reload" }); } catch (e) {}
    });
    history.replaceState(null, "", "/");
  }
  $("btnOutline").addEventListener("click", createOutline);
  $("btnGenerate").addEventListener("click", generateArticle);
  $("btnAdvanced").addEventListener("click", () => {
    const p = $("advancedPanel");
    p.hidden = !p.hidden;
    $("btnAdvanced").setAttribute("aria-expanded", String(!p.hidden));
  });
  $("btnAddSection").addEventListener("click", () => {
    state.outline.sections.push({
      id: "s" + (state.outline.sections.length + 1) + "-custom-" + Date.now(),
      title: "New section", goal: "", subpoints: [""],
    });
    renderOutlineEditor();
  });
  $("btnPdf").addEventListener("click", downloadPdf);
  $("btnDocx").addEventListener("click", downloadDocx);
  $("btnDiagnostics").addEventListener("click", () => {
    const p = $("diagPanel");
    p.hidden = !p.hidden;
    if (!p.hidden) p.scrollIntoView({ behavior: "smooth" });
  });
  $("topicInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") createOutline();
  });
  $("lightbox").addEventListener("click", () => forceHide($("lightbox")));
  checkHealth();
});

const BUILD = "2026.07.13-18";

async function checkHealth() {
  try {
    const r = await fetch(API + "/api/health");
    const h = await r.json();
    const txt = (h.any_text_provider
      ? "✓ providers ready"
      : "⚠ no LLM key configured — edit .env and restart")
      + "  ·  build " + (h.build || "?");
    if (h.build && h.build !== BUILD) {
      showError("Build mismatch — backend " + h.build + " vs frontend " +
        BUILD + ". Press Ctrl+F5 to hard-refresh; if it persists, " +
        "re-extract the zip into a fresh folder.");
    }
    $("providerStatus").textContent = txt;
    $("providerStatus").style.color = h.any_text_provider ? "var(--good)" : "var(--warn)";
  } catch {
    $("providerStatus").textContent = "⚠ backend unreachable";
  }
}

/* ---------------------------- options ---------------------------- */
function readOptions() {
  return {
    format: $("optFormat").value,
    current_findings: $("optCurrent").checked,
    web_research: $("optWeb").checked,
    image_count: parseInt($("optImageCount").value, 10),
  };
}

/* ---------------------------- status ---------------------------- */
let ticker = null, clockInt = null, clockT0 = null;
function ensureClock() {
  if (!document.getElementById("statusClock")) {
    const s = document.createElement("span");
    s.id = "statusClock";
    s.className = "status-clock";
    $("statusBar").append(s);
  }
}
function setStatus(title, detail) {
  forceHide($("errorBar"));
  forceShow($("statusBar"), "flex");
  $("statusTitle").textContent = title;
  $("statusDetail").textContent = detail || "";
  ensureClock();
  if (!clockInt) {
    clockT0 = Date.now();
    clockInt = setInterval(() => {
      const s = Math.floor((Date.now() - clockT0) / 1000);
      document.getElementById("statusClock").textContent =
        Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
    }, 1000);
  }
}
function startTicker(stages) {
  let i = 0;
  clearInterval(ticker);
  ticker = setInterval(() => {
    if (i < stages.length) $("statusDetail").textContent = stages[i++];
  }, 3600);
}
function clearStatus() {
  clearInterval(ticker);
  clearInterval(clockInt);
  clockInt = null;
  const c = document.getElementById("statusClock");
  if (c) c.textContent = "";
  forceHide($("statusBar"));
}
function showError(msg) {
  clearStatus();
  forceShow($("errorBar"), "flex");
  $("errorText").textContent = msg;
}

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return r;
}

/* ============================================================
   PHASE 1 — outline
   ============================================================ */
async function createOutline() {
  const topic = $("topicInput").value.trim();
  if (!topic || state.busy) return;
  state.busy = true;
  state.topic = topic;
  $("outlinePanel").hidden = true;
  $("articlePanel").hidden = true;
  $("diagPanel").hidden = true;
  setStatus("Designing the outline…", "Understanding the query");
  startTicker([
    "Research Director — decoding the query, brief and retrieval plan",
    "Outline Architect — adaptive layout + narrative thread",
  ]);
  try {
    const r = await apiPost("/api/outline", { topic, options: readOptions() });
    const data = await r.json();
    state.analysis = data.analysis;
    state.outline = data.outline;
    clearStatus();
    renderOutlineEditor();
    $("outlinePanel").hidden = false;
    $("btnGenerate").disabled = false;
    $("outlinePanel").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    showError(e.message);
  } finally {
    state.busy = false;
  }
}

function renderOutlineEditor() {
  const o = state.outline;
  if (!o.sections || !o.sections.length) {
    showError("The outline came back without sections — press " +
      "\u21bb Regenerate outline to retry.");
  }
  // regenerate button (created once, lives in the panel header)
  if (!document.getElementById("regenOutlineBtn")) {
    const btn = document.createElement("button");
    btn.id = "regenOutlineBtn";
    btn.className = "btn ghost regen-btn";
    btn.textContent = "\u21bb Regenerate outline";
    btn.onclick = () => createOutline();
    const drop = document.createElement("button");
    drop.id = "discardOutlineBtn";
    drop.className = "btn ghost regen-btn discard-btn";
    drop.textContent = "\u2715 Discard outline";
    drop.onclick = () => {
      state.outline = null;
      $("outlinePanel").hidden = true;
      setStatus("Outline discarded",
        "Edit the topic if you like, then Create Outline for a fresh " +
        "proposal — or press Generate to go end-to-end.");
      setTimeout(clearStatus, 4500);
    };
    const head = $("outlinePanel").querySelector("h2") ||
      $("outlinePanel").firstElementChild;
    head.insertAdjacentElement("afterend", drop);
    head.insertAdjacentElement("afterend", btn);
  }
  $("outlineTitle").value = o.title || state.topic;
  $("outlineTitle").oninput = (e) => { o.title = e.target.value; };
  $("outlineLayout").textContent = "layout · " + (o.layout || "auto").replace(/_/g, " ");
  const wrap = $("outlineSections");
  wrap.innerHTML = "";

  o.sections.forEach((sec, idx) => {
    const card = document.createElement("div");
    card.className = "osec";

    const row = document.createElement("div");
    row.className = "osec-row";

    const num = document.createElement("span");
    num.className = "osec-num";
    num.textContent = idx + 1;

    const title = document.createElement("input");
    title.className = "osec-title";
    title.value = sec.title;
    title.oninput = (e) => { sec.title = e.target.value; };

    const up = mkBtn("↑", () => moveSection(idx, -1));
    const down = mkBtn("↓", () => moveSection(idx, 1));
    const del = mkBtn("✕", () => { o.sections.splice(idx, 1); renderOutlineEditor(); });
    del.classList.add("del");

    row.append(num, title, up, down, del);
    card.append(row);

    if (sec.goal) {
      const goal = document.createElement("div");
      goal.className = "osec-goal";
      goal.textContent = sec.goal;
      card.append(goal);
    }

    const subs = document.createElement("div");
    subs.className = "osec-subs";
    (sec.subpoints || []).forEach((sp, spi) => {
      const line = document.createElement("div");
      line.className = "osub";
      const inp = document.createElement("input");
      inp.value = sp;
      inp.oninput = (e) => { sec.subpoints[spi] = e.target.value; };
      const rm = document.createElement("button");
      rm.textContent = "✕";
      rm.onclick = () => { sec.subpoints.splice(spi, 1); renderOutlineEditor(); };
      line.append(inp, rm);
      subs.append(line);
    });
    card.append(subs);

    const add = document.createElement("button");
    add.className = "oadd-sub";
    add.textContent = "+ add subpoint";
    add.onclick = () => { (sec.subpoints = sec.subpoints || []).push(""); renderOutlineEditor(); };
    card.append(add);

    wrap.append(card);
  });

  function mkBtn(label, fn) {
    const b = document.createElement("button");
    b.className = "osec-btn";
    b.textContent = label;
    b.onclick = fn;
    return b;
  }
  function moveSection(i, d) {
    const j = i + d;
    if (j < 0 || j >= o.sections.length) return;
    [o.sections[i], o.sections[j]] = [o.sections[j], o.sections[i]];
    renderOutlineEditor();
  }
}

/* ============================================================
   PHASE 2 — generate
   ============================================================ */
async function generateArticle() {
  if (state.busy) return;
  const topicNow = $("topicInput").value.trim();
  if (!topicNow) { showError("Type a topic first."); return; }
  // Direct mode: no outline yet (or topic changed) -> auto-create outline
  // and flow straight into generation.
  if (!state.outline || state.topic !== topicNow) {
    await createOutline();
    if (!state.outline || state.topic !== topicNow) return;
  }
  const sections = state.outline.sections
    .filter((s) => (s.title || "").trim())
    .map((s) => ({ ...s, subpoints: (s.subpoints || []).filter((p) => p.trim()) }));
  if (!sections.length) { showError("The outline needs at least one section."); return; }
  state.busy = true;
  setStatus("Generating the article…",
    "The full agent pipeline is running — this takes a few minutes.");
  startTicker([
    "Research Director — brief and retrieval plan",
    "Web + Academic Research — collecting sources in parallel",
    "Source Credibility — dropping weak or off-topic sources",
    "Current Facts + Visual Hunt — verified facts ∥ reference figures",
    "Article Writer — markdown drafting with extended thinking",
    "Scholarly Polish — standards, clarity, voice, cohesion",
    "Currentness Guard + Image Embedder — auditing ∥ embedding",
    "Quality Validator + Pre-Publish Gate — one audit, one verdict",
  ]);
  try {
    const r = await apiPost("/api/generate", {
      topic: state.topic,
      outline: { ...state.outline, sections },
      analysis: state.analysis,
      options: readOptions(),
    });
    const data = await r.json();
    state.article = data.article;
    await rasterizeArticleImages(state.article);
    state.diagnostics = data.diagnostics;
    clearStatus();
    renderArticle();
    renderDiagnostics();
    $("articlePanel").hidden = false;
    $("outlinePanel").hidden = true;
    $("articlePanel").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    showError(e.message);
  } finally {
    state.busy = false;
  }
}

/* ============================================================
   Article rendering — markdown + math with placeholder protection
   ============================================================ */
const TOK_OPEN = "\uE000", TOK_CLOSE = "\uE001";

function protectMath(md) {
  const store = [];
  const stash = (m) => {
    store.push(m);
    return TOK_OPEN + (store.length - 1) + TOK_CLOSE;
  };
  md = md.replace(/\$\$[\s\S]+?\$\$/g, stash);
  md = md.replace(/\\\[[\s\S]+?\\\]/g, stash);
  md = md.replace(/\\\((?:[\s\S]+?)\\\)/g, stash);
  // inline $...$ — no line breaks, not currency like "$5"
  md = md.replace(/\$(?!\s|\d[\d,.]*(?:\s|$))([^$\n]+?)\$/g, (m) => stash(m));
  return { md, store };
}
function restoreMath(html, store) {
  html = html.replace(new RegExp(TOK_OPEN + "(\\d+)" + TOK_CLOSE, "g"),
    (_, i) => store[+i] || "");
  // guarantee no internal placeholder ever leaks
  return html.replace(/@@(?:MATH|TBL|CODE)\d+@@/g, "")
             .replace(new RegExp("[" + TOK_OPEN + TOK_CLOSE + "]\\d*", "g"), "");
}

function mdToHtml(md) {
  md = (md || "")
    .replace(/<br\s*\/?>/gi, "; ")          // raw HTML never renders here
    .replace(/^\s*TEXT\s*$/gm, "");          // stray pseudo-figure labels
  const { md: safe, store } = protectMath(md);
  let html;
  if (window.marked) {
    marked.setOptions({ gfm: true, breaks: false, mangle: false, headerIds: false });
    html = marked.parse(safe);
  } else {
    html = "<p>" + safe
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
  }
  return restoreMath(html, store);
}

function typesetMath(rootEl) {
  if (window.renderMathInElement) {
    try {
      renderMathInElement(rootEl, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\[", right: "\\]", display: true },
          { left: "\\(", right: "\\)", display: false },
          { left: "$", right: "$", display: false },
        ],
        throwOnError: false,
        ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
      });
    } catch {}
  }
}

function renderArticle() {
  const a = state.article;
  const root = $("articleRoot");
  root.innerHTML = "";

  const h1 = document.createElement("h1");
  h1.className = "a-title";
  h1.textContent = a.title;
  const meta = document.createElement("div");
  meta.className = "a-meta";
  meta.textContent = "SEARCH AI · " + (a.layout || "").replace(/_/g, " ") +
    " · topic: " + a.topic;
  root.append(h1, meta);

  if (a.abstract) {
    const abs = document.createElement("div");
    abs.className = "a-abstract";
    abs.innerHTML = '<span class="lbl">Abstract</span>' + mdToHtml(a.abstract);
    linkCitations(abs);
    root.append(abs);
  }
  if (a.executive_answer) {
    const ans = document.createElement("div");
    ans.className = "a-answer";
    ans.innerHTML = '<span class="lbl">Direct answer</span>' + mdToHtml(a.executive_answer);
    linkCitations(ans);
    root.append(ans);
  }
  if ((a.key_takeaways || []).length) {
    const kt = document.createElement("div");
    kt.className = "a-takeaways";
    kt.innerHTML = '<span class="lbl">Key takeaways</span><ul>' +
      a.key_takeaways.map((k) => "<li>" + mdToHtml(k)
        .replace(/^<p>|<\/p>\s*$/g, "") + "</li>").join("") + "</ul>";
    linkCitations(kt);
    root.append(kt);
  }

  // group images by section
  const bySection = {};
  const loose = [];
  (a.images || []).forEach((img) => {
    const sid = img.section_id || "";
    const ids = a.sections.map((s) => s.id);
    if (sid && ids.includes(sid)) (bySection[sid] = bySection[sid] || []).push(img);
    else loose.push(img);
  });
  // spread unassigned images across sections
  let li = 0;
  a.sections.forEach((s, i) => {
    if (loose.length && i % Math.max(1, Math.floor(a.sections.length / loose.length)) === 0 && li < loose.length) {
      (bySection[s.id] = bySection[s.id] || []).push(loose[li++]);
    }
  });
  while (li < loose.length) {
    const last = a.sections[a.sections.length - 1];
    (bySection[last.id] = bySection[last.id] || []).push(loose[li++]);
  }

  a.sections.forEach((sec, i) => {
    const secEl = document.createElement("section");
    secEl.className = "a-sec";

    const h2 = document.createElement("h2");
    h2.innerHTML = '<span class="secnum">' + (i + 1) + '</span>' +
      escapeHtml(sec.title);
    secEl.append(h2);

    const body = document.createElement("div");
    body.className = "a-body";
    body.innerHTML = mdToHtml(sec.markdown);
    enhanceBody(body);
    linkCitations(body);

    // inject pull quote after the second block of the section
    if (sec.pull_quote) {
      const pq = document.createElement("div");
      pq.className = "pullquote";
      pq.textContent = sec.pull_quote;
      const blocks = body.children;
      if (blocks.length > 2) body.insertBefore(pq, blocks[2]);
      else body.append(pq);
    }
    secEl.append(body);

    (bySection[sec.id] || []).forEach((img) => secEl.append(figureEl(img)));
    root.append(secEl);
  });

  if ((a.references || []).length) {
    const refs = document.createElement("section");
    refs.className = "a-refs a-sec";
    refs.innerHTML = "<h2>References</h2>";
    const ol = document.createElement("ol");
    a.references.forEach((r, ri) => {
      const li2 = document.createElement("li");
      li2.id = "ref-" + (ri + 1);
      let html = escapeHtml(r.title || r.url);
      if (r.year) html += " (" + r.year + ")";
      if (r.doi) html += " · doi:" + escapeHtml(r.doi);
      if (r.url) html += ' — <a href="' + encodeURI(r.url) + '" target="_blank" rel="noopener">' +
        escapeHtml(shorten(r.url, 70)) + "</a>";
      li2.innerHTML = html;
      ol.append(li2);
    });
    refs.append(ol);
    root.append(refs);
  }

  typesetMath(root);
}

function imgSrc(u) {
  // route external images through the same-origin proxy so hotlink-blocked
  // hosts render and the PDF capture can draw them without CORS taint
  if (!u || u.startsWith("data:")) return u;
  return "/api/img?u=" + encodeURIComponent(u);
}

function figureEl(img) {
  const fig = document.createElement("figure");
  fig.className = "a-fig";
  const el = document.createElement("img");
  el.src = imgSrc(img.url);
  el.alt = img.caption || "figure";
  el.loading = "lazy";
  if (!img.url.startsWith("data:")) el.crossOrigin = "anonymous";
  el.onerror = () => {
    const ph = document.createElement("div");
    ph.className = "fig-missing";
    ph.textContent = "Figure " + img.slot + " could not be displayed — " +
      (img.caption || "image unavailable");
    el.replaceWith(ph);
  };
  el.onclick = () => {
    $("lightboxImg").src = imgSrc(img.url);
    $("lightboxCap").textContent = (img.caption || "") +
      (img.explanation ? " — " + img.explanation : "");
    forceShow($("lightbox"), "flex");
  };
  const cap = document.createElement("figcaption");
  const kindLabel = { reference: "source image", generated: "AI figure",
                      fallback_visual: "SEARCH AI visual" }[img.kind] || "figure";
  cap.innerHTML = "<b>Figure " + img.slot + ".</b> " + escapeHtml(img.caption || "") +
    (img.explanation ? "<br>" + escapeHtml(img.explanation) : "") +
    '<span class="fig-src">' + escapeHtml(img.source_label || kindLabel) + "</span>";
  fig.append(el, cap);
  return fig;
}

function linkCitations(el) {
  el.innerHTML = el.innerHTML.replace(/⟦([\d,\s]+)⟧/g, (_, nums) =>
    '<sup class="cite">' + nums.split(",").map((n) => n.trim())
      .filter(Boolean)
      .map((n) => '<a href="#ref-' + n + '">[' + n + "]</a>").join("") +
    "</sup>");
}

function enhanceBody(body) {
  // tables: horizontal-scroll container on screen, wrap-to-fit in PDF
  body.querySelectorAll("table").forEach((tb) => {
    if (tb.closest(".tbl-wrap")) return;
    tb.classList.add("a-table");
    const wrap = document.createElement("div");
    wrap.className = "tbl-wrap";
    tb.replaceWith(wrap);
    wrap.append(tb);
  });
  // code: header bar with language chip
  body.querySelectorAll("pre").forEach((pre) => {
    if (pre.closest(".codebox")) return;
    const code = pre.querySelector("code");
    let lang = "code";
    if (code) {
      const m = (code.className || "").match(/language-([\w+-]+)/i);
      if (m) lang = m[1].toLowerCase();
    }
    const box = document.createElement("div");
    box.className = "codebox";
    box.innerHTML = '<div class="codebox-head"><span class="codebox-lang">' +
      escapeHtml(lang) + "</span></div>";
    pre.replaceWith(box);
    box.append(pre);
  });
}

function escapeHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function shorten(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

/* ============================================================
   Diagnostics panel
   ============================================================ */
function renderDiagnostics() {
  const d = state.diagnostics;
  if (!d) return;
  const cls = (v) => /pass$/i.test(v) || v === "current" || v === "ok"
    ? "ok" : (/fail/i.test(v) ? "bad" : "warn");
  $("diagSummary").innerHTML = [
    ["Validation", d.validation_status],
    ["Outline alignment", d.outline_alignment_score + " / 100"],
    ["Currentness", d.currentness_status],
    ["Image relevance", d.image_relevance_status],
    ["Source credibility", d.source_credibility_status],
    ["Agents used", d.agents_used.length + " agents"],
  ].map(([k, v]) =>
    '<div class="diag-card"><span class="k">' + k + '</span>' +
    '<span class="v ' + cls(String(v)) + '">' + escapeHtml(String(v)) + "</span></div>"
  ).join("");

  $("diagWarnings").innerHTML = (d.warnings || [])
    .map((w) => '<div class="diag-warning">' + escapeHtml(w) + "</div>").join("");

  $("diagTrace").innerHTML = (d.trace || []).map((t) =>
    '<div class="trace-step">' +
    '<span class="trace-dot ' + escapeHtml(t.status) + '"></span>' +
    '<span class="trace-agent">' + escapeHtml(t.agent) + "</span>" +
    '<span class="trace-ms">' + (t.ms ? t.ms + " ms" : "—") + "</span>" +
    '<span class="trace-note">' + escapeHtml(t.note || t.status) + "</span></div>"
  ).join("");
}

/* ============================================================
   Exports
   ============================================================ */
async function downloadDocx() {
  if (!state.article) return;
  setStatus("Building Word document…", "Preserving headings, tables, figures and references");
  try {
    const r = await apiPost("/api/export/docx", { article: state.article });
    await saveBlob(await r.blob(), safeName(state.article.title) + ".docx");
    clearStatus();
  } catch (e) { showError("Word export failed: " + e.message); }
}

async function downloadPdf() {
  if (!state.article) return;
  if (!window.html2canvas || !window.jspdf) {
    return backendPdfFallback();
  }
  setStatus("Preparing PDF\u2026", "Paginating the article exactly as rendered");
  const PAGE_W = 794, PAGE_H = 1123, PAD = 46;          // A4 @ 96dpi
  const CONTENT_H = PAGE_H - PAD * 2;
  const stage = document.createElement("div");
  stage.className = "pdf-stage";
  document.body.append(stage);
  try {
    // 1) clone the live article into a fixed-width export layout
    const clone = $("articleRoot").cloneNode(true);
    clone.classList.add("pdf-export");
    stage.append(clone);
    await waitForImages(clone, 9000);
    await rasterizeSvgImages(clone);   // html2canvas cannot draw SVG <img>
    if (document.fonts && document.fonts.ready) {
      try { await document.fonts.ready; } catch {}
    }

    // 2) flatten into atomic blocks that must never be cut
    const blocks = [];
    const flatten = (el) => {
      Array.from(el.children).forEach((ch) => {
        const h = ch.offsetHeight;
        if (!h) return;
        if (h <= CONTENT_H) { blocks.push(ch); return; }
        // too tall for one page: split composites, keep leaves atomic
        const kids = Array.from(ch.children).filter((k) => k.offsetHeight);
        if (kids.length > 1 &&
            !/^(TABLE|PRE|FIGURE|IMG|UL|OL)$/.test(ch.tagName)) {
          flatten(ch);
        } else {
          blocks.push(ch);
        }
      });
    };
    flatten(clone);

    // 3) distribute blocks into A4 page frames (break BETWEEN blocks only)
    const pages = [];
    let page = null, used = 0;
    const newPage = () => {
      page = document.createElement("div");
      page.className = "pdf-page";
      page.style.cssText = "width:" + PAGE_W + "px;min-height:" + PAGE_H +
        "px;padding:" + PAD + "px;box-sizing:border-box;background:#fff;";
      stage.append(page);
      pages.push(page);
      used = 0;
    };
    newPage();
    blocks.forEach((b) => {
      let h = b.offsetHeight + 14;
      if (h > CONTENT_H) {
        // oversized atomic block (huge table/code): own page, scaled to fit
        if (used > 0) newPage();
        const f = Math.min(1, (CONTENT_H - 8) / b.offsetHeight);
        const shell = document.createElement("div");
        shell.style.cssText = "height:" + Math.ceil(b.offsetHeight * f) +
          "px;overflow:hidden;";
        b.style.transformOrigin = "top left";
        b.style.transform = "scale(" + f + ")";
        b.style.width = (100 / f) + "%";
        shell.append(b);
        page.append(shell);
        newPage();
        return;
      }
      if (used + h > CONTENT_H) newPage();
      page.append(b);
      used += h;
    });
    if (page && !page.children.length) { page.remove(); pages.pop(); }
    clone.remove();

    // 4) screenshot each page frame -> one clean PDF page each
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF({ unit: "mm", format: "a4", compress: true });
    const MM_W = 210, MM_H = 297, M = 6;
    for (let i = 0; i < pages.length; i++) {
      setStatus("Capturing PDF\u2026", "Page " + (i + 1) + " of " + pages.length);
      const canvas = await html2canvas(pages[i], {
        scale: 2, useCORS: true, backgroundColor: "#ffffff",
        logging: false, windowWidth: PAGE_W,
      });
      let w = MM_W - M * 2;
      let h = canvas.height * w / canvas.width;
      if (h > MM_H - M * 2) { h = MM_H - M * 2; w = canvas.width * h / canvas.height; }
      if (i) pdf.addPage();
      pdf.addImage(canvas.toDataURL("image/jpeg", 0.94), "JPEG",
        (MM_W - w) / 2, M, w, h);
      pdf.setFontSize(7.5);
      pdf.setTextColor(150);
      pdf.text("SEARCH AI \u00b7 " + safeName(state.article.title).replace(/_/g, " ").slice(0, 60),
        M, MM_H - 3.5);
      pdf.text("page " + (i + 1) + " / " + pages.length, MM_W - M, MM_H - 3.5,
        { align: "right" });
    }
    pdf.save(safeName(state.article.title) + ".pdf");
    clearStatus();
  } catch (e) {
    showError("In-browser PDF capture failed (" + e.message +
      "). Trying backend fallback\u2026");
    backendPdfFallback();
  } finally {
    stage.remove();
  }
}

async function rasterizeArticleImages(article) {
  const imgs = (article && article.images) || [];
  await Promise.all(imgs.map((im) => new Promise((res) => {
    if (!(im.url || "").startsWith("data:image/svg")) return res();
    const pic = new Image();
    pic.onload = () => {
      try {
        const w = pic.naturalWidth || 960, h = pic.naturalHeight || 560;
        const c = document.createElement("canvas");
        c.width = w * 2; c.height = h * 2;
        const g = c.getContext("2d");
        g.fillStyle = "#ffffff";
        g.fillRect(0, 0, c.width, c.height);
        g.drawImage(pic, 0, 0, c.width, c.height);
        im.url = c.toDataURL("image/png");
      } catch (e) { /* keep original */ }
      res();
    };
    pic.onerror = () => res();
    pic.src = im.url;
  })));
}

async function rasterizeSvgImages(root) {
  const imgs = Array.from(root.querySelectorAll("img"))
    .filter((im) => (im.src || "").startsWith("data:image/svg"));
  await Promise.all(imgs.map((im) => new Promise((res) => {
    const pic = new Image();
    pic.onload = () => {
      try {
        const w = pic.naturalWidth || 960, h = pic.naturalHeight || 560;
        const c = document.createElement("canvas");
        c.width = w * 2; c.height = h * 2;
        const g = c.getContext("2d");
        g.fillStyle = "#ffffff";
        g.fillRect(0, 0, c.width, c.height);
        g.drawImage(pic, 0, 0, c.width, c.height);
        im.src = c.toDataURL("image/png");
      } catch (e) { /* keep original */ }
      res();
    };
    pic.onerror = () => res();
    pic.src = im.src;
  })));
}

function waitForImages(root, timeoutMs) {
  const imgs = Array.from(root.querySelectorAll("img"));
  return Promise.all(imgs.map((im) => new Promise((res) => {
    if (im.complete && im.naturalWidth) return res();
    const done = () => res();
    im.addEventListener("load", done, { once: true });
    im.addEventListener("error", () => { im.closest("figure, .a-fig, div")?.remove(); done(); },
      { once: true });
    setTimeout(done, timeoutMs);
  })));
}

async function backendPdfFallback() {
  try {
    setStatus("Backend PDF fallback…", "Rendering via WeasyPrint");
    const r = await apiPost("/api/export/pdf", {
      html: $("articleRoot").outerHTML, title: state.article.title,
    });
    await saveBlob(await r.blob(), safeName(state.article.title) + ".pdf");
    clearStatus();
  } catch (e) { showError(e.message); }
}

async function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}
function safeName(t) {
  return (t || "SEARCH_AI_Article").replace(/[^\w\s-]/g, "").trim()
    .replace(/\s+/g, "_").slice(0, 70) || "SEARCH_AI_Article";
}
