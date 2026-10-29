"""Drives build/test-router (a Tarn server) with GDBus and the gdbus/busctl
command-line tools on the isolated bus."""
import subprocess
import sys
from pathlib import Path

from gi.repository import Gio, GLib

root = Path(__file__).resolve().parent.parent
NAME, PATH, IFACE = "org.tarn.Server", "/org/tarn/Calc", "org.tarn.Calc"
V = GLib.Variant
failures = []


def check(ok, what):
    if not ok:
        failures.append(what)
        print("FAIL", what)


def call(path, iface, member, params=None, flags=Gio.DBusCallFlags.NONE):
    return bus.call_sync(NAME, path, iface, member, params, None, flags, 2000, None)


def error_of(path, iface, member, params=None):
    try:
        call(path, iface, member, params)
    except GLib.Error as failure:
        return Gio.DBusError.get_remote_error(failure)
    return None


server = subprocess.Popen([str(root / "build/test-router")], stdout=subprocess.PIPE, text=True)
try:
    assert server.stdout.readline().strip() == "READY"
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    done = []
    bus.signal_subscribe(NAME, IFACE, "Done", PATH, None, Gio.DBusSignalFlags.NONE,
                         lambda *args: done.append(args[5].unpack()[0]))

    check(call(PATH, IFACE, "Add", V("(ii)", (40, 2))).unpack() == (42,), "Add returns 42")
    nested = V("(v)", (V("a{sv}", {"k": V("(sx)", ("ñ", -1))}),))
    check(call(PATH, IFACE, "Echo", nested).unpack() == nested.unpack(), "Echo round-trips a nested variant")
    check(call("/org/tarn/Calc/child", "org.tarn.Child", "Hello").unpack() == ("hola",), "child object")
    bare = Gio.DBusMessage.new_method_call(NAME, PATH, None, "Add")
    bare.set_body(V("(ii)", (1, 1)))
    answer, _ = bus.send_message_with_reply_sync(bare, Gio.DBusSendMessageFlags.NONE, 2000, None)
    check(answer.get_body().unpack() == (2,), "call without interface")
    check(error_of(PATH, IFACE, "Fail") == "org.tarn.Calc.Error.Nope", "application error name")
    check(error_of(PATH, IFACE, "Add", V("(s)", ("x",))) == "org.freedesktop.DBus.Error.InvalidArgs", "InvalidArgs")
    check(error_of(PATH, IFACE, "Missing") == "org.freedesktop.DBus.Error.UnknownMethod", "UnknownMethod")
    check(error_of(PATH, "org.tarn.Missing", "Add") == "org.freedesktop.DBus.Error.UnknownInterface", "UnknownInterface")
    check(error_of("/nowhere", IFACE, "Add") == "org.freedesktop.DBus.Error.UnknownObject", "UnknownObject")
    check(error_of("/org/tarn/Calc/child", "org.freedesktop.DBus.Properties", "GetAll", V("(s)", ("org.tarn.Child",))) ==
          "org.freedesktop.DBus.Error.UnknownInterface", "Properties not offered without properties")
    check(call(PATH, "org.freedesktop.DBus.Peer", "Ping").unpack() == (), "Peer.Ping")
    machine = call("/anything", "org.freedesktop.DBus.Peer", "GetMachineId").unpack()[0]
    check(machine == Path("/etc/machine-id").read_text().strip(), "Peer.GetMachineId")
    check(error_of(PATH, "org.freedesktop.DBus.Peer", "Nope") == "org.freedesktop.DBus.Error.UnknownMethod", "Peer unknown")
    call(PATH, IFACE, "Twice")

    # Properties.
    changes = []
    bus.signal_subscribe(NAME, "org.freedesktop.DBus.Properties", "PropertiesChanged", PATH, None,
                         Gio.DBusSignalFlags.NONE, lambda *args: changes.append(args[5].unpack()))
    props = "org.freedesktop.DBus.Properties"

    def get(name):
        return call(PATH, props, "Get", V("(ss)", (IFACE, name))).unpack()[0]

    def wait_changes(count):
        context = GLib.MainContext.default()
        for _ in range(200):
            if len(changes) >= count:
                return
            context.iteration(False)
            GLib.usleep(5000)

    check(get("Title") == "Inicial" and get("Count") == 0, "initial values")
    every = call(PATH, props, "GetAll", V("(s)", (IFACE,))).unpack()[0]
    check(set(every) == {"Title", "Count", "Icon"}, "GetAll omits write-only properties")
    check(call(PATH, props, "GetAll", V("(s)", ("",))).unpack()[0].keys() == every.keys(), "GetAll with empty interface")
    check(error_of(PATH, props, "Get", V("(ss)", (IFACE, "Secret"))) == "org.freedesktop.DBus.Error.AccessDenied", "write-only Get")
    check(error_of(PATH, props, "Get", V("(ss)", (IFACE, "Nope"))) == "org.freedesktop.DBus.Error.UnknownProperty", "UnknownProperty")
    check(error_of(PATH, props, "Get", V("(ss)", ("org.x.No", "Title"))) == "org.freedesktop.DBus.Error.UnknownInterface", "Get unknown interface")
    check(error_of(PATH, props, "Get", V("(s)", (IFACE,))) == "org.freedesktop.DBus.Error.InvalidArgs", "Get wrong arguments")
    check(error_of(PATH, props, "Set", V("(ssv)", (IFACE, "Count", V("u", 5)))) ==
          "org.freedesktop.DBus.Error.PropertyReadOnly", "read-only Set")
    check(error_of(PATH, props, "Set", V("(ssv)", (IFACE, "Title", V("u", 5)))) ==
          "org.freedesktop.DBus.Error.InvalidArgs", "Set with the wrong type")
    check(error_of(PATH, props, "Set", V("(ssv)", (IFACE, "Title", V("s", "rechazar")))) ==
          "org.tarn.Calc.Error.Rejected", "application refuses a Set")
    call(PATH, props, "Set", V("(ssv)", (IFACE, "Secret", V("s", "x"))))
    call(PATH, props, "Set", V("(ssv)", (IFACE, "Title", V("s", "Nuevo"))))
    wait_changes(1)
    check(get("Title") == "Nuevo" and changes[:1] == [(IFACE, {"Title": "Nuevo"}, [])], "Set updates and announces")
    call(PATH, IFACE, "Bump")
    wait_changes(2)
    check(changes[1:2] == [(IFACE, {"Count": 1, "Title": "Cambiado"}, [])], "two changes batched into one signal")
    call(PATH, IFACE, "Repaint")
    wait_changes(3)
    check(changes[2:3] == [(IFACE, {}, ["Icon"])], "invalidated property sends only its name")
    check(bytes(get("Icon")) == b"\xff", "invalidated value still readable with Get")
    tool = subprocess.run(["busctl", "--user", "get-property", NAME, PATH, IFACE, "Title"], capture_output=True, text=True, timeout=10)
    check(tool.stdout.strip() == 's "Cambiado"', "busctl get-property")
    tool = subprocess.run(["busctl", "--user", "set-property", NAME, PATH, IFACE, "Title", "s", "Desde busctl"],
                          capture_output=True, text=True, timeout=10)
    check(tool.returncode == 0 and get("Title") == "Desde busctl", "busctl set-property")
    check(Gio.DBusNodeInfo.new_for_xml(call(PATH, "org.freedesktop.DBus.Introspectable", "Introspect").unpack()[0])
          .lookup_interface(IFACE).lookup_property("Count").flags == Gio.DBusPropertyInfoFlags.READABLE, "introspected property access")

    xml = call(PATH, "org.freedesktop.DBus.Introspectable", "Introspect").unpack()[0]
    node = Gio.DBusNodeInfo.new_for_xml(xml)
    calc = node.lookup_interface(IFACE)
    check(calc is not None and calc.lookup_method("Add").in_args[1].signature == "i", "introspection parses with GDBus")
    check(calc.lookup_signal("Done") is not None, "introspected signal")
    check([n.path for n in node.nodes] == ["child"], "introspected child node")
    root_xml = call("/", "org.freedesktop.DBus.Introspectable", "Introspect").unpack()[0]
    check([n.path for n in Gio.DBusNodeInfo.new_for_xml(root_xml).nodes] == ["org"], "root lists the first path element")
    check(error_of("/nowhere", "org.freedesktop.DBus.Introspectable", "Introspect") ==
          "org.freedesktop.DBus.Error.UnknownObject", "introspect unknown path")

    tool = subprocess.run(["gdbus", "introspect", "--session", "--dest", NAME, "--object-path", PATH],
                          capture_output=True, text=True, timeout=10)
    check(tool.returncode == 0 and "Add(in  i a," in tool.stdout, "gdbus introspect")
    tool = subprocess.run(["busctl", "--user", "call", NAME, PATH, IFACE, "Add", "ii", "5", "6"],
                          capture_output=True, text=True, timeout=10)
    check(tool.returncode == 0 and tool.stdout.strip() == "i 11", "busctl call")
    tool = subprocess.run(["busctl", "--user", "introspect", NAME, PATH], capture_output=True, text=True, timeout=10)
    check(tool.returncode == 0 and ".Echo" in tool.stdout, "busctl introspect")

    # No reply expected: the server must not answer, and the next call still works.
    silent = Gio.DBusMessage.new_method_call(NAME, PATH, IFACE, "Add")
    silent.set_body(V("(ii)", (1, 2)))
    silent.set_flags(Gio.DBusMessageFlags.NO_REPLY_EXPECTED)
    bus.send_message(silent, Gio.DBusSendMessageFlags.NONE)
    check(call(PATH, IFACE, "Add", V("(ii)", (2, 2))).unpack() == (4,), "server continues after a no-reply call")
    call(PATH, IFACE, "Quit")
    context = GLib.MainContext.default()
    for _ in range(100):
        if done:
            break
        context.iteration(False)
        GLib.usleep(10000)
    check(done == ["quit"], "Done signal after Quit")
    check(server.wait(timeout=5) == 0 and server.stdout.read().strip() == "SERVED", "server exits cleanly")
finally:
    if server.poll() is None:
        server.kill()
    server.stdout.close()
print(f"router checks: {len(failures)} failures")
sys.exit(1 if failures else 0)
