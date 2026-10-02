// Keep in step with DEFAULTS in worker.js. The worker applies saved settings at once.
const DEFAULTS = {
  port: 8790,
  groupTitle: 'Pilot',
  groupColor: 'orange',
  showIndicator: true,
  blockedSites: []
}

const form = document.getElementById('settings')
const status = document.getElementById('status')
const saved = document.getElementById('saved')

/** "https://Accounts.Example.com/login" and "*.example.com" both become a bare host name. */
function hostOnly(line) {
  const text = line.trim().toLowerCase().replace(/^\*\./, '')

  if (!text) {
    return ''
  }

  try {
    return new URL(text.includes('://') ? text : `https://${text}`).hostname
  } catch {
    return ''
  }
}

function fill(settings) {
  form.port.value = settings.port
  form.groupTitle.value = settings.groupTitle
  form.groupColor.value = settings.groupColor
  form.showIndicator.checked = settings.showIndicator
  form.blockedSites.value = settings.blockedSites.join('\n')
}

async function load() {
  fill({ ...DEFAULTS, ...(await chrome.storage.local.get(Object.keys(DEFAULTS))) })
  await checkBridge()
}

async function checkBridge() {
  const port = Number(form.port.value) || DEFAULTS.port

  try {
    const health = await (await fetch(`http://127.0.0.1:${port}/health`)).json()

    status.dataset.state = health.extension_connected ? 'on' : 'off'
    status.textContent = health.extension_connected
      ? `Connected to the bridge on port ${port}.`
      : `The bridge is running on port ${port}, but this extension is not connected to it yet. It retries every few seconds.`
  } catch {
    status.dataset.state = 'off'
    status.textContent = `No bridge is answering on port ${port}. Start the bridge on this computer, then reload this page.`
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault()

  const blockedSites = [...new Set(form.blockedSites.value.split('\n').map(hostOnly).filter(Boolean))]

  await chrome.storage.local.set({
    port: Number(form.port.value),
    groupTitle: form.groupTitle.value.trim() || DEFAULTS.groupTitle,
    groupColor: form.groupColor.value,
    showIndicator: form.showIndicator.checked,
    blockedSites
  })

  form.blockedSites.value = blockedSites.join('\n')
  saved.textContent = 'Saved'
  setTimeout(() => (saved.textContent = ''), 2500)
  // Give the worker a moment to re-dial before reporting on the connection.
  setTimeout(checkBridge, 2500)
})

document.getElementById('reset').addEventListener('click', async () => {
  await chrome.storage.local.set(DEFAULTS)
  fill(DEFAULTS)
  saved.textContent = 'Defaults restored'
  setTimeout(() => (saved.textContent = ''), 2500)
  setTimeout(checkBridge, 2500)
})

void load()
