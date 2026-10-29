// Keep in step with DEFAULTS in worker.js. The worker applies saved settings at once.
const DEFAULTS = {
  ports: [8790],
  groupTitle: 'Pilot',
  groupColor: 'orange',
  showIndicator: true,
  bringToFront: true,
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

/** "8790, 8791" becomes [8790, 8791]: whole numbers a port can be, each once. */
function portsOf(text) {
  const ports = String(text).split(/[\s,]+/).map(Number).filter(port => Number.isInteger(port) && port > 0 && port < 65536)

  return [...new Set(ports)].slice(0, 8)
}

function fill(settings) {
  form.ports.value = settings.ports.join(', ')
  form.groupTitle.value = settings.groupTitle
  form.groupColor.value = settings.groupColor
  form.showIndicator.checked = settings.showIndicator
  form.bringToFront.checked = settings.bringToFront
  form.blockedSites.value = settings.blockedSites.join('\n')
}

async function load() {
  // `port` is what a version with one bridge stored.
  const { port, ...stored } = await chrome.storage.local.get([...Object.keys(DEFAULTS), 'port'])
  const ports = portsOf([].concat(stored.ports ?? port ?? DEFAULTS.ports).join(','))

  fill({ ...DEFAULTS, ...stored, ports: ports.length ? ports : DEFAULTS.ports })
  await checkBridge()
}

/** One sentence on the bridge at this port, and whether this extension is connected to it. */
async function checkPort(port) {
  try {
    const health = await (await fetch(`http://127.0.0.1:${port}/health`)).json()

    return health.extension_connected
      ? { on: true, text: `Connected to the bridge on port ${port}.` }
      : { on: false, text: `The bridge is running on port ${port}, but this extension is not connected to it yet. It retries every few seconds.` }
  } catch {
    return { on: false, text: `No bridge is answering on port ${port}. Start the bridge on this computer, then reload this page.` }
  }
}

async function checkBridge() {
  const ports = portsOf(form.ports.value)
  const found = await Promise.all((ports.length ? ports : DEFAULTS.ports).map(checkPort))

  status.dataset.state = found.every(bridge => bridge.on) ? 'on' : 'off'
  status.textContent = found.map(bridge => bridge.text).join(' ')
}

form.addEventListener('submit', async event => {
  event.preventDefault()

  const blockedSites = [...new Set(form.blockedSites.value.split('\n').map(hostOnly).filter(Boolean))]

  const ports = portsOf(form.ports.value)

  if (!ports.length) {
    saved.textContent = 'Type at least one port, such as 8790'

    return
  }

  await chrome.storage.local.remove('port')
  await chrome.storage.local.set({
    ports,
    groupTitle: form.groupTitle.value.trim() || DEFAULTS.groupTitle,
    groupColor: form.groupColor.value,
    showIndicator: form.showIndicator.checked,
    bringToFront: form.bringToFront.checked,
    blockedSites
  })

  form.ports.value = ports.join(', ')
  form.blockedSites.value = blockedSites.join('\n')
  saved.textContent = 'Saved'
  setTimeout(() => (saved.textContent = ''), 2500)
  // Give the worker a moment to re-dial before reporting on the connection.
  setTimeout(checkBridge, 2500)
})

document.getElementById('reset').addEventListener('click', async () => {
  await chrome.storage.local.remove('port')
  await chrome.storage.local.set(DEFAULTS)
  fill(DEFAULTS)
  saved.textContent = 'Defaults restored'
  setTimeout(() => (saved.textContent = ''), 2500)
  setTimeout(checkBridge, 2500)
})

void load()
