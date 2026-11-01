/* FasalRakshak frontend.
   A small, deliberate state machine: idle -> capturing -> processing ->
   result, with fail-closed UX: every error ends in a clear Hindi message,
   never a silent failure. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var els = {
    mic: $("mic-button"),
    voiceStatus: $("voice-status"),
    typeToggle: $("type-toggle"),
    typePanel: $("type-panel"),
    typeInput: $("type-input"),
    typeSend: $("type-send"),
    uploadZone: $("upload-zone"),
    photoInput: $("photo-input"),
    previewRow: $("preview-row"),
    previewThumb: $("preview-thumb"),
    previewName: $("preview-name"),
    previewClear: $("preview-clear"),
    processing: $("processing"),
    processingHi: $("processing-hi"),
    toast: $("toast"),
    resultArea: $("result-area"),
    audioBar: $("audio-bar"),
    audioPlay: $("audio-play"),
    audio: $("answer-audio"),
    audioTime: $("audio-time"),
    wave: $("wave"),
    demoStrip: $("demo-strip"),
  };

  var state = {
    image: null,        // File or Blob of the selected leaf photo
    imagePreview: null, // object URL for the thumbnail
    audioBlob: null,    // recorded voice note
    recorder: null,
    recordingTimer: null,
    sessionId: null,
  };

  /* ---------- tiny helpers ---------- */

  function show(el) { el.classList.add("show"); }
  function hide(el) { el.classList.remove("show"); }

  function toast(message) {
    els.toast.textContent = message;
    show(els.toast);
    window.setTimeout(function () { hide(els.toast); }, 6000);
  }

  function setBusy(busy, hindiLine) {
    els.processingHi.textContent = hindiLine || "जाँच हो रही है...";
    if (busy) {
      show(els.processing);
      hide(els.resultArea);
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

  /* ---------- result rendering ---------- */

  function notice(kind, iconPath, text) {
    return '<div class="notice ' + kind + '">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + iconPath + "</svg>" +
      "<span>" + escapeHtml(text) + "</span></div>";
  }

  var ICONS = {
    shieldCheck: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    shieldAlert: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    badgeCheck: '<path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z"/><path d="m9 12 2 2 4-4"/>',
  };

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
      (data.safety && data.safety.spoken_addendum || []).forEach(function (line) {
        html += notice("blocked", ICONS.shieldAlert, line);
      });
    } else if (data.status === "treated" && data.treatment) {
      var dx = data.diagnosis || {};
      html += '<div class="card"><div class="dx-head">' +
        '<div class="dx-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg></div>' +
        '<div><p class="dx-label-hi">' + escapeHtml(dx.label_hi || dx.label || "जाँच पूरी") + "</p>" +
        '<p class="dx-label-en">' + escapeHtml(dx.label || "") + (dx.pathogen ? " &middot; " + escapeHtml(dx.pathogen) : "") + "</p></div>" +
        '<div class="confidence"><div class="confidence-value">' + Math.round((dx.confidence || 0) * 100) + '%</div><div class="confidence-caption">confidence</div></div>' +
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

      (data.safety && data.safety.spoken_addendum || []).forEach(function (line) {
        var kind = /प्रतिबंधित/.test(line) ? "blocked" : (/न करें|पहले तक/.test(line) ? "phi" : "ppe");
        html += notice(kind, kind === "blocked" ? ICONS.shieldAlert : (kind === "phi" ? ICONS.clock : ICONS.shieldCheck), line);
      });

      (data.treatment.citations || []).forEach(function (citation) {
        html += '<span class="source-chip"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS.badgeCheck + '</svg> स्रोत: ' + escapeHtml(citation.org) + "</span>";
      });
    }

    html += '<div class="card"><div class="feedback-row">' +
      '<span class="feedback-q">3 दिन बाद: असर दिखा?</span>' +
      '<button class="fb-btn" type="button" data-outcome="resolved">हाँ</button>' +
      '<button class="fb-btn" type="button" data-outcome="worse">नहीं</button>' +
      "</div></div>";

    els.resultArea.innerHTML = html;

    var buttons = els.resultArea.querySelectorAll(".fb-btn");
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener("click", function () {
        Array.prototype.forEach.call(buttons, function (other) { other.classList.remove("chosen"); });
        button.classList.add("chosen");
        sendFeedback(button.getAttribute("data-outcome"));
      });
    });

    show(els.resultArea);
  }

  function setAudio(dataUri) {
    if (!dataUri) { hide(els.audioBar); return; }
    els.audio.src = dataUri;
    buildWave();
    show(els.audioBar);
  }

  function buildWave() {
    var heights = [8, 16, 22, 12, 24, 10, 18, 26, 14, 8, 20, 12, 22, 9, 16, 11, 24, 10];
    els.wave.innerHTML = heights.map(function (h) {
      return '<span style="height:' + h + 'px"></span>';
    }).join("");
  }

  /* ---------- api ---------- */

  function apiDiagnose(formData) {
    return fetch("/api/diagnose", { method: "POST", body: formData })
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            throw new Error(body && body.error ? body.error.message : "request failed");
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
    }).catch(function () { /* feedback is best effort */ });
  }

  function diagnose(formData, busyLine) {
    hide(els.toast);
    setBusy(true, busyLine);
    apiDiagnose(formData)
      .then(function (data) {
        state.sessionId = data.session_id;
        setBusy(false);
        renderResult(data);
        setAudio(data.audio && data.audio.data_uri);
        if (data.audio && data.audio.data_uri) { els.audio.play().catch(function () {}); }
      })
      .catch(function (error) {
        setBusy(false);
        toast("कुछ गड़बड़ हुई। फोटो और सवाल दोबारा भेजें। (" + error.message + ")");
      });
  }

  function requireImage() {
    if (state.image) { return true; }
    toast("पहले पत्ती की फोटो लें या चुनें।");
    return false;
  }

  /* ---------- photo capture ---------- */

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

  els.photoInput.addEventListener("change", function () {
    setImage(this.files && this.files[0]);
  });

  els.previewClear.addEventListener("click", function () {
    state.image = null;
    hide(els.previewRow);
    els.photoInput.value = "";
  });

  /* ---------- typed fallback ---------- */

  els.typeToggle.addEventListener("click", function () {
    els.typePanel.classList.toggle("open");
    if (els.typePanel.classList.contains("open")) { els.typeInput.focus(); }
  });

  els.typeSend.addEventListener("click", submitTyped);
  els.typeInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") { submitTyped(); }
  });

  function submitTyped() {
    var text = els.typeInput.value.trim();
    if (!text) { toast("पहले अपनी समस्या लिखें।"); return; }
    if (!requireImage()) { return; }
    var form = new FormData();
    form.append("image", state.image, "leaf.jpg");
    form.append("text", text);
    diagnose(form, "आपकी बात समझ रहे हैं...");
  }

  /* ---------- demo mode ---------- */

  els.demoStrip.addEventListener("click", function (event) {
    var tile = event.target.closest(".demo-tile");
    if (!tile) { return; }
    var form = new FormData();
    form.append("demo", "true");
    form.append("demo_sample", tile.getAttribute("data-sample"));
    form.append("text", "demo sample leaf");
    diagnose(form, "सैंपल पत्ती जाँच रहे हैं...");
  });

  /* ---------- voice recording ---------- */

  function defaultVoiceStatus() { els.voiceStatus.textContent = "बोलिए, क्या समस्या है?"; }

  els.mic.addEventListener("click", function () {
    if (els.mic.classList.contains("recording")) {
      stopRecording();
      return;
    }
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
          defaultVoiceStatus();
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
    if (state.recorder && state.recorder.state === "recording") {
      state.recorder.stop();
    }
  }

  function submitVoice() {
    if (!state.audioBlob) { return; }
    if (!requireImage()) { return; }
    setBusy(true, "आपकी आवाज़ सुन रहे हैं...");
    var form = new FormData();
    form.append("image", state.image, "leaf.jpg");
    form.append("audio", state.audioBlob, "note.webm");
    // Voice transcription runs server-side; send now.
    apiDiagnose(form)
      .then(function (data) {
        state.sessionId = data.session_id;
        setBusy(false);
        renderResult(data);
        setAudio(data.audio && data.audio.data_uri);
        if (data.audio && data.audio.data_uri) { els.audio.play().catch(function () {}); }
      })
      .catch(function (error) {
        setBusy(false);
        toast("कुछ गड़बड़ हुई। दोबारा कोशिश करें। (" + error.message + ")");
      });
  }

  /* ---------- audio playback ---------- */

  els.audioPlay.addEventListener("click", function () {
    if (els.audio.paused) { els.audio.play().catch(function () {}); }
    else { els.audio.pause(); }
  });

  els.audio.addEventListener("timeupdate", function () {
    var total = els.audio.duration || 0;
    var current = els.audio.currentTime || 0;
    var seconds = Math.round(total ? current : 0);
    els.audioTime.textContent = "0:" + ("0" + seconds).slice(-2);
  });
})();
