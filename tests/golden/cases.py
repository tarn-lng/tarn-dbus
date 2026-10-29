"""Reference messages built with GDBus (GLib/Gio). Test-only: shared by the
golden generator and the verifier of messages encoded by Tarn."""
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

V = GLib.Variant
PIXELS = bytes(range(16))


def body(name):
    if name == "basic":
        return V("(ybnqiuxtdsog)", (200, True, -300, 65000, -70000, 4000000000, -5000000000000,
                                    9223372036854775813, 3.14159, "héllo ✓", "/org/x", "a{sv}"))
    if name == "notify":
        hints = {"urgency": V("y", 1), "x": V("i", 5), "desktop-entry": V("s", "tarn")}
        return V("(susssasa{sv}i)", ("app", 0, "icon", "Sum", "Body", ["a", "Act"], hints, -1))
    if name == "empty":
        return V("(asa{sv}aya(ii))", ([], {}, b"", []))
    if name == "pixmap":
        return V("(a(iiay))", ([(2, 2, PIXELS)],))
    if name == "nested":
        return V("(v)", (V("v", V("(sa{sv})", ("in", {"k": V("as", ["x", "y"])}))),))
    if name == "doubles":
        return V("(ddddd)", (0.0, -0.0, 1e-310, 1.7976931348623157e308, -1.5))
    if name == "unsigned":
        return V("(qut)", (65535, 4294967295, 18446744073709551615))
    if name in ("signal", "error", "reply"):
        return V("(s)", ("text",))
    raise KeyError(name)


# name -> (type, flags, serial, path, interface, member, error, reply serial, destination, big endian)
MESSAGES = {
    "basic": ("call", 0, 7, "/a", "org.x.I", "M", "", 0, "org.x.Y", False),
    "notify": ("call", 0, 8, "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify", "", 0,
               "org.freedesktop.Notifications", False),
    "notify_be": ("call", 0, 9, "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify", "", 0,
                  "org.freedesktop.Notifications", True),
    "empty": ("call", 1, 10, "/", "org.x.I", "Empty", "", 0, ":1.5", False),
    "pixmap": ("call", 0, 11, "/StatusNotifierItem", "org.x.I", "Icon", "", 0, "", False),
    "nested": ("call", 0, 12, "/n", "org.x.I", "Nested", "", 0, "", False),
    "doubles": ("call", 0, 13, "/d", "org.x.I", "D", "", 0, "", False),
    "unsigned": ("call", 0, 14, "/u", "org.x.I", "U", "", 0, "", False),
    "signal": ("signal", 0, 15, "/s", "org.x.I", "Changed", "", 0, "", False),
    "error": ("error", 0, 16, "", "", "", "org.x.Error.Failed", 3, ":1.9", False),
    "reply": ("reply", 0, 17, "", "", "", "", 4, ":1.9", False),
}


def body_name(name):
    return "notify" if name == "notify_be" else name


def build(name):
    kind, flags, serial, path, iface, member, error, reply, dest, big = MESSAGES[name]
    if kind == "call":
        m = Gio.DBusMessage.new_method_call(dest or None, path, iface, member)
    elif kind == "signal":
        m = Gio.DBusMessage.new_signal(path, iface, member)
    else:
        m = Gio.DBusMessage.new()
        m.set_message_type(Gio.DBusMessageType.ERROR if kind == "error" else Gio.DBusMessageType.METHOD_RETURN)
        m.set_reply_serial(reply)
        m.set_destination(dest)
        if error:
            m.set_error_name(error)
    m.set_flags(Gio.DBusMessageFlags(flags))
    m.set_serial(serial)
    m.set_body(body(body_name(name)))
    if big:
        m.set_byte_order(Gio.DBusMessageByteOrder.BIG_ENDIAN)
    return m
