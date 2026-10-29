"""Acts as the tray host against build/test-tray on an isolated bus: a fake
watcher receives the registration, then this script reads properties, opens
the menu, clicks entries and restarts the watcher."""
import subprocess
import sys
from pathlib import Path

from gi.repository import Gio, GLib

root = Path(__file__).resolve().parent.parent
V = GLib.Variant
ITEM, MENU = "org.kde.StatusNotifierItem", "com.canonical.dbusmenu"
failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
        print("FAIL", what)


def start_watcher():
    process = subprocess.Popen(["/usr/bin/python3", str(root / "tests/tray_watcher.py")], stdout=subprocess.PIPE, text=True)
    assert process.stdout.readline().strip() == "READY"
    return process


def stop(process):
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)
    process.stdout.close()


watcher = start_watcher()
tray = subprocess.Popen([str(root / "build/test-tray")], stdout=subprocess.PIPE, text=True)
try:
    ready = tray.stdout.readline().split()
    check(len(ready) == 3 and ready[0] == "READY" and ready[2] == "yes", f"tray registered at start: {ready}")
    service = ready[1]
    line = watcher.stdout.readline().split()
    check(line[:2] == ["REGISTERED", service], "watcher received the service name")
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    signals = []
    for interface in (ITEM, MENU, "org.freedesktop.DBus.Properties"):
        bus.signal_subscribe(service, interface, None, None, None, Gio.DBusSignalFlags.NONE,
                             lambda c, s, p, i, member, params: signals.append((member, params.unpack())))

    def call(path, interface, member, params=None):
        return bus.call_sync(service, path, interface, member, params, None, Gio.DBusCallFlags.NONE, 2000, None).unpack()

    def pump(count):
        context = GLib.MainContext.default()
        for _ in range(300):
            if len(signals) >= count:
                return
            context.iteration(False)
            GLib.usleep(5000)

    props = call("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "GetAll", V("(s)", (ITEM,)))[0]
    check(props["Id"] == "tarn-test" and props["Title"] == "Tarn Test" and props["Status"] == "Active", "basic properties")
    check(props["IconName"] == "applications-development" and props["Menu"] == "/MenuBar", "icon and menu path")
    check(props["ToolTip"] == ("applications-development", [], "Tarn Test", "") and props["ItemIsMenu"] is False, "tooltip")
    check(Gio.DBusNodeInfo.new_for_xml(call("/StatusNotifierItem", "org.freedesktop.DBus.Introspectable", "Introspect")[0])
          .lookup_interface(ITEM).lookup_method("Activate") is not None, "item introspection")

    menu_props = call("/MenuBar", "org.freedesktop.DBus.Properties", "GetAll", V("(s)", (MENU,)))[0]
    check(menu_props["Version"] == 3 and menu_props["Status"] == "normal", "menu properties")
    revision, layout = call("/MenuBar", MENU, "GetLayout", V("(iias)", (0, -1, [])))
    check(revision == 1 and layout[0] == 0 and layout[1] == {"children-display": "submenu"}, "layout root")
    children = layout[2]
    check([c[0] for c in children] == [1, 2, 3, 4, 6], "top-level ids in order")
    check(children[0][1] == {"label": "Mostrar", "icon-name": "window-new"}, "entry properties")
    check(children[1][1] == {"label": "Modo oscuro", "toggle-type": "checkmark", "toggle-state": 0}, "checkbox properties")
    check(children[2][1] == {"type": "separator"}, "separator properties")
    check(children[3][1].get("children-display") == "submenu" and [c[0] for c in children[3][2]] == [5], "submenu")
    shallow = call("/MenuBar", MENU, "GetLayout", V("(iias)", (0, 1, ["label"])))[1]
    check(shallow[2][3][2] == [] and shallow[2][0][1] == {"label": "Mostrar"}, "recursion depth and property filter")
    check(call("/MenuBar", MENU, "GetProperty", V("(is)", (6, "label")))[0] == "Salir", "GetProperty")
    group = call("/MenuBar", MENU, "GetGroupProperties", V("(aias)", ([1, 6, 99], ["label"])))[0]
    check(group == [(1, {"label": "Mostrar"}), (6, {"label": "Salir"})], "GetGroupProperties skips unknown ids")
    check(call("/MenuBar", MENU, "AboutToShow", V("(i)", (4,)))[0] is False, "AboutToShow")
    check(call("/MenuBar", MENU, "AboutToShowGroup", V("(ai)", ([4, 99],))) == ([], [99]), "AboutToShowGroup errors")

    # Clicks on the icon.
    call("/StatusNotifierItem", ITEM, "Activate", V("(ii)", (10, 20)))
    pump(1)
    check(("NewTitle", ()) in signals, "NewTitle after Activate")
    check(call("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "Get", V("(ss)", (ITEM, "Title")))[0] ==
          "Activado en 10,20", "Activate coordinates reach the app")
    signals.clear()
    call("/StatusNotifierItem", ITEM, "SecondaryActivate", V("(ii)", (0, 0)))
    pump(1)
    check(("NewStatus", ("NeedsAttention",)) in signals, "NewStatus")
    signals.clear()
    call("/StatusNotifierItem", ITEM, "Scroll", V("(is)", (3, "vertical")))
    pump(1)
    check(("NewToolTip", ()) in signals, "NewToolTip after Scroll")
    call("/StatusNotifierItem", ITEM, "ProvideXdgActivationToken", V("(s)", ("tok",)))

    # Menu: toggling only changes properties; adding an entry changes the layout.
    signals.clear()
    call("/MenuBar", MENU, "Event", V("(isvu)", (2, "clicked", V("i", 0), 0)))
    pump(1)
    updated = [s for s in signals if s[0] == "ItemsPropertiesUpdated"]
    check(updated and updated[0][1][0] == [(2, {"label": "Modo oscuro", "toggle-type": "checkmark", "toggle-state": 1})],
          "toggle sends ItemsPropertiesUpdated for that item only")
    check(not [s for s in signals if s[0] == "LayoutUpdated"], "toggle does not relayout")
    signals.clear()
    errors = call("/MenuBar", MENU, "EventGroup", V("(a(isvu))", ([(5, "clicked", V("i", 0), 0), (99, "clicked", V("i", 0), 0)],)))
    check(errors == ([99],), "EventGroup reports unknown ids")
    pump(1)
    check(("LayoutUpdated", (2, 0)) in signals, "new entry sends LayoutUpdated with the next revision")
    revision, layout = call("/MenuBar", MENU, "GetLayout", V("(iias)", (4, -1, [])))
    check(revision == 2 and [c[0] for c in layout[2]] == [5, 7], "relayout visible to the host")
    signals.clear()
    call("/MenuBar", MENU, "Event", V("(isvu)", (1, "clicked", V("i", 0), 0)))
    pump(1)
    pixmap = call("/StatusNotifierItem", "org.freedesktop.DBus.Properties", "Get", V("(ss)", (ITEM, "IconPixmap")))[0]
    check(pixmap == [(1, 1, [255, 10, 20, 30])] and ("NewIcon", ()) in signals, "RGBA converted to ARGB pixmap")

    # Watcher restart: the item registers again on its own.
    stop(watcher)
    check(tray.stdout.readline().strip() == "WATCHER-GONE", "tray notices the watcher leaving")
    watcher = start_watcher()
    line = watcher.stdout.readline().split()
    check(line[:2] == ["REGISTERED", service], "registered again with the new watcher")
    check(tray.stdout.readline().strip() == "REREGISTERED", "tray reports the new registration")

    call("/MenuBar", MENU, "Event", V("(isvu)", (6, "clicked", V("i", 0), 0)))
    check(tray.wait(timeout=5) == 0 and tray.stdout.read().strip() == "QUIT", "Quit entry ends the app")
    names = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "ListNames",
                          None, None, Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
    check(service not in names, "service name released on exit")
finally:
    if tray.poll() is None:
        tray.kill()
    tray.stdout.close()
    stop(watcher)
print(f"tray checks: {len(failures)} failures")
sys.exit(1 if failures else 0)
