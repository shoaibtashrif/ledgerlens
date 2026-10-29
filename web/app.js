// LedgerLens Frontend Client
let currentDocId = null;
let currentSettings = null;

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupUpload();
  loadSettings();
  loadSamples();
  loadDocuments();
  loadReport();
  loadLogs();

  document.getElementById('btn-open-settings').addEventListener('click', openSettingsModal);
});

// Toast notification helper
function showToast(message, type = 'info') {
  const t = document.getElementById('toast');
  t.textContent = message;
  t.className = `toast show ${type}`;
  setTimeout(() => {
    t.className = 'toast';
  }, 3500);
}

// Tab navigation
function setupTabs() {
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      
      btn.classList.add('active');
      const target = btn.getAttribute('data-tab');
      document.getElementById(target).classList.add('active');

      if (target === 'tab-review' || target === 'tab-ledger') loadDocuments();
      if (target === 'tab-analytics') loadReport();
      if (target === 'tab-logs') loadLogs();
    });
  });
}

// Load System Settings and API Keys status
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();
    currentSettings = data;

    let hasAnyKey = false;
    data.providers.forEach(p => {
      const badge = document.getElementById(`badge-${p.name}`);
      if (badge) {
        if (p.available) {
          badge.classList.add('active');
          badge.setAttribute('title', `${p.label}: Ready (${p.text_model})`);
          hasAnyKey = true;
        } else {
          badge.classList.remove('active');
          badge.setAttribute('title', `${p.label}: Key required or offline`);
        }
      }
    });

    const banner = document.getElementById('banner-no-keys');
    if (!hasAnyKey) {
      banner.style.display = 'flex';
    } else {
      banner.style.display = 'none';
    }

    renderSettingsModal(data);
  } catch (err) {
    console.error('Failed to load settings:', err);
  }
}

// Render Settings Modal
function renderSettingsModal(data) {
  const container = document.getElementById('providers-config-list');
  container.innerHTML = '';

  data.providers.forEach(p => {
    const card = document.createElement('div');
    card.className = 'card';
    card.style.marginBottom = '1rem';

    let modelSelectHtml = '';
    if (p.installed_models && p.installed_models.length > 0) {
      modelSelectHtml = `
        <div class="form-group" style="margin-top:0.5rem;">
          <label>Installed Ollama Model</label>
          <select id="sel-model-${p.name}" onchange="changeOllamaModel('${p.name}')">
            ${p.installed_models.map(m => `<option value="${m}" ${m === p.text_model ? 'selected' : ''}>${m}</option>`).join('')}
          </select>
        </div>`;
    }

    card.innerHTML = `
      <div class="flex-between">
        <div>
          <strong>${p.label}</strong>
          <span class="badge ${p.available ? 'badge-auto_approved' : 'badge-needs_review'}" style="margin-left:0.5rem;">
            ${p.available ? 'Connected' : 'Missing Key'}
          </span>
        </div>
        ${p.key_url ? `<a href="${p.key_url}" target="_blank" class="btn btn-sm btn-outline">Get ${p.label} API Key ↗</a>` : ''}
      </div>
      <p class="text-sm text-muted" style="margin: 0.35rem 0;">Text: <code>${p.text_model || 'none'}</code> | Vision: <code>${p.vision_model || 'none'}</code></p>
      
      ${p.requires_key ? `
        <div style="margin-top: 0.75rem;">
          <label class="text-sm">API Key ${p.key_masked ? `<span class="text-muted">(Currently: ${p.key_masked})</span>` : ''}</label>
          <div style="display:flex; gap:0.5rem; margin-top:0.25rem;">
            <input type="password" id="input-key-${p.name}" placeholder="Paste ${p.label} API key here..." style="flex:1;">
            <button class="btn btn-primary btn-sm" onclick="saveKey('${p.name}')">Test & Save</button>
            ${p.key_masked ? `<button class="btn btn-danger btn-sm" onclick="deleteKey('${p.name}')">Remove</button>` : ''}
          </div>
          <div style="margin-top:0.35rem;">
            <label class="text-sm text-muted">
              <input type="checkbox" id="chk-remember-${p.name}" checked> Remember key in .env file
            </label>
          </div>
        </div>
      ` : `
        <div style="margin-top: 0.5rem;">
          <span class="text-sm text-muted">
            ${p.name === 'shoaib_cloud' ? '⚡ Connected to Shoaib Dedicated Cloud Relay (No API key required. Requests are processed free via cloud backend).' : (p.available ? 'Local daemon connected. No API key needed.' : 'Ollama is not running locally on port 11434.')}
          </span>
          ${modelSelectHtml}
        </div>
      `}
    `;
    container.appendChild(card);
  });
}

// Save Key Action
async function saveKey(provider) {
  const input = document.getElementById(`input-key-${provider}`);
  const chk = document.getElementById(`chk-remember-${provider}`);
  const key = input.value.trim();

  if (!key) {
    showToast('Please enter an API key first.', 'warning');
    return;
  }

  showToast(`Verifying ${provider} API key...`, 'info');
  try {
    const res = await fetch('/api/keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        api_key: key,
        remember: chk.checked
      })
    });
    const result = await res.json();
    if (!res.ok) {
      throw new Error(result.detail || 'Failed to verify key');
    }
    showToast(`Key verified and saved successfully!`, 'success');
    input.value = '';
    loadSettings();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'danger');
  }
}

// Delete Key Action
async function deleteKey(provider) {
  if (!confirm(`Remove API key for ${provider}?`)) return;
  try {
    await fetch(`/api/keys/${provider}`, { method: 'DELETE' });
    showToast(`Key removed.`, 'info');
    loadSettings();
  } catch (err) {
    showToast(`Error removing key: ${err.message}`, 'danger');
  }
}

// Change Ollama model
async function changeOllamaModel(provider) {
  const sel = document.getElementById(`sel-model-${provider}`);
  const model = sel.value;
  await fetch('/api/models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider, text_model: model })
  });
  showToast(`Ollama model updated to ${model}`, 'success');
  loadSettings();
}

function openSettingsModal() {
  document.getElementById('settings-modal').classList.add('open');
}

function closeSettingsModal() {
  document.getElementById('settings-modal').classList.remove('open');
}

// Drag & Drop File Upload
function setupUpload() {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, e => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', e => {
    const files = e.dataTransfer.files;
    if (files.length) handleFiles(files);
  });

  fileInput.addEventListener('change', e => {
    if (fileInput.files.length) handleFiles(fileInput.files);
  });
}

// Handle Uploaded Files
async function handleFiles(files) {
  const sec = document.getElementById('processing-section');
  const itemsContainer = document.getElementById('processing-items');
  const counter = document.getElementById('proc-counter');
  sec.style.display = 'block';

  let total = files.length;
  counter.textContent = `${total} in flight`;

  for (let file of files) {
    const item = document.createElement('div');
    item.className = 'sample-item';
    item.innerHTML = `
      <div><strong>${file.name}</strong> <span class="meta">(${Math.round(file.size / 1024)} KB)</span></div>
      <div class="meta" id="status-${file.name}"><span class="spinner spinner-primary"></span> Analyzing document with AI...</div>
    `;
    itemsContainer.prepend(item);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/process', {
        method: 'POST',
        body: formData
      });
      const doc = await res.json();
      const statusEl = document.getElementById(`status-${file.name}`);
      if (res.ok) {
        statusEl.innerHTML = `<span class="badge badge-${doc.status}">${doc.status}</span>`;
      } else {
        statusEl.innerHTML = `<span class="badge badge-failed">Failed</span> <button class="btn btn-sm btn-warning" style="margin-left:0.5rem;" onclick="loadDocuments()">View in Queue</button>`;
      }
    } catch (err) {
      document.getElementById(`status-${file.name}`).innerHTML = `<span class="badge badge-failed">Failed</span>`;
    }
    total--;
    counter.textContent = total > 0 ? `${total} in flight` : 'Completed';
  }

  loadDocuments();
  loadReport();
  loadLogs();
}

// Load built-in sample invoices
async function loadSamples() {
  try {
    const res = await fetch('/api/samples');
    const data = await res.json();
    const container = document.getElementById('sample-list');
    container.innerHTML = '';

    if (!data.samples || data.samples.length === 0) {
      container.innerHTML = '<span class="text-sm text-muted">No built-in samples found.</span>';
      return;
    }

    data.samples.forEach(s => {
      const el = document.createElement('div');
      el.className = 'sample-item';
      el.innerHTML = `
        <div>
          <strong>${s}</strong>
        </div>
        <button class="btn btn-sm btn-primary" onclick="runSample('${s}')">Run Test</button>
      `;
      container.appendChild(el);
    });
  } catch (err) {
    console.error('Failed to load samples:', err);
  }
}

// Run a built-in sample
async function runSample(name) {
  showToast(`Processing sample "${name}"...`, 'info');
  try {
    const res = await fetch(`/api/samples/${name}`, { method: 'POST' });
    const doc = await res.json();
    if (!res.ok) throw new Error(doc.detail || 'Processing failed');
    showToast(`Sample processed: ${doc.status}`, 'success');
    loadDocuments();
    loadReport();
    loadLogs();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'danger');
  }
}

// Load all documents for tables
async function loadDocuments() {
  try {
    const res = await fetch('/api/documents');
    const docs = await res.json();

    const recentTbody = document.getElementById('recent-docs-tbody');
    const reviewTbody = document.getElementById('review-docs-tbody');
    const ledgerTbody = document.getElementById('ledger-docs-tbody');

    const reviewDocs = docs.filter(d => d.status === 'needs_review');
    const ledgerDocs = docs.filter(d => d.status === 'auto_approved' || d.status === 'approved');

    document.getElementById('cnt-review').textContent = reviewDocs.length;
    document.getElementById('cnt-ledger').textContent = ledgerDocs.length;

    // Recent Ingest
    if (docs.length === 0) {
      recentTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No documents processed yet.</td></tr>';
    } else {
      recentTbody.innerHTML = docs.slice(0, 10).map(d => renderDocRow(d)).join('');
    }

    // Review Queue
    if (reviewDocs.length === 0) {
      reviewTbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Queue clean! No invoices currently waiting for review.</td></tr>';
    } else {
      reviewTbody.innerHTML = reviewDocs.map(d => renderReviewRow(d)).join('');
    }

    // Ledger
    if (ledgerDocs.length === 0) {
      ledgerTbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No approved invoices yet.</td></tr>';
    } else {
      ledgerTbody.innerHTML = ledgerDocs.map(d => renderLedgerRow(d)).join('');
    }
  } catch (err) {
    console.error('Error loading documents:', err);
  }
}

function renderDocRow(d) {
  const data = d.data || {};
  const total = data.total ? `${data.currency || ''} ${data.total.toLocaleString()}` : '--';
  return `
    <tr id="row-${d.id}">
      <td><strong>${d.filename}</strong><br><span class="meta">${d.created_at || ''}</span></td>
      <td>${data.vendor_name || '<span class="text-muted">Unknown</span>'}</td>
      <td><strong>${total}</strong></td>
      <td><span class="badge badge-${d.status}">${d.status}</span></td>
      <td>${Math.round((d.confidence || 0) * 100)}%</td>
      <td><span class="meta">${d.provider || 'none'}</span></td>
      <td>
        <div class="btn-group">
          ${(d.status === 'failed' || d.status === 'needs_review') ? `<button class="btn btn-sm btn-warning" onclick="retryDocument('${d.id}', event)">🔄 Retry</button>` : ''}
          <button class="btn btn-sm btn-secondary" onclick="openReviewModal('${d.id}')">Inspect</button>
        </div>
      </td>
    </tr>
  `;
}

function renderReviewRow(d) {
  const data = d.data || {};
  const total = data.total ? `${data.currency || ''} ${data.total.toLocaleString()}` : '--';
  const issueList = (d.issues || []).map(i => `<span class="badge badge-${i.severity === 'error' ? 'failed' : 'needs_review'}">${i.message}</span>`).join(' ');
  return `
    <tr id="rev-row-${d.id}">
      <td><strong>${d.filename}</strong></td>
      <td>${issueList || '<span class="text-muted">Flagged for verification</span>'}</td>
      <td>${data.vendor_name || 'Unknown'}</td>
      <td><strong>${total}</strong></td>
      <td>${Math.round((d.confidence || 0) * 100)}%</td>
      <td>
        <div class="btn-group">
          <button class="btn btn-sm btn-warning" onclick="retryDocument('${d.id}', event)">🔄 Retry</button>
          <button class="btn btn-sm btn-primary" onclick="openReviewModal('${d.id}')">Review & Fix</button>
        </div>
      </td>
    </tr>
  `;
}

function renderLedgerRow(d) {
  const data = d.data || {};
  return `
    <tr>
      <td>${data.invoice_date || '--'}</td>
      <td><strong>${data.vendor_name || '--'}</strong></td>
      <td><code>${data.invoice_number || '--'}</code></td>
      <td><span class="badge badge-auto_approved">${d.category || 'Uncategorized'}</span></td>
      <td>${data.currency || '--'}</td>
      <td>${data.subtotal != null ? data.subtotal.toLocaleString() : '--'}</td>
      <td>${data.tax != null ? data.tax.toLocaleString() : '--'}</td>
      <td><strong>${data.total != null ? data.total.toLocaleString() : '--'}</strong></td>
      <td><span class="meta">${d.status === 'auto_approved' ? '⚡ AI Validated' : '👤 Human Approved'}</span></td>
      <td>
        <button class="btn btn-sm btn-outline" onclick="openReviewModal('${d.id}')">Details</button>
      </td>
    </tr>
  `;
}

// Open Review Modal Drawer
async function openReviewModal(docId) {
  currentDocId = docId;
  const res = await fetch(`/api/documents/${docId}`);
  const doc = await res.json();
  const data = doc.data || {};

  document.getElementById('rev-filename').textContent = doc.filename;
  const statusBadge = document.getElementById('rev-status-badge');
  statusBadge.textContent = doc.status;
  statusBadge.className = `badge badge-${doc.status}`;

  document.getElementById('rev-file-link').href = `/api/documents/${docId}/file`;
  document.getElementById('doc-iframe').src = `/api/documents/${docId}/file`;

  // Issues Alert Box
  const issuesBox = document.getElementById('rev-issues-alert');
  if (doc.issues && doc.issues.length > 0) {
    issuesBox.style.display = 'block';
    issuesBox.innerHTML = `
      <strong>Validation Checks:</strong>
      <ul>${doc.issues.map(i => `<li>[${i.severity.toUpperCase()}] ${i.message}</li>`).join('')}</ul>
    `;
  } else {
    issuesBox.style.display = 'none';
  }

  // Populate categories
  const catSelect = document.getElementById('f-category');
  catSelect.innerHTML = (currentSettings?.categories || []).map(c => 
    `<option value="${c}" ${c === doc.category ? 'selected' : ''}>${c}</option>`
  ).join('');

  // Populate Form Fields
  document.getElementById('f-vendor').value = data.vendor_name || '';
  document.getElementById('f-number').value = data.invoice_number || '';
  document.getElementById('f-date').value = data.invoice_date || '';
  document.getElementById('f-due').value = data.due_date || '';
  document.getElementById('f-currency').value = data.currency || 'USD';
  document.getElementById('f-subtotal').value = data.subtotal ?? '';
  document.getElementById('f-tax').value = data.tax ?? '';
  document.getElementById('f-total').value = data.total ?? '';
  document.getElementById('f-notes').value = doc.reviewer_note || '';

  // Audit Meta
  document.getElementById('rev-audit-meta').innerHTML = `
    Provider: ${doc.provider || 'none'} | Model: ${doc.model || 'none'} | Latency: ${doc.latency_ms || 0}ms<br>
    Tokens: ${doc.tokens_in || 0} in / ${doc.tokens_out || 0} out | Confidence: ${Math.round((doc.confidence || 0) * 100)}%
  `;

  document.getElementById('review-modal').classList.add('open');
}

function closeReviewModal() {
  document.getElementById('review-modal').classList.remove('open');
  document.getElementById('doc-iframe').src = '';
  currentDocId = null;
}

// Submit Review Form
async function submitReview(action) {
  if (!currentDocId) return;

  const data = {
    vendor_name: document.getElementById('f-vendor').value.trim(),
    invoice_number: document.getElementById('f-number').value.trim(),
    invoice_date: document.getElementById('f-date').value.trim(),
    due_date: document.getElementById('f-due').value.trim() || null,
    currency: document.getElementById('f-currency').value.trim(),
    subtotal: document.getElementById('f-subtotal').value ? parseFloat(document.getElementById('f-subtotal').value) : null,
    tax: document.getElementById('f-tax').value ? parseFloat(document.getElementById('f-tax').value) : null,
    total: document.getElementById('f-total').value ? parseFloat(document.getElementById('f-total').value) : null
  };

  const category = document.getElementById('f-category').value;
  const note = document.getElementById('f-notes').value.trim();

  try {
    const res = await fetch(`/api/documents/${currentDocId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ data, category, action, note })
    });
    const updated = await res.json();
    if (!res.ok) throw new Error(updated.detail || 'Failed to update document');

    showToast(`Document ${action === 'approve' ? 'approved to ledger' : action === 'reject' ? 'rejected' : 'saved'}!`, 'success');
    closeReviewModal();
    loadDocuments();
    loadReport();
    loadLogs();
  } catch (err) {
    showToast(`Error: ${err.message}`, 'danger');
  }
}

// Load Financial & Operational Metrics
async function loadReport() {
  try {
    const res = await fetch('/api/report');
    const data = await res.json();
    const m = data.metrics || {};

    const strPercent = Math.round((m.straight_through_rate || 0) * 100);
    const touchPercent = Math.round((m.manual_touch_rate || 0) * 100);

    document.getElementById('qs-str').textContent = `${strPercent}%`;
    document.getElementById('m-str').textContent = `${strPercent}%`;
    document.getElementById('m-touch').textContent = `${touchPercent}%`;
    document.getElementById('m-latency').textContent = `${m.avg_latency_s || 0}s`;
    document.getElementById('m-cost').textContent = `$${(m.est_cost_usd || 0).toFixed(4)}`;

    // Category Breakdown
    const catContainer = document.getElementById('category-breakdown');
    catContainer.innerHTML = (data.by_category || []).map(c => `
      <div class="breakdown-item">
        <span><strong>${c.category}</strong></span>
        <span>${c.currency} ${c.total.toLocaleString()}</span>
      </div>
    `).join('') || '<div class="text-sm text-muted">No spend recorded yet.</div>';

    // Vendor Breakdown
    const venContainer = document.getElementById('vendor-breakdown');
    venContainer.innerHTML = (data.by_vendor || []).map(v => `
      <div class="breakdown-item">
        <span><strong>${v.vendor}</strong></span>
        <span>${v.total.toLocaleString()}</span>
      </div>
    `).join('') || '<div class="text-sm text-muted">No vendor activity recorded yet.</div>';

  } catch (err) {
    console.error('Error loading report:', err);
  }
}

// Load Audit Logs
async function loadLogs() {
  try {
    const res = await fetch('/api/logs');
    const logs = await res.json();
    const pre = document.getElementById('log-console');
    pre.textContent = logs.map(l => `[${l.ts}] [${l.level.toUpperCase()}] [${l.step}] ${l.message}`).join('\n') || 'No logs recorded yet.';
  } catch (err) {
    console.error('Error loading logs:', err);
  }
}

// Retry processing an existing document without re-uploading
async function retryDocument(docId, event) {
  if (event) event.stopPropagation();
  showToast('Re-processing document with AI...', 'info');

  const overlay = document.getElementById('rev-loading-overlay');
  if (overlay && currentDocId === docId) {
    overlay.style.display = 'flex';
  }

  try {
    const res = await fetch(`/api/documents/${docId}/rerun`, { method: 'POST' });
    const doc = await res.json();
    if (!res.ok) throw new Error(doc.detail || 'Retry failed');

    if (doc.status === 'failed') {
      const errMsg = (doc.issues && doc.issues[0]) ? doc.issues[0].message : 'AI processing failed';
      showToast(errMsg, 'danger');
    } else {
      showToast(`Processed: ${doc.status} (Confidence: ${Math.round((doc.confidence || 0) * 100)}%)`, 'success');
    }

    // Refresh modal if currently open
    if (currentDocId === docId) {
      await openReviewModal(docId);
    }
    loadDocuments();
    loadReport();
    loadLogs();
  } catch (err) {
    showToast(`Retry error: ${err.message}`, 'danger');
  } finally {
    if (overlay) overlay.style.display = 'none';
  }
}

async function retryCurrentDocument() {
  if (!currentDocId) return;
  await retryDocument(currentDocId);
}
