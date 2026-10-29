# Browser Pilot

Browser Pilot gives your own AI agent a tab group to work in, inside the Chrome you already use. The agent can open tabs in that group, read the pages, and click, type and scroll in them. It cannot see or change any of your other tabs, so your own tabs stay private.

It works with any agent that supports MCP (Model Context Protocol, the common way AI agents connect to tools), such as [Hermes Agent](https://github.com/NousResearch/hermes-agent), Claude Code or Cursor. It is an independent open-source project and is not connected with any of them.

## What you get

- **Its own tab group.** The agent opens its tabs in a tab group of its own, and can keep several pages open and move between them. Links that try to open a new tab are pulled back into the tab they came from.
- **Your tabs stay private.** The agent has no way to list, read or touch a tab outside its group.
- **You can see what it is doing.** The agent's tabs have a coloured border, a label, and a pointer of its own that moves to whatever it clicks. Your mouse pointer is never moved.
- **It works in the background.** The agent's tabs open behind your current one and never take focus, unless the agent needs you to see something and says so.
- **It tidies up.** The agent's tabs are closed when the task is finished, or after ten minutes of no activity.
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

It copies the bridge to `~/.local/share/browser-pilot` and sets it to start when you log in. To remove it again, run `./scripts/uninstall.sh`.

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

Now ask your agent to look something up on a website. A tab group named Pilot appears, and the agent works inside it.

## Settings

Click the toolbar icon to open the settings page.

| Setting | What it does | Default |
|---|---|---|
| Bridge ports | The port the bridge listens on. Change it only if you started the bridge on another port. List several ports, with commas between them, when you run a bridge for each of several agents. | 8790 |
| Tab group name | The name shown on the agent's tab group and on its label. | Pilot |
| Colour | The colour of the tab group, the border and the agent's pointer. | Orange |
| Show border, label and pointer | Switch the markings on the agent's tabs on or off. | On |
| Sites the agent may never open | One site per line. A name also covers everything under it. | None |

The bridge has a few options of its own.

| Option | What it does | Default |
|---|---|---|
| `--port` | Port to listen on. | 8790 |
| `--idle-close-seconds` | Close the agent's tabs after this long without activity. Use 0 to leave them open. | 600 |
| `--extension-id` | Accept only this extension. Copy the ID from `chrome://extensions`. | Any |
| `BROWSER_PILOT_TOKEN` | Set this environment variable to make agents send a password with every request. | Not set |
| `--allow-host` | Also accept agent requests addressed to this host name. Repeat it for each name, or list the names in `BROWSER_PILOT_ALLOWED_HOSTS` with commas between them. Needs `BROWSER_PILOT_TOKEN`. | `127.0.0.1` and `localhost` only |

### Several agents at the same time

One bridge serves one agent and its tab group. To let two agents work at the same time, start a second bridge on another port and tell the extension about it:

```sh
python3 bridge/bridge.py --port 8791
```

Open the extension's settings and write both ports in **Bridge ports**, such as `8790, 8791`. Each agent now has a tab group of its own and cannot reach the other's tabs. Each bridge has its own options, so one can ask for a password while the other does not.

### Reaching the bridge from somewhere else

The bridge listens on this computer only, and that does not change. An agent that runs in a container, or on another machine behind a tunnel you set up, reaches the bridge by a different name, and the bridge refuses a name it was not told about. Name each one and set a password:

```sh
BROWSER_PILOT_TOKEN=choose-a-long-password python3 bridge/bridge.py \
  --allow-host host.docker.internal \
  --allow-host pilot.example.com
```

The bridge will not start with an allowed name and no password. Only the agent's address (`/mcp`) answers to an allowed name. The extension still connects on `127.0.0.1`.

## What the agent can do

| Tool | What it does |
|---|---|
| `tabs_context` | List the agent's tabs, with the id, title and address of each, and which one is current |
| `tabs_create` | Open a new tab in the agent's group and make it the current tab |
| `open` | Load a web address in the current tab, or open the first tab |
| `act` | Carry out several steps in one go, such as open a site, type a search and submit it, then hand back the page |
| `read` | Get the page text and a numbered list of the links, buttons and fields on screen |
| `click` | Click an item, by its number or by its visible text |
| `type` | Fill in a field, and optionally press Enter |
| `press_key` | Press a key such as Enter, Escape or Tab |
| `scroll` | Scroll the page, or its main panel on pages that scroll inside a frame |
| `hover` | Rest the pointer on an item to reveal a menu or a tooltip |
| `show` | Bring the current tab to the front and focus the Chrome window |
| `back` | Go back one page |
| `close` | Close one tab, or all of the agent's tabs |
| `status` | Report whether the extension is connected, what the current tab shows, and how many tabs are open |

Every tool that works in a tab takes an optional `tab_id`, from `tabs_context`. The named tab becomes the current tab. Without it, the tool works in the current tab.

Doing several steps in one go matters more than it sounds. An agent pauses to think between every tool it uses, so three steps in one call is roughly three times quicker than three calls.

## Privacy and safety

- Nothing leaves your computer except the pages the agent visits. The bridge listens on `127.0.0.1` only. There is no account, no analytics and no remote server. See [PRIVACY.md](PRIVACY.md).
- The agent works in your real Chrome, so it is signed in wherever you are. Give it tasks you would be happy to hand to an assistant sitting at your computer, and block the sites you would not.
- The extension refuses to type into password fields.
- A web page cannot give orders to the bridge. Requests that come from a page are refused.
- Text on a page can try to trick an agent into doing something you did not ask for. Use an agent that asks you before it buys, sends or deletes anything.

[SECURITY.md](SECURITY.md) explains what the project protects against, what it does not, and how to report a problem.

## Limits

- It reads text, not pictures. Anything drawn rather than written, such as a graph, a video or an embedded frame, is not visible to it. It tells the agent when a page has such parts.
- Clicks and typing are simulated inside the page. A small number of sites ignore simulated input.
- Pages that only load their content while you are looking at them can be slow in a background tab.
- Chrome does not allow extensions to run on its own pages, such as `chrome://settings`, or on the Chrome Web Store.
- Chrome puts a tab you open from one of the agent's tabs into the agent's group. The agent can then see that tab. Drag it out of the group to make it yours again.

## Develop

```sh
python3 -m unittest discover -s tests -v   # bridge tests
node --check extension/worker.js           # extension syntax
python3 scripts/make_icons.py              # redraw the icons
```

After changing the extension, reload it on `chrome://extensions`. [CONTRIBUTING.md](CONTRIBUTING.md) has the details.

## Licence

MIT. See [LICENSE](LICENSE).
