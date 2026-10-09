# tarn-dbus

An independent Tarn library for Linux session D-Bus, backed by the installed
`libdbus-1` C library. It is **not part of Tarn's standard library**.

Version 0.1 is a blocking client and signal foundation. The desktop widget currently keeps
its Python adapter; this library does not yet publish tray objects or menus.

## Requirements and validation

- Current Tarn compiler with native FFI support, Linux x86_64.
- `libdbus-1` plus headers/pkg-config for ABI validation (Debian/Ubuntu:
  `libdbus-1-dev`). The validated local version is 1.16.2.
- Test-only tools: C compiler, pkg-config, dbus-run-session, Python with dbus and
  GLib bindings. Python is not linked or used by the library or example.

```sh
TARN=/path/to/tarn/target/release/tarn ./test.sh
./build/list-names
```

The test script verifies native layouts and builds explicitly with `--link
dbus-1`, then creates an isolated session bus and a test-only Python service.
It tests string arguments, scalar/container replies, remote errors, invalid
arguments, actual timeout behavior, nested containers, oversized reply limits,
descriptor cleanup after callback errors and compile-time connection escape rejection.
It does not change the desktop service or communicate with desktop applications.

The example imports `src/dbus` from the project root:

```tarn
import "src/dbus"
fn inspect(bus &mut dbus.Connection) Result<void, dbus.Error> {
    names := try bus.list_names()
    for name in names.as_slice() { print(name) }
    return Ok(())
}
```

`dbus.with_session(inspect)` acquires a private connection and closes it on every
ordinary callback result, including Err. Raw handles do not escape. There are no
user destructors or background collector processes. Panic follows Tarn's normal
process-abort semantics. `Error` owns `name` and `message`; native errors retain
their D-Bus identity and diagnostic text.

## API and boundaries

- `with_session(callback)` scopes a private session connection.
- `Connection.list_names()` returns owned names.
- `Connection.name_owner(name)` returns an owned owner name.
- `Connection.call_strings(destination, path, interface_name, member, arguments,
  timeout_ms)` calls a method with string arguments; timeout must be 1..60000 ms.
- `Value` decodes string-like values, bool, i32, u32, u64, arrays, structs,
  dictionary entries and variants into owned Tarn data. String, object-path and
  signature replies currently share `Text`; exact wire signatures are not yet
  preserved in the public value model.
- Unsupported types fail explicitly. This includes double, byte, i16/u16/i64
  and Unix file descriptors in 0.1. Maximum decoded depth is 32 and total value
  count is 4096. This limit also applies to large arrays of values.
- `Connection.request_name(name)` acquires a well-known name without replacing
  its current owner or queuing; scope completion releases it.
- `Connection.add_match(rule)` / `remove_match(rule)` manage subscriptions using
  native D-Bus match grammar and preserve invalid-rule errors.
- `Connection.signal(path, interface_name, member)` queues an empty signal;
  there is no implicit unbounded flush or remote delivery guarantee.
- `Connection.receive(timeout_ms)` returns at most one owned `Message`, with
  type/path/interface/member/sender and decoded body. Wait is 0..60000 ms;
  disconnected transport returns an error. It services transport when the local
  queue is empty. Incoming replies and bus control signals may also be returned,
  so applications filter by message type and metadata.
- Calls block the current native task. No async executor or
  server object publication, automatic reconnect or concurrent connection access
  is provided. `Connection` contains a raw native handle and is not transferable.

For an application, copy/vendor the source under the application's module root
or publish it through Tarn's existing source-package workflow. There is no
registry release yet. Consumers must explicitly grant `--link dbus-1`; the
library cannot grant native linking authority merely by being imported. No
installation or build hook is required by the package.

## Native dependency decision

D-Bus authentication, message validation and transport are complex enough that
an improvised wire implementation would be a poor foundation. `libdbus-1` is the
focused protocol library already installed on the target system, avoiding a
GLib/GIO dependency in the runtime library. No Cargo dependency or compiler
change is added. Local `ldd` inspection lists libsystemd, libc and libm as loaded
native dependencies; this is an observation of the installed build, not a
complete supply-chain guarantee for every system distribution.

C code is outside Tarn's memory-safety proof. The small unsafe boundary uses
opaque handles, keeps C strings alive during synchronous calls, copies replies
before unref and frees every acquired message/error/connection on ordinary
success/failure. DBusMessageIter and DBusError use verified native storage;
`tests/abi.c` must pass when changing the supported system ABI.

## Next steps, guided by the widget

1. Typed argument encoding and remaining reply types/signatures.
2. Extend empty signals to typed bodies and add sender/destination/serial metadata.
3. Method replies and object/property publication without C callback pointers.
4. Separate StatusNotifierItem/dbusmenu application layer in status_device.
5. Validate tray re-registration, shutdown and CPU before replacing Python.

Desktop-specific types and policies belong above this protocol library.

## Signal validation

The isolated-bus tests acquire `org.tarn.Client`, reject taking the existing
fixture name, subscribe to an interface/member, emit and receive a real empty
signal, check owned metadata, remove the subscription, and reject malformed
match rules, signal paths and negative receive waits. Server publication and
method replies remain unimplemented; the running widget still uses Python.
