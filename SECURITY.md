# Security

Browser Yolo Agent lets a program on your computer act in your real, signed-in browser. This page says plainly what guards that, and what does not.

## What the project protects against

**A web page giving orders to the bridge.** Browsers attach an `Origin` header to requests a page makes to another address. The bridge refuses any request that carries one, and refuses requests addressed to any name other than `127.0.0.1` or `localhost`. A page you visit therefore cannot open tabs or read pages through the bridge.

**A web page posing as the extension.** The bridge only accepts the extension connection from a Chrome extension. You can go further and name the one extension it should accept with `--extension-id`.

**Access from other computers.** The bridge listens on `127.0.0.1` only. It is not reachable from your network. The extension will only ever connect to `127.0.0.1`, whatever is saved in its settings.

**The agent reaching your other tabs.** The extension has no command that lists, reads or changes a tab other than the agent's own. A link that tries to open a new tab is pulled back into the agent's tab.

**Passwords.** The extension refuses to type into password fields and does not report their contents.

**Sites you have blocked.** The agent cannot open a blocked site. If a link or redirect leads its tab to one, the tab is cleared at once.

## What it does not protect against

**Other programs on your computer.** Any program running as you can talk to the bridge and so drive the agent's tab. A program that can do that could already do worse. If you share the computer, set `BROWSER_YOLO_AGENT_TOKEN` so that agents must send a password.

**Another Chrome extension you have installed.** Unless you set `--extension-id`, a different extension could connect to the bridge in place of this one and feed your agent false page content.

**Pages that try to trick the agent.** Text on a page can be written to look like an instruction. Whether the agent obeys it depends on the agent, not on this project. Use an agent that treats page content as information and asks you before it buys, sends, deletes or signs in.

**What the agent does on sites where you are signed in.** The agent's tab shares your logins. Block the sites you do not want it near.

## Reporting a problem

Please do not open a public issue for a security problem. Use the **Report a vulnerability** button under the Security tab of the GitHub repository, which sends a private report to the maintainer.

Say what you found, how to reproduce it, and which version you used. You should get a reply within a week.
