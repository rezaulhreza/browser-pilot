# Changelog

Notable changes to this project are recorded here. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

- The extension can connect to several bridges at once. List the ports on the settings page, such as `8790, 8791`. Each bridge is one agent with a working tab of its own, so two agents can work at the same time without sharing a tab or a password.
- `--allow-host` and `BROWSER_PILOT_ALLOWED_HOSTS` let the bridge answer agent requests addressed to other host names, for an agent in a container or behind a tunnel. Any number of names can be listed. The bridge refuses to start with an allowed name and no password.
- A maintenance route on the bridge, `POST /admin/extension-ports`, sets the extension's list of bridge ports from this computer, so a second bridge can be added without opening the settings page.

## 0.1.0

First release.

- The agent works in one tab, kept in its own tab group, and cannot reach any other tab.
- Tools for the agent to open, read, click, type, press a key, scroll, hover, show, go back, close and report status.
- A tool that carries out several steps in one call and hands back the resulting page, so the agent pauses to think less often.
- Elements can be named by their visible text as well as by number.
- Reading a page lists what is on screen by default and returns long text a part at a time.
- A border, a label and a pointer of its own mark the tab the agent is working in.
- The tab is closed after ten minutes without activity.
- A settings page for the bridge port, the tab group name and colour, the markings, and a list of sites the agent may never open.
- The bridge refuses requests from web pages and listens on this computer only.
- Optional password for agents, and an option to accept one named extension only.
- Install and uninstall scripts for macOS and Linux.
