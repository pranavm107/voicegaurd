let mediaRecorder = null;
let audioChunks = [];
let recordingTabId = null;

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === 'OFFSCREEN_START') {
    startRecording(msg.streamId, msg.duration, msg.tabId);
  }
  if (msg.action === 'OFFSCREEN_STOP_EARLY') {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
  }
});


async function startRecording(streamId, duration, tabId) {
  recordingTabId = tabId;
  audioChunks = [];

  try {
    // Use the streamId from tabCapture.getMediaStreamId
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: 'tab',
          chromeMediaSourceId: streamId
        }
      },
      video: false
    });

    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

    mediaRecorder.ondataavailable = e => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      await analyzeAudio();
    };

    mediaRecorder.start(200);

    // Notify popup
    chrome.runtime.sendMessage({ action: 'RECORDING_STARTED' }).catch(() => {});

    // Auto stop
    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        chrome.runtime.sendMessage({ action: 'ANALYZING_STARTED' }).catch(() => {});
      }
    }, duration * 1000);

  } catch (err) {
    chrome.runtime.sendMessage({
      action: 'RECORDING_ERROR',
      error: err.message
    }).catch(() => {});
  }
}

async function analyzeAudio() {
  try {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('file', blob, 'recording.webm');

    const response = await fetch('http://127.0.0.1:8000/api/v1/analyze', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `API error ${response.status}`);
    }

    const data = await response.json();

    // Notify background/popup
    // Background script will save storage, inject badge and close this doc
    chrome.runtime.sendMessage({ 
      action: 'ANALYSIS_DONE', 
      result: data,
      tabId: recordingTabId 
    }).catch(() => {});

  } catch (err) {
    chrome.runtime.sendMessage({
      action: 'RECORDING_ERROR',
      error: 'Analysis failed: ' + err.message
    }).catch(() => {});
  }
}