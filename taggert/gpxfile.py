#!/usr/bin/python

# gpxfile.py - Used to import GPX XML files into applications
# GPX files are maintained as a list of lxml.etree ElementTrees
# Copyright (C) 2014 Martijn Grendelman
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from pprint import pprint
from lxml import etree
from iso8601 import parse_date as parse_xml_date
from datetime import datetime, timedelta
from pytz import timezone   # apt-get install python-tz
from math import radians, sin, cos, atan2, sqrt
import os.path
import copy
import version

nsuri = 'http://www.topografix.com/GPX/1/1'
ns = '{' + nsuri + '}'
minimal_xml = """<gpx xmlns="%s" version="1.1" creator="Taggert v%s">
</gpx>
""" % (nsuri, version.VERSION)

class Track(object):
    """
    An object representing a track. It holds a reference to a <trk> element
    and some metadata.
    """
    tid = None
    trk = None
    tz = timezone('UTC')     # a pytz timezone object
    starttime = None
    endtime = None
    distance = None

    def __init__(self, tid, trk=None, tz=None):
        """
        Initialize the track object and optionally set the 'trk' element and
        timezone object
        """
        self.tid =  tid
        if trk is not None:
            self.set_track(trk)
        if tz is not None:
            self.tz = tz

    def set_track(self, trk):
        """
        Setter for the trk attribute
        """
        self.trk = trk

    def parse_timestamps(self):
        """
        Update data from <time> elements found within the track
        """
        alltimes = self.trk.findall(ns + 'trkseg/' + ns + 'trkpt/' + ns + 'time')
        starttime = parse_xml_date(alltimes[0].text).replace(tzinfo=None)
        endtime = parse_xml_date(alltimes[-1].text).replace(tzinfo=None)
        delta = self.tz.utcoffset(starttime, False)
        self.starttime = starttime + delta
        self.endtime = endtime + delta

    def get_timestamps(self):
        """
        Return the track's start and endtime. Calculate those times if necessary.
        """
        if self.starttime is None:
            self.parse_timestamps()
        return (self.starttime, self.endtime)

    def get_starttime(self):
        """
        Return the track's starttime. Calculate it is necessary.
        """
        if self.starttime is None:
            self.parse_timestamps()
        return self.starttime

    def get_name(self):
        """
        Return the contents of the <name> element if present, or a generated track name
        """
        return self.trk.findtext(ns + 'name') or \
            self.get_starttime().strftime('%Y-%m-%d %H:%M:%S')

    def get_points(self):
        """
        Return al track points from the track
        """
        return self.trk.findall(ns + 'trkseg/' + ns + 'trkpt')

    def trkpt_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculate and return the distance in meters between two track points
        """
        radius = 6371000 # meter
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2) * sin(dlat/2) + cos(lat1) \
            * cos(lat2) * sin(dlon/2) * sin(dlon/2)
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        d = radius * c
        return d

    def get_distance(self):
        """
        Calculate the total distance of the track by iterating over all track points
        """
        if self.distance is None:
            distance = 0
            oldlat = None
            for trkpt in self.trk.findall(ns + 'trkseg/' + ns + 'trkpt'):
                lat = float(trkpt.get('lat'))
                lon = float(trkpt.get('lon'))
                if oldlat != None:
                    distance += self.trkpt_distance(oldlat, oldlon, lat, lon)
                oldlat = lat
                oldlon = lon
            self.distance = distance
        return self.distance

class GPXfile(object):
    """
    An object holding references to all loaded tracks, providing methods for
    importing and validating GPX files from disk
    """

    delta = None  # a timedelta object
    tz = None     # a pytz timezone object
    data_dir = '.'
    tree = etree.ElementTree(etree.fromstring(minimal_xml))
    schemafile = None
    schema = None
    xmlparser = None
    ns = '{http://www.topografix.com/GPX/1/1}'
    tracks = {}

    def __init__(self, data_dir):
        """
        Initialize the object and create an XML parser using the GPX schema
        """
        self.data_dir = data_dir
        self.schemafile = os.path.join(self.data_dir, 'gpx.xsd')
        self.schema = etree.XMLSchema(file=self.schemafile)
        self.xmlparser = etree.XMLParser(schema=self.schema)

    def import_gpx(self, filename, tz):
        """
        Read a GPX file from disk and parse it
        """
        self.tz = timezone(tz)
        self.delta = None

        # lxml
        try:
           tree = etree.parse(filename, self.xmlparser)
        except etree.XMLSyntaxError as e:
            return (False, e)

        # Use the first file as skeleton
        if self.tree is None:
            self.tree = tree

        root = tree.getroot()
        return self.parse_tracks(root)

    def parse_tracks(self, root):
        """
        Parse <trk> elements from a given XML tree, create Track instances
        for them and store references.
        Make sure the list of parsed tracks does not grow larger than 40,
        because it leads to a 'Bus Error', crashing the program.
        """
        dest_root = self.tree.getroot()
        ids = []
        tracks = root.findall(ns + 'trk')
        msg = ''
        for trk in tracks:
            if len(self.tracks) >= 40:
                msg = 'Track list too long'
                break
            # Copy the <trk> element to the XML tree
            trk2 = copy.deepcopy(trk)
            dest_root.append(trk2)
            # Compose a Track object
            tid = id(trk2)
            tobj = Track(tid, trk2, self.tz)
            self.tracks[tid] = tobj
            ids.append(tid)
        # Return a list of newly added track ids
        return (ids, msg)

    def get_tracks(self, id_list):
        """
        Return a dict of track objects for a given list of ids
        """
        return { k: v for k, v in self.tracks.iteritems() if k in id_list }

    def remove_track(self, tid):
        """
        Remove a track from the XML tree and from the reference-dictionary
        """
        if tid in self.tracks:
            trk = self.tracks[tid].trk
            root = self.tree.getroot()
            root.remove(trk)
            del self.tracks[tid]

    def save_gpx(self, fname=None):
        """
        Dump the currently loaded tracks to a GPX file
        """
        if fname is None:
            fname = 'zzzzzzzzzzz.gpx'
        self.tree.write(fname, xml_declaration = True, encoding='utf-8')

    def find_coordinates(self, dt):
        """
        Find a coordinate for a given DateTime, used for tagging images
        """
        lat = lon = None
        ele = 0.0
        latx = lonx = elex = None
        for tid, tobj in self.tracks.iteritems():
            if dt >= tobj.starttime and dt <= tobj.endtime:
                for p in tobj.get_points():
                    try:
                        if latx is None:
                            latx = float(p.get('lat'))
                            lonx = float(p.get('lon'))
                            elex = float(p.findtext(ns + 'ele'))
                        t0 = parse_xml_date(p.findtext(ns + 'time')).replace(tzinfo=None)
                        delta = self.tz.utcoffset(t0, False)
                        t0 += delta
                        if t0 > dt:
                            lat = (latx + float(p.get('lat'))) / 2
                            lon = (lonx + float(p.get('lon'))) / 2
                            ele = (elex + float(p.findtext(ns + 'ele'))) / 2
                            break
                        else:
                            latx = float(p.get('lat'))
                            lonx = float(p.get('lon'))
                            elex = float(p.findtext(ns + 'ele'))
                    except Exception:
                        latx = lonx = elex = None
                        pass

        return (lat,lon,ele)

class Bookmarksfile(object):
    """
    An object representing a bookmarks file, which is a GPX file containing
    <wpt> elements. The bookmarks are kept in a dictionary for easy mapping to
    GtkMenuItems, and only converted to an XML tree when saving to disk.
    """

    tree = None
    filename = None
    bookmarks = {}

    def __init__(self, filename):
        """
        Import a GPX file containing waypoints. Silenty ignore failure.
        """
        self.filename = filename
        try:
            tree = etree.parse(self.filename)
            self.parse_wpt(tree)
        except Exception as e:
            pass

    def parse_wpt(self, tree):
        """
        Construct a dictionary from <wpt> elements from a given ElementTree
        """
        root = tree.getroot()
        waypoints = root.findall(ns + 'wpt')
        for wpt in waypoints:
            # If lat/lon cannot be converted to float, skip this entry
            try:
                bookmark = {}
                bookmark['name'] = wpt.findtext(ns + 'name')
                bookmark['latitude'] = float(wpt.get('lat'))
                bookmark['longitude'] = float(wpt.get('lon'))
            except ValueError:
                continue
            self.bookmarks[self.make_bm_id()] = bookmark

    def save(self):
        """
        Save the internal bookmarks dictionary to a GPX file, converting
        bookmark names to unicode on the fly
        """
        tree = etree.ElementTree(etree.fromstring(minimal_xml))
        root = tree.getroot()
        for bm_id, bm in self.bookmarks.items():
            wpt = etree.Element(ns + 'wpt', lat=str(bm['latitude']), lon=str(bm['longitude']))
            name = etree.Element(ns + 'name')
            if isinstance(bm['name'], unicode):
                name.text = bm['name']
            else:
                name.text = bm['name'].decode('utf-8')
            wpt.append(name)
            root.append(wpt)
        tree.write(self.filename, xml_declaration = True, encoding='utf-8')

    def add(self, bookmark):
        """
        Add a bookmark and save
        """
        self.bookmarks[self.make_bm_id()] = bookmark
        self.save()

    def delete(self, bm_id):
        """
        Delete a bookmark and save
        """
        if bm_id in self.bookmarks:
            del(self.bookmarks[bm_id])
            self.save()

    def make_bm_id(self):
        """
        Generate a simple ID for a new bookmark, to be used as the name of
        the corresponding GtkMenuItem
        """
        return "bookmark%d" % (len(self.bookmarks) + 1)

    def find(self, name):
        """
        Find bookmarks by name in an ElementTree using XPath
        Method is not currently in use
        """
        nsmap = {'ns0': ns}
        wpt = self.tree.xpath("/ns0:gpx/ns0:wpt[descendant::ns0:name[contains(., \"%s\")]]" % name,
                namespaces=nsmap)
