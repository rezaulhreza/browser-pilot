# Contributing

Thank you for helping. Small, focused changes are the easiest to review and the quickest to merge.

## How the project is laid out

| Folder | What is in it |
|---|---|
| `extension/` | The Chrome extension. `worker.js` does the work, `options.*` is the settings page. |
| `bridge/` | `bridge.py`, the program that passes messages between an agent and the extension. |
| `scripts/` | Install and uninstall scripts, the script that draws the icons, and `package.sh`, which builds the zip for the Chrome Web Store. |
| `tests/` | Tests for the bridge. |
| `docs/` | Text for the Chrome Web Store listing. |

## Before you open a pull request

Run the checks.

```sh
python3 -m unittest discover -s tests -v
node --check extension/worker.js
node --check extension/options.js
```

Then try your change in a real browser. Load the `extension` folder on `chrome://extensions`, start the bridge with `python3 bridge/bridge.py`, and reload the extension after each edit.

## Ground rules

- **The agent keeps to its own tab group.** Do not add a tool that lists, reads or changes a tab outside the agent's group. This is the promise the project makes to the people who install it.
- **The bridge uses the Python standard library only.** No packages to install.
- **The extension has no build step and loads no code from the internet.** Plain JavaScript files only.
- **The bridge listens on this computer only.**
- **A change in behaviour comes with a test** where the bridge is concerned, and a line in `CHANGELOG.md`.
- **Write for someone who has never seen the code.** Plain words, British spelling.

## Reporting a bug

Open an issue and say what you did, what you expected and what happened. Include your Chrome version, your operating system and the agent you use.

Security problems go through a private report instead. See [SECURITY.md](SECURITY.md).
