"""Test-only org.freedesktop.Notifications server on the isolated bus. It
records each Notify call and lets the test simulate clicks and dismissals."""
from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="org.freedesktop.Notifications">
    <method name="Notify">
      <arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>
      <arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/>
      <arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/>
    </method>
    <method name="CloseNotification"><arg type="u" direction="in"/></method>
    <method name="GetCapabilities"><arg type="as" direction="out"/></method>
    <method name="GetServerInformation">
      <arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/><arg type="s" direction="out"/>
    </method>
  </interface>
  <interface name="org.tarn.NotifyTest">
    <method name="Last"><arg type="v" direction="out"/></method>
    <method name="Invoke"><arg type="u" direction="in"/><arg type="s" direction="in"/></method>
    <method name="Dismiss"><arg type="u" direction="in"/></method>
  </interface>
</node>
"""
V = GLib.Variant
PATH = "/org/freedesktop/Notifications"
IFACE = "org.freedesktop.Notifications"
state = {"next": 1, "last": V("()", ())}


def emit(connection, member, signature, args):
    connection.emit_signal(None, PATH, IFACE, member, V(signature, args))


def call(connection, sender, path, interface, method, params, invocation):
    if method == "Notify":
        state["last"] = params
        replaces = params.unpack()[1]
        notification_id = replaces or state["next"]
        if not replaces:
            state["next"] += 1
        invocation.return_value(V("(u)", (notification_id,)))
    elif method == "CloseNotification":
        emit(connection, "NotificationClosed", "(uu)", (params.unpack()[0], 3))
        invocation.return_value(None)
    elif method == "GetCapabilities":
        invocation.return_value(V("(as)", (["actions", "body", "persistence"],)))
    elif method == "GetServerInformation":
        invocation.return_value(V("(ssss)", ("Fixture", "Tarn", "1.0", "1.2")))
    elif method == "Last":
        invocation.return_value(V("(v)", (state["last"],)))
    elif method == "Invoke":
        notification_id, key = params.unpack()
        emit(connection, "ActivationToken", "(us)", (notification_id, "token-123"))
        emit(connection, "ActionInvoked", "(us)", (notification_id, key))
        invocation.return_value(None)
    elif method == "Dismiss":
        emit(connection, "NotificationClosed", "(uu)", (params.unpack()[0], 2))
        invocation.return_value(None)


def acquired(connection, name):
    print("READY", flush=True)


bus = Gio.bus_get_sync(Gio.BusType.SESSION)
for info in Gio.DBusNodeInfo.new_for_xml(XML).interfaces:
    bus.register_object(PATH, info, call)
Gio.bus_own_name_on_connection(bus, IFACE, Gio.BusNameOwnerFlags.NONE, acquired, None)
GLib.MainLoop().run()
