# Privacy

Browser Pilot collects nothing. There is no account, no analytics, no advertising and no server run by this project.

## What the extension can see

The extension works in one tab, the one it opened for your agent. In that tab it reads the page text and the links, buttons and fields on the page, and passes them to your agent when the agent asks.

It does not read, list or change any other tab. It does not read your browsing history, bookmarks, saved passwords or cookies.

## Where the information goes

Page content from the agent's tab goes to the bridge, a program running on your own computer, at the address `127.0.0.1`. The bridge hands it to your AI agent. Nothing is sent anywhere else by this project.

What happens next depends on the agent you use. If your agent sends what it reads to an AI company to get an answer, that company's privacy terms apply to it. Check them before giving the agent pages that hold private information.

## What is stored

The extension stores your settings in Chrome on your computer. These are the bridge port, the tab group name and colour, whether the markings are shown, and your list of blocked sites. Nothing else is kept, and the settings are not synced or uploaded.

## Why the extension asks for its permissions

| Permission | Why it is needed |
|---|---|
| Read and change data on all websites | The agent may be asked to visit any site, so the extension must be able to read and act on the page in its own tab. It only ever does so in that one tab. |
| Tabs and tab groups | To open the agent's tab, keep it in its own group, and close it afterwards. |
| Scripting | To read the page and to click, type and scroll in the agent's tab. |
| Storage | To keep your settings. |
| Alarms | To reconnect to the bridge if the connection drops. |

## Changes

If this policy changes, the change will be recorded in [CHANGELOG.md](CHANGELOG.md).

## Questions

Open an issue on the project's GitHub page.
