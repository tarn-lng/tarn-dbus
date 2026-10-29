# tarn-dbus

Keep this library independent of the Tarn compiler/stdlib and desktop applications.
Implementation, tests and documentation are English. Target Linux x86_64 only.
Pure Tarn: no libdbus, no C sources, no FFI and no `unsafe` in the library.

Read README.md for implemented scope and native ownership contracts. Preserve
scoped connections, bounded waits, error names, the wire limits in
src/marshal and src/message, and explicit unsupported-type errors. Do not export raw handles or assume
Tarn provides destructors for user native wrappers. Tests use an isolated bus;
never restart or alter a user's desktop/service just to run library tests.

Run TARN=/absolute/path/to/tarn ./test.sh after semantic changes. Python (Gio) is a
test fixture only; regenerate tests/golden/messages.txt only when adding cases. Future server/signal support must have session-bus tests and
must not duplicate desktop-specific policy inside the protocol library.
