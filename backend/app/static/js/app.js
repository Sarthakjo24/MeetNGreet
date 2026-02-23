const api = {
  start: "/api/candidates/start",
  upload: "/api/responses/upload",
  uploadStatus: (sessionId, questionId) =>
    `/api/sessions/${encodeURIComponent(sessionId)}/questions/${encodeURIComponent(questionId)}/upload-status`
};

const RESPONSE_DURATION_SECONDS = 90;

const state = {
  sessionId: null,
  candidateId: null,
  authUser: null,
  questions: [],
  currentQuestionIndex: 0,
  completedQuestionIds: new Set(),
  mediaStream: null,
  mediaRecorder: null,
  recordingChunks: [],
  recordingStartedAt: null,
  isRecording: false,
  countdownTicker: null,
  remainingSeconds: RESPONSE_DURATION_SECONDS,
  transcriptBuffer: "",
  interimTranscript: "",
  speechRecognition: null
};

function ensureStopButton() {
  let stopBtn = document.getElementById("stop-btn");
  if (stopBtn) {
    return stopBtn;
  }

  const controls = document.querySelector(".controls");
  const recordBtn = document.getElementById("record-btn");
  if (!controls || !recordBtn) {
    return null;
  }

  stopBtn = document.createElement("button");
  stopBtn.id = "stop-btn";
  stopBtn.type = "button";
  stopBtn.disabled = true;
  stopBtn.textContent = "Stop Response";
  recordBtn.insertAdjacentElement("afterend", stopBtn);
  return stopBtn;
}

const dom = {
  startPanel: document.getElementById("start-panel"),
  interviewPanel: document.getElementById("interview-panel"),
  thankyouPanel: document.getElementById("thankyou-panel"),
  signedInEmail: document.getElementById("signed-in-email"),
  signedInProvider: document.getElementById("signed-in-provider"),
  logoutBtn: document.getElementById("logout-btn"),
  startStatus: document.getElementById("start-status"),
  startBtn: document.getElementById("start-btn"),
  preview: document.getElementById("preview"),
  cameraTimer: document.getElementById("camera-timer"),
  sessionId: document.getElementById("session-id"),
  progress: document.getElementById("progress"),
  questionTitle: document.getElementById("question-title"),
  questionText: document.getElementById("question-text"),
  recordBtn: document.getElementById("record-btn"),
  stopBtn: ensureStopButton(),
  nextBtn: document.getElementById("next-btn"),
  recordStatus: document.getElementById("record-status")
};

dom.startBtn.addEventListener("click", startInterview);
dom.recordBtn.addEventListener("click", startRecording);
if (dom.stopBtn) {
  dom.stopBtn.addEventListener("click", stopRecordingForUpload);
}
dom.nextBtn.addEventListener("click", goNextQuestion);
if (dom.logoutBtn) {
  dom.logoutBtn.addEventListener("click", onLogout);
}

setTimerDisplay(RESPONSE_DURATION_SECONDS);
initializePage();

async function initializePage() {
  try {
    state.authUser = await AuthClient.requireAuth();
  } catch (_err) {
    return;
  }

  state.candidateId = state.authUser.email;
  if (dom.signedInEmail) {
    dom.signedInEmail.textContent = state.authUser.email;
  }
  if (dom.signedInProvider) {
    dom.signedInProvider.textContent = String(state.authUser.provider || "-").toUpperCase();
  }
  setStartStatus("Authenticated. Click Start Interview to begin.");
}

async function onLogout() {
  await AuthClient.logout();
  window.location.href = "/auth?next=/interview";
}

function setStatus(message, isError = false) {
  dom.recordStatus.textContent = message;
  dom.recordStatus.style.color = isError ? "#fb2c36" : "#e2e8f0";
}

function setStartStatus(message = "", isError = false) {
  if (!dom.startStatus) return;

  if (!message) {
    dom.startStatus.textContent = "";
    dom.startStatus.classList.add("hidden");
    return;
  }

  dom.startStatus.classList.remove("hidden");
  dom.startStatus.textContent = message;
  dom.startStatus.style.color = isError ? "#fb2c36" : "#e2e8f0";
}

function normalizeTranscript(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim();
}

function appendTranscript(baseText, additionText) {
  const base = normalizeTranscript(baseText);
  const addition = normalizeTranscript(additionText);

  if (!addition) return base;
  if (!base) return addition;

  const baseWords = base.split(" ");
  const additionWords = addition.split(" ");
  const maxOverlap = Math.min(baseWords.length, additionWords.length);

  let overlap = 0;
  for (let k = maxOverlap; k > 0; k -= 1) {
    const baseSlice = baseWords.slice(baseWords.length - k).join(" ").toLowerCase();
    const additionSlice = additionWords.slice(0, k).join(" ").toLowerCase();
    if (baseSlice === additionSlice) {
      overlap = k;
      break;
    }
  }

  if (overlap >= additionWords.length) {
    return base;
  }

  const remaining = additionWords.slice(overlap).join(" ");
  return normalizeTranscript(`${base} ${remaining}`);
}

function buildTranscriptHint() {
  return appendTranscript(state.transcriptBuffer, state.interimTranscript);
}

function getCurrentQuestion() {
  return state.questions[state.currentQuestionIndex] || null;
}

function updateQuestionView() {
  const q = getCurrentQuestion();
  if (!q) return;

  const completedCount = state.completedQuestionIds.size;
  dom.progress.textContent = `${completedCount} / ${state.questions.length}`;
  dom.questionTitle.textContent = `Question ${state.currentQuestionIndex + 1}`;
  dom.questionText.textContent = q.question_text;

  const setStopButton = (disabled) => {
    if (!dom.stopBtn) {
      return;
    }
    dom.stopBtn.disabled = disabled;
    dom.stopBtn.textContent = "Stop Response";
  };

  const done = state.completedQuestionIds.has(q.question_id);
  if (done) {
    dom.recordBtn.disabled = true;
    dom.recordBtn.textContent = "Response Submitted";
    setStopButton(true);
  } else if (state.isRecording) {
    dom.recordBtn.disabled = true;
    dom.recordBtn.textContent = "Recording...";
    setStopButton(false);
  } else {
    dom.recordBtn.disabled = false;
    dom.recordBtn.textContent = "Start Response";
    setStopButton(true);
  }
  const lastQuestion = state.currentQuestionIndex >= state.questions.length - 1;
  dom.nextBtn.disabled = state.isRecording || !done || lastQuestion;
}

async function startInterview() {
  dom.startBtn.disabled = true;
  setStartStatus("Starting interview...");

  try {
    const res = await fetch(api.start, {
      method: "POST",
      credentials: "same-origin"
    });

    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    state.sessionId = data.session_id;
    state.candidateId = data.candidate_id;
    state.questions = data.questions;
    state.currentQuestionIndex = 0;
    state.completedQuestionIds.clear();

    await setupMediaPreview();
    setupSpeechRecognition();

    dom.sessionId.textContent = state.sessionId;
    dom.startPanel.classList.add("hidden");
    dom.interviewPanel.classList.remove("hidden");
    setStartStatus("");
    setStatus("Camera and microphone connected. Click Start Response to record and Stop Response to submit.");
    resetTimer();
    updateQuestionView();
  } catch (err) {
    console.error("Unable to start interview", err);
    setStartStatus(`Unable to start interview: ${err.message}`, true);
  } finally {
    dom.startBtn.disabled = false;
  }
}

async function setupMediaPreview() {
  try {
    state.mediaStream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true
    });
    dom.preview.srcObject = state.mediaStream;
  } catch (_err) {
    throw new Error(
      "Camera/microphone access failed. Allow permissions in your browser and try again."
    );
  }
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    state.speechRecognition = null;
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = true;
  recognition.continuous = true;

  recognition.onresult = (event) => {
    let finalizedChunk = "";
    let interimChunk = "";

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const alternative = event.results[i][0];
      const piece = alternative && alternative.transcript ? alternative.transcript.trim() : "";
      if (!piece) continue;

      if (event.results[i].isFinal) {
        finalizedChunk = appendTranscript(finalizedChunk, piece);
      } else {
        interimChunk = appendTranscript(interimChunk, piece);
      }
    }

    if (finalizedChunk) {
      state.transcriptBuffer = appendTranscript(state.transcriptBuffer, finalizedChunk);
    }
    state.interimTranscript = interimChunk;
  };

  recognition.onerror = () => {
    // Browser speech recognition can fail silently depending on permissions.
  };

  state.speechRecognition = recognition;
}

function getRecorderMimeType() {
  const options = [
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9,opus",
    "video/webm"
  ];
  for (const opt of options) {
    if (MediaRecorder.isTypeSupported(opt)) return opt;
  }
  return "video/webm";
}

function startRecording() {
  if (!state.mediaStream || state.isRecording) {
    return;
  }

  const q = getCurrentQuestion();
  if (!q || state.completedQuestionIds.has(q.question_id)) {
    return;
  }

  state.recordingChunks = [];
  state.transcriptBuffer = "";
  state.interimTranscript = "";
  state.recordingStartedAt = Date.now();

  try {
    state.mediaRecorder = new MediaRecorder(state.mediaStream, {
      mimeType: getRecorderMimeType()
    });
  } catch (err) {
    setStatus(`Failed to initialize recorder: ${err.message}`, true);
    return;
  }

  state.mediaRecorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) {
      state.recordingChunks.push(event.data);
    }
  };

  state.mediaRecorder.onerror = () => {
    clearCountdownTicker();
    state.isRecording = false;
    resetTimer();
    updateQuestionView();
    setStatus("Recording failed. Please try starting the response again.", true);
  };

  state.mediaRecorder.onstop = async () => {
    clearCountdownTicker();

    const blob = new Blob(state.recordingChunks, { type: "video/webm" });
    const duration = Math.min(
      (Date.now() - state.recordingStartedAt) / 1000,
      RESPONSE_DURATION_SECONDS
    );

    try {
      const uploadResult = await uploadCurrentAnswer(blob, duration);
      state.completedQuestionIds.add(q.question_id);

      if (uploadResult.auto_evaluated || state.completedQuestionIds.size === state.questions.length) {
        finishInterview();
        return;
      }

      setStatus(`Response submitted for ${q.question_id}. You can continue to next question.`);
      resetTimer();
    } catch (err) {
      setStatus(`Upload failed: ${err.message}`, true);
      resetTimer();
    } finally {
      state.isRecording = false;
      updateQuestionView();
    }
  };

  state.mediaRecorder.start();
  state.isRecording = true;

  if (state.speechRecognition) {
    try {
      state.speechRecognition.start();
    } catch (_err) {
      // Start can throw if already running.
    }
  }

  startCountdown();

  setStatus("Recording started. Click Stop Response to submit.");
  updateQuestionView();
}

function startCountdown() {
  clearCountdownTicker();
  state.remainingSeconds = RESPONSE_DURATION_SECONDS;
  setTimerDisplay(state.remainingSeconds);

  state.countdownTicker = window.setInterval(() => {
    state.remainingSeconds = Math.max(state.remainingSeconds - 1, 0);
    setTimerDisplay(state.remainingSeconds);

    if (state.remainingSeconds <= 0) {
      clearCountdownTicker();
      if (state.isRecording) {
        setStatus("90 seconds reached. Click Stop Response to submit.");
      }
    }
  }, 1000);
}

function setTimerDisplay(seconds) {
  const mm = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const ss = Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0");

  dom.cameraTimer.textContent = `${mm}:${ss}`;
  if (seconds <= 10) {
    dom.cameraTimer.classList.add("low-time");
  } else {
    dom.cameraTimer.classList.remove("low-time");
  }
}

function stopRecordingForUpload() {
  if (!state.mediaRecorder || state.mediaRecorder.state !== "recording") {
    return;
  }

  if (state.speechRecognition) {
    try {
      state.speechRecognition.stop();
    } catch (_err) {
      // Ignore speech recognition stop error.
    }
  }

  setStatus("Stopping response. Uploading...\ndont close your browser until the response is submitted .");
  state.mediaRecorder.stop();
}

function clearCountdownTicker() {
  if (!state.countdownTicker) {
    return;
  }

  window.clearInterval(state.countdownTicker);
  state.countdownTicker = null;
}

function resetTimer() {
  state.remainingSeconds = RESPONSE_DURATION_SECONDS;
  setTimerDisplay(state.remainingSeconds);
}

async function uploadCurrentAnswer(blob, durationSeconds) {
  const q = getCurrentQuestion();
  if (!q) throw new Error("Question not found");

  const maxAttempts = 8;
  let lastError = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const formData = new FormData();
    formData.append("session_id", state.sessionId);
    formData.append("question_id", q.question_id);
    formData.append("attempt_no", "1");
    formData.append("duration_seconds", String(durationSeconds));
    formData.append("transcript_hint", buildTranscriptHint());
    formData.append("media_file", blob, `${q.question_id}.webm`);

    try {
      const res = await fetch(api.upload, {
        method: "POST",
        credentials: "same-origin",
        body: formData
      });

      if (!res.ok) {
        const errText = await res.text();
        const message = (errText || "").trim() || `Upload failed (${res.status})`;
        throw new Error(message);
      }

      return await res.json();
    } catch (err) {
      lastError = err;
      const message = (err && err.message ? err.message : "").toLowerCase();
      const isTransientNetwork =
        err instanceof TypeError ||
        message.includes("failed to fetch") ||
        message.includes("networkerror") ||
        message.includes("load failed");

      if (isTransientNetwork) {
        const recovered = await confirmUploadPersisted(state.sessionId, q.question_id);
        if (recovered) {
          return recovered;
        }
      }

      if (!isTransientNetwork || attempt >= maxAttempts) {
        break;
      }

      setStatus(`Connection interrupted. Retrying upload (${attempt}/${maxAttempts})...`);
      await delay(Math.min(1500 * attempt, 7000));
    }
  }

  throw lastError || new Error("Upload failed");
}

async function confirmUploadPersisted(sessionId, questionId) {
  try {
    const res = await fetch(api.uploadStatus(sessionId, questionId), {
      method: "GET",
      credentials: "same-origin"
    });
    if (!res.ok) {
      return null;
    }

    const payload = await res.json();
    if (!payload.uploaded) {
      return null;
    }

    setStatus("Upload confirmed on server. Continuing...");
    return {
      response_id: payload.response_id || -1,
      question_id: questionId,
      transcript: "",
      uploaded_at: payload.uploaded_at || new Date().toISOString(),
      auto_evaluated: false
    };
  } catch (_err) {
    return null;
  }
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function goNextQuestion() {
  const q = getCurrentQuestion();
  if (!q) {
    return;
  }

  if (!state.completedQuestionIds.has(q.question_id)) {
    setStatus("Complete and upload the current response before moving to next question.", true);
    return;
  }

  if (state.currentQuestionIndex < state.questions.length - 1) {
    state.currentQuestionIndex += 1;
    updateQuestionView();
    resetTimer();
    setStatus("Ready for next question.");
  }
}

function finishInterview() {
  clearCountdownTicker();

  if (state.speechRecognition) {
    try {
      state.speechRecognition.stop();
    } catch (_err) {
      // ignore
    }
  }

  if (state.mediaStream) {
    state.mediaStream.getTracks().forEach((track) => track.stop());
  }

  dom.interviewPanel.classList.add("hidden");
  dom.thankyouPanel.classList.remove("hidden");
}
