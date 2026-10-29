# Changelog

## Unreleased (0.2)

- Native wire format, milestone M1 of [the plan](docs/plan.md): typed values,
  signatures, name validation, marshalling and message headers in pure Tarn.
  Verified in both directions against GDBus.
- Native connection, milestone M2: address resolution, SASL EXTERNAL, Hello,
  bounded queues, blocking and non-blocking calls with local timeouts, typed
  signals, `raw_fd` for foreign event loops. libdbus and `--link dbus-1` are
  removed; the 0.1 API is a layer over the native core.
- Desktop notifications, milestone M5: `desktop/notifications` with notify,
  replace, close, capabilities, server information and typed events.
- Object publication, milestone M3: `src/router` with interface descriptions,
  signature-checked dispatch, standard errors, Peer and generated
  introspection; `Connection.reply` and `reply_error`.
- Properties, milestone M4: `set_property`, `property`, `invalidate`,
  `emit_changed`, and `Get`, `GetAll` and checked `Set` in the router.
- Tray icon and menu, milestone M6: `desktop/status_notifier` and
  `desktop/dbusmenu`, with re-registration after watcher restarts and menu
  diffing.
- `Call.answered` is now `Call.is_answered`.
- `Value.clone` and `Dict.clone`.
- A reply body that breaks a limit now fails only its own call.
- Test fixtures use GDBus instead of dbus-python.
- The escape test expects E3079: the connection no longer holds a raw pointer.

## 0.1.0

- Blocking client and signal foundation backed by libdbus-1.
