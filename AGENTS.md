# tarn-dbus

Keep this library independent of the Tarn compiler/stdlib and desktop applications.
Implementation, tests and documentation are English. Target Linux x86_64 only.
No native linking authority is granted by imports; consumers pass --link dbus-1.

Read README.md for implemented scope and native ownership contracts. Preserve
scoped private connections, bounded blocking calls, error names, native ABI
checks and explicit unsupported-type errors. Do not export raw handles or assume
Tarn provides destructors for user native wrappers. Tests use an isolated bus;
never restart or alter a user's desktop/service just to run library tests.

Run TARN=/absolute/path/to/tarn ./test.sh after semantic changes. Python is a
test fixture only. Future server/signal support must have session-bus tests and
must not duplicate desktop-specific policy inside the protocol library.
