chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'START_RECORDING') {
    startOffscreenRecording(msg.streamId, msg.duration, msg.tabId);
    sendResponse({ ok: true });
  }
  
  if (msg.action === 'ANALYSIS_DONE') {
    // Save result to storage in background context where API is guaranteed
    chrome.storage.local.set({ 
      lastResult: msg.result, 
      hasResult: true 
    });

    // Auto-inject badge on the recorded tab if it's still open
    if (msg.tabId) {
      chrome.scripting.executeScript({
        target: { tabId: msg.tabId },
        func: injectBadge,
        args: [msg.result]
      }).catch(err => console.error("Badge injection failed:", err));
    }

    // Close offscreen document now that work is done
    chrome.offscreen.closeDocument().catch(() => {});
  }


  if (msg.action === 'RECORDING_ERROR') {
    // Close offscreen document on error as well
    chrome.offscreen.closeDocument().catch(() => {});
  }

  
  return true;
});

async function startOffscreenRecording(streamId, duration, tabId) {
  // Create offscreen document if not exists
  const existingContexts = await chrome.runtime.getContexts({
    contextTypes: ['OFFSCREEN_DOCUMENT']
  });

  if (existingContexts.length === 0) {
    await chrome.offscreen.createDocument({
      url: 'offscreen.html',
      reasons: ['USER_MEDIA'],
      justification: 'Recording tab audio for deepfake detection'
    });
  }

  // Tell offscreen to start recording
  chrome.runtime.sendMessage({
    action: 'OFFSCREEN_START',
    streamId,
    duration,
    tabId
  });
}

// This function is stringified and injected into the content page
function injectBadge(data) {
  const old = document.getElementById('vg-badge');
  if (old) old.remove();

  const bg = data.verdict === 'FAKE' ? '#E24B4A'
           : data.verdict === 'REAL' ? '#639922' : '#BA7517';
  const icon = data.verdict === 'FAKE' ? '⚠' : data.verdict === 'REAL' ? '✓' : '?';

  const badge = document.createElement('div');
  badge.id = 'vg-badge';
  badge.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px">
      <span style="font-size:24px">${icon}</span>
      <div>
        <div style="font-weight:700;font-size:15px">VoiceGuard: ${data.verdict}</div>
        <div style="font-size:12px;opacity:.85">${data.confidence}% confidence · ${data.risk_level} risk</div>
        <div style="font-size:11px;opacity:.65;margin-top:2px">${data.artifacts[0] || ''}</div>
      </div>
      <span onclick="document.getElementById('vg-badge').remove()"
            style="margin-left:8px;cursor:pointer;opacity:.7;font-size:20px">✕</span>
    </div>`;

  badge.style.cssText = `
    position:fixed;top:20px;right:20px;z-index:2147483647;
    background:${bg};color:white;padding:16px 20px;border-radius:12px;
    font-family:-apple-system,sans-serif;max-width:340px;
    box-shadow:0 8px 32px rgba(0,0,0,.4);`;

  const s = document.createElement('style');
  s.textContent = `@keyframes vgIn{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}
                   #vg-badge{animation:vgIn .4s cubic-bezier(.175,.885,.32,1.275)}`;
  document.head.appendChild(s);
  document.body.appendChild(badge);
  setTimeout(() => badge?.remove(), 15000);
}
