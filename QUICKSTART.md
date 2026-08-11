# Quickstart

Run the catalog on your own computer so you can preview it and see your edits
live. This assumes you have unzipped the project and are in a terminal.

## Prerequisites

- Python 3.9 or newer. Check with `python3 --version`.

## One-time setup

Create a virtual environment (venv) and install the two dependencies. The venv
keeps these packages inside the project folder and avoids the
`externally-managed-environment` error on recent Ubuntu.

```bash
cd occ-biomech-datasets
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r scripts/requirements.txt
```

`pyyaml` reads the YAML files, `jsonschema` validates them against the schema.
You only do this once per machine.

## Build the catalog

```bash
python scripts/build_catalog.py
```

This validates every dataset and compiles it into the page. On success you see:

```
Validated 9 entries, no errors.
Built catalog: 9 datasets {'open': 6, 'restricted': 1, 'coming_soon': 2}
  -> site/catalog.json
  -> injected into site/index.html
```

If a YAML file is wrong, it prints `INVALID ...` with the file and field, then
stops. Fix the entry and build again.

## Preview in a browser

```bash
python -m http.server -d site 8000
```

Open http://localhost:8000 to see the site and try the filters. Stop the server
with Ctrl+C. (The catalog data is embedded in the page, so you can also open
`site/index.html` directly, but the server is closer to the deployed setup.)

If port 8000 is already taken — editors and other dev tools often hold it — pick
another, e.g. `python -m http.server -d site 8080`, and open that port instead.

## Previewing over SSH

If you edit on a remote machine over SSH, the server runs there but your browser
runs locally, so `http://localhost:8080` will not reach it on its own: `localhost`
means your own machine. You need to forward the port.

Bind the server to the loopback interface, so it is reachable through the tunnel
but not exposed to the rest of the network:

```bash
python -m http.server -d site -b 127.0.0.1 8080
```

Then forward it, whichever way you connect:

- **Plain SSH.** Connect with `ssh -L 8080:localhost:8080 user@host`. The left port
  is the one on your local machine, the right one is on the remote. Open
  http://localhost:8080 locally.
- **VS Code Remote-SSH.** Ports started in the *integrated terminal* are forwarded
  automatically, and VS Code offers to open them. A server started any other way
  (a background job, `tmux`, an agent) is not detected: open the **PORTS** panel,
  click **Forward a Port**, and enter the port number by hand.

A backgrounded server survives your SSH session ending. If a later start fails with
`Address already in use`, an old one is probably still holding the port — see the
troubleshooting table.

## The edit loop (what you will do most)

1. Edit a file in `datasets/` (add a dataset or change an existing one).
2. Rebuild: `python scripts/build_catalog.py`.
3. Refresh the browser.

Rebuild after every data change: the site reads the compiled output, not the
YAML directly. In a fresh terminal, re-activate the venv first with
`source .venv/bin/activate`. You do not need to reinstall.

## Troubleshooting

| Problem | Fix |
|---|---|
| `python: command not found` | Use `python3`. Inside the venv, `python` also works. |
| `externally-managed-environment` | You are not in the venv. Activate it, or append `--break-system-packages` to the pip command. |
| `Address already in use` | Something already holds the port — often another editor or dev server, or a previous preview server you left running. Find it with `ss -tlnp \| grep 8000` (Linux) and stop it, or just use a free port. |
| Page loads but looks unstyled | Make sure you opened the page over `http://localhost:<port>`, not as a `file://` path. Fonts load over the network and fall back to system fonts offline. |
| `ERR_CONNECTION_REFUSED` over SSH | The port is not forwarded to your local machine. See [Previewing over SSH](#previewing-over-ssh). |

## Windows notes

Running the project **locally on Windows**: use `python` instead of `python3`, and
activate the venv with `.venv\Scripts\activate`. Everything else is the same.

Editing on a **remote Linux machine from Windows** is a different setup — the
commands above run unchanged on the remote, and the only extra step is forwarding
the preview port. See [Previewing over SSH](#previewing-over-ssh).
