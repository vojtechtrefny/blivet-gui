# rectangle.py
# Gtk.Button modified for device visualization
#
# Copyright (C) 2015  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Vojtech Trefny <vtrefny@redhat.com>
#
# ---------------------------------------------------------------------------- #

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk

from ..i18n import _, P_

import blivet


class Rectangle(Gtk.RadioButton):
    """ Rectangle object """

    def __init__(self, rtype, group, width, height, device, blivet_gui, label=True, parent_size=None):
        self.width = width
        self.height = height

        self.device = device
        self.blivet_gui = blivet_gui

        Gtk.RadioButton.__init__(self, group=group, width_request=width, height_request=height)

        self.set_mode(False)
        self.set_name("bg-" + rtype)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, homogeneous=False, spacing=6)
        self.add(hbox)

        self.device_icons = {"group": ("drive-multidisk-symbolic", _("Group device")),
                             "livecd": ("media-optical-symbolic", _("LiveUSB device")),
                             "encrypted": ("changes-prevent-symbolic", _("Encrypted device (locked)")),
                             "decrypted": ("changes-allow-symbolic", _("Encrypted device (unlocked)")),
                             "empty": ("radio-symbolic", _("Empty device")),
                             "snapshot": ("camera-photo-symbolic", _("Snapshot")),
                             "nodisklabel": ("drive-harddisk-symbolic", _("Missing partition table")),
                             "protected": ("action-unavailable-symbolic", _("Device or format is write protected")),
                             "cached": ("drive-harddisk-solidstate-symbolic", _("Cached device")),
                             "incomplete": ("dialog-warning-symbolic", _("Incomplete device")),
                             "nobtrfsinformation": ("dialog-question-symbolic", _("Missing subvolume information"))}

        if self.device.size == blivet.size.Size(0):
            # TRANSLATORS: size value for device with invalid/unknown size
            devsize = _("unknown")
        elif parent_size is not None and self.device.size > parent_size:
            # TRANSLATORS: size label for a device spanning multiple parents
            # (e.g. RAID), showing per-parent contribution and total size
            devsize = _("{parent_size} of {total_size}").format(
                parent_size=str(parent_size),
                total_size=str(self.device.size))
        else:
            devsize = str(self.device.size)

        if label:
            child_count_str = self._get_child_count_label()
            if child_count_str:
                label_text = "%s \n<small><i>(%s)</i></small>\n%s" % (self.device.name, child_count_str, devsize)
            else:
                label_text = "%s\n%s" % (self.device.name, devsize)

            label_device = Gtk.Label(justify=Gtk.Justification.CENTER,
                                     label="<small>%s</small>" % label_text,
                                     use_markup=True, name="dark")

            hbox.pack_start(child=label_device, expand=True, fill=True, padding=0)

            icons = self._add_device_icons()
            hbox.pack_start(child=icons, expand=False, fill=False, padding=0)

        if self.device.type in ("lvmvg", "btrfs volume", "mdarray", "stratis pool"):
            self.connect("enter-notify-event", self._on_enter_set_cursor)
            self.connect("leave-notify-event", self._on_leave_reset_cursor)
            self.connect("unrealize", self._on_leave_reset_cursor)

    def _on_enter_set_cursor(self, widget, _event):
        display = widget.get_display()
        cursor = Gdk.Cursor.new_from_name(display, "pointer")
        window = widget.get_window()
        if window:
            window.set_cursor(cursor)

    def _on_leave_reset_cursor(self, widget, _event=None):
        window = widget.get_window()
        if window:
            window.set_cursor(None)

    def _add_device_icons(self):
        device_properties = self._get_device_properties()

        icon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, homogeneous=False, spacing=4)
        for prop in device_properties:
            icon = Gtk.Image.new_from_icon_name(self.device_icons[prop][0], Gtk.IconSize.MENU)
            if prop == "group":
                icon.set_tooltip_text(self._get_group_tooltip())
            else:
                icon.set_tooltip_text(self.device_icons[prop][1])
            icon.set_opacity(0.85)
            icon_box.pack_end(child=icon, expand=False, fill=False, padding=0)

        return icon_box

    def _get_group_tooltip(self):
        # TRANSLATORS: tooltip for group device icon with double-click hint
        group_tooltips = {
            "lvmvg": _("LVM2 Volume Group — double-click to view Logical Volumes"),
            "btrfs volume": _("Btrfs Volume — double-click to view subvolumes"),
            "mdarray": _("RAID Array — double-click to view contents"),
            "stratis pool": _("Stratis Pool — double-click to view filesystems"),
        }
        return group_tooltips.get(self.device.type, self.device_icons["group"][1])

    def _get_child_count_label(self):
        count = len(self.device.children)
        if self.device.type == "lvmvg":
            # TRANSLATORS: count of Logical Volumes in a Volume Group, e.g. "3 logical volumes"
            return P_("{count} logical volume", "{count} logical volumes", count).format(count=count)
        elif self.device.type == "btrfs volume":
            # TRANSLATORS: count of subvolumes in a Btrfs volume, e.g. "3 subvolumes"
            return P_("{count} subvolume", "{count} subvolumes", count).format(count=count)
        elif self.device.type == "mdarray" and self.device.format.type == "disklabel":
            # TRANSLATORS: count of partitions on a RAID array, e.g. "3 partitions"
            return P_("{count} partition", "{count} partitions", count).format(count=count)
        elif self.device.type == "stratis pool":
            # TRANSLATORS: count of filesystems in a Stratis pool, e.g. "3 filesystems"
            return P_("{count} filesystem", "{count} filesystems", count).format(count=count)
        return None

    def _get_device_properties(self):
        properties = []
        if self.device.type in ("lvmvg", "btrfs volume", "mdarray", "stratis pool"):
            properties.append("group")
        if self.device.format and self.device.format.type in ("iso9660", "udf"):
            properties.append("livecd")
        if self.device.type == "partition" and self.device.format.type == "luks":
            if self.device.children:
                properties.append("decrypted")
            else:
                properties.append("encrypted")
        if self.device.type == "luks/dm-crypt" or any(parent.type == "luks/dm-crypt" for parent in self.device.parents):
            properties.append("decrypted")
        if self.device.type in ("lvmsnapshot", "btrfs snapshot", "lvmthinsnapshot"):
            properties.append("snapshot")
        if self.device.type == "free space" or (self.device.format and self.device.format.type == "lvmpv" and
                                                not self.device.children):
            properties.append("empty")
        if self.device.type == "free space" and self.device.is_uninitialized_disk:
            properties.append("nodisklabel")

        if self.device.format.exists and self.device.protected:
            properties.append("protected")

        if self.device.type in ("lvmlv", "lvmthinpool") and self.device.cached:
            properties.append("cached")

        if self.device.type in ("mdarray", "lvmvg") and not self.device.complete:
            properties.append("incomplete")

        if self.device.type == "btrfs volume" and self.blivet_gui.auto_dev_updates_warning and \
           not self.device.format.status and not any(sub.format.status for sub in self.device.subvolumes):
            properties.append("nobtrfsinformation")

        return properties
