// Saves options to chrome.storage
function saveOptions(e) {
  e.preventDefault();
  const port = document.getElementById('backend-port').value;
  chrome.storage.sync.set({ backendPort: port }, function() {
    const status = document.getElementById('status');
    status.textContent = 'Saved!';
    setTimeout(() => { status.textContent = ''; }, 1200);
  });
}

// Restores the port setting from chrome.storage
function restoreOptions() {
  chrome.storage.sync.get({ backendPort: '8000' }, function(items) {
    document.getElementById('backend-port').value = items.backendPort;
  });
}

document.addEventListener('DOMContentLoaded', restoreOptions);
document.getElementById('options-form').addEventListener('submit', saveOptions); 