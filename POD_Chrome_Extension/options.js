function saveOptions(e) {
  e.preventDefault();
  const port = document.getElementById('backend-port').value;
  const url  = document.getElementById('backend-url').value.trim().replace(/\/$/, '');
  chrome.storage.sync.set({ backendPort: port, backendUrl: url }, function() {
    const status = document.getElementById('status');
    status.textContent = 'Saved!';
    setTimeout(() => { status.textContent = ''; }, 1500);
  });
}

function restoreOptions() {
  chrome.storage.sync.get({ backendPort: '8000', backendUrl: '' }, function(items) {
    document.getElementById('backend-port').value = items.backendPort;
    document.getElementById('backend-url').value  = items.backendUrl || '';
  });
}

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('options-form').addEventListener('submit', saveOptions);
