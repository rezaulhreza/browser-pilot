# Hermes in Chrome

Hermes in Chrome gives your own AI agent one tab to work in, inside the Chrome you already use. The agent can open pages, read them, click, type and scroll in that tab. It cannot see or change any of your other tabs, so you carry on with your own work while it gets on with its task.

It was written for [Hermes Agent](https://github.com/NousResearch/hermes-agent) and works with any agent that supports MCP (Model Context Protocol, the common way AI agents connect to tools), such as Claude Code or Cursor.

This is an unofficial community project. It is not made by, or connected with, Nous Research.

## What you get

- **One tab, in its own tab group.** Every page the agent visits loads in the same tab. Links that try to open a new tab are pulled back into it.
- **Your tabs stay private.** The agent has no way to list, read or touch any other tab.
- **You can see what it is doing.** The agent's tab has a coloured border, a label, and a pointer of its own that moves to whatever it clicks. Your mouse pointer is never moved.
- **It works in the background.** The tab opens behind your current one and never takes focus, unless the agent needs you to see something and says so.
- **It tidies up.** The tab is closed when the task is finished, or after ten minutes of no activity.
- **No debugging prompts.** Chrome does not ask you to approve a connection each time.
- **Sites you choose are off limits.** List the sites the agent must never open, such as your bank.

## What you need

- Google Chrome 116 or newer
- Python 3.9 or newer (already on macOS and most Linux systems)
- An agent that supports MCP

## Install

There are three parts. The extension lives in Chrome. The bridge is a small program on your computer that passes messages between your agent and the extension. Then you tell your agent where the bridge is.

### 1. Start the bridge

On macOS or Linux, run this from the folder you downloaded.

```sh
./scripts/install.sh
```

It copies the bridge to `~/.local/share/hermes-in-chrome` and sets it to start when you log in. To remove it again, run `./scripts/uninstall.sh`.

On Windows, or if you would rather start it yourself, run the bridge directly and leave it running.

```sh
python3 bridge/bridge.py
```

### 2. Add the extension to Chrome

1. Open `chrome://extensions`.
2. Switch on **Developer mode** in the top right corner.
3. Choose **Load unpacked** and pick the `extension` folder.

The toolbar icon shows a small `!` if the extension cannot reach the bridge. Click the icon to open the settings page, which tells you what is wrong.

### 3. Connect your agent

Point your agent at the bridge. The address is `http://127.0.0.1:8790/mcp`.

For Hermes Agent, add this to `~/.hermes/config.yaml`.

```yaml
mcp_servers:
  chrome:
    url: http://127.0.0.1:8790/mcp
    enabled: true
```

For Claude Code, run this once.

```sh
claude mcp add --transport http chrome http://127.0.0.1:8790/mcp
```

Other agents take the same address wherever they list their MCP servers.

Now ask your agent to look something up on a website. A tab group named Hermes appears, and the agent works inside it.

## Settings

Click the toolbar icon to open the settings page.

| Setting | What it does | Default |
|---|---|---|
| Bridge port | The port the bridge listens on. Change it only if you started the bridge on another port. | 8790 |
| Tab group name | The name shown on the agent's tab group and on its label. | Hermes |
| Colour | The colour of the tab group, the border and the agent's pointer. | Orange |
| Show border, label and pointer | Switch the markings on the agent's tab on or off. | On |
| Sites the agent may never open | One site per line. A name also covers everything under it. | None |

The bridge has a few options of its own.

| Option | What it does | Default |
|---|---|---|
| `--port` | Port to listen on. | 8790 |
| `--idle-close-seconds` | Close the agent's tab after this long without activity. Use 0 to leave it open. | 600 |
| `--extension-id` | Accept only this extension. Copy the ID from `chrome://extensions`. | Any |
| `HERMES_IN_CHROME_TOKEN` | Set this environment variable to make agents send a password with every request. | Not set |

## What the agent can do

| Tool | What it does |
|---|---|
| `open` | Load a web address in the agent's tab |
| `read` | Get the page text and a numbered list of links, buttons and fields |
| `click` | Click one of those numbered items |
| `type` | Fill in a field, and optionally press Enter |
| `press_key` | Press a key such as Enter, Escape or Tab |
| `scroll` | Scroll the page, or its main panel on pages that scroll inside a frame |
| `hover` | Rest the pointer on an item to reveal a menu or a tooltip |
| `show` | Bring the agent's tab to the front |
| `back` | Go back one page |
| `close` | Close the agent's tab |
| `status` | Report whether the extension is connected and what the tab shows |

## Privacy and safety

- Nothing leaves your computer except the pages the agent visits. The bridge listens on `127.0.0.1` only. There is no account, no analytics and no remote server. See [PRIVACY.md](PRIVACY.md).
- The agent works in your real Chrome, so it is signed in wherever you are. Give it tasks you would be happy to hand to an assistant sitting at your computer, and block the sites you would not.
- The extension refuses to type into password fields.
- A web page cannot give orders to the bridge. Requests that come from a page are refused.
- Text on a page can try to trick an agent into doing something you did not ask for. Use an agent that asks you before it buys, sends or deletes anything.

[SECURITY.md](SECURITY.md) explains what the project protects against, what it does not, and how to report a problem.

## Limits

- It reads text, not pictures. Numbers drawn inside a chart are not visible to it.
- Clicks and typing are simulated inside the page. A small number of sites ignore simulated input.
- Pages that only load their content while you are looking at them can be slow in a background tab.
- Chrome does not allow extensions to run on its own pages, such as `chrome://settings`, or on the Chrome Web Store.
- One agent tab at a time.

## Develop

```sh
python3 -m unittest discover -s tests -v   # bridge tests
node --check extension/worker.js           # extension syntax
python3 scripts/make_icons.py              # redraw the icons
```

After changing the extension, reload it on `chrome://extensions`. [CONTRIBUTING.md](CONTRIBUTING.md) has the details.

## Licence

MIT. See [LICENSE](LICENSE).
