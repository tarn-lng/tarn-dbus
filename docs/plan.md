# tarn-dbus expansion plan: native implementation

Status: in progress, 2026-10-28 (native approach). P0 done in the Tarn
repository (`UnixStream.raw_fd`, with test); M1 done (`test_wire.tarn`,
73 checks, GDBus verified in both directions); M2 done (`test_native.tarn`,
18 checks, plus the 0.1 suite on the native core; libdbus removed); M5 done
(`test_notifications.tarn`, 10 checks against a fake server; manual check
with `notify_demo.tarn` passed on Plasma 6.8.1 on 2026-10-28: notification
shown, replaced with buttons, and the "yes" action received); M3 done
(`test_router.tarn` served to `tests/run_router.py` with GDBus,
`gdbus introspect` and `busctl`); M4 done (properties in the same suite,
42 checks in total, including `busctl get-property` and `set-property`); M6
done in automated tests (`tests/run_tray.py`, 34 checks against a fake watcher
and host, including a watcher restart); manual check with `tray_demo.tarn` on
Plasma passed on 2026-10-28 (icon, menu and notifications). This work found a
compiler bug: type checking was exponential in the length of call chains
(20 calls took 14 s); fixed in the Tarn type checker with scaling regression
tests.
Not covered yet by M2 tests: a peer that stops reading (full socket buffer)
and a bus that dies mid-message. Goal: let Tarn
applications publish a tray icon with a menu, send desktop notifications and
keep running in the background, starting with Tarn UI on KDE Plasma.

**Decision:** tarn-dbus becomes a pure Tarn implementation of the D-Bus wire
protocol over the stdlib `UnixStream`, like the organization's native
PostgreSQL, MySQL, Redis and MongoDB drivers. `libdbus-1`, `--link dbus-1` and
`tests/abi.c` are removed. No C source is written for this work.

## 1. Where we start (0.1)

| Area | 0.1 (libdbus FFI) | Native target |
| --- | --- | --- |
| Transport | libdbus private connection | `UnixStream` to `$DBUS_SESSION_BUS_ADDRESS`, non-blocking |
| Authentication | libdbus | SASL `EXTERNAL` in Tarn (uid from `/proc/self/status`) |
| Values | Decode `s o g b i u t`, containers; encode strings only | Every type except Unix FDs, both directions, exact signatures |
| Calls | Blocking, string arguments | Blocking with bound and non-blocking with serials |
| Signals | Empty body | Typed body, unicast and broadcast |
| Server side | None | Replies, errors, router, introspection, properties |
| Desktop | None | Notifications, StatusNotifierItem, DBusMenu |

The 0.1 public API (`with_session`, `list_names`, `name_owner`, `request_name`,
`add_match`, `remove_match`, `receive`, `signal`, `call_strings`) is kept as a
compatibility layer over the native core during 0.2, then retired.

## 2. Principles

- Pure Tarn: no C sources and no native libraries beyond what the compiled
  program already needs. No `unsafe` in the library.
- Scoped connection: `with_session` owns the socket and closes it on every
  ordinary result, including `Err`.
- Polling model: the app receives messages and answers them explicitly, with no
  callbacks.
- Every wait is bounded. No hidden threads, retries or reconnects.
- Explicit errors with D-Bus names (`tarn.dbus.*` locally, remote names kept).
- Limits from the spec, enforced before allocation: message 128 MiB (library
  default 1 MiB, configurable), array 64 MiB, signature 255 bytes, depth 32/32
  per container kind, plus 4096 values per message by default.
- Protocol and desktop policy stay separate (section 3).
- Every feature has isolated-bus tests (`dbus-run-session`); the user's desktop
  is used only for the final, manual acceptance steps.

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Application (Tarn UI app)                                    │
├──────────────────────────────────────────────────────────────┤
│ tarn-ui/desktop: tray + menu + notifications + background    │  ← UI policy
├──────────────────────────────────────────────────────────────┤
│ tarn-dbus/desktop: notifications · status_notifier · dbusmenu│  ← freedesktop specs
├──────────────────────────────────────────────────────────────┤
│ tarn-dbus/src                                                │
│   connection  — address, auth, Hello, send/receive queues    │
│   message     — header fields, serials, flags                │
│   wire        — marshalling with alignment, little-endian    │
│   signature   — parse/validate, Value ↔ signature            │
│   value       — typed Value model and builders               │
│   router      — method dispatch, introspection, Peer         │
│   properties  — Get/GetAll/Set, PropertiesChanged            │
├──────────────────────────────────────────────────────────────┤
│ stdlib net.UnixStream (non-blocking) · os · string · bytes   │
└──────────────────────────────────────────────────────────────┘
```

The desktop modules bind freedesktop specs with no application policy. They
live in this repository under `desktop/`, as separate importable modules.
Anything that touches windows, the event loop or the "close to tray" decision
lives in Tarn UI.

## 4. Prerequisite in the Tarn compiler

**P0 — Expose the socket descriptor (stdlib, tarn repository).** Add
`UnixStream.raw_fd(&self) i32`: a borrowed descriptor, valid while the stream
lives, documented as not owned by the caller. GTK's main loop needs it to
watch the D-Bus socket. Include tests that the descriptor matches the open
stream and that closing the stream invalidates it. Everything else the native
implementation needs (connect, non-blocking read/write, byte buffers, string
parsing, file reads for `/proc/self/status`) already exists.

## 5. Milestones

Each milestone is releasable on its own, ends with `./test.sh` green and a
README and CHANGELOG update, and lists exit criteria. Versions follow 0.x.

### M1 — Native wire format and values (0.2, offline)

Pure data work, testable without any bus.

- `value.tarn`: `Byte`, `Bool`, `I16`, `U16`, `I32`, `U32`, `I64`, `U64`,
  `Double`, `Text`, `ObjectPath`, `Signature`, `Bytes(Vec<u8>)` for `ay`,
  `Array(element_signature, Vec<Value>)`, `Dict(key_sig, value_sig, entries)`,
  `Struct(Vec<Value>)`, `Variant(signature, Box<Value>)`. Unix FDs (`h`) return
  `UnsupportedType`.
- `signature.tarn`: spec grammar, validation, limits, and `Value.signature()`.
  The encoder checks that a value matches its declared signature.
- `wire.tarn`: an encoder and decoder with alignment padding (1/2/4/8),
  little-endian output, big-endian input accepted, valid UTF-8 and no NUL in
  strings, valid object paths, booleans only 0/1, and array length limits
  checked before reading.
- `message.tarn`: header (endianness, type, flags, version 1, body length,
  serial) and header fields (path, interface, member, error name, reply serial,
  destination, sender, signature), with rules per message type.
- Builders: `dbus.text`, `dbus.u32`, `dbus.array_of`, `dbus.dict_sv`,
  `dbus.variant` and so on, so call sites stay readable.

Exit: golden byte tests against messages produced by `dbus-send` and
`gdbus`, captured once and stored under `tests/golden/`. Round trip
encode → decode for every type, empty arrays of each kind, `a{sv}` with nested
variants, `a(iiay)` with 64×64 ARGB data, depth and size limits, and truncated
or corrupted input. All of this runs without a bus.

### M2 — Native connection (0.3)

Replace libdbus for the transport.

- Address parsing for `unix:path=` and `unix:abstract=`, with escaping, from
  `DBUS_SESSION_BUS_ADDRESS`, or `$XDG_RUNTIME_DIR/bus` as the systemd default.
  Other transports (`tcp:`, `launchd:`) are rejected explicitly.
- SASL authentication: send a NUL byte, then `AUTH EXTERNAL <hex uid>`, accept
  `OK <guid>`, send `BEGIN`. The uid comes from `/proc/self/status`. Handle
  `REJECTED` and `ERROR` with clear errors and a bounded handshake time.
  `NEGOTIATE_UNIX_FD` is not requested.
- `Hello` gives the unique name. `with_session` connects, authenticates,
  greets and always closes.
- Bounded read and write queues. `send` assigns serials. `flush(timeout)` and
  `dispatch(max)` read without blocking, using the non-blocking `UnixStream`.
- Blocking `call(..., timeout)` built on serials: the reply is matched by
  `reply_serial`, and other messages that arrive meanwhile are queued for later
  delivery, not lost.
- Non-blocking `send_call` returns a serial. A `Pending` table with timeouts
  produces local `tarn.dbus.Timeout` replies.
- Typed `signal(path, interface, member, args)` with optional destination.
- `raw_fd()` from P0, for external event loops.
- Port the 0.1 API onto the native core; remove libdbus, `tests/abi.c` and the
  `--link dbus-1` requirement.

Exit: the existing 0.1 test suite passes unchanged on the native core. New
tests: authentication rejected, a dead bus, a peer that closes mid-message,
1000 queued signals, replies interleaved with signals, timeouts firing without
blocking, a full socket buffer (fixture stops reading), and an idle-CPU check.
`busctl --user` sees the unique name and its well-known names.

### M3 — Serving methods (0.4)

- `reply(&Message, args)` and `reply_error(&Message, name, text)` use the
  stored serial, sender and `NO_REPLY_EXPECTED` flag. A second reply, or a
  reply to a message that is not a call, is an error.
- `Router`: the app registers objects with interface descriptions (methods,
  signals, properties with signatures). `route(message)` returns a `Call` for
  registered methods. It answers `UnknownObject`, `UnknownInterface`,
  `UnknownMethod` and `InvalidArgs` itself.
- Built-ins: `org.freedesktop.DBus.Peer` (`Ping`, `GetMachineId` from
  `/etc/machine-id`) and `Introspectable.Introspect`, with XML generated from
  the registered descriptions, including child nodes.

Exit: `gdbus introspect` and `busctl --user call` work against a test object.
Standard errors match GDBus for the same mistakes. Malformed calls and wrong
signatures never crash the router.

### M4 — Properties (0.5)

- `PropertyStore` per object, with typed values and `read`, `readwrite` or
  `write` access.
- The router answers `Get` and `GetAll`. `Set` is returned to the app as a
  `Call` to accept or reject.
- `update(name, value)` reports whether the value changed; `emit_changed()`
  sends one batched `PropertiesChanged` with values and invalidations.

Exit: `busctl --user get-property` and `set-property` work, and a fixture
observes batched changes and access errors.

### M5 — Desktop notifications (`desktop/notifications.tarn`)

Spec: org.freedesktop.Notifications 1.2.

- `server_information()` and `capabilities()`.
- `notify(Notification{app_name, replaces_id, icon, summary, body, actions,
  hints, timeout})` returns the id. Typed hints: `urgency`, `category`,
  `desktop-entry`, `image-path`, `transient`, `resident`.
- `close(id)`.
- Events through `dispatch`: `ActionInvoked`, `NotificationClosed` (with the
  reason) and `ActivationToken`.

Exit: a fixture implementing the Notifications server checks every argument;
manual check on Plasma covering actions, replace and close reasons.

### M6 — StatusNotifierItem and DBusMenu (`desktop/status_notifier.tarn`, `desktop/dbusmenu.tarn`)

- **Item:** own `org.kde.StatusNotifierItem-<pid>-<n>` and publish
  `/StatusNotifierItem`:
  - Properties: `Category`, `Id`, `Title`, `Status`, `IconName`, `IconPixmap
    a(iiay)`, `AttentionIconName`, `ToolTip (sa(iiay)ss)`, `ItemIsMenu`, `Menu`.
  - Methods returned to the app: `Activate`, `SecondaryActivate`,
    `ContextMenu`, `Scroll`.
  - Signals: `NewIcon`, `NewTitle`, `NewToolTip`, `NewStatus`.
- **Registration:** `RegisterStatusNotifierItem` with the Watcher, watch
  `NameOwnerChanged` and re-register automatically. If there is no Watcher,
  report it so the app can fall back.
- **Menu:** a tree with stable integer ids and the properties `label`,
  `enabled`, `visible`, `type`, `toggle-type`, `toggle-state`, `icon-name` and
  `children-display`.
  - Methods answered: `GetLayout`, `GetGroupProperties`, `GetProperty`,
    `Event`, `EventGroup`, `AboutToShow`, `AboutToShowGroup`.
  - Signals: `LayoutUpdated` and `ItemsPropertiesUpdated`, produced by diffing
    the old and new tree with the same model as Tarn UI views.
- **Pixmaps:** an RGBA → ARGB32 network byte order helper with size limits.

Exit: a fixture with a fake Watcher and Host covers registration, every
property, opening the menu, clicking and toggling items, and a Watcher
restart. Then manual acceptance on Plasma.

### M7 — Tarn UI integration (in the `ui` repository) — done

Implemented as `ui/core/desktop.tarn` (not `ui/desktop/`, which would clash
with this library's `desktop/` import paths), bridge ABI 14 and
`ui/scripts/test-tray.sh`. The Plasma checklist and the 10-minute idle run
are still manual.

- **Event loop:** watch the D-Bus socket from Tarn through GLib's
  `g_unix_fd_add_full`, using a static `ffi.callback`. No C code; it does not
  depend on migrating `bridge.c`. Readability queues one coalesced event to the
  session.
- **Background mode:** `set_hide_on_close`, `present` and a `Hidden` event; the
  window really exits only through `request_close` or the app's Quit action.
- **Tray and notifications:** `ui/desktop/tray.tarn` describes the tray (icon,
  tooltip, menu with actions) and is reconciled like `View`.
  `ui/desktop/notify.tarn` maps notification actions to app actions.
- **Example:** `examples/tray` with an icon and tooltip, show/hide on click, a
  menu with Show, a toggle and Quit, and a notification with actions.
- **Fallback:** without a Watcher, the app keeps working and `hide_on_close`
  stays off.

Exit: Tarn UI suites green, an isolated-bus end-to-end test, the Plasma
checklist, 10 minutes idle in the tray without CPU above baseline, and a clean
unregister on exit.

## 6. Order and dependencies

```
P0 raw_fd ─────────────────────────────┐
M1 wire ──► M2 connection ──► M3 router ──► M4 properties ──► M6 tray + menu ──► M7 Tarn UI
                  └──────────► M5 notifications ─────────────────────────────┘
```

Suggested order: P0 and M1 in parallel → M2 → M5 (first visible result) → M3 →
M4 → M6 → M7.

## 7. Testing strategy

- **Golden bytes** captured from `dbus-send` and `gdbus`, for the marshaller
  without a bus.
- **Isolated bus** for every live test: `dbus-run-session`, with Python
  fixtures (dbus-python) as counterparts: echo service, Notifications server,
  Watcher and Host. Python stays test-only.
- **Cross-checks** on the isolated bus with `busctl`, `gdbus introspect` and
  `dbus-send`.
- **Hostile input:** truncated headers, wrong lengths, bad alignment padding,
  invalid UTF-8, oversized arrays, deep nesting and wrong booleans. Every case
  must give an error, never a panic.
- **Resources:** descriptor count before and after each test, bounded queues
  and idle CPU.
- **Manual acceptance on Plasma** only for M5–M7, as written checklists in
  `docs/`. Tests never restart desktop services.

## 8. Risks and decisions

| Risk | Mitigation |
| --- | --- |
| Hand-written marshalling bugs | Golden bytes from reference tools, round trips, hostile-input suite |
| Authentication differences (abstract sockets, other uids) | Support `EXTERNAL` only, test both address forms, clear rejection errors |
| Blocking calls freeze the UI | Non-blocking `send_call`; blocking `call` documented as non-UI |
| Write queue grows if the peer does not read | Bounded queue, `flush` with timeout, backpressure error |
| Host differences (Plasma, Waybar, GNOME extension) | Follow the KDE spec, Plasma first, others documented as untested |
| Watcher restarts | `NameOwnerChanged` tracking and a re-registration test |
| API break from 0.1 | 0.x versioning, CHANGELOG, 0.1 API kept as a layer during 0.2 |
| Performance of pure Tarn byte handling | Benchmark 10 000 messages per second as a reference target; profile before optimizing |

Open decisions:

1. Keep `desktop/` in this repository (proposed) or create `tarn-desktop`.
2. Plasma only for the first tray release (proposed), or also Waybar and the
   GNOME AppIndicator extension.
3. Replace the existing status-device tray program with this stack after M6,
   as a real-world acceptance test.

## 9. Effort estimate

| Milestone | Size | Main work |
| --- | --- | --- |
| P0 | Small | stdlib accessor and tests |
| M1 | Large | Value model, signatures, marshalling, golden tests |
| M2 | Large | Address, SASL, queues, serials, pending calls, 0.1 port |
| M3 | Medium | Router, standard errors, introspection XML |
| M4 | Small | Property store and signals |
| M5 | Small | Spec binding and fixture |
| M6 | Large | Two specs, menu diffing, pixmaps, re-registration |
| M7 | Medium | GLib fd watch from Tarn, background mode, example, checklist |
