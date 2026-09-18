/* ── Playlist Helper — Web UI Application Logic ──────────────────── */

const API_BASE = '/api';

// ── State ──────────────────────────────────────────────────────────

const state = {
  tracks: [],
  selectedId: null,
  batchIds: new Set(),
  results: [],
  loading: false,
};

// ── DOM References ─────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const els = {};

function initDOMElements() {
  els.trackList = document.getElementById('track-list');
  els.trackListEmpty = document.getElementById('track-list-empty');
  els.trackCount = document.getElementById('track-count');
  els.batchCount = document.getElementById('batch-count');
  els.batchBar = document.getElementById('batch-bar');
  els.detailPanel = document.getElementById('detail-panel');
  els.noSelection = document.getElementById('no-selection');
  els.selectedName = document.getElementById('selected-name');
  els.toastContainer = document.getElementById('toast-container');
  els.resultsList = document.getElementById('results-list');
  els.resultsArea = document.getElementById('results-area');
  els.clearResultsBtn = document.getElementById('clear-results');
  els.uploadInput = document.getElementById('file-input');
  els.uploadZone = document.getElementById('upload-zone');
  els.scanInput = document.getElementById('scan-path');
  els.scanBtn = document.getElementById('scan-btn');
  els.clearTracksBtn = document.getElementById('clear-tracks');
  els.eqTargetDb = document.getElementById('eq-target-db');
  els.eqAvgBtn = document.getElementById('eq-avg-btn');
  els.eqLoudBtn = document.getElementById('eq-loud-btn');
  els.loadingOverlay = document.getElementById('loading-overlay');
}

// ── Toast Notifications ────────────────────────────────────────────

function toast(message, type = 'info', duration = 4000) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  els.toastContainer.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300);
  }, duration);
}

// ── Loading State ──────────────────────────────────────────────────

function setLoading(on) {
  state.loading = on;
  els.loadingOverlay.classList.toggle('active', on);
}

// ── API Helpers ────────────────────────────────────────────────────

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: { 'Accept': 'application/json' },
    ...options,
  };

  // Don't set Content-Type for FormData (browser sets it with boundary)
  if (config.body instanceof FormData) {
    delete config.headers['Content-Type'];
  } else if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
    config.body = JSON.stringify(config.body);
  }

  try {
    const resp = await fetch(url, config);
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(errData.detail || `HTTP ${resp.status}`);
    }
    const ct = resp.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      return await resp.json();
    }
    return resp;
  } catch (err) {
    if (err.message.includes('Failed to fetch')) {
      throw new Error('Cannot connect to server. Is it running?');
    }
    throw err;
  }
}

// ── File Management ────────────────────────────────────────────────

async function uploadFiles(files) {
  if (!files.length) return;
  setLoading(true);
  try {
    const form = new FormData();
    for (const f of files) {
      form.append('files', f);
    }
    const data = await api('/upload', { method: 'POST', body: form });
    state.tracks.push(...data.tracks);
    renderTrackList();
    toast(`Uploaded ${data.count} file(s)`, 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function scanFolder(path) {
  if (!path) {
    toast('Please enter a folder path', 'warning');
    return;
  }
  setLoading(true);
  try {
    const data = await api('/scan', {
      method: 'POST',
      body: { folder_path: path },
    });
    state.tracks.push(...data.tracks);
    renderTrackList();
    toast(`Scanned ${data.count} file(s) from ${path}`, 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function deleteTrack(id) {
  try {
    await api(`/tracks/${id}`, { method: 'DELETE' });
    state.tracks = state.tracks.filter(t => t.track_id !== id);
    state.batchIds.delete(id);
    if (state.selectedId === id) {
      state.selectedId = null;
    }
    renderTrackList();
    renderDetail();
    toast('Track removed', 'info');
  } catch (err) {
    toast(err.message, 'error');
  }
}

function clearAllTracks() {
  if (state.tracks.length === 0) return;
  state.tracks = [];
  state.selectedId = null;
  state.batchIds.clear();
  state.results = [];
  renderTrackList();
  renderDetail();
  renderResults();
  toast('All tracks cleared', 'info');
}

// ── Track Operations ───────────────────────────────────────────────

async function analyzeTrack(id) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/analyze`, { method: 'POST' });
    // Update track in state
    const track = state.tracks.find(t => t.track_id === id);
    if (track) {
      track.average_volume_db = data.mean_volume_db;
      track.cleaned_average_db = data.cleaned_average_db;
      track.max_volume_db = data.max_volume_db;
    }
    renderDetail();
    toast('Analysis complete', 'success');
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function trimTrack(id, start, end) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/trim`, {
      method: 'POST',
      body: { start_time: start, end_time: end },
    });
    if (data.success) {
      state.results.push({
        track_id: id,
        type: 'trim',
        result_id: data.result_id,
        output_path: data.output_path,
        duration: data.duration_seconds,
        success: true,
        downloaded: false,
      });
      renderResults();
      toast('Trim complete', 'success');
    }
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function convertTrack(id, format) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/convert`, {
      method: 'POST',
      body: { target_format: format },
    });
    if (data.success) {
      state.results.push({
        track_id: id,
        type: `convert to ${format}`,
        result_id: data.result_id,
        duration: data.duration_seconds,
        success: true,
        downloaded: false,
      });
      renderResults();
      toast('Conversion complete', 'success');
    }
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function processTrack(id, opts) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/process`, {
      method: 'POST',
      body: opts,
    });
    if (data.success) {
      state.results.push({
        track_id: id,
        type: 'process',
        result_id: data.result_id,
        duration: data.duration_seconds,
        success: true,
        downloaded: false,
      });
      renderResults();
      toast('Processing complete', 'success');
    }
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function setTitle(id, title) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/metadata/title`, {
      method: 'PUT',
      body: { title },
    });
    if (data.success) {
      const track = state.tracks.find(t => t.track_id === id);
      if (track) track.title = title;
      toast('Title updated', 'success');
      renderDetail();
    }
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function renameTrack(id, newName) {
  setLoading(true);
  try {
    const data = await api(`/tracks/${id}/rename`, {
      method: 'PUT',
      body: { new_filename: newName },
    });
    const track = state.tracks.find(t => t.track_id === id);
    if (track) {
      track.file_name = data.file_name;
    }
    toast('File renamed', 'success');
    renderTrackList();
    renderDetail();
    return data;
  } catch (err) {
    toast(err.message, 'error');
    return null;
  } finally {
    setLoading(false);
  }
}

async function equalizeAverage(ids, targetDb) {
  if (!ids.length) {
    toast('No tracks selected for equalization', 'warning');
    return;
  }
  setLoading(true);
  try {
    const data = await api('/equalize/average', {
      method: 'POST',
      body: { target_db: targetDb, track_ids: ids },
    });
    for (const r of data) {
      state.results.push({
        track_id: r.track_id,
        type: 'equalize-avg',
        result_id: r.result_id,
        success: r.success,
        error: r.error,
        downloaded: false,
      });
    }
    renderResults();
    const ok = data.filter(r => r.success).length;
    toast(`Equalized ${ok}/${data.length} tracks to average`, 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function equalizeLoudest(ids, targetDb) {
  if (!ids.length) {
    toast('No tracks selected', 'warning');
    return;
  }
  setLoading(true);
  try {
    const data = await api('/equalize/loudest', {
      method: 'POST',
      body: { target_db: targetDb, track_ids: ids },
    });
    for (const r of data) {
      state.results.push({
        track_id: r.track_id,
        type: 'equalize-loud',
        result_id: r.result_id,
        success: r.success,
        error: r.error,
        downloaded: false,
      });
    }
    renderResults();
    const ok = data.filter(r => r.success).length;
    toast(`Equalized ${ok}/${data.length} tracks to loudest`, 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function setCover(id, file) {
  if (!file) {
    toast('Please select an image file', 'warning');
    return;
  }
  setLoading(true);
  try {
    const form = new FormData();
    form.append('file', file);
    await api(`/tracks/${id}/cover`, { method: 'POST', body: form });
    toast('Cover art updated', 'success');
    renderDetail();
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    setLoading(false);
  }
}

async function downloadTrack(id, format = null) {
  try {
    let url = `${API_BASE}/tracks/${id}/download`;
    if (format) url += `?format=${format}`;
    // Use fetch to trigger download
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('Download failed');
    const blob = await resp.blob();
    const track = state.tracks.find(t => t.track_id === id);
    const name = track ? track.file_name.replace(/\.[^.]+$/, '') : id;
    const ext = format ? `.${format}` : (track ? '.' + track.format : '');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${name}${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function downloadResult(pathOrResultId) {
  try {
    // Check if this is a result_id (short numeric string) or a file path
    const isResultId = /^\d+$/.test(pathOrResultId);
    const url = isResultId
      ? `${API_BASE}/results/${pathOrResultId}/download`
      : pathOrResultId;
    const resp = await fetch(url, {
      headers: { 'Accept': '*/*' },
    });
    if (!resp.ok) throw new Error('Download failed');
    const blob = await resp.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    // Try to get filename from Content-Disposition header, fall back to path
    const cd = resp.headers.get('Content-Disposition');
    let filename = 'output';
    if (cd) {
      const match = cd.match(/filename="?(.+?)"?$/);
      if (match) filename = match[1];
    } else {
      filename = pathOrResultId.split('/').pop() || 'output';
    }
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
    return true;
  } catch (err) {
    toast(err.message, 'error');
    return false;
  }
}

// ── Rendering ──────────────────────────────────────────────────────

function formatDuration(sec) {
  if (!sec || sec <= 0) return '--:--';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatDb(val) {
  if (val === undefined || val === null) return '--';
  return `${val >= 0 ? '+' : ''}${val.toFixed(1)} dB`;
}

function formatSize(bytes) {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderTrackList() {
  const container = els.trackList;

  if (state.tracks.length === 0) {
    container.innerHTML = '';
    els.trackListEmpty.style.display = 'flex';
    els.trackCount.textContent = '0';
    els.batchBar.style.display = 'none';
    return;
  }

  els.trackListEmpty.style.display = 'none';
  els.trackCount.textContent = state.tracks.length;

  // Update batch bar
  const batchCount = state.batchIds.size;
  if (batchCount > 0) {
    els.batchBar.style.display = 'flex';
    els.batchCount.textContent = batchCount;
  } else {
    els.batchBar.style.display = 'none';
  }

  container.innerHTML = state.tracks.map(t => {
    const selected = state.selectedId === t.track_id ? 'selected' : '';
    const checked = state.batchIds.has(t.track_id) ? 'checked' : '';
    const ext = t.format.toUpperCase();
    return `
      <div class="track-item ${selected}" data-id="${t.track_id}">
        <input type="checkbox" class="track-checkbox" ${checked} data-id="${t.track_id}">
        <div class="track-info" data-action="select">
          <div class="track-name">${escapeHtml(t.file_name)}</div>
          <div class="track-meta">
            <span class="track-badge">${escapeHtml(ext)}</span>
            <span>${t.media_type}</span>
            <span>${formatDuration(t.duration_seconds)}</span>
            ${t.cleaned_average_db ? `<span>${formatDb(t.cleaned_average_db)}</span>` : ''}
          </div>
        </div>
        <div class="track-duration">${formatDuration(t.duration_seconds)}</div>
      </div>
    `;
  }).join('');

  // Event listeners
  container.querySelectorAll('.track-item').forEach(item => {
    const id = item.dataset.id;

    // Click on info area = select
    item.querySelector('[data-action="select"]')?.addEventListener('click', () => {
      selectTrack(id);
    });

    // Checkbox
    item.querySelector('.track-checkbox')?.addEventListener('change', (e) => {
      if (e.target.checked) {
        state.batchIds.add(id);
      } else {
        state.batchIds.delete(id);
      }
      renderTrackList();
    });
  });
}

function selectTrack(id) {
  state.selectedId = id;
  renderTrackList();
  renderDetail();
}

function renderDetail() {
  const track = state.tracks.find(t => t.track_id === state.selectedId);

  if (!track) {
    els.noSelection.style.display = 'flex';
    els.detailPanel.style.display = 'none';
    return;
  }

  els.noSelection.style.display = 'none';
  els.detailPanel.style.display = 'block';
  els.selectedName.textContent = track.file_name;

  // Info Tab
  renderInfoTab(track);
  // Volume Tab
  renderVolumeTab(track);
  // Trim Tab
  renderTrimTab(track);
  // Convert Tab
  renderConvertTab(track);
  // Process Tab
  renderProcessTab(track);
  // Playback Tab
  renderPlaybackTab(track);
  // Metadata Tab
  renderMetadataTab(track);
}

function renderInfoTab(track) {
  const tab = document.getElementById('tab-info');
  tab.innerHTML = `
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Filename</div>
        <div class="info-value">${escapeHtml(track.file_name)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Path</div>
        <div class="info-value" style="font-size:0.8rem;font-family:var(--font-mono)">${escapeHtml(track.file_path)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Format</div>
        <div class="info-value">${track.format.toUpperCase()}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Duration</div>
        <div class="info-value">${formatDuration(track.duration_seconds)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Media Type</div>
        <div class="info-value">${track.media_type}</div>
      </div>
      <div class="info-item">
        <div class="info-label">File Size</div>
        <div class="info-value">${formatSize(track.size_bytes)}</div>
      </div>
      <div class="info-item" style="grid-column: 1/-1">
        <div class="info-label">Title Metadata</div>
        <div class="info-value">
          <div class="form-row">
            <input type="text" id="title-input" value="${escapeHtml(track.title || '')}" placeholder="Enter title...">
            <button class="btn btn-primary btn-sm" id="save-title-btn">Save</button>
          </div>
        </div>
      </div>
      <div class="info-item" style="grid-column: 1/-1">
        <div class="info-label">Rename File</div>
        <div class="info-value">
          <div class="form-row">
            <input type="text" id="rename-input" value="${escapeHtml(track.file_name)}">
            <button class="btn btn-primary btn-sm" id="rename-btn">Rename</button>
          </div>
        </div>
      </div>
    </div>

    <div class="cover-container mt-16">
      <div id="cover-display" class="cover-image placeholder">🎵</div>
      <div style="flex:1">
        <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:8px">Cover Art</p>
        <div class="form-row">
          <input type="file" id="cover-file-input" accept="image/*" style="flex:1;padding:4px">
          <button class="btn btn-primary btn-sm" id="set-cover-btn">Upload</button>
        </div>
        <p style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">
          ${track.has_cover ? '✓ Has cover art' : 'No cover art detected'}
        </p>
      </div>
    </div>

    <div class="mt-16">
      <button class="btn btn-primary" id="track-analyze-btn">🔍 Analyze Volume</button>
      <button class="btn btn-sm" id="track-download-btn">⬇ Download</button>
      <button class="btn btn-danger btn-sm" id="track-delete-btn">🗑 Delete</button>
    </div>
  `;

  // Load cover if available
  if (track.has_cover) {
    loadCover(track.track_id);
  }

  // Title save
  tab.querySelector('#save-title-btn')?.addEventListener('click', () => {
    const title = tab.querySelector('#title-input')?.value || '';
    setTitle(track.track_id, title);
  });

  // Rename
  tab.querySelector('#rename-btn')?.addEventListener('click', () => {
    const newName = tab.querySelector('#rename-input')?.value || '';
    if (newName) renameTrack(track.track_id, newName);
  });

  // Cover upload
  tab.querySelector('#set-cover-btn')?.addEventListener('click', () => {
    const file = tab.querySelector('#cover-file-input')?.files?.[0];
    if (file) setCover(track.track_id, file);
  });

  // Analyze
  tab.querySelector('#track-analyze-btn')?.addEventListener('click', () => {
    analyzeTrack(track.track_id);
  });

  // Download
  tab.querySelector('#track-download-btn')?.addEventListener('click', () => {
    downloadTrack(track.track_id);
  });

  // Delete
  tab.querySelector('#track-delete-btn')?.addEventListener('click', () => {
    if (confirm('Remove this track from the session?')) {
      deleteTrack(track.track_id);
    }
  });
}

async function loadCover(id) {
  const display = document.getElementById('cover-display');
  if (!display) return;
  try {
    const resp = await fetch(`${API_BASE}/tracks/${id}/cover`);
    if (!resp.ok) return;
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    display.className = 'cover-image';
    display.innerHTML = '';
    display.style.backgroundImage = `url(${url})`;
    display.style.backgroundSize = 'cover';
    display.style.backgroundPosition = 'center';
  } catch {
    // silently fail
  }
}

function renderVolumeTab(track) {
  const tab = document.getElementById('tab-volume');
  tab.innerHTML = `
    <div class="volume-metrics">
      <div class="metric"><span class="metric-label">Mean Volume</span><span class="metric-value">${formatDb(track.average_volume_db)}</span></div>
      <div class="metric"><span class="metric-label">Max Volume</span><span class="metric-value">${formatDb(track.max_volume_db)}</span></div>
      <div class="metric"><span class="metric-label">Cleaned Avg (80%)</span><span class="metric-value">${formatDb(track.cleaned_average_db)}</span></div>
      <div class="metric"><span class="metric-label">Volume Range</span><span class="metric-value">${track.average_volume_db && track.max_volume_db ? (track.max_volume_db - track.average_volume_db).toFixed(1) + ' dB' : '--'}</span></div>
    </div>
    ${track.cleaned_average_db ? `
      <div class="volume-bar mt-8">
        <div class="volume-bar-fill ${track.cleaned_average_db < -20 ? 'low' : track.cleaned_average_db > -6 ? 'high' : 'normal'}"
             style="width: ${Math.min(100, Math.max(5, (track.cleaned_average_db + 60) * 2))}%">
        </div>
      </div>
      <p style="font-size:0.75rem;color:var(--text-muted);text-align:right">
        Cleaned average: ${formatDb(track.cleaned_average_db)}
      </p>
    ` : `
      <p class="text-muted">Run volume analysis to see metrics</p>
      <button class="btn btn-primary btn-sm mt-8" id="vol-analyze-btn">🔍 Analyze Now</button>
    `}
  `;

  tab.querySelector('#vol-analyze-btn')?.addEventListener('click', () => {
    analyzeTrack(track.track_id);
  });
}

function renderTrimTab(track) {
  const tab = document.getElementById('tab-trim');
  const dur = track.duration_seconds || 0;
  const mid = dur / 2;
  tab.innerHTML = `
    <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:12px">
      Track duration: <strong>${formatDuration(dur)}</strong>
    </p>
    <div class="form-row">
      <div class="form-group">
        <label>Start Time (seconds)</label>
        <input type="number" id="trim-start" value="0" min="0" max="${Math.max(0, dur - 0.1)}" step="0.1">
      </div>
      <div class="form-group">
        <label>End Time (seconds)</label>
        <input type="number" id="trim-end" value="${dur > 0 ? dur.toFixed(1) : 10}" min="0.1" max="${dur || 999}" step="0.1">
      </div>
    </div>
    <p id="trim-dur-preview" style="font-size:0.8rem;color:var(--text-muted);margin-top:4px">
      Resulting duration: <span id="trim-result-dur">${dur > 0 ? dur.toFixed(1) : '--'}</span>s
    </p>
    <button class="btn btn-primary mt-8" id="trim-btn">✂ Trim</button>
  `;

  // Update preview on input change
  const updatePreview = () => {
    const start = parseFloat(tab.querySelector('#trim-start')?.value || 0);
    const end = parseFloat(tab.querySelector('#trim-end')?.value || 0);
    const preview = tab.querySelector('#trim-result-dur');
    if (preview && end > start) {
      preview.textContent = (end - start).toFixed(1);
    }
  };

  tab.querySelector('#trim-start')?.addEventListener('input', updatePreview);
  tab.querySelector('#trim-end')?.addEventListener('input', updatePreview);

  tab.querySelector('#trim-btn')?.addEventListener('click', () => {
    const start = parseFloat(tab.querySelector('#trim-start')?.value || 0);
    const end = parseFloat(tab.querySelector('#trim-end')?.value || 0);
    if (end <= start) {
      toast('End time must be greater than start time', 'warning');
      return;
    }
    trimTrack(track.track_id, start, end);
  });
}

function renderConvertTab(track) {
  const tab = document.getElementById('tab-convert');
  const currentFmt = track.format;
  const formats = ['mp3', 'wav', 'flac'];
  tab.innerHTML = `
    <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:12px">
      Current format: <strong>${currentFmt.toUpperCase()}</strong>
    </p>
    <div class="format-options">
      ${formats.map(f => `
        <label class="format-option">
          <input type="radio" name="convert-format" value="${f}" ${f === currentFmt ? 'checked' : ''}>
          <span>${f.toUpperCase()}</span>
        </label>
      `).join('')}
    </div>
    <button class="btn btn-primary mt-8" id="convert-btn">🔄 Convert</button>
  `;

  tab.querySelector('#convert-btn')?.addEventListener('click', () => {
    const selected = tab.querySelector('input[name="convert-format"]:checked');
    if (!selected) return;
    convertTrack(track.track_id, selected.value);
  });
}

function renderProcessTab(track) {
  const tab = document.getElementById('tab-process');
  const dur = track.duration_seconds || 0;
  const formats = ['mp3', 'wav', 'flac'];

  tab.innerHTML = `
    <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:12px">
      Combined trim + convert + volume adjustment in one pass
    </p>
    <div class="form-group mb-8">
      <label>Output Format</label>
      <div class="format-options">
        ${formats.map(f => `
          <label class="format-option">
            <input type="radio" name="proc-format" value="${f}" ${f === 'mp3' ? 'checked' : ''}>
            <span>${f.toUpperCase()}</span>
          </label>
        `).join('')}
      </div>
    </div>
    <div class="form-row mb-8">
      <div class="form-group">
        <label>Trim Start (s, optional)</label>
        <input type="number" id="proc-start" value="0" min="0" step="0.1">
      </div>
      <div class="form-group">
        <label>Trim End (s, optional)</label>
        <input type="number" id="proc-end" value="" placeholder="${dur > 0 ? dur.toFixed(1) : 'end'}" min="0" step="0.1">
      </div>
    </div>
    <div class="form-group mb-8">
      <label>Volume Gain dB (optional, e.g. 2.0 or -3.0)</label>
      <input type="number" id="proc-gain" value="" step="0.5" placeholder="0.0">
    </div>
    <button class="btn btn-primary mt-8" id="process-btn">⚙ Process</button>
  `;

  tab.querySelector('#process-btn')?.addEventListener('click', () => {
    const fmt = tab.querySelector('input[name="proc-format"]:checked')?.value || 'mp3';
    const start = parseFloat(tab.querySelector('#proc-start')?.value || 0);
    const endRaw = tab.querySelector('#proc-end')?.value;
    const end = endRaw ? parseFloat(endRaw) : null;
    const gainRaw = tab.querySelector('#proc-gain')?.value;
    const gain = gainRaw ? parseFloat(gainRaw) : null;

    processTrack(track.track_id, {
      target_format: fmt,
      start_time: start,
      end_time: end,
      volume_gain_db: gain,
    });
  });
}

// ── Playback Tab ──────────────────────────────────────────────────

function renderPlaybackTab(track) {
  const tab = document.getElementById('tab-playback');
  const streamUrl = `${API_BASE}/tracks/${track.track_id}/stream`;
  const canPlay = ['mp3', 'wav', 'flac', 'm4a', 'opus', 'ogg', 'mp4', 'webm'].includes(track.format);

  if (!canPlay) {
    tab.innerHTML = `<p class="text-muted">Playback not available for ${track.format.toUpperCase()} format in browser.</p>`;
    return;
  }

  tab.innerHTML = `
    <div class="player">
      <audio id="audio-player" controls style="width:100%">
        <source src="${streamUrl}" type="audio/${track.format === 'm4a' ? 'mp4' : track.format === 'opus' ? 'ogg' : track.format}">
        Your browser does not support audio playback.
      </audio>
      <div class="player-info">
        <span>${escapeHtml(track.file_name)}</span>
        <span class="text-muted">${formatDuration(track.duration_seconds)}</span>
      </div>
    </div>
  `;
}

// ── Metadata Tab ──────────────────────────────────────────────────

function renderMetadataTab(track) {
  const tab = document.getElementById('tab-metadata');
  tab.innerHTML = `
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Track ID</div>
        <div class="info-value" style="font-family:var(--font-mono)">${escapeHtml(track.track_id)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Filename</div>
        <div class="info-value">${escapeHtml(track.file_name)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Path</div>
        <div class="info-value" style="font-size:0.8rem;font-family:var(--font-mono)">${escapeHtml(track.file_path)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Format</div>
        <div class="info-value">${track.format.toUpperCase()}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Media Type</div>
        <div class="info-value">${track.media_type}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Duration</div>
        <div class="info-value">${formatDuration(track.duration_seconds)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Size</div>
        <div class="info-value">${formatSize(track.size_bytes)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Title Metadata</div>
        <div class="info-value">${escapeHtml(track.title || '(none)')}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Cover Art</div>
        <div class="info-value">${track.has_cover ? '✓ Yes' : '✗ No'}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Volume (cleaned avg)</div>
        <div class="info-value">${formatDb(track.cleaned_average_db)}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Volume (max)</div>
        <div class="info-value">${formatDb(track.max_volume_db)}</div>
      </div>
    </div>
    <div style="margin-top:12px">
      <button class="btn btn-primary btn-sm" id="meta-refresh-btn">🔄 Refresh Metadata</button>
    </div>
  `;

  tab.querySelector('#meta-refresh-btn')?.addEventListener('click', async () => {
    try {
      const data = await api(`/tracks/${track.track_id}/metadata`);
      const trackInState = state.tracks.find(t => t.track_id === track.track_id);
      if (trackInState) {
        trackInState.title = data.title || '';
        trackInState.has_cover = data.has_cover || false;
      }
      toast('Metadata refreshed', 'success');
      renderDetail();
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}

function renderResults() {
  if (state.results.length === 0) {
    els.resultsArea.style.display = 'none';
    return;
  }

  els.resultsArea.style.display = 'block';
  els.resultsList.innerHTML = state.results.map((r, i) => {
    const statusClass = r.success ? 'success' : 'error';
    const statusText = r.success ? '✓ Done' : `✗ ${r.error || 'Failed'}`;
    const showLink = r.success && (r.result_id || r.output_path) && !r.downloaded;
    return `
      <div class="result-item">
        <div class="result-info">
          <span class="result-status ${statusClass}">${statusText}</span>
          <span style="font-size:0.8rem;color:var(--text-secondary)">
            Track #${r.track_id} — ${r.type}
            ${r.duration ? `(${r.duration.toFixed(1)}s)` : ''}
            ${r.downloaded ? '<span style="color:var(--text-muted)"> (downloaded)</span>' : ''}
          </span>
        </div>
        <div>
          ${showLink
            ? `<a href="#" class="download-link" data-result-id="${escapeHtml(r.result_id || '')}" data-index="${i}">⬇ Download</a>`
            : ''
          }
        </div>
      </div>
    `;
  }).join('');

  // Download links
  els.resultsList.querySelectorAll('.download-link').forEach(link => {
    link.addEventListener('click', async (e) => {
      e.preventDefault();
      const resultId = link.dataset.resultId;
      const index = parseInt(link.dataset.index, 10);
      const ok = resultId ? await downloadResult(resultId) : false;
      if (ok && !isNaN(index) && state.results[index]) {
        state.results[index].downloaded = true;
        renderResults();
      }
    });
  });
}

// ── Tab Switching ──────────────────────────────────────────────────

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.dataset.tab;
      // Deactivate all
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      // Activate target
      btn.classList.add('active');
      const content = document.getElementById(tabId);
      if (content) content.classList.add('active');
    });
  });
}

// ── Upload Drag & Drop ─────────────────────────────────────────────

function initUpload() {
  const zone = els.uploadZone;
  const input = els.uploadInput;

  zone.addEventListener('click', () => input.click());

  input.addEventListener('change', () => {
    if (input.files.length) {
      uploadFiles(input.files);
      input.value = '';
    }
  });

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });

  zone.addEventListener('dragleave', () => {
    zone.classList.remove('drag-over');
  });

  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files.length) {
      uploadFiles(e.dataTransfer.files);
    }
  });
}

// ── Event Registration ─────────────────────────────────────────────

function initEvents() {
  // Scan
  els.scanBtn?.addEventListener('click', () => scanFolder(els.scanInput.value));
  els.scanInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') scanFolder(els.scanInput.value);
  });

  // Clear all
  els.clearTracksBtn?.addEventListener('click', clearAllTracks);

  // Clear results
  els.clearResultsBtn?.addEventListener('click', () => {
    state.results = [];
    renderResults();
  });

  // Batch equalize
  els.eqAvgBtn?.addEventListener('click', () => {
    const target = parseFloat(els.eqTargetDb?.value || -16);
    equalizeAverage([...state.batchIds], target);
  });

  els.eqLoudBtn?.addEventListener('click', () => {
    const target = parseFloat(els.eqTargetDb?.value || -16);
    equalizeLoudest([...state.batchIds], target);
  });

  // Tab switching
  initTabs();
}

// ── Utility ─────────────────────────────────────────────────────────

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Init ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initDOMElements();
  initUpload();
  initEvents();
  renderTrackList();
  renderDetail();
  renderResults();

  // Select first tab by default
  const firstTab = document.querySelector('.tab-btn');
  if (firstTab) firstTab.click();
});
