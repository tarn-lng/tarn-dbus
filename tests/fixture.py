"""Test-only service on the isolated session bus, implemented with GDBus."""
from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="org.tarn.DBusTest">
    <method name="Mixed"><arg type="s" direction="out"/><arg type="b" direction="out"/><arg type="i" direction="out"/>
      <arg type="u" direction="out"/><arg type="t" direction="out"/><arg type="as" direction="out"/></method>
    <method name="Empty"/>
    <method name="Huge"><arg type="as" direction="out"/></method>
    <method name="Nested"><arg type="(su)" direction="out"/><arg type="a{sv}" direction="out"/></method>
    <method name="Slow"/>
    <method name="Unsupported"><arg type="d" direction="out"/></method>
    <method name="Echo"><arg type="v" direction="in"/><arg type="v" direction="out"/></method>
    <method name="Burst"><arg type="u" direction="in"/></method>
    <method name="Fail"/>
  </interface>
</node>
"""
V = GLib.Variant


def call(connection, sender, path, interface, method, params, invocation):
    if method == "Mixed":
        invocation.return_value(V("(sbiutas)", ("Tarn", True, -42, 4294967295, 18446744073709551615, ["one", "two"])))
    elif method == "Empty":
        invocation.return_value(None)
    elif method == "Huge":
        invocation.return_value(V("(as)", (["bounded"] * 5000,)))
    elif method == "Nested":
        invocation.return_value(V("((su)a{sv})", (("nested", 7), {"active": V("b", True)})))
    elif method == "Slow":
        GLib.timeout_add(100, lambda: invocation.return_value(None) and False)
    elif method == "Unsupported":
        invocation.return_value(V("(d)", (3.5,)))
    elif method == "Echo":
        invocation.return_value(params)
    elif method == "Burst":
        # Signals addressed to the caller, then the reply: ordering test.
        count = params.unpack()[0]
        for index in range(count):
            connection.emit_signal(sender, "/Test", "org.tarn.DBusTest", "Tick", V("(u)", (index,)))
        invocation.return_value(None)
    elif method == "Fail":
        invocation.return_dbus_error("org.tarn.DBusTest.Error.Failed", "deliberate failure")


def acquired(connection, name):
    print("READY", flush=True)


bus = Gio.bus_get_sync(Gio.BusType.SESSION)
info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
bus.register_object("/Test", info, call)
Gio.bus_own_name_on_connection(bus, "org.tarn.DBusTest", Gio.BusNameOwnerFlags.NONE, acquired, None)
GLib.MainLoop().run()
