#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Rightsee - Windows Context Menu Manager
---------------------------------------
Lists all right-click (context) menu entries found in the registry and lets
you disable / re-enable them from a simple cmd interface.

Supported entry types:
  * Static shell commands  (HKCR\...\shell\<name>)
  * Shell extension handlers (HKCR\...\shellex\ContextMenuHandlers\<name>)

Disabling methods (fully reversible):
  * Static items  -> set the standard "LegacyDisable" value.
  * Shellex items -> back up the default CLSID value, then clear it.

Modifying HKCR (which maps to HKLM\Software\Classes) requires administrator
rights, so the script will self-elevate when needed.
"""

import os
import sys
import ctypes
import winreg

# ---------------------------------------------------------------------------
# Registry locations
# ---------------------------------------------------------------------------

# (hive, subkey path, human-readable scope label)
STATIC_LOCATIONS = [
    (winreg.HKEY_CLASSES_ROOT, r"*\shell", "All Files"),
    (winreg.HKEY_CLASSES_ROOT, r"Directory\shell", "Folders"),
    (winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shell", "Folder / Desktop Background"),
    (winreg.HKEY_CLASSES_ROOT, r"Folder\shell", "Folder Class"),
    (winreg.HKEY_CLASSES_ROOT, r"AllFilesystemObjects\shell", "All Filesystem Objects"),
    (winreg.HKEY_CLASSES_ROOT, r"Drive\shell", "Drives"),
    (winreg.HKEY_CLASSES_ROOT, r"LibraryFolder\Background\shell", "Library Background"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\*\shell", "All Files (User)"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell", "Folders (User)"),
    (winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\Background\shell", "Folder Background (User)"),
]

SHELLEX_LOCATIONS = [
    (winreg.HKEY_CLASSES_ROOT, r"*\shellex\ContextMenuHandlers", "All Files"),
    (winreg.HKEY_CLASSES_ROOT, r"Directory\shellex\ContextMenuHandlers", "Folders"),
    (winreg.HKEY_CLASSES_ROOT, r"Directory\Background\shellex\ContextMenuHandlers", "Folder / Desktop Background"),
    (winreg.HKEY_CLASSES_ROOT, r"Folder\shellex\ContextMenuHandlers", "Folder Class"),
    (winreg.HKEY_CLASSES_ROOT, r"AllFilesystemObjects\shellex\ContextMenuHandlers", "All Filesystem Objects"),
    (winreg.HKEY_CLASSES_ROOT, r"Drive\shellex\ContextMenuHandlers", "Drives"),
]

# Value name used to back up the original CLSID of a disabled shellex handler.
BACKUP_VALUE = "_Rightsee_CLSID"

# Marker prepended to subkey names as an alternative disable method.
DISABLED_PREFIX = "_RightseeDisabled_"

# Filter out these default Windows entries (they are not user-visible menu
# items and toggling them can break the shell).
SYSTEM_SKIP_NAMES = {
    "open",
    "opennewwindow",
    "opennewprocess",
    "explore",
    "find",
    "print",
    "printto",
    "preview",
    "Properties",
    "RunAs",
    "runas",
    "OpenWithList",
    "OpenWithProgIds",
    "Command",
    "BackgroundDefault",
    "MultiSelectModel",
    "Default",
    "",  # empty default value
}

# ---------------------------------------------------------------------------
# Admin elevation
# ---------------------------------------------------------------------------

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_as_admin():
    params = " ".join('"%s"' % a for a in sys.argv)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    if rc <= 32:
        print("Failed to elevate to administrator privileges.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MenuItem:
    """Represents a single context-menu entry in the registry."""

    def __init__(self, hive, parent_path, sub_name, display_name,
                 kind, scope, enabled):
        self.hive = hive
        self.parent_path = parent_path      # e.g. r"*\shell"
        self.sub_name = sub_name            # subkey name
        self.display_name = display_name    # friendly text
        self.kind = kind                    # "static" | "shellex"
        self.scope = scope                  # scope label
        self.enabled = enabled              # bool

    @property
    def full_path(self):
        return self.parent_path + "\\" + self.sub_name

    def __repr__(self):
        flag = "[ON] " if self.enabled else "[OFF]"
        return "%s %-32s  (%s, %s)" % (flag, self.display_name[:32],
                                       self.kind, self.scope)


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

def _open(hive, path, access=winreg.KEY_READ):
    return winreg.OpenKey(hive, path, 0, access | winreg.KEY_WOW64_64KEY)


def _enum_subkeys(hive, path):
    try:
        key = _open(hive, path)
    except OSError:
        return
    try:
        index = 0
        while True:
            try:
                yield winreg.EnumKey(key, index)
                index += 1
            except OSError:
                break
    finally:
        winreg.CloseKey(key)


def _get_value(hive, path, name=None):
    try:
        with _open(hive, path) as key:
            return winreg.QueryValueEx(key, name)
    except OSError:
        return None, None


def _set_value(hive, path, name, value, type_=winreg.REG_SZ):
    with _open(hive, path, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, type_, value)


def _delete_value(hive, path, name):
    try:
        with _open(hive, path, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except OSError:
        pass


def _clsid_name(clsid):
    """Resolve a CLSID to its registered server name."""
    if not clsid:
        return ""
    try:
        with _open(winreg.HKEY_CLASSES_ROOT, "CLSID\\" + clsid) as key:
            name, _ = winreg.QueryValueEx(key, None)
            if name:
                return name
    except OSError:
        pass
    return clsid


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------

def _pretty_static_name(hive, parent_path, sub_name):
    sub_path = parent_path + "\\" + sub_name
    # Prefer MUIVerb, then the subkey default value, then the key name.
    for vname in ("MUIVerb", None):
        val, _ = _get_value(hive, sub_path, vname)
        if val:
            # strip @dll,-123 style references down to the name part
            return val
    # Last resort: title-case the key name.
    return sub_name.replace("_", " ").strip()


def enumerate_static():
    items = []
    for hive, path, scope in STATIC_LOCATIONS:
        for sub in _enum_subkeys(hive, path):
            if sub in SYSTEM_SKIP_NAMES:
                continue
            if sub.startswith(DISABLED_PREFIX):
                continue
            display = _pretty_static_name(hive, path, sub)
            enabled = not _static_is_disabled(hive, path, sub)
            items.append(MenuItem(hive, path, sub, display, "static", scope, enabled))
    return items


def enumerate_shellex():
    items = []
    for hive, path, scope in SHELLEX_LOCATIONS:
        for sub in _enum_subkeys(hive, path):
            if sub in SYSTEM_SKIP_NAMES:
                continue
            clsid, _ = _get_value(hive, path + "\\" + sub, None)
            display = _clsid_name(clsid) if clsid else sub
            enabled = not _shellex_is_disabled(hive, path, sub)
            items.append(MenuItem(hive, path, sub, display, "shellex", scope, enabled))
    return items


def enumerate_all():
    return enumerate_static() + enumerate_shellex()


# ---------------------------------------------------------------------------
# Disable / enable logic
# ---------------------------------------------------------------------------

def _static_is_disabled(hive, parent_path, sub_name):
    """A static item is disabled if it has a LegacyDisable value."""
    val, _ = _get_value(hive, parent_path + "\\" + sub_name, "LegacyDisable")
    return val is not None


def _static_disable(item):
    _set_value(item.hive, item.full_path, "LegacyDisable", "")


def _static_enable(item):
    _delete_value(item.hive, item.full_path, "LegacyDisable")


def _shellex_is_disabled(hive, parent_path, sub_name):
    """A shellex handler is disabled if its default CLSID value is empty
    and we have stashed the original CLSID in BACKUP_VALUE."""
    backup, _ = _get_value(hive, parent_path + "\\" + sub_name, BACKUP_VALUE)
    if backup is None:
        return False
    current, _ = _get_value(hive, parent_path + "\\" + sub_name, None)
    return (current or "") == ""


def _shellex_disable(item):
    path = item.full_path
    current, _ = _get_value(item.hive, path, None)
    if current:
        _set_value(item.hive, path, BACKUP_VALUE, current)
    # Clear the default value so the handler is no longer loaded.
    with _open(item.hive, path, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "")


def _shellex_enable(item):
    path = item.full_path
    backup, _ = _get_value(item.hive, path, BACKUP_VALUE)
    if backup is None:
        return  # nothing to restore
    with _open(item.hive, path, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, backup)
    _delete_value(item.hive, path, BACKUP_VALUE)


def toggle_item(item):
    if item.enabled:
        if item.kind == "static":
            _static_disable(item)
        else:
            _shellex_disable(item)
        item.enabled = False
        return "disabled"
    else:
        if item.kind == "static":
            _static_enable(item)
        else:
            _shellex_enable(item)
        item.enabled = True
        return "enabled"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

_BANNER_FONT = {
    "R": ["█████", "█   █", "█████", "█  █ ", "█   █"],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "G": ["█████", "█    ", "█  ██", "█   █", "█████"],
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "S": ["█████", "█    ", "█████", "    █", "█████"],
    "E": ["█████", "█    ", "█████", "█    ", "█████"],
}


def _render_banner(text, sep=" "):
    rows = ["", "", "", "", ""]
    for ch in text:
        glyph = _BANNER_FONT.get(ch.upper())
        if not glyph:
            continue
        for i in range(5):
            rows[i] += glyph[i] + sep
    if sep:
        rows = [r[: -len(sep)] for r in rows]
    return "\n".join(rows)


def _set_cmd_encoding():
    try:
        os.system("chcp 65001 > nul")
    except OSError:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def _print_menu(items, hide_enabled=False, hide_disabled=False):
    print()
    print("=" * 78)
    print(" #   STATE  TYPE     SCOPE                       ENTRY NAME")
    print("=" * 78)
    shown = 0
    for i, it in enumerate(items, start=1):
        if hide_enabled and it.enabled:
            continue
        if hide_disabled and not it.enabled:
            continue
        state = "ON " if it.enabled else "OFF"
        name = it.display_name or it.sub_name
        print(" %-3d %-4s  %-7s  %-26s %s" % (i, state, it.kind, it.scope[:26], name[:40]))
        shown += 1
    if shown == 0:
        print("  (no entries match the current filter)")
    print("=" * 78)
    print("  Total: %d shown / %d found" % (shown, len(items)))


def _parse_index(arg, items):
    """Return (zero_based_index, error_message). On success error_message is
    None; on failure index is None and error_message explains the problem."""
    try:
        idx = int(arg)
    except ValueError:
        return None, "Invalid number: %r" % arg
    if not 1 <= idx <= len(items):
        return None, "Number out of range: %d" % idx
    return idx - 1, None


def main():
    _set_cmd_encoding()

    if not is_admin():
        print("Administrator rights are required to modify context-menu entries.")
        print("Re-launching elevated...")
        relaunch_as_admin()
        return

    print("Running as Administrator. Scanning registry...\n")
    items = enumerate_all()
    filter_mode = "all"
    status = ""  # carries the result message of the previous command

    while True:
        # Clear the screen each cycle so only one fresh list + banner is
        # visible at a time (no scrolling pile-up).
        os.system("cls")
        if status:
            print(status)
            print("-" * 78)
            status = ""  # shown once, then cleared
        _print_menu(
            items,
            hide_enabled=(filter_mode == "disabled"),
            hide_disabled=(filter_mode == "enabled"),
        )
        # Big banner + tutorial, shown right above the input prompt so the
        # user always sees them without scrolling up.
        print()
        print(_render_banner("RIGHTSEE"))
        print("  Windows Context Menu Manager  (cmd edition)")
        print("-" * 78)
        print("  Quick tutorial:")
        print("    Type the NUMBER next to an entry to toggle it ON <-> OFF.")
        print("    Example: type '3' to enable/disable entry #3.")
        print("    Other: 'a'=all  'd'=disabled  'e'=enabled  'r'=refresh  '?'=help  'q'=quit")
        print("-" * 78)
        try:
            raw = input("Rightsee> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        if cmd in ("q", "quit", "exit"):
            print("Bye.")
            break
        elif cmd == "?":
            # Re-show the help block at the top of the next cycle.
            status = (
                "Commands:\n"
                "  <number>      Toggle (enable/disable) the entry at that number.\n"
                "  a             Show ALL entries (default).\n"
                "  d             Show only DISABLED entries.\n"
                "  e             Show only ENABLED entries.\n"
                "  r             Refresh the list from the registry.\n"
                "  on <n>        Force-enable entry n.\n"
                "  off <n>       Force-disable entry n.\n"
                "  ?             Show this help.\n"
                "  q             Quit."
            )
        elif cmd == "a" or cmd == "all":
            filter_mode = "all"
            status = "Filter: showing ALL entries."
        elif cmd == "d" or cmd == "disabled":
            filter_mode = "disabled"
            status = "Filter: showing only DISABLED entries."
        elif cmd == "e" or cmd == "enabled":
            filter_mode = "enabled"
            status = "Filter: showing only ENABLED entries."
        elif cmd == "r" or cmd == "refresh":
            items = enumerate_all()
            status = "Refreshed the list from the registry."
        elif cmd in ("on", "off") and len(parts) >= 2:
            i, err = _parse_index(parts[1], items)
            if err:
                status = err
            elif i is not None:
                it = items[i]
                want_on = (cmd == "on")
                if want_on and not it.enabled:
                    toggle_item(it)
                    status = "Enabled: %s" % (it.display_name or it.sub_name)
                elif (not want_on) and it.enabled:
                    toggle_item(it)
                    status = "Disabled: %s" % (it.display_name or it.sub_name)
                else:
                    status = "Already %s: %s" % ("enabled" if it.enabled else "disabled",
                                                 it.display_name or it.sub_name)
        elif cmd.isdigit():
            i, err = _parse_index(cmd, items)
            if err:
                status = err
            elif i is not None:
                it = items[i]
                result = toggle_item(it)
                status = "Toggled -> %s: %s" % (result, it.display_name or it.sub_name)
        else:
            status = "Unknown command. Type ? for help."


if __name__ == "__main__":
    main()
