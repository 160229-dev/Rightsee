<div align="center">

# ████ RIGHTSEE ████
### Tame your chaotic Windows right-click menu — one toggle at a time.

[![Windows](https://img.shields.io/badge/platform-Windows-0078D4?logo=windows11)](#)
[![Python](https://img.shields.io/badge/python-3.8+-3776AB?logo=python&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![No Install](https://img.shields.io/badge/standalone-.exe-orange)](#quick-start)
[![Reversible](https://img.shields.io/badge/operations-100%25%20reversible-brightgreen)](#how-it-works)

</div>

---

> **Ever right-clicked a file and been greeted by a wall of 40 menu items you never asked for?**
> 7-Zip, Git, three antiviruses, "Open with IDE you uninstalled last year", that sketchy tool you tried once in 2022...
> **Rightsee** puts you back in charge. One tiny terminal app. Every entry listed. One keystroke to hide, one to bring back. Nothing is ever deleted.

---

##  Highlights

- **🎯 See everything at a glance** — Every static command *and* shell-extension handler, across All Files / Folders / Desktop Background / Drives, with ON/OFF state, scope, and type. No more hunting through `regedit`.
- **One-keystroke toggle** — Type a number, hit Enter. Done. The entry disappears from your menu (or comes back). No reboot, no logging out.
- **100% reversible, nothing is deleted** — Rightsee uses Windows' native `LegacyDisable` flag for static items and backs up CLSIDs for shell extensions. Every action can be undone — even months later.
- **Auto-elevates itself** — The `.exe` has `requireAdministrator` baked into its manifest. Just double-click; it handles the UAC prompt.
- **🖥️ Gorgeous terminal UI** — A block-character `RIGHTSEE` banner, a clean numbered table, and a tutorial pinned above the prompt. Clear the screen each cycle — never a scrolling mess.
- **🪶 Zero dependencies, zero install** — Pure standard-library Python. Ships as a single 9 MB `.exe`. No Python needed on the target machine.
- **🧠 Smart filtering** — Skips critical system entries (`open`, `Properties`, `explore`...) so you can't accidentally break the shell. Shows All / Disabled-only / Enabled-only views.
- **🔍 Real names, not GUIDs** — Resolves each shell-extension CLSID to its registered server name, so you see "7-Zip" instead of `{23170F69-40C1-278A-1000-...}`.

---

## 🚀 Quick Start

### Option A — Grab the `.exe` (recommended)

1. Download **`Rightsee.exe`** from the [latest release](../../releases).
2. Double-click it. Approve the UAC prompt.
3. That's it. You're in.

### Option B — Run from source

```bash
git clone https://github.com/160229-dev/Rightsee.git
cd Rightsee
python Rightsee.py
```
*(Python 3.8+ on Windows. Admin rights will be requested automatically.)*

---

## 0-Second Tutorial

Once Rightsee opens, you'll see a numbered table of every context-menu entry on your system:

```
==============================================================================
 #   STATE  TYPE     SCOPE                       ENTRY NAME
==============================================================================
 1   ON    static   All Files                  Open with
 2   ON    shellex  All Files                  7-Zip
 3   ON    shellex  All Files                  Git GUI Here
 4   OFF   static   Folders                    Edit with Notepad++
 5   ON    shellex  Folder / Desktop Background  Open PowerShell
==============================================================================
  Total: 5 shown / 5 found

█████ ███ █████ █   █ █████ █████ █████ █████
█   █  █  █     █   █   █   █     █     █
█████  █  █  ██ █████   █   █████ █████ █████
█  █   █  █   █ █   █   █       █ █     █
█   █ ███ █████ █   █   █   █████ █████ █████
  Windows Context Menu Manager  (cmd edition)
------------------------------------------------------------------------------
  Quick tutorial:
    Type the NUMBER next to an entry to toggle it ON <-> OFF.
    Example: type '3' to enable/disable entry #3.
    Other: 'a'=all  'd'=disabled  'e'=enabled  'r'=refresh  '?'=help  'q'=quit
------------------------------------------------------------------------------
Rightsee>
```

| You type | What happens |
|---|---|
| `2` | Toggles entry #2 (7-Zip) — hides it from the menu, or brings it back |
| `on 4` | Force-enables entry #4 (even if already on) |
| `off 5` | Force-disables entry #5 |
| `d` | Shows only your currently **disabled** entries |
| `e` | Shows only your currently **enabled** entries |
| `a` | Shows **all** entries again |
| `r` | Re-scans the registry (handy after installing/uninstalling software) |
| `?` | Full command help |
| `q` | Quit |

> 💡 **Tip:** After toggling, right-click any file to see the change live. Some apps cache their handlers — if a change doesn't show immediately, restart Explorer via Task Manager.

---

## 🧩 How It Works

Windows stores your right-click menu in two places in the registry:

| Type | Location | What Rightsee does to disable |
|---|---|---|
| **Static commands** | `HKCR\*\shell\<name>` etc. | Sets the standard Windows `LegacyDisable` value — the official "hide this entry" flag |
| **Shell extensions** (COM handlers) | `HKCR\*\shellex\ContextMenuHandlers\<name>` | Backs up the CLSID to `_Rightsee_CLSID`, then clears the default value so Windows stops loading the handler |

Both methods are **fully reversible** — Rightsee never deletes a registry key, only flips flags and stashes backups. Re-enabling simply removes the flag / restores the CLSID.

### Scopes scanned

- `*\shell` & `*\shellex` — All files
- `Directory\shell` & `Directory\shellex` — Folders
- `Directory\Background\shell` & `\shellex` — Folder / Desktop background
- `Folder\shell` & `Folder\shellex` — Folder class
- `AllFilesystemObjects\shell` & `\shellex` — All filesystem objects
- `Drive\shell` & `Drive\shellex` — Drives
- `LibraryFolder\Background\shell` — Library backgrounds
- Plus all the `HKCU\Software\Classes\...` user-level equivalents

---

## 🔨 Build Your Own `.exe`

Want to rebuild from source? It's one command (PyInstaller required):

```bash
python -m PyInstaller --onefile --console --uac-admin --name Rightsee --clean --noconfirm Rightsee.py
```

The `--uac-admin` flag is what bakes the auto-elevation manifest into the executable. Output lands in `dist\Rightsee.exe`.

---

## ❓ FAQ

**Is it safe?**  
Yes. Rightsee only flips reversible flags and stashes backups — it never deletes registry keys. Critical system entries (`open`, `Properties`, `explore`, etc.) are skipped so you can't break the shell. Worst case, re-run Rightsee and toggle things back.

**Do I need Python installed?**  
No. The release `.exe` is fully self-contained. You only need Python if you run the `.py` directly or rebuild.

**Why does it ask for admin rights?**  
Context-menu entries live under `HKEY_CLASSES_ROOT`, which maps to `HKEY_LOCAL_MACHINE\Software\Classes` — that hive requires administrator access to modify. The `.exe` auto-elevates so you don't have to remember.

**A toggle didn't take effect.**  
Most changes are instant, but some apps cache their shell handlers. Open Task Manager → restart **Windows Explorer**, or simply reboot.

**Will it work on Windows 11?**  
Yes — fully tested on Windows 10 and 11. The registry layout Rightsee reads has been stable since Windows 7.

---

## ⚠️ Disclaimer

Modifying the registry always carries some risk. While Rightsee is designed to be non-destructive and reversible, **please create a System Restore point** before your first session (Windows + R → `sysdm.cpl` → System Protection → Create). The author takes no responsibility for any menu mishaps.

---

## 🤝 Contributing

Found a menu entry Rightsee doesn't catch? Want a dark-mode banner? PRs welcome!

1. Fork it
2. Create your feature branch (`git checkout -b feature/cool-thing`)
3. Commit your changes
4. Open a pull request

---

## 📄 License

MIT © feel free to use, fork, and share.

---

<div align="center">

**Tired of a cluttered right-click menu? Give Rightsee a ⭐ and take back control.**

</div>
