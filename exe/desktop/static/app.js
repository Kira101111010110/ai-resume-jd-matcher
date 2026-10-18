// หน้าเว็บของ Resume AI (ไม่มี build step / ไม่โหลดอะไรจากภายนอก)
// API key ที่ผู้ใช้พิมพ์อยู่แค่ในช่อง input ระหว่างตรวจ/บันทึก และถูกล้างทิ้งทันทีหลังบันทึก
"use strict";

const MAX_FILE_MB = 10;
// error ที่แก้ได้ในหน้าตั้งค่า → แนบลิงก์ไปหน้าตั้งค่า
const ERROR_LINKS = {
  no_key: "ไปใส่ API key →",
  invalid_key: "ไปเปลี่ยน API key →",
  quota: "ไปเปลี่ยนโมเดล / ค่าย AI →",
  model_not_found: "ไปเลือกโมเดลใหม่ →",
};

let settings = null;   // ผลจาก GET /api/settings
let status = null;     // ผลจาก GET /api/status
let analyzing = false;
let lastResult = null; // { r, source } ไว้คัดลอกผล

const $ = (sel, root = document) => root.querySelector(sel);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body instanceof FormData) opts.body = body;
  else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch {
    throw { kind: "server_down", message: "ติดต่อโปรแกรม Resume AI ไม่ได้ — โปรแกรมอาจถูกปิดไปแล้ว ดับเบิลคลิกไอคอน Resume AI บนเดสก์ท็อปเพื่อเปิดใหม่ แล้วรีเฟรชหน้านี้" };
  }
  let data = null;
  try { data = await res.json(); } catch { /* ไม่ใช่ JSON */ }
  if (!res.ok) {
    const d = data && data.detail;
    if (d && typeof d === "object" && !Array.isArray(d)) throw { kind: d.kind || "other", message: d.message };
    if (typeof d === "string") throw { kind: "other", message: d };
    throw { kind: "other", message: `เกิดข้อผิดพลาด (HTTP ${res.status}) — ลองใหม่อีกครั้ง` };
  }
  return data;
}

function providerById(id) {
  return settings && settings.providers.find(p => p.id === id);
}

// ============================================================
// สถานะโปรแกรม (กำลังโหลดโมเดล / พร้อม)
// ============================================================
let statusTimer = null;

async function pollStatus() {
  try {
    status = await api("GET", "/api/status");
  } catch (e) {
    showBanner("error", e.message);
    statusTimer = setTimeout(pollStatus, 3000);
    return;
  }
  $("#app-version").textContent = `v${status.version}`;
  if (status.load_failed) {
    showBanner("error", "โหลดโมเดล AI ไม่สำเร็จ — ปิดโปรแกรม (คลิกขวาไอคอน Resume AI ที่มุมขวาล่างของจอ → ออก) แล้วเปิดใหม่ ถ้ายังไม่ได้ให้ส่งไฟล์ log ให้ผู้ดูแล");
  } else if (!status.ready) {
    showBanner("loading", "กำลังเตรียมระบบ AI… (ประมาณ 1 นาทีหลังเปิดโปรแกรม) ระหว่างนี้ตั้งค่าหรือกรอกข้อมูลรอไว้ได้เลย");
    statusTimer = setTimeout(pollStatus, 2000);
  } else {
    showBanner();
  }
  updateAnalyzeButton();
}

function showBanner(kind, text) {
  const b = $("#boot-banner");
  if (!text) { b.hidden = true; return; }
  b.className = `boot-banner ${kind}`;
  b.replaceChildren(kind === "loading" ? el("span", { class: "spinner" }) : "", text);
  b.hidden = false;
}

// ============================================================
// แท็บ / หน้า
// ============================================================
function currentPage() {
  const h = location.hash.replace("#", "");
  return ["setup", "settings", "analyze"].includes(h) ? h : "analyze";
}

async function showPage() {
  await loadSettings();
  let page = currentPage();
  // ยังไม่มี key เลย → พาไปหน้าตั้งค่าครั้งแรก (ยกเว้นตั้งใจเปิดหน้าตั้งค่าเอง)
  if (page === "analyze" && settings && !settings.active_provider) {
    location.replace("#setup");
    page = "setup";
  }
  for (const name of ["setup", "analyze", "settings"]) {
    $(`#page-${name}`).hidden = name !== page;
  }
  $("#tab-analyze").setAttribute("aria-selected", String(page !== "settings"));
  $("#tab-settings").setAttribute("aria-selected", String(page === "settings"));
  if (page === "setup") startSetup();
  if (page === "settings") renderSettingsPage();
}

async function loadSettings() {
  try {
    settings = await api("GET", "/api/settings");
  } catch (e) {
    settings = null;
    $("#active-bar").replaceChildren(el("div", { class: "alert error" }, e.message));
    return;
  }
  renderActiveBar();
}

// ============================================================
// ตั้งค่าครั้งแรก (3 ขั้น)
// ============================================================
const setup = { provider: "gemini", models: null, key: "" };

function setupStep(n) {
  for (const i of [1, 2, 3]) {
    $(`#setup-step-${i}`).hidden = i !== n;
    const dot = $(`#step-dot-${i}`);
    dot.classList.toggle("is-current", i === n);
    dot.classList.toggle("is-done", i < n);
  }
}

function startSetup() {
  const list = $("#setup-providers");
  if (!settings) return;
  list.replaceChildren(...settings.providers.map(p => {
    const id = `setup-p-${p.id}`;
    const input = el("input", { type: "radio", name: "setup-provider", id, value: p.id });
    input.checked = p.id === setup.provider;
    input.addEventListener("change", () => { setup.provider = p.id; });
    return el("label", { class: "choice", for: id },
      input,
      el("span", { class: "choice-body" },
        el("span", { class: "choice-title" }, p.label, p.id === "gemini" ? el("span", { class: "pill good" }, "แนะนำ") : null),
        el("span", { class: "muted small" }, p.id === "gemini"
          ? "ใช้ฟรีได้ ให้ผลดีที่สุดในการทดสอบ และใช้อ่านทักษะจากกราฟิกในเรซูเม่ได้ด้วย"
          : "ต้องเติมเครดิตในบัญชีก่อนใช้งาน")));
  }));
  setupStep(1);
}

function setupMsg(sel, kind, text) {
  const box = $(sel);
  box.className = "editor-msg" + (text ? ` alert ${kind}` : "");
  box.textContent = text || "";
}

$("#setup-next-1").addEventListener("click", () => {
  const p = providerById(setup.provider);
  $("#setup-provider-name").textContent = p.label;
  $("#setup-key-steps").textContent = p.key_help.steps;
  $("#setup-key-link").href = p.key_help.url;
  $("#setup-key-link").textContent = `เปิดหน้าขอ API key (${p.key_help.url.replace("https://", "")}) →`;
  $("#setup-key").value = "";
  setupMsg("#setup-key-msg");
  setupStep(2);
  $("#setup-key").focus();
});
$("#setup-back-2").addEventListener("click", () => setupStep(1));
$("#setup-back-3").addEventListener("click", () => setupStep(2));
$("#setup-key-toggle").addEventListener("click", ev => toggleSecret($("#setup-key"), ev.currentTarget));
$("#setup-key").addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); setupValidate(); } });
$("#setup-validate").addEventListener("click", setupValidate);
$("#setup-save").addEventListener("click", setupSave);

async function setupValidate() {
  const key = $("#setup-key").value.trim();
  if (!key) return setupMsg("#setup-key-msg", "error", "กรุณาวาง API key ก่อน (คัดลอกจากหน้าขอ key แล้วกด Ctrl+V ในช่อง)");
  const btn = $("#setup-validate");
  btn.disabled = true;
  setupMsg("#setup-key-msg", "", "กำลังตรวจสอบ key…");
  try {
    const res = await api("POST", "/api/settings/validate", { provider: setup.provider, api_key: key });
    if (!res.ok) return setupMsg("#setup-key-msg", "error", res.error.message);
    setup.key = key;
    fillSelect($("#setup-model"), res.models, null);
    setupMsg("#setup-save-msg", "ok", "key ใช้ได้ ✓");
    setupStep(3);
  } catch (e) {
    setupMsg("#setup-key-msg", "error", e.message);
  } finally {
    btn.disabled = false;
  }
}

async function setupSave() {
  const btn = $("#setup-save");
  btn.disabled = true;
  try {
    settings = await api("POST", "/api/settings/save", {
      provider: setup.provider, model: $("#setup-model").value, api_key: setup.key, make_active: true,
    });
    setup.key = "";
    $("#setup-key").value = "";
    location.hash = "#analyze";
  } catch (e) {
    setupMsg("#setup-save-msg", "error", e.message);
  } finally {
    btn.disabled = false;
  }
}

function toggleSecret(input, btn) {
  const show = input.type === "password";
  input.type = show ? "text" : "password";
  btn.textContent = show ? "ซ่อน" : "ดู";
  btn.setAttribute("aria-label", show ? "ซ่อน" : "แสดง");
}

function fillSelect(sel, models, selectedId) {
  sel.replaceChildren(...models.map(m => {
    const text = (m.recommended ? "★ " : "") + m.id + (m.label && m.label !== m.id ? ` — ${m.label}` : "") + (m.recommended ? " (แนะนำ)" : "");
    return el("option", { value: m.id }, text);
  }));
  // ค่าเริ่มต้น: โมเดลเดิม (ตอนเปลี่ยนโมเดล) ไม่งั้นตัวบนสุด (★ ถ้ามี)
  sel.value = selectedId && models.some(m => m.id === selectedId) ? selectedId : models[0].id;
}

// ============================================================
// หน้าวิเคราะห์
// ============================================================
function renderActiveBar() {
  const bar = $("#active-bar");
  const active = settings && settings.active_provider && providerById(settings.active_provider);
  if (!active) {
    bar.replaceChildren(el("div", { class: "alert warn" },
      "ยังไม่ได้ตั้ง API key — ต้องมี key ของ Gemini, OpenAI หรือ Claude อย่างน้อย 1 ตัวก่อนวิเคราะห์ ",
      el("a", { href: "#setup" }, "ตั้งค่าตอนนี้ →")));
  } else {
    bar.replaceChildren(
      el("span", { class: "muted" }, "ใช้ AI:"),
      el("span", { class: "pill good" }, active.label),
      el("span", { class: "mono" }, active.model || "(โมเดลค่าเริ่มต้น)"),
      el("a", { href: "#settings" }, "เปลี่ยน"));
  }
  updateAnalyzeButton();
}

function canAnalyze() {
  return !analyzing && !!(settings && settings.active_provider) && !!(status && status.ready);
}

function updateAnalyzeButton() {
  const ok = canAnalyze();
  $("#btn-analyze").disabled = !ok;
  for (const b of document.querySelectorAll(".sample-btn")) b.disabled = !ok;
  $("#btn-analyze").title = status && !status.ready ? "รอระบบเตรียมโมเดลให้เสร็จก่อน" : "";
}

function setAnalyzeError(err) {
  const box = $("#analyze-error");
  if (!err) { box.hidden = true; box.replaceChildren(); return; }
  box.replaceChildren(err.message || "เกิดข้อผิดพลาด");
  if (ERROR_LINKS[err.kind]) box.append(" ", el("a", { href: "#settings" }, ERROR_LINKS[err.kind]));
  box.hidden = false;
}

async function loadSamples() {
  try {
    const data = await api("GET", "/api/samples");
    $("#sample-job-title").textContent = data.job_title;
    $("#sample-list").replaceChildren(...data.samples.map(s => {
      const btn = el("button", { type: "button", class: "sample-btn" },
        el("span", { class: "sample-title" }, s.title),
        el("span", { class: "muted small" }, s.description));
      btn.addEventListener("click", () => runSample(s, data));
      return el("div", { class: "sample" }, btn,
        el("a", { class: "small", href: `/api/samples/${s.id}/file`, target: "_blank", rel: "noopener" }, "ดูไฟล์"));
    }));
    updateAnalyzeButton();
  } catch (e) {
    $("#sample-list").replaceChildren(el("div", { class: "alert error" }, e.message));
  }
}

function runSample(s, data) {
  return runAnalysis(() => api("POST", `/api/samples/${s.id}/analyze`), {
    label: `ตัวอย่าง: ${s.title}`, jobTitle: data.job_title,
  });
}

function onAnalyze(ev) {
  ev.preventDefault();
  setAnalyzeError(null);
  const file = $("#f-file").files[0];
  const jobText = $("#f-job-text").value.trim();
  if (!file) return setAnalyzeError({ message: "กรุณาเลือกไฟล์เรซูเม่ (PDF)" });
  if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") return setAnalyzeError({ message: "รับเฉพาะไฟล์ PDF เท่านั้น — เลือกไฟล์นามสกุล .pdf" });
  if (file.size > MAX_FILE_MB * 1024 * 1024) return setAnalyzeError({ message: `ไฟล์ใหญ่เกิน ${MAX_FILE_MB} MB — ลองบีบอัดไฟล์ หรือบันทึก PDF ใหม่แบบความละเอียดต่ำลง` });
  if (!jobText) return setAnalyzeError({ message: "กรุณากรอกรายละเอียดงาน" });

  const fd = new FormData();
  fd.append("file", file);
  fd.append("job_text", jobText);
  const title = $("#f-job-title").value.trim();
  const faculty = $("#f-faculty-match").value.trim();
  if (title) fd.append("job_title", title);
  if (faculty) fd.append("faculty_match", faculty);
  runAnalysis(() => api("POST", "/analyze-file", fd), { label: file.name, jobTitle: title });
}

async function runAnalysis(request, source) {
  if (!canAnalyze()) return;
  setAnalyzeError(null);
  analyzing = true;
  updateAnalyzeButton();
  const box = $("#analyze-status");
  box.replaceChildren(el("span", { class: "spinner" }),
    `กำลังวิเคราะห์ ${source.label}… (ปกติ 10–60 วินาที ไฟล์ที่ต้องอ่านจากภาพอาจนานกว่านั้น)`);
  box.hidden = false;
  const started = performance.now();
  try {
    const r = await request();
    lastResult = { r, source };
    renderResult(r, source);
    box.textContent = `เสร็จใน ${((performance.now() - started) / 1000).toFixed(1)} วินาที`;
    $("#result").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    setAnalyzeError(e);
    box.hidden = true;
  } finally {
    analyzing = false;
    updateAnalyzeButton();
  }
}

// แสดงเฉพาะ field ที่มีอยู่จริงใน response
const has = (r, k) => r && Object.prototype.hasOwnProperty.call(r, k) && r[k] !== null && r[k] !== undefined && r[k] !== "";
const pct = v => `${Math.round(Number(v) * 100)}%`;

function verdictClass(text) {
  if (text.startsWith("ไม่ควรรับ")) return "bad";
  if (text.startsWith("ควรรับ")) return "good";
  return "";
}

const STORY_LABEL = { High: "ดี", Medium: "ปานกลาง", Low: "น้อย" };

function scoreLabel(v) {
  if (v >= 75) return "เหมาะสมมาก";
  if (v >= 60) return "ค่อนข้างเหมาะสม";
  if (v >= 45) return "เหมาะสมบางส่วน";
  return "ไม่ค่อยตรงกับงาน";
}

function splitSkills(r) {
  const visual = r.visual_skills_used ? (r.visual_skills || []) : [];
  const vset = new Set(visual.map(s => s.toLowerCase()));
  // สกิลจากกราฟิกถูกต่อท้ายข้อความก่อนวิเคราะห์ จึงอาจโผล่ใน hard skills ซ้ำ — แสดงที่ป้าย "อ่านจากกราฟิก" ที่เดียว
  const hard = ((r.skills && r.skills.hard) || []).filter(s => !vset.has(s.toLowerCase()));
  const soft = (r.skills && r.skills.soft) || [];
  return { hard, soft, visual };
}

function renderResult(r, source) {
  const out = [];

  out.push(el("div", { class: "result-head" },
    el("div", {},
      el("div", { class: "muted small" }, "ผลการวิเคราะห์"),
      el("div", { class: "result-title" }, source.label + (source.jobTitle ? ` → ${source.jobTitle}` : ""))),
    el("div", { class: "result-actions" },
      el("button", { type: "button", class: "btn", id: "btn-copy" }, "คัดลอกผล"),
      el("button", { type: "button", class: "btn", id: "btn-print" }, "บันทึกเป็น PDF"))));

  for (const n of r.notices || []) {
    out.push(el("div", { class: `alert ${n.level === "warn" ? "warn" : "info"}` }, n.text));
  }

  // 1. คะแนน + คำแนะนำ
  const top = el("div", { class: "top-summary" });
  if (has(r, "matching_score")) {
    const v = Math.max(0, Math.min(100, Number(r.matching_score)));
    top.append(el("div", { class: "score" },
      el("h3", {}, "คะแนนความเหมาะสมกับตำแหน่ง"),
      el("div", { class: "score-value" }, Number(r.matching_score).toFixed(1), el("small", {}, " / 100")),
      el("div", { class: "bar", role: "img", "aria-label": `คะแนน ${v} จาก 100` }, el("span", { style: `width:${v}%` })),
      el("div", { class: "muted small" }, scoreLabel(v))));
  }
  if (has(r, "recommendation_reason")) {
    const text = r.recommendation_reason;
    const cls = verdictClass(text);
    const stamp = cls === "bad" ? "ไม่ควรรับ" : cls === "good" ? "ควรรับ" : "ควรพิจารณา";
    top.append(el("div", { class: `verdict ${cls}` },
      el("span", { class: "verdict-stamp" }, stamp),
      el("div", {}, el("h3", {}, "คำแนะนำ"), el("p", {}, text))));
  }
  out.push(top);

  // 2. ทักษะที่พบ
  if (has(r, "skills")) {
    const { hard, soft, visual } = splitSkills(r);
    const block = el("div", { class: "block" }, el("h3", {}, "ทักษะที่พบในเรซูเม่"));
    const chips = (items, cls) => items.length
      ? el("div", { class: "chips" }, items.map(s => el("span", { class: `chip ${cls}` }, s)))
      : el("span", { class: "muted small" }, "ไม่พบ");
    block.append(el("div", { class: "skill-group" }, el("h4", {}, `ทักษะเฉพาะทาง (${hard.length})`), chips(hard, "")));
    if (visual.length) {
      block.append(el("div", { class: "skill-group" },
        el("h4", {}, `อ่านจากกราฟิก (${visual.length})`, " ", el("span", { class: "muted small" }, "— ทักษะที่แสดงเป็นแถบกราฟ/ดาว/โลโก้ในเรซูเม่")),
        chips(visual, "visual")));
    }
    block.append(el("div", { class: "skill-group" }, el("h4", {}, `ทักษะด้านอื่น (${soft.length})`), chips(soft, "soft")));
    out.push(block);
  }

  // 3. จุดเด่นเทียบกับงาน
  if (has(r, "specific_strengths")) {
    out.push(el("div", { class: "block" }, el("h3", {}, "จุดเด่นเทียบกับงาน"), el("p", {}, r.specific_strengths)));
  }

  // 4. การเล่าเรื่องในเรซูเม่
  if (has(r, "storytelling_score") || has(r, "ai_reason")) {
    const head = el("div", { class: "block-head" }, el("h3", {}, "การเล่าเรื่องในเรซูเม่"));
    if (has(r, "storytelling_score")) {
      const s = r.storytelling_score;
      head.append(el("span", { class: `pill ${s === "High" ? "good" : s === "Low" ? "bad" : "warn"}` }, STORY_LABEL[s] || s));
    }
    const block = el("div", { class: "block" }, head,
      el("p", { class: "muted small" }, "เรซูเม่ที่ดีเล่าว่าเจอปัญหาอะไร → ทำอะไร → ได้ผลอย่างไร (มีตัวเลข) ไม่ใช่แค่ลิสต์ทักษะ"));
    if (has(r, "ai_reason")) block.append(el("p", {}, r.ai_reason));
    if (has(r, "faculty_match")) block.append(el("p", {}, el("b", {}, "คณะ/สาขา: "), r.faculty_match));
    out.push(block);
  }

  // 5. ค่าทางเทคนิค (พับไว้)
  const details = [
    ["raw_matching_score", "คะแนนดิบ (SBERT ก่อนหักคะแนน)", v => v],
    ["matching_penalty_multiplier", "ตัวคูณหักคะแนน (คณะ × ทักษะ)", v => `×${v}`],
    ["skill_overlap_ratio", "ทักษะที่งานต้องการแล้วเรซูเม่มี", pct],
    ["resume_quality_score", "คุณภาพเรซูเม่ (ไม่เทียบกับงาน)", v => `${v} / 100`],
    ["matching_confidence", "ความมั่นใจของคะแนน", pct],
    ["skill_extraction_confidence", "ความมั่นใจการดึงทักษะ", pct],
    ["storytelling_confidence", "ความมั่นใจของ AI", pct],
    ["overall_confidence", "ความมั่นใจรวม", pct],
    ["storytelling_provider", "ค่าย AI ที่ใช้", v => v],
    ["storytelling_latency_seconds", "เวลาที่ AI ใช้", v => `${v} วินาที`],
    ["text_extraction_method", "วิธีอ่านไฟล์", v => (v === "ocr_fallback" ? "อ่านจากภาพ (OCR)" : v === "text_layer" ? "ข้อความในไฟล์ (text layer)" : v)],
    ["text_extraction_warning", "หมายเหตุการอ่านไฟล์", v => v],
  ].filter(([k]) => has(r, k));
  if (details.length) {
    out.push(el("details", { class: "block more" },
      el("summary", {}, "รายละเอียดเพิ่มเติม (ค่าทางเทคนิค)"),
      el("dl", { class: "kv" }, details.flatMap(([k, label, fmt]) => [el("dt", {}, label), el("dd", {}, fmt(r[k]))]))));
  }

  $("#result").replaceChildren(...out);
  $("#btn-copy").addEventListener("click", copyResult);
  $("#btn-print").addEventListener("click", () => {
    // เปิดรายละเอียดเพิ่มเติมก่อนพิมพ์ จะได้อยู่ใน PDF ด้วย
    for (const d of document.querySelectorAll("#result details")) d.open = true;
    window.print();
  });
}

function resultAsText(r, source) {
  const { hard, soft, visual } = splitSkills(r);
  const lines = [
    `ผลการวิเคราะห์เรซูเม่ (Resume AI ${status ? "v" + status.version : ""})`,
    `ไฟล์: ${source.label}` + (source.jobTitle ? ` | ตำแหน่ง: ${source.jobTitle}` : ""),
    "",
  ];
  if (has(r, "matching_score")) lines.push(`คะแนนความเหมาะสม: ${Number(r.matching_score).toFixed(1)} / 100 (${scoreLabel(r.matching_score)})`);
  if (has(r, "recommendation_reason")) lines.push(`คำแนะนำ: ${r.recommendation_reason}`);
  lines.push("", `ทักษะเฉพาะทาง: ${hard.join(", ") || "-"}`);
  if (visual.length) lines.push(`ทักษะที่อ่านจากกราฟิก: ${visual.join(", ")}`);
  lines.push(`ทักษะด้านอื่น: ${soft.join(", ") || "-"}`);
  if (has(r, "specific_strengths")) lines.push("", `จุดเด่นเทียบกับงาน: ${r.specific_strengths}`);
  if (has(r, "storytelling_score")) lines.push("", `การเล่าเรื่องในเรซูเม่: ${STORY_LABEL[r.storytelling_score] || r.storytelling_score}`);
  if (has(r, "ai_reason")) lines.push(r.ai_reason);
  if (has(r, "faculty_match")) lines.push(`คณะ/สาขา: ${r.faculty_match}`);
  for (const n of r.notices || []) lines.push("", `หมายเหตุ: ${n.text}`);
  return lines.join("\n");
}

async function copyResult() {
  if (!lastResult) return;
  const text = resultAsText(lastResult.r, lastResult.source);
  const btn = $("#btn-copy");
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "คัดลอกแล้ว ✓";
  } catch {
    // เบราว์เซอร์บางตัวไม่ให้เข้าถึง clipboard — ใช้วิธีเลือกข้อความแทน
    const ta = el("textarea", { style: "position:fixed;opacity:0" }, text);
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    btn.textContent = ok ? "คัดลอกแล้ว ✓" : "คัดลอกไม่ได้";
  }
  setTimeout(() => { btn.textContent = "คัดลอกผล"; }, 2000);
}

// ============================================================
// หน้าตั้งค่า
// ============================================================
function settingsMessage(kind, text) {
  const box = $("#settings-msg");
  if (!text) { box.hidden = true; return; }
  box.className = `alert ${kind}`;
  box.textContent = text;
  box.hidden = false;
}

function renderSettingsPage() {
  if (!settings) return;
  renderProviders();
  renderVisual();
}

function renderVisual() {
  const v = settings.visual;
  $("#visual-enabled").checked = v.enabled;
  $("#visual-enabled-label").textContent = v.enabled ? "เปิด" : "ปิด";
  $("#visual-model").textContent = v.active
    ? `ใช้โมเดล ${v.model || "Gemini ค่าเริ่มต้น"} (โมเดลเดียวกับที่เลือกไว้ให้ Gemini ด้านบน)`
    : (v.enabled ? "" : "ปิดอยู่ — ทักษะที่เป็นกราฟิกในเรซูเม่จะไม่ถูกนับ");
  $("#visual-note").hidden = !v.note;
  $("#visual-note").textContent = v.note || "";
}

$("#visual-enabled").addEventListener("change", async ev => {
  try {
    settings = await api("POST", "/api/settings/visual", { enabled: ev.target.checked });
    renderVisual();
  } catch (e) {
    settingsMessage("error", e.message);
  }
});

function renderProviders() {
  const list = $("#provider-list");
  // ไม่วาดใหม่ทับการ์ดที่กำลังแก้อยู่ (ไม่งั้น key ที่พิมพ์ค้างไว้จะหาย)
  if (list.querySelector(".editor:not([hidden])")) return;
  list.replaceChildren(...settings.providers.map(buildProviderCard));
}

function buildProviderCard(p) {
  const card = $("#tpl-provider").content.firstElementChild.cloneNode(true);
  card.dataset.provider = p.id;
  const isActive = settings.active_provider === p.id;
  card.classList.toggle("is-active", isActive);

  $(".p-name", card).textContent = p.label;
  $(".p-name-inline", card).textContent = p.label;
  const st = $(".p-status", card);
  st.textContent = p.configured ? "ตั้งค่าแล้ว" : "ยังไม่ตั้ง";
  st.classList.add(p.configured ? "good" : "warn");
  $(".p-key", card).textContent = p.masked_key || "—";
  $(".p-model", card).textContent = p.configured ? (p.model || "(ค่าเริ่มต้นของโปรแกรม)") : "—";
  $(".p-key-steps", card).textContent = p.key_help.steps;
  $(".p-key-link", card).href = p.key_help.url;

  const radio = $(".p-active", card);
  radio.id = `active-${p.id}`;
  radio.checked = isActive;
  radio.disabled = !p.configured;
  radio.addEventListener("change", () => makeActive(p));

  const keyBtn = $(".p-btn-key", card);
  keyBtn.textContent = p.configured ? "เปลี่ยน key" : "ใส่ API key";
  if (!p.configured) keyBtn.classList.add("primary");
  keyBtn.addEventListener("click", () => openKeyEditor(card, p));
  $(".p-btn-model", card).hidden = !p.configured;
  $(".p-btn-model", card).addEventListener("click", () => openModelEditor(card, p));
  $(".p-btn-delete", card).hidden = !p.configured;
  $(".p-btn-delete", card).addEventListener("click", () => { $(".p-confirm", card).hidden = false; });
  $(".p-confirm-no", card).addEventListener("click", () => { $(".p-confirm", card).hidden = true; });
  $(".p-confirm-yes", card).addEventListener("click", () => deleteProvider(p));

  const keyInput = $(".p-key-input", card);
  keyInput.id = `key-${p.id}`;
  $(".p-model-select", card).id = `model-${p.id}`;
  $(".p-make-active", card).id = `make-active-${p.id}`;
  $(".p-toggle-key", card).addEventListener("click", ev => toggleSecret(keyInput, ev.currentTarget));
  // แก้ key หลังตรวจผ่านแล้ว = ต้องตรวจใหม่ (กันบันทึก key ที่ยังไม่ได้ตรวจ)
  keyInput.addEventListener("input", () => {
    $(".model-row", card).hidden = true;
    $(".p-save", card).hidden = true;
    editorMsg(card);
  });
  keyInput.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); validateKey(card, p); } });
  $(".p-validate", card).addEventListener("click", () => validateKey(card, p));
  $(".p-save", card).addEventListener("click", () => saveProvider(card, p));
  $(".p-cancel", card).addEventListener("click", () => closeEditor(card));
  return card;
}

function editorMsg(card, kind, text) {
  const box = $(".editor-msg", card);
  box.className = "editor-msg" + (text ? ` alert ${kind}` : "");
  box.textContent = text || "";
}

function closeEditor(card) {
  $(".p-key-input", card).value = "";
  $(".editor", card).hidden = true;
  editorMsg(card);
}

function openKeyEditor(card, p) {
  settingsMessage();
  const ed = $(".editor", card);
  ed.hidden = false;
  ed.dataset.mode = "key";
  $(".p-key-help", card).hidden = false;
  $(".key-row", card).hidden = false;
  $(".model-row", card).hidden = true;
  $(".p-save", card).hidden = true;
  $(".p-make-active", card).checked = !settings.active_provider || settings.active_provider === p.id;
  editorMsg(card);
  $(".p-key-input", card).focus();
}

async function validateKey(card, p) {
  const key = $(".p-key-input", card).value.trim();
  if (!key) return editorMsg(card, "error", "กรุณาวาง API key ก่อน");
  const btn = $(".p-validate", card);
  btn.disabled = true;
  editorMsg(card, "", "กำลังตรวจสอบ key กับ " + p.label + "…");
  try {
    const res = await api("POST", "/api/settings/validate", { provider: p.id, api_key: key });
    if (!res.ok) {
      $(".model-row", card).hidden = true;
      $(".p-save", card).hidden = true;
      return editorMsg(card, "error", res.error.message);
    }
    fillSelect($(".p-model-select", card), res.models, null);
    $(".model-row", card).hidden = false;
    $(".p-save", card).hidden = false;
    editorMsg(card, "ok", `key ใช้ได้ — เลือกโมเดลแล้วกด “บันทึก”`);
  } catch (e) {
    editorMsg(card, "error", e.message);
  } finally {
    btn.disabled = false;
  }
}

async function openModelEditor(card, p) {
  settingsMessage();
  const ed = $(".editor", card);
  ed.hidden = false;
  ed.dataset.mode = "model";
  $(".p-key-help", card).hidden = true;
  $(".key-row", card).hidden = true;
  $(".model-row", card).hidden = true;
  $(".p-save", card).hidden = true;
  $(".p-make-active", card).checked = settings.active_provider === p.id;
  editorMsg(card, "", "กำลังดึงรายชื่อโมเดล…");
  try {
    const res = await api("GET", `/api/settings/${p.id}/models`);
    if (!res.ok) return editorMsg(card, "error", res.error.message);
    fillSelect($(".p-model-select", card), res.models, p.model);
    $(".model-row", card).hidden = false;
    $(".p-save", card).hidden = false;
    editorMsg(card);
  } catch (e) {
    editorMsg(card, "error", e.message);
  }
}

async function saveProvider(card, p) {
  const body = {
    provider: p.id,
    model: $(".p-model-select", card).value,
    make_active: $(".p-make-active", card).checked,
  };
  if ($(".editor", card).dataset.mode === "key") body.api_key = $(".p-key-input", card).value.trim();
  const btn = $(".p-save", card);
  btn.disabled = true;
  try {
    settings = await api("POST", "/api/settings/save", body);
    closeEditor(card);
    settingsMessage("ok", `บันทึกการตั้งค่า ${p.label} แล้ว (โมเดล ${body.model}) — มีผลกับการวิเคราะห์ครั้งถัดไปทันที`);
    renderSettingsPage();
    renderActiveBar();
  } catch (e) {
    editorMsg(card, "error", e.message);
  } finally {
    btn.disabled = false;
  }
}

async function makeActive(p) {
  try {
    settings = await api("POST", "/api/settings/save", { provider: p.id, make_active: true });
    settingsMessage("ok", `ตั้ง ${p.label} เป็นค่ายหลักแล้ว`);
  } catch (e) {
    settingsMessage("error", e.message);
  }
  renderSettingsPage();
  renderActiveBar();
}

async function deleteProvider(p) {
  try {
    settings = await api("DELETE", `/api/settings/${p.id}`);
    settingsMessage("ok", `ลบ key ของ ${p.label} แล้ว`);
  } catch (e) {
    settingsMessage("error", e.message);
  }
  renderSettingsPage();
  renderActiveBar();
}

async function openLogs() {
  try {
    const res = await api("POST", "/api/open-log-folder");
    settingsMessage("ok", `เปิดโฟลเดอร์ log แล้ว (${res.path}) — ส่งไฟล์ resume_ai.log ให้ผู้ดูแลได้เลย`);
  } catch (e) {
    settingsMessage("error", e.message);
  }
}
$("#open-logs").addEventListener("click", openLogs);
$("#footer-logs").addEventListener("click", async () => {
  try { await api("POST", "/api/open-log-folder"); } catch (e) { alert(e.message); }
});

// ============================================================
// ขั้นสูง: เชื่อมต่อกับเว็บ (ngrok tunnel + token ลับ)
// ============================================================
const TUNNEL_DOT = { connected: "good", connecting: "warn", reconnecting: "warn", error: "bad" };
let connection = null;
let connectionTimer = null;

function connectMessage(kind, text) {
  const box = $("#connect-msg");
  if (!text) { box.hidden = true; return; }
  box.className = `alert ${kind}`;
  box.textContent = text;
  box.hidden = false;
}

async function loadConnection() {
  try {
    connection = await api("GET", "/api/connection");
    renderConnection();
  } catch (e) {
    connectMessage("error", e.message);
  }
}

function renderConnection() {
  const c = connection;
  const t = c.tunnel;
  $("#tunnel-label").textContent = t.label;
  $("#tunnel-dot").className = `dot ${TUNNEL_DOT[t.state] || ""}`;
  const err = $("#tunnel-error");
  err.hidden = !t.message;
  err.className = `alert ${t.state === "error" ? "error" : "warn"}`;
  err.textContent = t.message || "";

  $("#tunnel-enabled").checked = c.enabled;
  $("#tunnel-enabled").disabled = !c.ngrok_configured;
  $("#tunnel-url").textContent = t.url || "— (ยังไม่เชื่อมต่อ)";
  $("#copy-url").disabled = !t.url;
  $("#service-token").textContent = c.service_token_masked || "—";
  $("#ngrok-masked").textContent = c.ngrok_masked || "ยังไม่ได้ใส่";
  $("#ngrok-edit").textContent = c.ngrok_configured ? "เปลี่ยน authtoken" : "ใส่ authtoken";
  $("#ngrok-edit").classList.toggle("primary", !c.ngrok_configured);
  $("#ngrok-delete").hidden = !c.ngrok_configured;
}

function startConnectionPolling() {
  stopConnectionPolling();
  loadConnection();
  // สถานะ tunnel เปลี่ยนเองได้ (หลุด/ต่อใหม่) — ดึงใหม่เป็นระยะเฉพาะตอนเปิดส่วนขั้นสูงอยู่
  connectionTimer = setInterval(loadConnection, 3000);
}

function stopConnectionPolling() {
  if (connectionTimer) clearInterval(connectionTimer);
  connectionTimer = null;
}

function syncConnectionPolling() {
  if (currentPage() === "settings" && $("#advanced").open) startConnectionPolling();
  else stopConnectionPolling();
}
$("#advanced").addEventListener("toggle", syncConnectionPolling);

async function copyText(text, what) {
  try {
    await navigator.clipboard.writeText(text);
    connectMessage("ok", `คัดลอก${what}แล้ว`);
  } catch {
    connectMessage("error", `คัดลอกอัตโนมัติไม่ได้ — ${what}: ${text}`);
  }
}

$("#copy-url").addEventListener("click", () => {
  if (connection && connection.tunnel.url) copyText(connection.tunnel.url.replace(/\/$/, ""), " URL ");
});
$("#copy-token").addEventListener("click", async () => {
  try {
    const res = await api("GET", "/api/connection/service-token");
    await copyText(res.token, " token ");
  } catch (e) {
    connectMessage("error", e.message);
  }
});
$("#regen-token").addEventListener("click", () => { $("#regen-confirm").hidden = false; });
$("#regen-no").addEventListener("click", () => { $("#regen-confirm").hidden = true; });
$("#regen-yes").addEventListener("click", async () => {
  $("#regen-confirm").hidden = true;
  try {
    connection = await api("POST", "/api/connection/service-token/regenerate");
    renderConnection();
    connectMessage("warn", "สร้าง token ใหม่แล้ว — กด “คัดลอก” แล้วไปอัปเดต AI_SERVICE_TOKEN บน Render (ระหว่างนี้เว็บจะเรียก AI ไม่ได้)");
  } catch (e) {
    connectMessage("error", e.message);
  }
});

$("#tunnel-enabled").addEventListener("change", async ev => {
  try {
    connection = await api("POST", "/api/connection/enabled", { enabled: ev.target.checked });
    renderConnection();
  } catch (e) {
    connectMessage("error", e.message);
  }
});

function closeNgrokEditor() {
  $("#ngrok-input").value = "";
  $("#ngrok-editor").hidden = true;
}
$("#ngrok-edit").addEventListener("click", () => {
  $("#ngrok-editor").hidden = false;
  $("#ngrok-input").focus();
});
$("#ngrok-cancel").addEventListener("click", closeNgrokEditor);
$("#ngrok-toggle").addEventListener("click", ev => toggleSecret($("#ngrok-input"), ev.currentTarget));
async function saveNgrok() {
  const authtoken = $("#ngrok-input").value.trim();
  if (!authtoken) return connectMessage("error", "กรุณาวาง ngrok authtoken");
  try {
    connection = await api("POST", "/api/connection/ngrok", { authtoken });
    closeNgrokEditor();
    renderConnection();
    connectMessage("ok", "บันทึก authtoken แล้ว กำลังเชื่อมต่อ…");
  } catch (e) {
    connectMessage("error", e.message);
  }
}
$("#ngrok-save").addEventListener("click", saveNgrok);
$("#ngrok-input").addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); saveNgrok(); } });
$("#ngrok-delete").addEventListener("click", async () => {
  try {
    connection = await api("DELETE", "/api/connection/ngrok");
    renderConnection();
    connectMessage("ok", "ลบ ngrok authtoken แล้ว ปิดการเชื่อมต่อแล้ว");
  } catch (e) {
    connectMessage("error", e.message);
  }
});

// ============================================================
window.addEventListener("hashchange", () => { showPage(); syncConnectionPolling(); });
$("#analyze-form").addEventListener("submit", onAnalyze);
pollStatus();
loadSamples();
showPage();
