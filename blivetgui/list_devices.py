# -*- coding: utf-8 -*-
# list_devices.py
# Load and display root and group devices
#
# Copyright (C) 2014  Red Hat, Inc.
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
#------------------------------------------------------------------------------#

from gi.repository import Gtk, GdkPixbuf

import gettext

import sys

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

class ListDevices(object):
    """ List of parent devices
    """

    def __init__(self, blivet_gui):
        """

        :param blivet_gui: instance of BlivetGUI class
        :type blivet_gui: :class:`~.blivetgui.BlivetGUI`

        """

        self.blivet_gui = blivet_gui

        # last selected device from list
        self.last_iter = None

        # currently selected device
        self.selected_device = None

        self.device_list = self.blivet_gui.builder.get_object("liststore_devices")
        num_devices = self.load_devices()

        if not num_devices:
            msg = _("blivet-gui failed to find at least one storage device to work with." \
                "\n\nPlease connect a storage device to your computer and re-run blivet-gui.")
            self.blivet_gui.show_error_dialog(msg)
            sys.exit(0)

        self.disks_view = self.blivet_gui.builder.get_object("treeview_devices")

        selection = self.disks_view.get_selection()
        self.selection_signal = selection.connect("changed", self.on_disk_selection_changed)

    def load_disks(self):
        """ Load disks
        """

        icon_theme = Gtk.IconTheme.get_default()
        icon_disk = Gtk.IconTheme.load_icon(icon_theme, "drive-harddisk", 32, 0)
        icon_disk_usb = Gtk.IconTheme.load_icon(icon_theme, "drive-removable-media", 32, 0)

        disks = self.blivet_gui.client.remote_call("get_disks")

        if disks:
            self.device_list.append([None, None, _("<b>Disks</b>")])

        for disk in disks:
            if disk.removable:
                self.device_list.append([disk, icon_disk_usb, str(disk.name + "\n<i><small>" +
                                                                  str(disk.model) + "</small></i>")])
            else:
                self.device_list.append([disk, icon_disk, str(disk.name + "\n<i><small>" +
                                                              str(disk.model) + "</small></i>")])

        return len(disks)

    def load_lvm_volume_groups(self):
        """ Load LVM2 VGs
        """

        gdevices = self.blivet_gui.client.remote_call("get_group_devices")

        if gdevices:
            self.device_list.append([None, None, _("<b>LVM2 Volume Groups</b>")])

        icon_theme = Gtk.IconTheme.get_default()
        icon_group = Gtk.IconTheme.load_icon(icon_theme, "drive-removable-media", 32, 0)

        for device in gdevices:
            self.device_list.append([device, icon_group,
                                     str(device.name + "\n<i><small>LVM2 VG</small></i>")])

        return len(gdevices)

    def load_devices(self):
        """ Load all devices
        """
        self.device_list.clear()

        devices = 0

        devices += self.load_disks()
        devices += self.load_lvm_volume_groups()

        return devices

    def update_devices_view(self):
        """ Update device view
        """

        # remember previously selected device name
        selection = self.disks_view.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter and model:
            selected_device = model[treeiter][0].name

        # reload devices
        # adding new devices into TreeStore causing "changed" signal being
        # emitted, causing pointless reloading partitions views on all existing
        # devices -> block the selection_signal for now to avoid this
        selection.handler_block(self.selection_signal)
        self.load_devices()
        selection.handler_unblock(self.selection_signal)

        # if the device still exists, select it; else select first device in list
        i = 0
        selected = False

        for device in self.device_list:
            if device[0] != None and device[0].name == selected_device:
                self.disks_view.set_cursor(i)
                selected = True

            i += 1

        if not selected:
            self.disks_view.set_cursor(1)

    def on_disk_selection_changed(self, selection):
        """ Onselect action for devices
        """

        model, treeiter = selection.get_selected()

        if treeiter and model:

            # 'Disks', 'LVM2 Volume Groups' and 'LVM2 Physical Volumes' are just
            # labels. If user select one of these, we need to unselect this and
            # select previous choice
            if model[treeiter][0] == None:
                selection.handler_block(self.selection_signal)
                selection.unselect_iter(treeiter)
                selection.handler_unblock(self.selection_signal)
                selection.select_iter(self.last_iter)
                treeiter = self.last_iter

            else:
                self.last_iter = treeiter

            if self.device_list.iter_is_valid(treeiter):
                self.selected_device = model[treeiter][0]
                self.blivet_gui.update_partitions_view(device_changed=True)
