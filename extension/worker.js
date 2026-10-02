/**
 * Hermes in Chrome, the browser half.
 *
 * Holds a WebSocket to the local bridge (127.0.0.1) and carries out the agent's commands in ONE
 * working tab, kept in its own tab group. Everything is addressed at that tab only: the agent
 * has no command that lists, reads or changes any other tab, so the user's own tabs stay private
 * and undisturbed. The working tab opens in the background and shows a border and a badge while
 * it is under the agent's control.
 */

const DEFAULTS = {
  port: 8790,
  groupTitle: 'Hermes',
  groupColor: 'orange',
  showIndicator: true,
  // Host names the agent may never open, one per entry. A name also covers its subdomains.
  blockedSites: []
}
// Chrome's tab group colours, as the hex values the on-page indicator is drawn in.
const GROUP_COLORS = {
  grey: '#5f6368', blue: '#1a73e8', red: '#d93025', yellow: '#f9ab00', green: '#188038',
  pink: '#d01884', purple: '#9334e6', cyan: '#007b83', orange: '#e8710a'
}
const LOAD_TIMEOUT_MS = 20_000
const KEEPALIVE_MS = 20_000
const TAB_KEY = 'workingTabId'

let settings = { ...DEFAULTS }

async function loadSettings() {
  const stored = await chrome.storage.local.get(Object.keys(DEFAULTS))

  settings = { ...DEFAULTS, ...stored }

  if (!(settings.groupColor in GROUP_COLORS)) {
    settings.groupColor = DEFAULTS.groupColor
  }

  return settings
}

function bridgeUrl() {
  // Loopback only, whatever is stored: the bridge must never be a remote machine.
  const port = Number.isInteger(Number(settings.port)) && settings.port > 0 && settings.port < 65536 ? Number(settings.port) : DEFAULTS.port

  return `ws://127.0.0.1:${port}/ext`
}

/** The blocked entry that covers this URL's host, or null. */
function blockedBy(url) {
  let host

  try {
    host = new URL(url).hostname.toLowerCase()
  } catch {
    return null
  }

  for (const entry of settings.blockedSites || []) {
    const blocked = String(entry).trim().toLowerCase().replace(/^\*\./, '')

    if (blocked && (host === blocked || host.endsWith(`.${blocked}`))) {
      return blocked
    }
  }

  return null
}

function indicator() {
  return { color: GROUP_COLORS[settings.groupColor], label: `${settings.groupTitle} is working in this tab`, show: settings.showIndicator }
}

let socket = null
let keepalive = null

// ── connection ───────────────────────────────────────────────────────────────────────────────

async function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }

  await loadSettings()

  // A second caller may have connected while the settings were loading.
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return
  }

  const ws = new WebSocket(bridgeUrl())
  socket = ws

  ws.addEventListener('open', () => {
    chrome.action.setBadgeText({ text: '' })
    chrome.action.setTitle({ title: 'Hermes in Chrome is connected' })
    // Traffic on the socket is what keeps a Manifest V3 service worker from being suspended.
    clearInterval(keepalive)
    keepalive = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, KEEPALIVE_MS)
  })

  ws.addEventListener('message', async ({ data }) => {
    let message

    try {
      message = JSON.parse(data)
    } catch {
      return
    }

    let reply

    try {
      reply = { id: message.id, ok: true, result: await run(message.command, message.args || {}) }
    } catch (error) {
      reply = { id: message.id, ok: false, error: String(error?.message || error) }
    }

    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(reply))
    }
  })

  ws.addEventListener('close', () => {
    if (socket === ws) {
      socket = null
      clearInterval(keepalive)
      chrome.action.setBadgeText({ text: '!' })
      chrome.action.setBadgeBackgroundColor({ color: '#b45309' })
      chrome.action.setTitle({ title: 'Hermes in Chrome cannot reach the bridge' })
      // Re-dial soon; the alarm below is the slower safety net for a suspended worker.
      setTimeout(connect, 2000)
    }
  })
}

// The alarm wakes a suspended worker and re-dials a bridge that was down.
chrome.alarms.create('reconnect', { periodInMinutes: 0.5 })
chrome.alarms.onAlarm.addListener(() => void connect())
chrome.runtime.onStartup.addListener(() => void connect())
chrome.runtime.onInstalled.addListener(() => void connect())
chrome.action.onClicked.addListener(() => chrome.runtime.openOptionsPage())

// Settings saved on the options page take effect at once.
chrome.storage.onChanged.addListener(async (changes, area) => {
  if (area !== 'local') {
    return
  }

  const portChanged = 'port' in changes

  await loadSettings()

  if (portChanged && socket) {
    socket.close() // the close handler re-dials, now on the new port
  } else {
    void connect()
  }

  const tab = await workingTab()

  if (tab) {
    await chrome.tabGroups.update(tab.groupId, { color: settings.groupColor, title: settings.groupTitle }).catch(() => undefined)
    await inPage(tab.id, paintIndicator, [indicator()]).catch(() => undefined)
  }
})

void connect()

// ── the working tab ──────────────────────────────────────────────────────────────────────────

async function workingTab() {
  const { [TAB_KEY]: tabId } = await chrome.storage.session.get(TAB_KEY)

  if (typeof tabId !== 'number') {
    return null
  }

  try {
    const tab = await chrome.tabs.get(tabId)

    // Dragged out of the group by the user: it is theirs again.
    if (tab.groupId === chrome.tabGroups.TAB_GROUP_ID_NONE) {
      await chrome.storage.session.remove(TAB_KEY)

      return null
    }

    return tab
  } catch {
    await chrome.storage.session.remove(TAB_KEY)

    return null
  }
}

async function requireTab() {
  const tab = await workingTab()

  if (!tab) {
    throw new Error('No working tab is open. Call `open` with a URL first.')
  }

  return tab
}

function waitForLoad(tabId, timeoutMs = LOAD_TIMEOUT_MS) {
  return new Promise(resolve => {
    let done = false

    const finish = () => {
      if (!done) {
        done = true
        chrome.tabs.onUpdated.removeListener(listener)
        clearTimeout(timer)
        resolve()
      }
    }

    const listener = (id, change) => {
      if (id === tabId && change.status === 'complete') {
        finish()
      }
    }

    const timer = setTimeout(finish, timeoutMs)

    chrome.tabs.onUpdated.addListener(listener)
    chrome.tabs.get(tabId).then(tab => tab.status === 'complete' && finish(), finish)
  })
}

async function describe(tabId) {
  const tab = await chrome.tabs.get(tabId)

  return { title: tab.title || '', url: tab.url || tab.pendingUrl || '' }
}

/** Run a self-contained function in the working tab's page. */
async function inPage(tabId, func, args = []) {
  let frames

  try {
    frames = await chrome.scripting.executeScript({ target: { tabId }, func, args })
  } catch (error) {
    throw new Error(`Chrome does not allow scripts on this page (${String(error?.message || error)}).`)
  }

  const result = frames?.[0]?.result

  if (result && result.error) {
    throw new Error(result.error)
  }

  return result
}

/** After an action that may navigate: give it a moment, then wait out any page load. */
async function settle(tabId) {
  await new Promise(resolve => setTimeout(resolve, 450))

  const tab = await chrome.tabs.get(tabId)

  if (tab.status !== 'complete') {
    await waitForLoad(tabId, 12_000)
  }

  await inPage(tabId, paintIndicator, [indicator()]).catch(() => undefined)

  return describe(tabId)
}

// A link or script in the working tab that opens a NEW tab is pulled back into the working tab,
// so the agent never spreads beyond its one tab.
chrome.tabs.onCreated.addListener(async created => {
  const tab = await workingTab()

  if (!tab || created.openerTabId !== tab.id) {
    return
  }

  const url = created.pendingUrl || created.url

  await chrome.tabs.remove(created.id).catch(() => undefined)

  if (url && /^https?:/.test(url) && !blockedBy(url)) {
    await chrome.tabs.update(tab.id, { url }).catch(() => undefined)
  }
})

chrome.tabs.onUpdated.addListener(async (tabId, change) => {
  if (change.status !== 'complete' && !change.url) {
    return
  }

  const tab = await workingTab()

  if (!tab || tab.id !== tabId) {
    return
  }

  // A link or redirect led the working tab to a blocked site: leave it at once.
  if (blockedBy(tab.url || '')) {
    await chrome.tabs.update(tabId, { url: 'about:blank' }).catch(() => undefined)

    return
  }

  if (change.status === 'complete') {
    inPage(tabId, paintIndicator, [indicator()]).catch(() => undefined)
  }
})

// ── commands ─────────────────────────────────────────────────────────────────────────────────

const COMMANDS = {
  async open({ url }) {
    if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) {
      throw new Error('`url` must be an absolute http(s) URL.')
    }

    const blocked = blockedBy(url)

    if (blocked) {
      throw new Error(`The user has blocked ${blocked} for the agent. Do not try to reach it another way.`)
    }

    let tab = await workingTab()

    if (tab) {
      await chrome.tabs.update(tab.id, { url })
      // The tab still reports the old page as complete for a moment after a new URL is set.
      await new Promise(resolve => setTimeout(resolve, 350))
    } else {
      // In the background: the user's active tab and focus are left alone.
      tab = await chrome.tabs.create({ active: false, url })

      const groupId = await chrome.tabs.group({ tabIds: [tab.id] })

      await chrome.tabGroups.update(groupId, { collapsed: false, color: settings.groupColor, title: settings.groupTitle })
      await chrome.storage.session.set({ [TAB_KEY]: tab.id })
    }

    await waitForLoad(tab.id)
    await inPage(tab.id, paintIndicator, [indicator()]).catch(() => undefined)

    return describe(tab.id)
  },

  async read({ max_chars: maxChars, filter }) {
    const tab = await requireTab()

    return inPage(tab.id, snapshotPage, [Number(maxChars) > 0 ? Number(maxChars) : 6000, String(filter || '')])
  },

  async click({ ref }) {
    const tab = await requireTab()

    await inPage(tab.id, clickElement, [Number(ref)])

    return settle(tab.id)
  },

  async type({ ref, text, submit }) {
    const tab = await requireTab()

    await inPage(tab.id, typeIntoElement, [Number(ref), String(text ?? ''), Boolean(submit)])

    return submit ? settle(tab.id) : describe(tab.id)
  },

  async press_key({ key }) {
    const tab = await requireTab()

    await inPage(tab.id, pressKey, [String(key || '')])

    return settle(tab.id)
  },

  async scroll({ direction, pages }) {
    const tab = await requireTab()

    return inPage(tab.id, scrollPage, [String(direction || 'down'), Number(pages) > 0 ? Number(pages) : 1])
  },

  async hover({ ref }) {
    const tab = await requireTab()

    await inPage(tab.id, hoverElement, [Number(ref)])
    await new Promise(resolve => setTimeout(resolve, 350))

    return describe(tab.id)
  },

  /** Bring the working tab to the front, for work that needs the real screen (computer use). */
  async show() {
    const tab = await requireTab()

    await chrome.tabs.update(tab.id, { active: true })
    await chrome.windows.update(tab.windowId, { focused: true })

    return { shown: true, ...(await describe(tab.id)) }
  },

  async back() {
    const tab = await requireTab()

    // history.back() in the page: chrome.tabs.goBack rejects on tabs whose history Chrome has
    // not recorded as session entries (background tabs navigated by form submits).
    await inPage(tab.id, () => {
      history.back()

      return { went_back: true }
    })

    return settle(tab.id)
  },

  async close() {
    const tab = await workingTab()

    if (tab) {
      await chrome.tabs.remove(tab.id)
      await chrome.storage.session.remove(TAB_KEY)
    }

    return { closed: Boolean(tab) }
  },

  /** Maintenance, not an agent tool: pick up edited extension files without a manual reload. */
  async _reload() {
    setTimeout(() => chrome.runtime.reload(), 150)

    return { reloading: true }
  },

  async status() {
    const tab = await workingTab()

    return { connected: true, working_tab: tab ? await describe(tab.id) : null }
  }
}

async function run(command, args) {
  const handler = COMMANDS[command]

  if (!handler) {
    throw new Error(`Unknown command: ${command}`)
  }

  return handler(args)
}

// ── page functions (serialised into the tab, so each must be self-contained) ─────────────────

/** A border and a badge that mark the tab as under the agent's control. Lives on <html>, outside
 *  <body>, so it never shows up in the page text the agent reads. */
function paintIndicator(look) {
  for (const id of ['__hermes_style', '__hermes_frame', '__hermes_badge', '__hermes_cursor']) {
    document.getElementById(id)?.remove()
  }

  // The agent's own pointer: an arrow drawn on the page that glides to whatever the agent is
  // about to act on. It is separate from the user's mouse pointer, which is never moved.
  window.__hermesPointTo = (x, y) => {
    if (!look.show) {
      return Promise.resolve()
    }

    let cursor = document.getElementById('__hermes_cursor')

    if (!cursor) {
      cursor = document.createElement('div')
      cursor.id = '__hermes_cursor'
      cursor.innerHTML =
        '<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M3 2l15 7.5-6.4 2.1L9.5 18z" /></svg>'
      cursor.style.transform = `translate(${window.innerWidth / 2}px, ${window.innerHeight - 80}px)`
      document.documentElement.append(cursor)
      cursor.getBoundingClientRect() // commit the starting point so the first move animates
    }

    cursor.style.transform = `translate(${Math.round(x)}px, ${Math.round(y)}px)`

    // A hidden tab does not animate, and some people ask for no motion: do not wait for either.
    const still = document.visibilityState !== 'visible' || matchMedia('(prefers-reduced-motion: reduce)').matches

    return new Promise(resolve => setTimeout(resolve, still ? 0 : 420))
  }

  // The click and hover ring is feedback the user asked for by installing this, so its style
  // stays even when the standing border and badge are switched off.
  const style = document.createElement('style')

  style.id = '__hermes_style'
  style.textContent = `
    :root { --hermes-accent: ${look.color}; }
    #__hermes_frame { position: fixed; inset: 0; z-index: 2147483646; pointer-events: none;
      box-shadow: inset 0 0 0 3px var(--hermes-accent); animation: __hermes_breathe 2.4s ease-in-out infinite; }
    #__hermes_badge { position: fixed; left: 50%; bottom: 14px; transform: translateX(-50%);
      z-index: 2147483647; pointer-events: none; padding: 6px 12px; border-radius: 999px;
      background: #1c1917; color: #fff; border: 2px solid var(--hermes-accent);
      font: 600 12px/1.2 system-ui, sans-serif; box-shadow: 0 2px 10px rgba(0, 0, 0, .35); }
    #__hermes_cursor { position: fixed; left: 0; top: 0; z-index: 2147483647; pointer-events: none;
      transition: transform .4s cubic-bezier(.2, .8, .2, 1); filter: drop-shadow(0 1px 2px rgba(0, 0, 0, .45)); }
    #__hermes_cursor path { fill: var(--hermes-accent); stroke: #fff; stroke-width: 1.5; stroke-linejoin: round; }
    .__hermes_ring { position: fixed; z-index: 2147483647; pointer-events: none; border-radius: 8px;
      box-shadow: 0 0 0 3px var(--hermes-accent); animation: __hermes_ping .7s ease-out forwards; }
    @keyframes __hermes_breathe { 50% { box-shadow: inset 0 0 0 6px var(--hermes-accent); } }
    @keyframes __hermes_ping { from { opacity: 1; transform: scale(1.25); } to { opacity: 0; transform: scale(1); } }
    @media (prefers-reduced-motion: reduce) {
      #__hermes_frame, .__hermes_ring { animation: none; }
      #__hermes_cursor { transition: none; }
    }
  `
  document.documentElement.append(style)

  if (!look.show) {
    return
  }

  const frame = document.createElement('div')

  frame.id = '__hermes_frame'

  const badge = document.createElement('div')

  badge.id = '__hermes_badge'
  badge.textContent = look.label

  document.documentElement.append(frame, badge)
}

function snapshotPage(maxChars, filter) {
  const SELECTOR = [
    'a[href]', 'button', 'input:not([type=hidden])', 'select', 'textarea', 'summary',
    '[role=button]', '[role=link]', '[role=tab]', '[role=menuitem]', '[role=option]', '[role=checkbox]',
    '[role=radio]', '[role=combobox]', '[role=searchbox]', '[role=textbox]', '[role=switch]',
    '[contenteditable=""]', '[contenteditable=true]', '[onclick]', '[tabindex]:not([tabindex="-1"])'
  ].join(',')

  const clean = text => String(text || '').replace(/\s+/g, ' ').trim()

  const shown = element => {
    const box = element.getBoundingClientRect()

    if (box.width < 2 || box.height < 2) {
      return false
    }

    const style = getComputedStyle(element)

    return style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity) !== 0
  }

  const label = element =>
    clean(
      element.getAttribute('aria-label') ||
        element.innerText ||
        element.value ||
        element.getAttribute('placeholder') ||
        element.getAttribute('title') ||
        element.querySelector('img[alt]')?.getAttribute('alt') ||
        element.getAttribute('name')
    ).slice(0, 90)

  const elements = []

  for (const element of document.querySelectorAll(SELECTOR)) {
    if (elements.length >= 400) {
      break
    }

    if (shown(element) && !element.disabled) {
      elements.push(element)
    }
  }

  // Refs index into this list until the next read.
  window.__hermesElements = elements

  const needle = filter.toLowerCase()
  const listed = []

  elements.forEach((element, ref) => {
    const name = label(element)

    if (!name || (needle && !name.toLowerCase().includes(needle))) {
      return
    }

    const tag = element.tagName.toLowerCase()
    const entry = { ref, kind: element.getAttribute('role') || (tag === 'a' ? 'link' : tag), name }

    if (tag === 'input') {
      entry.kind = `input:${element.type}`

      if (element.type !== 'password' && element.value) {
        entry.value = clean(element.value).slice(0, 60)
      }
    }

    if (listed.length < 250) {
      listed.push(entry)
    }
  })

  const text = clean(document.body?.innerText || '')

  return {
    title: document.title,
    url: location.href,
    text: text.slice(0, maxChars),
    text_truncated: text.length > maxChars,
    scroll: {
      position: Math.round(window.scrollY),
      page_height: document.documentElement.scrollHeight,
      viewport_height: window.innerHeight
    },
    elements: listed,
    elements_total: elements.length,
    ...visualOnly()
  }

  function visualOnly() {
    const canvases = [...document.querySelectorAll('canvas')].filter(shown).length

    if (!canvases) {
      return {}
    }

    return {
      canvas_charts: canvases,
      note:
        `This page draws ${canvases} canvas element(s) (usually charts). Their values are pixels, not ` +
        'text, so they are not in `text`, and values shown only on hover need a real pointer: call ' +
        '`show`, then use computer_use on the Chrome window.'
    }
  }
}

async function clickElement(ref) {
  const element = window.__hermesElements?.[ref]

  if (!element || !element.isConnected) {
    return { error: 'That ref is no longer on the page. Read the page again and use a fresh ref.' }
  }

  element.scrollIntoView({ block: 'center', inline: 'center' })

  const box = element.getBoundingClientRect()

  await window.__hermesPointTo?.(box.left + box.width / 2, box.top + box.height / 2)

  const ring = document.createElement('div')

  ring.className = '__hermes_ring'
  ring.style.cssText = `left:${box.left - 4}px;top:${box.top - 4}px;width:${box.width + 8}px;height:${box.height + 8}px`
  document.documentElement.append(ring)
  setTimeout(() => ring.remove(), 800)

  // Keep links that would open a new tab inside the working tab.
  if (element.tagName === 'A' && element.target && element.target !== '_self') {
    element.target = '_self'
  }

  const point = { bubbles: true, cancelable: true, clientX: box.left + box.width / 2, clientY: box.top + box.height / 2, view: window }

  element.dispatchEvent(new PointerEvent('pointerdown', point))
  element.dispatchEvent(new MouseEvent('mousedown', point))
  element.dispatchEvent(new PointerEvent('pointerup', point))
  element.dispatchEvent(new MouseEvent('mouseup', point))
  element.click()

  return { clicked: true }
}

async function typeIntoElement(ref, text, submit) {
  const element = window.__hermesElements?.[ref]

  if (!element || !element.isConnected) {
    return { error: 'That ref is no longer on the page. Read the page again and use a fresh ref.' }
  }

  if (element.type === 'password') {
    return { error: 'Refused: passwords are for the user to type.' }
  }

  element.scrollIntoView({ block: 'center', inline: 'center' })

  const place = element.getBoundingClientRect()

  await window.__hermesPointTo?.(place.left + Math.min(24, place.width / 2), place.top + place.height / 2)
  element.focus()

  const tag = element.tagName

  if (tag === 'INPUT' || tag === 'TEXTAREA') {
    // Framework-controlled inputs (React and friends) only notice a change made through the
    // native setter followed by an input event.
    const prototype = tag === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype

    Object.getOwnPropertyDescriptor(prototype, 'value').set.call(element, text)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  } else if (tag === 'SELECT') {
    const wanted = text.trim().toLowerCase()
    const option = [...element.options].find(
      candidate => candidate.value.toLowerCase() === wanted || candidate.text.trim().toLowerCase() === wanted
    )

    if (!option) {
      return { error: `No option "${text}". Options: ${[...element.options].map(o => o.text.trim()).slice(0, 30).join(', ')}` }
    }

    element.value = option.value
    element.dispatchEvent(new Event('change', { bubbles: true }))
  } else if (element.isContentEditable) {
    document.execCommand('selectAll', false)
    document.execCommand('insertText', false, text)
  } else {
    return { error: 'That element does not take text.' }
  }

  if (submit) {
    const enter = { bubbles: true, cancelable: true, key: 'Enter', code: 'Enter', keyCode: 13, which: 13 }
    const handled = !element.dispatchEvent(new KeyboardEvent('keydown', enter))

    element.dispatchEvent(new KeyboardEvent('keyup', enter))

    if (!handled && element.form) {
      element.form.requestSubmit()
    }
  }

  return { typed: true }
}

function pressKey(key) {
  const KEYS = {
    Enter: 13, Escape: 27, Tab: 9, ArrowDown: 40, ArrowUp: 38, ArrowLeft: 37, ArrowRight: 39,
    PageDown: 34, PageUp: 33, Backspace: 8, Space: 32
  }

  if (!(key in KEYS)) {
    return { error: `Unsupported key. Use one of: ${Object.keys(KEYS).join(', ')}` }
  }

  const target = document.activeElement || document.body
  const init = { bubbles: true, cancelable: true, key: key === 'Space' ? ' ' : key, code: key, keyCode: KEYS[key], which: KEYS[key] }
  const handled = !target.dispatchEvent(new KeyboardEvent('keydown', init))

  target.dispatchEvent(new KeyboardEvent('keyup', init))

  if (!handled) {
    if (key === 'Enter' && target.form) {
      target.form.requestSubmit()
    } else if (key === 'PageDown' || key === 'PageUp') {
      window.scrollBy({ top: (key === 'PageDown' ? 1 : -1) * window.innerHeight * 0.9 })
    }
  }

  return { pressed: key }
}

async function scrollPage(direction, pages) {
  // App-style pages keep the window fixed and scroll an inner panel instead, so pick whatever
  // actually scrolls: the document if it does, else the largest scrollable element on screen.
  const page = document.scrollingElement || document.documentElement
  let box = page
  let container = 'page'

  if (page.scrollHeight <= window.innerHeight + 4) {
    let bestArea = window.innerWidth * window.innerHeight * 0.15

    for (const element of document.querySelectorAll('*')) {
      if (element.scrollHeight <= element.clientHeight + 4) {
        continue
      }

      if (!/(auto|scroll|overlay)/.test(getComputedStyle(element).overflowY)) {
        continue
      }

      const rect = element.getBoundingClientRect()
      const area = rect.width * rect.height

      if (area > bestArea) {
        bestArea = area
        box = element
        container = 'inner panel'
      }
    }
  }

  const before = box.scrollTop
  const screen = box.clientHeight * 0.9
  const target =
    direction === 'top' ? 0 : direction === 'bottom' ? box.scrollHeight : before + (direction === 'up' ? -1 : 1) * screen * pages
  const area = box === page ? { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight } : box.getBoundingClientRect()

  await window.__hermesPointTo?.(area.left + area.width / 2, area.top + area.height / 2)

  // Smooth scrolling only runs in a tab someone can see; a background tab would never arrive.
  const watched = document.visibilityState === 'visible' && !matchMedia('(prefers-reduced-motion: reduce)').matches

  if (watched) {
    box.scrollTo({ behavior: 'smooth', top: target })
    await new Promise(resolve => setTimeout(resolve, 650))
  }

  // Land exactly, whether or not the animation finished.
  box.scrollTop = target

  const moved = Math.round(box.scrollTop - before)
  const result = {
    moved_by: moved,
    position: Math.round(box.scrollTop),
    content_height: box.scrollHeight,
    viewport_height: box.clientHeight,
    at_top: box.scrollTop <= 1,
    at_bottom: box.scrollTop + box.clientHeight >= box.scrollHeight - 2,
    container
  }

  if (moved === 0) {
    result.note =
      'Nothing moved: the page is already at that end, or it does not scroll in a way a script can drive. ' +
      'If content is still missing, call `show` and scroll it with computer_use.'
  }

  return result
}

async function hoverElement(ref) {
  const element = window.__hermesElements?.[ref]

  if (!element || !element.isConnected) {
    return { error: 'That ref is no longer on the page. Read the page again and use a fresh ref.' }
  }

  element.scrollIntoView({ block: 'center', inline: 'center' })

  const box = element.getBoundingClientRect()

  await window.__hermesPointTo?.(box.left + box.width / 2, box.top + box.height / 2)

  const ring = document.createElement('div')

  ring.className = '__hermes_ring'
  ring.style.cssText = `left:${box.left - 4}px;top:${box.top - 4}px;width:${box.width + 8}px;height:${box.height + 8}px`
  document.documentElement.append(ring)
  setTimeout(() => ring.remove(), 800)

  const point = { bubbles: true, cancelable: true, clientX: box.left + box.width / 2, clientY: box.top + box.height / 2, view: window }

  for (const type of ['pointerover', 'pointerenter', 'pointermove']) {
    element.dispatchEvent(new PointerEvent(type, point))
  }

  for (const type of ['mouseover', 'mouseenter', 'mousemove']) {
    element.dispatchEvent(new MouseEvent(type, point))
  }

  return { hovering: true }
}
