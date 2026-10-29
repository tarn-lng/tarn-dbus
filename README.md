# tarn-dbus

An independent, pure Tarn library for the Linux session D-Bus. It speaks the
D-Bus wire protocol over a Unix stream socket: no libdbus, no C, no FFI and no
`unsafe`. It is **not part of Tarn's standard library**.

Version 0.2 (in progress, see [the plan](docs/plan.md)) has a native
connection with typed values, blocking and non-blocking calls and typed
signals. The 0.1 API in `src/dbus` remains as a compatibility layer.

```sh
TARN=/path/to/tarn ./test.sh
./build/list-names
```

## Native connection (`src/connection`)

```tarn
import "src/connection"
import "src/message"
import "src/value"
fn work(bus &mut connection.Connection) Result<void, error.Error> {
    var body: Vec<value.Value> = Vec.new()
    body.push(value.text(&"org.freedesktop.DBus"))
    reply := try bus.call(message.call(&"org.freedesktop.DBus", &"/org/freedesktop/DBus",
        &"org.freedesktop.DBus", &"GetNameOwner", body), 1000)
    return Ok(())
}
```

- `with_session(work)` resolves `DBUS_SESSION_BUS_ADDRESS` (first
  `unix:path=` entry, `%XX` escapes) or `$XDG_RUNTIME_DIR/bus`, authenticates
  with SASL `EXTERNAL` (uid from `/proc/self/status`, 5 s bound), sends
  `Hello`, and closes on every ordinary result, including `Err`. Abstract
  sockets and other transports return `tarn.dbus.UnsupportedAddress`.
- `send(message) -> serial` queues and writes what the socket accepts;
  `flush(timeout)` finishes writing.
- `call(message, timeout)` blocks for the reply; messages arriving meanwhile
  stay queued in order. Remote errors keep their name and text.
- `send_call(message, timeout) -> serial` does not block. The reply arrives
  through `dispatch` or `receive` with that `reply_serial`; after the timeout,
  a local `org.freedesktop.DBus.Error.NoReply` arrives instead and a late
  real reply is dropped.
- `dispatch(max)` never blocks; `receive(timeout)` waits at most 60 s for one
  message. Waits use `poll`, so an idle connection uses no CPU.
- `signal(path, interface, member, body, destination)` emits typed broadcast
  or unicast signals.
- `request_name`, `release_name`, `add_match`, `remove_match`, `list_names`,
  `name_owner`, `unique_name`.
- `raw_fd()` lends the socket descriptor to a foreign event loop (GLib).
- Bounds: 4096 queued incoming messages (reading pauses), 16 MiB queued
  output, timeouts up to 60000 ms. A reply whose body breaks a limit fails
  only its own call; a malformed header ends the connection.

## Publishing objects (`src/router`)

The application describes its interfaces, routes each received message and
answers the calls it gets back. No callbacks cross into the library.

```tarn
var routes = router.Router.new()
try routes.register(&"/org/example/App", router.describe(&"org.example.App")
    .method(&"Add", inputs, outputs)
    .signal(&"Done", args))
for {
    match try bus.receive(1000) {
        Some(incoming) => {
            match try routes.route(bus, incoming) {
                router.Routed.Call(call) => { var current = call
                    try current.reply(bus, body) }
                router.Routed.Handled => {}
                router.Routed.Other(signal) => {}
            }
        }
        None => {}
    }
}
```

- `route` checks the call's signature against the description before the app
  sees it, and answers `UnknownObject`, `UnknownInterface`, `UnknownMethod`
  and `InvalidArgs` itself.
- Built in: `org.freedesktop.DBus.Peer` (`Ping`, `GetMachineId`) on every path,
  and `Introspectable.Introspect` with generated XML, including child nodes.
- Properties: declare them with `.property(name, signature, access)` and give
  values with `set_property` (checked against the signature; returns whether
  it changed). The router answers `Get` and `GetAll` (write-only properties
  are omitted) with the standard errors. `Set` is checked (read-only, type)
  and then returned to the app as a Call, which may refuse it or accept it
  with `set_property`. `emit_changed` sends one batched `PropertiesChanged`
  per object and interface; `invalidate` announces a name without its value.
  The first value of a property is not announced.
- `Call.reply` and `Call.fail` answer exactly once; `Connection.reply` and
  `reply_error` send nothing when the caller set `NO_REPLY_EXPECTED`.
- Calls without an interface match the first registered method of that name.
- An unknown path is `UnknownObject` (GDBus reports `UnknownMethod` there; the
  specification's name is used).

## Desktop notifications (`desktop/notifications`)

Binding of org.freedesktop.Notifications 1.2, with no application policy.

```tarn
item := notifications.Notification.new(&"My app", &"Done")
    .with_body(&"The export finished.")
    .with_action(&"default", &"Open")
    .with_urgency(notifications.Urgency.Normal)
try notifications.subscribe(bus)
id := try notifications.notify(bus, &item, 2000)
// later, for each received message:
match notifications.event(&message) { Some(notifications.Event.ActionInvoked(found)) => { ... } _ => {} }
```

- `notify` returns the id; `replacing(id)` updates an existing notification.
- Hints: `with_urgency`, `with_category`, `with_desktop_entry`,
  `with_image_path`, `transient`, `resident`, or any `hint(key, value)`.
- `close`, `capabilities`, `server_information`, `subscribe`.
- `event` reads `ActionInvoked`, `ActivationToken` and `NotificationClosed`
  (with `Expired`, `Dismissed`, `Closed` or `Undefined`).

`notify_demo.tarn` is the manual check on the real desktop: it shows a
notification, replaces it with one that has buttons and prints what you do.

## Tray icon and menu (`desktop/status_notifier`, `desktop/dbusmenu`)

StatusNotifierItem with a com.canonical.dbusmenu menu, as shown by Plasma's
system tray. Spec binding only: what clicks do belongs to the application.

```tarn
var items: Vec<dbusmenu.Item> = Vec.new()
items.push(dbusmenu.entry(1, &"Show").with_icon(&"window-new"))
items.push(dbusmenu.checkbox(2, &"Do not disturb", false))
items.push(dbusmenu.separator(3))
items.push(dbusmenu.entry(4, &"Quit"))
var tray = try status_notifier.start(bus, &"my-app", &"My app", &"applications-development", items)
for {
    match try bus.receive(60000) {
        Some(incoming) => {
            events := try tray.handle(bus, incoming)
            // Activate(point), SecondaryActivate, Scroll, Menu(event), Registered, WatcherGone, Other(message)
        }
        None => {}
    }
}
```

- `start` publishes `/StatusNotifierItem` and `/MenuBar`, takes
  `org.kde.StatusNotifierItem-<pid>-1` and registers with the watcher.
  `is_registered()` is false when no watcher runs (no icon is shown).
- When the watcher restarts, the item registers again by itself and
  `handle` reports `WatcherGone` and `Registered`.
- `set_title`, `set_icon_name`, `set_icon_pixmaps`, `set_attention_icon_name`,
  `set_tooltip` and `set_status` update properties and send the matching
  `New*` signal plus `PropertiesChanged`. `pixmap_from_rgba` converts RGBA to
  the spec's ARGB byte order (up to 256×256).
- Menus: `entry`, `checkbox`, `radio`, `separator`, `.with_icon`,
  `.disabled`, `.hidden`, `.with_children`, with unique positive ids.
  `set_menu` diffs the new tree: a structure change sends `LayoutUpdated`
  with a new revision; property changes send `ItemsPropertiesUpdated` for the
  changed items only. `GetLayout` honours depth and property filters.
- `tray_demo.tarn` is the manual check on the desktop.

## Wire format (`src/value`, `src/marshal`, `src/message`)

- `src/value`: typed values for every D-Bus type except Unix FDs; containers
  keep element signatures, `ay` is `Bytes`. Builders: `text`, `path`, `array`,
  `structure`, `variant`, `dict_sv().put_sv(...)`.
- `src/signature`: validation and splitting, with the spec's 255-byte and
  32/32 nesting limits.
- `src/names`: object path, interface, member, error and bus name rules.
- `src/marshal`: encoding (little-endian) and bounded decoding of both byte
  orders: zero padding, 0/1 booleans, UTF-8 strings without NUL, 64 MiB
  arrays, 64 nested containers, 4096 values per message.
- `src/message`: headers, per-type field rules, `frame_length` for stream
  framing, `call`, `signal_message`, `reply_to`, `error_to`.

`test_wire.tarn` runs offline. It compares Tarn bodies byte for byte with
messages produced by GDBus (`tests/golden/messages.txt`, regenerated with
`tests/golden/generate.py`), decodes those messages, and writes its own for
`tests/golden/verify.py` to parse with GDBus. It also covers IEEE 754 edge
cases, a 64×64 icon and hostile input (every truncation, bad padding,
booleans, UTF-8, lengths, signatures and nesting).

## Requirements and validation

- Current Tarn compiler, Linux x86_64. No native libraries and no `--link`.
- Test-only tools: `dbus-run-session` and Python with GObject introspection
  (`gi`, Gio). Python provides the GDBus reference messages and the isolated
  service; it is not used by the library.

`test.sh` runs the offline wire tests (`test_wire.tarn`, GDBus golden messages
in both directions), checks that a borrowed connection cannot escape its scope
(E3079), then starts an isolated session bus with the GDBus fixture
(`tests/fixture.py`) for `test_client.tarn` (0.1 API) and `test_native.tarn`
(native API), a fake notification server for `test_notifications.tarn`, and
`tests/run_router.py`, which drives the `test_router.tarn` server with GDBus,
`gdbus introspect` and `busctl`, and `tests/run_tray.py`, which plays the
watcher and the host for `test_tray.tarn`, including a watcher restart. It never talks to the desktop session bus.

## 0.1 compatibility layer (`src/dbus`)

```tarn
import "src/dbus"
fn inspect(bus &mut dbus.Connection) Result<void, dbus.Error> {
    names := try bus.list_names()
    for name in names.as_slice() { print(name) }
    return Ok(())
}
```

`with_session`, `list_names`, `name_owner`, `request_name`, `add_match`,
`remove_match`, `receive`, `signal` (empty body) and `call_strings` keep their
0.1 contracts on top of the native connection. Its `Value` model keeps 0.1
behavior: strings, object paths and signatures share `Text`, and byte,
int16/uint16, int64 and double replies return `tarn.dbus.UnsupportedType`.
New code should use `src/connection` with `src/value`.

For an application, copy/vendor the source under the application's module root
or publish it through Tarn's source-package workflow. There is no registry
release yet.
