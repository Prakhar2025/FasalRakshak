/* FasalRakshak frontend v2.
   A deliberate state machine: idle -> capturing -> processing -> result.
   Everything the user can click does something real: 10-language switching,
   voice recording, drag-and-drop upload, and an audio player driven by the
   actual audio signal (WebAudio analyser), with seek and correct states.
   Fail-closed UX: every error ends in a clear message, never silence. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var els = {
    langs: $("langs"),
    voiceStatus: $("voice-status"),
    mic: $("mic-button"),
    typeToggle: $("type-toggle"),
    typePanel: $("type-panel"),
    typeInput: $("type-input"),
    typeSend: $("type-send"),
    dropzone: $("dropzone"),
    photoInput: $("photo-input"),
    previewRow: $("preview-row"),
    previewThumb: $("preview-thumb"),
    previewName: $("preview-name"),
    previewClear: $("preview-clear"),
    demoStrip: $("demo-strip"),
    processing: $("processing"),
    processingHi: $("processing-hi"),
    toast: $("toast"),
    emptyHint: $("empty-hint"),
    resultArea: $("result-area"),
    audioBar: $("audio-bar"),
    audioPlay: $("audio-play"),
    audio: $("answer-audio"),
    audioTime: $("audio-time"),
    waveform: $("waveform"),
    progressbar: $("progressbar"),
    progressFill: $("progress-fill"),
  };

  var state = {
    lang: localStorage.getItem("fr_lang") || "hi",
    image: null,
    imagePreview: null,
    audioBlob: null,
    recorder: null,
    recordingTimer: null,
    sessionId: null,
    audioContext: null,
    analyser: null,
    rafId: null,
    waveEls: [],
  };

  /* ================= i18n ================= */

  function t(key) {
    var pack = window.FR_I18N[state.lang] || window.FR_I18N.en;
    return pack[key] != null ? pack[key] : (window.FR_I18N.en[key] || key);
  }

  function applyLang() {
    document.documentElement.lang = state.lang;
    var pack = window.FR_I18N[state.lang] || window.FR_I18N.en;
    Array.prototype.forEach.call(document.querySelectorAll("[data-i18n]"), function (el) {
      var value = pack[el.getAttribute("data-i18n")];
      if (value != null) { el.textContent = value; }
    });
    els.typeInput.placeholder = state.lang === "en" ? "e.g. brown spots on the leaves" : t("speak");
    Array.prototype.forEach.call(els.langs.querySelectorAll(".lang-chip"), function (chip) {
      chip.classList.toggle("active", chip.getAttribute("data-lang") === state.lang);
    });
  }

  els.langs.addEventListener("click", function (event) {
    var chip = event.target.closest(".lang-chip");
    if (!chip) { return; }
    state.lang = chip.getAttribute("data-lang");
    localStorage.setItem("fr_lang", state.lang);
    applyLang();
  });

  /* ================= helpers ================= */

  function show(el) { el.classList.add("show"); }
  function hide(el) { el.classList.remove("show"); }

  function toast(message) {
    els.toast.textContent = message;
    show(els.toast);
    window.setTimeout(function () { hide(els.toast); }, 6000);
  }

  function setBusy(busy, line) {
    els.processingHi.textContent = line || t("processing");
    if (busy) {
      show(els.processing);
      hide(els.resultArea);
      hide(els.emptyHint);
      els.mic.disabled = true;
    } else {
      hide(els.processing);
      els.mic.disabled = false;
    }
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  /* ================= audio player v2 ================= */

  var BAR_COUNT = 28;

  function buildWave() {
    els.waveform.innerHTML = "";
    state.waveEls = [];
    for (var i = 0; i < BAR_COUNT; i++) {
      var bar = document.createElement("i");
      bar.style.height = "20%";
      els.waveform.appendChild(bar);
      state.waveEls.push(bar);
    }
  }

  function connectAnalyser() {
    try {
      state.audioContext = state.audioContext || new (window.AudioContext || window.webkitAudioContext)();
      var source = state.audioContext.createMediaElementSource(els.audio);
      state.analyser = state.audioContext.createAnalyser();
      state.analyser.fftSize = 64;
      source.connect(state.analyser);
      state.analyser.connect(state.audioContext.destination);
    } catch (error) {
      state.analyser = null; /* analyser is decoration; playback still works */
    }
  }

  function animateWave() {
    if (!state.analyser) { return; }
    var data = new Uint8Array(state.analyser.frequencyBinCount);
    state.analyser.getByteFrequencyData(data);
    var step = Math.floor(data.length / BAR_COUNT) || 1;
    for (var i = 0; i < BAR_COUNT; i++) {
      var value = data[i * step] / 255;
      state.waveEls[i].style.height = Math.max(12, Math.round(value * 100)) + "%";
      state.waveEls[i].classList.toggle("on", value > 0.35);
    }
    state.rafId = requestAnimationFrame(animateWave);
  }

  function stopWave() {
    if (state.rafId) { cancelAnimationFrame(state.rafId); state.rafId = null; }
    for (var i = 0; i < state.waveEls.length; i++) {
      state.waveEls[i].style.height = "20%";
      state.waveEls[i].classList.remove("on");
    }
  }

  function fmt(seconds) {
    if (!isFinite(seconds)) { seconds = 0; }
    var m = Math.floor(seconds / 60);
    var s = Math.floor(seconds % 60);
    return m + ":" + ("0" + s).slice(-2);
  }

  function updateProgress() {
    var total = els.audio.duration || 0;
    var current = els.audio.currentTime || 0;
    var pct = total ? (current / total) * 100 : 0;
    els.progressFill.style.right = (100 - pct) + "%";
    els.progressbar.setAttribute("aria-valuenow", Math.round(pct));
    els.audioTime.textContent = fmt(current) + " / " + fmt(total);
  }

  function setAudio(dataUri) {
    if (!dataUri) { hide(els.audioBar); return; }
    buildWave();
    els.audio.src = dataUri;
    show(els.audioBar);
    els.audio.play().catch(function () {});
  }

  els.audioPlay.addEventListener("click", function () {
    if (els.audio.paused) { els.audio.play().catch(function () {}); }
    else { els.audio.pause(); }
  });

  els.audio.addEventListener("play", function () {
    els.audioPlay.classList.add("playing");
    if (!state.analyser) { connectAnalyser(); }
    if (state.audioContext && state.audioContext.state === "suspended") { state.audioContext.resume(); }
    stopWave();
    animateWave();
  });

  els.audio.addEventListener("pause", function () {
    els.audioPlay.classList.remove("playing");
    stopWave();
  });

  els.audio.addEventListener("timeupdate", updateProgress);
  els.audio.addEventListener("ended", function () {
    els.audioPlay.classList.remove("playing");
    stopWave();
    updateProgress();
  });

  els.progressbar.addEventListener("click", function (event) {
    var rect = els.progressbar.getBoundingClientRect();
    var fraction = (event.clientX - rect.left) / rect.width;
    if (els.audio.duration) { els.audio.currentTime = fraction * els.audio.duration; }
  });

  /* ================= result rendering ================= */

  var ICONS = {
    shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    shieldAlert: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    badgeCheck: '<path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/><path d="m9 12 2 2 4-4"/>',
  };

  function notice(kind, iconPath, text) {
    return '<div class="notice ' + kind + '">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + iconPath + "</svg>" +
      "<span>" + escapeHtml(text) + "</span></div>";
  }

  function renderResult(data) {
    var html = "";
    if (data.status === "retake") {
      html += notice("info", ICONS.info, "यह फोटो ठीक से नहीं आई। पत्ती को साफ रोशनी में, पास से दोबारा फोटो लें।");
    } else if (data.status === "escalated") {
      html += notice("blocked", ICONS.shieldAlert, "यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।");
      if (data.safety && data.safety.rules_triggered && data.safety.rules_triggered.some(function (r) { return r.rule_id === "R7"; })) {
        html += notice("blocked", ICONS.shieldAlert, "आपातकाल: तुरंत 112 पर कॉल करें या नज़दीकी अस्पताल जाएँ।");
      }
    } else if (data.status === "blocked") {
      html += notice("blocked", ICONS.shieldAlert, "यह सुझाव सुरक्षा जाँच में नहीं टिका। कृषि अधिकारी से मिलें।");
      ((data.safety && data.safety.spoken_addendum) || []).forEach(function (line) {
        html += notice("blocked", ICONS.shieldAlert, line);
      });
    } else if (data.status === "treated" && data.treatment) {
      var dx = data.diagnosis || {};
      var label = state.lang === "en" ? (dx.label || "") : (dx.label_hi || dx.label || "");
      html += '<div class="card"><div class="dx-head">' +
        '<div class="dx-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg></div>' +
        '<div><p class="dx-label-hi">' + escapeHtml(label) + "</p>" +
        '<p class="dx-label-en">' + escapeHtml(dx.label || "") + (dx.pathogen ? " · " + escapeHtml(dx.pathogen) : "") + "</p></div>" +
        '<div class="confidence"><div class="confidence-value">' + Math.round((dx.confidence || 0) * 100) + '%</div><div class="confidence-caption">' + escapeHtml(t("confidence")) + "</div></div>" +
        "</div>";
      html += '<ol class="steps">' +
        data.treatment.steps.map(function (step) { return "<li>" + escapeHtml(step) + "</li>"; }).join("") +
        "</ol></div>";

      if (data.treatment.products && data.treatment.products.length) {
        html += '<div class="card" style="padding-top:6px;padding-bottom:4px;">';
        data.treatment.products.forEach(function (product) {
          html += '<div class="product-row"><span class="product-name">' + escapeHtml(product.name) + "</span>" +
            '<span class="chip dose">' + escapeHtml(product.dose + " " + product.unit) + "</span>" +
            (product.phi_days > 0 ? '<span class="chip phi">फसल तोड़ने से ' + product.phi_days + " दिन पहले तक नहीं</span>" : "") +
            "</div>";
        });
        html += "</div>";
      }

      ((data.safety && data.safety.spoken_addendum) || []).forEach(function (line) {
        var kind = /प्रतिबंधित/.test(line) ? "blocked" : (/न करें|पहले तक/.test(line) ? "phi" : "ppe");
        html += notice(kind, kind === "blocked" ? ICONS.shieldAlert : (kind === "phi" ? ICONS.clock : ICONS.shieldCheck), line);
      });

      ((data.treatment.citations) || []).forEach(function (citation) {
        html += '<span class="source-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS.badgeCheck + '</svg> ' + escapeHtml(t("source")) + ": " + escapeHtml(citation.org) + "</span>";
      });
    }

    html += '<div class="card"><div class="feedback-row">' +
      '<span class="feedback-q">' + escapeHtml(t("feedback_q")) + "</span>" +
      '<button class="fb-btn" type="button" data-outcome="resolved">' + escapeHtml(t("yes")) + "</button>" +
      '<button class="fb-btn" type="button" data-outcome="worse">' + escapeHtml(t("no")) + "</button>" +
      "</div></div>";

    els.resultArea.innerHTML = html;
    Array.prototype.forEach.call(els.resultArea.querySelectorAll(".fb-btn"), function (button) {
      button.addEventListener("click", function () {
        Array.prototype.forEach.call(els.resultArea.querySelectorAll(".fb-btn"), function (other) { other.classList.remove("chosen"); });
        button.classList.add("chosen");
        sendFeedback(button.getAttribute("data-outcome"));
      });
    });
    show(els.resultArea);
  }

  /* ================= api ================= */

  function apiDiagnose(formData) {
    return fetch("/api/diagnose", { method: "POST", body: formData })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            throw new Error(body && body.detail ? body.detail : "request failed");
          }
          return body;
        });
      });
  }

  function sendFeedback(outcome) {
    if (!state.sessionId) { return; }
    fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: state.sessionId, outcome: outcome }),
    }).catch(function () {});
  }

  function handleResult(data) {
    state.sessionId = data.session_id;
    setBusy(false);
    hide(els.emptyHint);
    renderResult(data);
    setAudio(data.audio && data.audio.data_uri);
  }

  function diagnose(formData, busyLine) {
    hide(els.toast);
    setBusy(true, busyLine);
    apiDiagnose(formData)
      .then(handleResult)
      .catch(function (error) {
        setBusy(false);
        toast("कुछ गड़बड़ हुई। दोबारा कोशिश करें। (" + error.message + ")");
      });
  }

  function requireImage() {
    if (state.image) { return true; }
    toast("पहले पत्ती की फोटो लें या चुनें।");
    return false;
  }

  /* ================= photo upload (fixed: valid markup + drag-drop) ================= */

  function setImage(file) {
    if (!file) { return; }
    if (!/image\/(jpeg|png)/.test(file.type)) {
      toast("सिर्फ JPEG या PNG फोटो चलेगी।");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast("फोटो 8 MB से छोटी होनी चाहिए।");
      return;
    }
    state.image = file;
    if (state.imagePreview) { URL.revokeObjectURL(state.imagePreview); }
    state.imagePreview = URL.createObjectURL(file);
    els.previewThumb.src = state.imagePreview;
    els.previewName.textContent = file.name || "photo";
    show(els.previewRow);
  }

  els.dropzone.addEventListener("click", function () { els.photoInput.click(); });
  els.dropzone.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); els.photoInput.click(); }
  });
  ["dragover", "dragenter"].forEach(function (name) {
    els.dropzone.addEventListener(name, function (event) {
      event.preventDefault();
      els.dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(function (name) {
    els.dropzone.addEventListener(name, function (event) {
      event.preventDefault();
      els.dropzone.classList.remove("dragover");
    });
  });
  els.dropzone.addEventListener("drop", function (event) {
    var file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    setImage(file);
  });
  els.photoInput.addEventListener("change", function () {
    setImage(this.files && this.files[0]);
  });
  els.previewClear.addEventListener("click", function () {
    state.image = null;
    hide(els.previewRow);
    els.photoInput.value = "";
  });

  /* ================= typed fallback ================= */

  els.typeToggle.addEventListener("click", function () {
    els.typePanel.classList.toggle("open");
    if (els.typePanel.classList.contains("open")) { els.typeInput.focus(); }
  });

  function submitTyped() {
    var text = els.typeInput.value.trim();
    if (!text) { toast("पहले अपनी समस्या लिखें।"); return; }
    if (!requireImage()) { return; }
    var form = new FormData();
    form.append("image", state.image, "leaf.jpg");
    form.append("text", text);
    form.append("lang", state.lang);
    diagnose(form, t("processing"));
  }

  els.typeSend.addEventListener("click", submitTyped);
  els.typeInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { submitTyped(); }
  });

  /* ================= demo mode ================= */

  els.demoStrip.addEventListener("click", function (event) {
    var tile = event.target.closest(".sample");
    if (!tile) { return; }
    var form = new FormData();
    form.append("demo", "true");
    form.append("demo_sample", tile.getAttribute("data-sample"));
    form.append("text", "demo sample leaf");
    form.append("lang", state.lang);
    diagnose(form, t("processing"));
  });

  /* ================= voice recording ================= */

  els.mic.addEventListener("click", function () {
    if (els.mic.classList.contains("recording")) { stopRecording(); return; }
    if (!window.MediaRecorder) {
      toast("इस ब्राउज़र में आवाज़ नहीं चलेगी, लिखकर बताएँ।");
      els.typePanel.classList.add("open");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (stream) {
        var mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
        state.recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
        state.audioBlob = null;
        var chunks = [];
        state.recorder.ondataavailable = function (event) { chunks.push(event.data); };
        state.recorder.onstop = function () {
          stream.getTracks().forEach(function (track) { track.stop(); });
          state.audioBlob = new Blob(chunks, { type: mime || "audio/webm" });
          els.mic.classList.remove("recording");
          window.clearTimeout(state.recordingTimer);
          els.voiceStatus.textContent = t("speak");
          submitVoice();
        };
        state.recorder.start();
        els.mic.classList.add("recording");
        els.voiceStatus.textContent = "सुन रहे हैं... बोलते रहें";
        state.recordingTimer = window.setTimeout(stopRecording, 15000);
      })
      .catch(function () {
        toast("माइक की अनुमति नहीं मिली। लिखकर बताएँ।");
        els.typePanel.classList.add("open");
      });
  });

  function stopRecording() {
    if (state.recorder && state.recorder.state === "recording") { state.recorder.stop(); }
  }

  function submitVoice() {
    if (!state.audioBlob) { return; }
    if (!requireImage()) { return; }
    setBusy(true, "आपकी आवाज़ सुन रहे हैं...");
    var form = new FormData();
    form.append("image", state.image, "leaf.jpg");
    form.append("audio", state.audioBlob, "note.webm");
    form.append("lang", state.lang);
    diagnose(form, "आपकी आवाज़ सुन रहे हैं...");
  }

  /* ================= boot ================= */

  buildWave();
  applyLang();
  show(els.emptyHint);
})();
