import sys
import os
import gtk.gdk
import gobject
import osmgpsmap  # apt-get install python-osmgpsmap
from ui import UI
import pyexiv2

#print "using library: %s (version %s)" % (osmgpsmap.__file__, osmgpsmap.__version__)
assert osmgpsmap.__version__ == "0.7.3"

class App(object):

    def __init__(self):
        gobject.threads_init()
        gtk.gdk.threads_init()

        self.marker_lat = 0
        self.market_lon = 0
        self.imagedir   = '/home/martijn/Pictures/2012'

        self.imagestore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.populate_store(self.imagestore, self.imagedir)

    def main(self):
        self.ui = UI()
        self.ui.treeview0.set_model(self.imagestore)
        self.ui.connect('destroy', self.quit)
        self.ui.menuitem_quit.connect("activate", self.quit)
        self.ui.show_all()
        if os.name == "nt": gtk.gdk.threads_enter()
        gtk.main()
        if os.name == "nt": gtk.gdk.threads_leave()

    def quit(self, _widget):
        print "bla"
        gtk.main_quit()

    def populate_store (self, store, imagedir):
        store.clear()
        if imagedir:
            for fl in os.listdir(imagedir):
                if not fl[0] == '.':
                    fname = os.path.join(imagedir, fl)
                    if not os.path.isdir(fname):
                        if os.path.splitext(fname)[1].lower() == ".jpg":
                            metadata = pyexiv2.ImageMetadata(fname)
                            metadata.read()
                            try:
                                dt = metadata['Exif.Image.DateTime'].raw_value
                            except KeyError:
                                dt = ''
                            try:
                                rot =  metadata['Exif.Image.Orientation'].raw_value
                            except KeyError:
                                rot = 1
                            try:
                                imglat = metadata['Exif.GPSInfo.GPSLatitude'].human_value
                            except KeyError:
                                imglat = ''
                            try:
                                imglon = metadata['Exif.GPSInfo.GPSLongitude'].human_value
                            except KeyError:
                                imglon = ''
                            store.append([fl, dt, rot, imglat, imglon])
