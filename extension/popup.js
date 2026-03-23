const listenBtn = document.getElementById('listenBtn');
const btnText = document.getElementById('btnText');
let isRecording = false;
let recordDuration = 10;

// Duration buttons
document.querySelectorAll('.dur-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.dur-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        recordDuration = parseInt(btn.dataset.sec);
    });
});

// Listen for messages from background
chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'RECORDING_STARTED') {
        setStatus('listening', `Recording ${recordDuration}s — you can close this popup`);
        listenBtn.className = 'listen-btn recording';
        btnText.textContent = 'Recording...';
        document.getElementById('wave').style.display = 'flex';
        document.getElementById('progressBar').style.display = 'block';
        startProgress();
    }
    if (msg.action === 'ANALYZING_STARTED') {
        setStatus('analyzing', 'Analyzing audio...');
        btnText.textContent = 'Analyzing...';
        document.getElementById('wave').style.display = 'none';
        listenBtn.disabled = true;
        listenBtn.className = 'listen-btn idle';
    }
    if (msg.action === 'ANALYSIS_DONE') {
        showResult(msg.result);
        resetBtn();
    }
    if (msg.action === 'RECORDING_ERROR') {
        showError(msg.error);
        resetBtn();
    }
});

// Load previous result if popup reopened
if (chrome.storage && chrome.storage.local) {
    chrome.storage.local.get(['lastResult', 'hasResult'], ({ lastResult, hasResult }) => {
        if (hasResult && lastResult) {
            showResult(lastResult);
        }
    });
} else {
    console.warn("Chrome storage API not available. Make sure 'storage' permission is granted and extension is reloaded.");
}

// Main button
listenBtn.addEventListener('click', async () => {
    if (isRecording) {
        // Stop recording
        chrome.runtime.sendMessage({ action: 'OFFSCREEN_STOP_EARLY' }).catch(() => {});
        isRecording = false;
        resetBtn();
        return;
    }

    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) throw new Error("No active tab found");

        // Get stream ID from popup context (this is the correct MV3 way)
        const streamId = await new Promise((resolve, reject) => {
            chrome.tabCapture.getMediaStreamId(
                { targetTabId: tab.id },
                id => {
                    if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
                    else resolve(id);
                }
            );
        });

        isRecording = true;

        // Send stream ID to background which passes it to offscreen
        chrome.runtime.sendMessage({
            action: 'START_RECORDING',
            streamId,
            duration: recordDuration,
            tabId: tab.id
        });

        setStatus('listening', 'Starting capture...');
        listenBtn.className = 'listen-btn recording';
        btnText.textContent = 'Starting...';

    } catch (err) {
        showError('Capture failed: ' + err.message);
        isRecording = false;
    }
});

let progressInterval = null;
function startProgress() {
    let elapsed = 0;
    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
        elapsed += 100;
        const pct = Math.min((elapsed / (recordDuration * 1000)) * 100, 100);
        document.getElementById('progressFill').style.width = pct + '%';
        if (elapsed >= recordDuration * 1000) clearInterval(progressInterval);
    }, 100);
}

function setStatus(state, text) {
    document.getElementById('statusDot').className = `status-dot ${state}`;
    document.getElementById('statusText').textContent = text;
}

function showResult(data) {
    if (!data || !data.verdict) return;
    
    const verdict = data.verdict.toLowerCase();
    const result = document.getElementById('result');
    result.className = `result ${verdict}`;
    document.getElementById('verdictValue').textContent = data.verdict;
    document.getElementById('verdictValue').className = `verdict-value ${verdict}`;
    document.getElementById('confNum').textContent = data.confidence + '%';
    document.getElementById('confNum').className = `conf-num ${verdict}`;
    
    const riskPill = document.getElementById('riskPill');
    riskPill.textContent = (data.risk_level || 'UNKNOWN') + ' RISK';
    riskPill.className = `risk-pill risk-${data.risk_level || 'UNKNOWN'}`;
    
    document.getElementById('artifactsList').innerHTML = (data.artifacts || [])
        .map(a => `<div class="artifact"><span class="artifact-arrow">▸</span>${a}</div>`)
        .join('');
        
    result.style.display = 'block';
    document.getElementById('errorBox').style.display = 'none'; // Hide errors if showing results
    document.getElementById('progressBar').style.display = 'none';
    document.getElementById('wave').style.display = 'none';
    
    const statusMap = { 
        fake: ['listening', 'DEEPFAKE DETECTED'], 
        real: ['ready', 'Voice is authentic'], 
        inconclusive: ['analyzing', 'Inconclusive Result'] 
    };
    const [state, text] = statusMap[verdict] || ['ready', 'Analysis Complete'];
    setStatus(state, text);
}

function showError(msg) {
    document.getElementById('errorBox').textContent = msg;
    document.getElementById('errorBox').style.display = 'block';
    document.getElementById('result').style.display = 'none';
    setStatus('ready', 'Ready to listen');
}

function resetBtn() {
    isRecording = false;
    listenBtn.disabled = false;
    listenBtn.className = 'listen-btn idle';
    btnText.textContent = 'Listen Now';
    clearInterval(progressInterval);
}

document.getElementById('badgeBtn').addEventListener('click', () => {
    if (!chrome.storage || !chrome.storage.local) return;
    
    chrome.storage.local.get('lastResult', ({ lastResult }) => {
        if (!lastResult) return;
        chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
            if (!tabs[0]) return;
            chrome.scripting.executeScript({
                target: { tabId: tabs[0].id },
                func: (data) => {
                    const old = document.getElementById('vg-badge');
                    if (old) old.remove();
                    const bg = data.verdict === 'FAKE' ? '#E24B4A' : data.verdict === 'REAL' ? '#639922' : '#BA7517';
                    const icon = data.verdict === 'FAKE' ? '⚠' : data.verdict === 'REAL' ? '✓' : '?';
                    const badge = document.createElement('div');
                    badge.id = 'vg-badge';
                    badge.innerHTML = `<div style="display:flex;align-items:center;gap:10px"><span style="font-size:20px">${icon}</span><div><div style="font-weight:700;font-size:14px">VoiceGuard: ${data.verdict}</div><div style="font-size:11px;opacity:.85">${data.confidence}% · ${data.risk_level} risk</div></div><span onclick="document.getElementById('vg-badge').remove()" style="margin-left:8px;cursor:pointer;font-size:18px">✕</span></div>`;
                    badge.style.cssText = `position:fixed;top:20px;right:20px;z-index:2147483647;background:${bg};color:white;padding:14px 18px;border-radius:12px;font-family:-apple-system,sans-serif`;
                    document.body.appendChild(badge);
                    setTimeout(() => badge?.remove(), 12000);
                },
                args: [lastResult]
            });
        });
    });
});