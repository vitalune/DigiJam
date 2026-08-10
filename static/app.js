// ========== STATE ==========
const state = {
  playerCount: 1,
  players: [{ instrument: 'drums', hand: 'right' }],
  bpm: 120,
  keyNote: 'E',
  keyMode: 'Minor',
  mediaStream: null,
  mediaRecorder: null,
  recordedChunks: [],
  recStartTime: null,
  recTimerInterval: null,
};

// ========== NAVIGATION ==========
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${page}`).classList.add('active');

  if (page === 'recording') {
    initWebcam();
  }
}

// ========== CONFIG: PLAYER COUNT ==========
function setPlayerCount(count) {
  state.playerCount = count;
  document.querySelectorAll('.num-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.count) === count);
  });

  // Adjust players array
  while (state.players.length < count) {
    state.players.push({ instrument: 'drums', hand: 'right' });
  }
  state.players.length = count;

  renderPlayerCards();
}

function renderPlayerCards() {
  const container = document.getElementById('players-config');
  const instruments = ['drums', 'guitar', 'piano', 'vocals'];

  container.innerHTML = state.players.map((p, i) => `
    <div class="config-card player-card">
      <div class="player-card-header">Player ${i + 1}</div>
      <div class="config-row">
        <select class="config-select" onchange="updatePlayer(${i}, 'instrument', this.value)">
          ${instruments.map(inst => `<option value="${inst}" ${p.instrument === inst ? 'selected' : ''}>${inst.charAt(0).toUpperCase() + inst.slice(1)}</option>`).join('')}
        </select>
        <select class="config-select" onchange="updatePlayer(${i}, 'hand', this.value)">
          <option value="right" ${p.hand === 'right' ? 'selected' : ''}>Right-handed</option>
          <option value="left" ${p.hand === 'left' ? 'selected' : ''}>Left-handed</option>
        </select>
      </div>
    </div>
  `).join('');
}

function updatePlayer(index, field, value) {
  state.players[index][field] = value;
}

function updateBPM(val) {
  state.bpm = parseInt(val);
  document.getElementById('bpm-value').textContent = `${val} BPM`;
}

// ========== RECORDING ==========
async function initWebcam() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720, facingMode: 'user' },
      audio: false
    });
    state.mediaStream = stream;
    document.getElementById('webcam-preview').srcObject = stream;
    document.getElementById('webcam-recording').srcObject = stream;
  } catch (err) {
    alert('Camera access is required. Please allow camera permissions and try again.');
    console.error('Webcam error:', err);
  }
}

function startRecording() {
  // Read config values
  state.keyNote = document.getElementById('key-note').value;
  state.keyMode = document.getElementById('key-mode').value;
  state.bpm = parseInt(document.getElementById('bpm-slider').value);

  navigateTo('recording');

  // Show pre-recording screen
  document.getElementById('pre-recording').classList.remove('hidden');
  document.getElementById('active-recording').classList.add('hidden');
}

function beginCountdown() {
  document.getElementById('pre-recording').classList.add('hidden');
  document.getElementById('active-recording').classList.remove('hidden');

  // Set HUD info
  document.getElementById('hud-bpm').textContent = `${state.bpm} BPM`;
  document.getElementById('hud-key').textContent = `${state.keyNote} ${state.keyMode}`;

  // Countdown
  const countdownEl = document.getElementById('countdown-overlay');
  const numEl = document.getElementById('countdown-number');
  let count = 5;

  countdownEl.classList.remove('hidden');
  numEl.textContent = count;

  const countInterval = setInterval(() => {
    count--;
    if (count <= 0) {
      clearInterval(countInterval);
      countdownEl.classList.add('hidden');
      beginActualRecording();
    } else {
      numEl.textContent = count;
    }
  }, 1000);
}

function beginActualRecording() {
  state.recordedChunks = [];

  // Try to record video from webcam
  const stream = state.mediaStream;
  const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
    ? 'video/webm;codecs=vp9'
    : 'video/webm';

  const recorder = new MediaRecorder(stream, { mimeType });
  state.mediaRecorder = recorder;

  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) state.recordedChunks.push(e.data);
  };

  recorder.start(100); // collect data every 100ms

  // Start timer
  state.recStartTime = Date.now();
  state.recTimerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - state.recStartTime) / 1000);
    const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const secs = String(elapsed % 60).padStart(2, '0');
    document.getElementById('rec-timer').textContent = `${mins}:${secs}`;
  }, 200);
}

function stopRecording() {
  if (!state.mediaRecorder || state.mediaRecorder.state === 'inactive') return;

  state.mediaRecorder.stop();
  clearInterval(state.recTimerInterval);

  state.mediaRecorder.onstop = () => {
    // Stop webcam
    if (state.mediaStream) {
      state.mediaStream.getTracks().forEach(t => t.stop());
    }

    const blob = new Blob(state.recordedChunks, { type: 'video/webm' });
    uploadAndProcess(blob);
  };
}

// Space bar to stop
document.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    e.preventDefault();
    stopRecording();
  }
});

// ========== UPLOAD & PROCESS ==========
async function uploadAndProcess(videoBlob) {
  navigateTo('loading');

  const steps = ['step-detect', 'step-classify', 'step-render'];
  let currentStep = 0;

  // Animate loading steps
  const stepInterval = setInterval(() => {
    if (currentStep < steps.length) {
      document.getElementById(steps[currentStep]).classList.add('active');
      if (currentStep > 0) {
        document.getElementById(steps[currentStep - 1]).classList.remove('active');
        document.getElementById(steps[currentStep - 1]).classList.add('done');
      }
      currentStep++;
    }
  }, 2000);

  try {
    const formData = new FormData();
    formData.append('video', videoBlob, 'recording.webm');

    const config = {
      playerCount: state.playerCount,
      players: state.players,
      bpm: state.bpm,
      keyNote: state.keyNote,
      keyMode: state.keyMode,
    };
    formData.append('config', JSON.stringify(config));

    const response = await fetch('/api/generate-music', {
      method: 'POST',
      body: formData,
    });

    clearInterval(stepInterval);

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Processing failed');
    }

    const result = await response.json();

    // Mark all steps done
    steps.forEach(s => {
      document.getElementById(s).classList.remove('active');
      document.getElementById(s).classList.add('done');
    });

    // Show result
    setTimeout(() => showResult(result.audioUrl), 500);
  } catch (err) {
    clearInterval(stepInterval);
    console.error('Processing error:', err);
    alert(`Error: ${err.message}\n\nReturning to home.`);
    navigateTo('home');
  }
}

function showResult(audioUrl) {
  navigateTo('end');
  const audioEl = document.getElementById('result-audio');
  audioEl.src = audioUrl;
  const downloadLink = document.getElementById('download-link');
  downloadLink.href = audioUrl;
}

// ========== INIT ==========
document.addEventListener('DOMContentLoaded', () => {
  renderPlayerCards();
});
