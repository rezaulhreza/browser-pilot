# Changelog

Notable changes to this project are recorded here. Versions follow [Semantic Versioning](https://semver.org).

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
