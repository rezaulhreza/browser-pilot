# Chrome Web Store listing

Text to paste into the Chrome Web Store developer dashboard when the extension is published. It is kept here so the listing and the project say the same thing.

## Name

Browser Pilot

## Short description (132 characters at most)

Gives your own AI agent a tab group to work in, inside the Chrome you already use. Your other tabs stay private.

## Category

Workflow and planning

## Detailed description

Browser Pilot gives your own AI agent a tab group to work in, inside the Chrome you already use.

The agent can open tabs in that group, read the pages, and click, type and scroll in them. It cannot see or change any of your other tabs, so your own tabs stay private.

What you get

Its own tab group. The agent keeps its tabs in a tab group of its own and moves between them.
Your tabs stay private. The agent has no way to list, read or touch a tab outside its group.
You can see what it is doing. The agent's tabs have a coloured border, a label and a pointer of its own. Your mouse pointer is never moved.
You see it start. Chrome switches to the agent's tab when it starts work. A setting lets it work in the background instead.
It tidies up. The agent's tabs are closed when the task is finished.
Sites you choose are off limits. List the sites the agent must never open.

What you need

This extension is one half of the tool. The other half is a small free program, the bridge, that runs on your own computer and passes messages between your agent and the extension. Setup takes a few minutes and is explained on the project page.

You also need an AI agent that supports MCP, such as Hermes Agent or Claude Code. This extension does not include an AI.

Privacy

Nothing is collected. There is no account, no analytics and no server run by this project. Page content from the agent's tabs goes only to the bridge on your own computer.

This is an independent open-source project, released under the MIT licence. It is not connected with the makers of any AI agent.

## Single purpose

Lets an AI agent running on the user's own computer browse the web in its own dedicated tab group.

## Permission justifications

Host permission for all sites. The user's agent may be asked to visit any website, so the extension must be able to read and act on the pages in the agent's tabs. It only does so in the tabs of the agent's own tab group.

tabs and tabGroups. To open the agent's tabs, keep them in their own tab group, list them for the agent, and close them when the task is finished.

scripting. To read the page text and to click, type and scroll in the agent's tabs.

storage. To keep the user's settings on their own computer.

alarms. To reconnect to the bridge on the user's computer if the connection drops.

## Data use

The extension does not collect or transmit user data to the developer or to any third party. Website content from the agent's tabs is passed to a program on the user's own computer at 127.0.0.1 and nowhere else.

Remote code. None. All code is in the package.

## Still to prepare before publishing

- At least one screenshot at 1280 by 800 showing the agent's tabs with their border and tab group
- A privacy policy web address (the PRIVACY.md page on GitHub works once the repository is public)
- A developer account on the Chrome Web Store
