"""Test-only org.kde.StatusNotifierWatcher: records registrations."""
from gi.repository import Gio, GLib

XML = """
<node><interface name="org.kde.StatusNotifierWatcher">
  <method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
  <signal name="StatusNotifierItemRegistered"><arg type="s"/></signal>
</interface></node>
"""


def call(connection, sender, path, interface, method, params, invocation):
    service = params.unpack()[0]
    print("REGISTERED", service, sender, flush=True)
    connection.emit_signal(None, "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                           "StatusNotifierItemRegistered", GLib.Variant("(s)", (service,)))
    invocation.return_value(None)


bus = Gio.bus_get_sync(Gio.BusType.SESSION)
bus.register_object("/StatusNotifierWatcher", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0], call)
Gio.bus_own_name_on_connection(bus, "org.kde.StatusNotifierWatcher", Gio.BusNameOwnerFlags.NONE,
                               lambda *a: print("READY", flush=True), None)
GLib.MainLoop().run()
