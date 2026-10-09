import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus();name=dbus.service.BusName('org.tarn.DBusTest',bus)
class Fixture(dbus.service.Object):
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='sbiutas')
    def Mixed(self):return 'Tarn',True,-42,4294967295,18446744073709551615,['one','two']
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='')
    def Empty(self):pass
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='as')
    def Huge(self):return ['bounded']*5000
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='(su)a{sv}')
    def Nested(self):return ('nested',7),{'active':dbus.Boolean(True,variant_level=1)}
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='',async_callbacks=('reply','failure'))
    def Slow(self,reply,failure):
        def done():reply();return False
        GLib.timeout_add(100,done)
    @dbus.service.method('org.tarn.DBusTest',in_signature='',out_signature='d')
    def Unsupported(self):return 3.5
fixture=Fixture(bus,'/Test');print('READY',flush=True);GLib.MainLoop().run()
