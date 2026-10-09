#include <dbus/dbus.h>
#include <stdint.h>
#include <stddef.h>
#if !defined(__linux__) || !defined(__x86_64__)
#error "Only Linux x86_64 is supported"
#endif
_Static_assert(sizeof(dbus_bool_t) == 4, "D-Bus boolean ABI changed");
_Static_assert(offsetof(DBusError, name) == 0, "Error name offset changed");
_Static_assert(offsetof(DBusError, message) == 8, "Error message offset changed");
_Static_assert(_Alignof(DBusError) <= _Alignof(uint64_t), "Error alignment changed");
_Static_assert(sizeof(void *) == 8, "Linux x86_64 required");
_Static_assert(sizeof(DBusMessageIter) == 9 * sizeof(uint64_t), "Iterator ABI changed");
_Static_assert(_Alignof(DBusMessageIter) <= _Alignof(uint64_t), "Iterator alignment changed");
_Static_assert(sizeof(DBusError) == 4 * sizeof(uint64_t), "Error ABI changed");
int main(void) { return 0; }
