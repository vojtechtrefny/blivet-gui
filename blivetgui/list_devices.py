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
# ---------------------------------------------------------------------------- #

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .i18n import _

# ---------------------------------------------------------------------------- #


class ListDevices(object):
    """ List of parent devices
    """

    def __init__(self, blivet_gui):
        """

        :param blivet_gui: instance of BlivetGUI class
        :type blivet_gui: :class:`~.blivetgui.BlivetGUI`

        """

        self.blivet_gui = blivet_gui

        self.last_iter = None  # last selected device from list
        self.selected_device = None  # currently selected device

        self.device_list = self.blivet_gui.builder.get_object("liststore_devices")
        self.disks_view = self.blivet_gui.builder.get_object("treeview_devices")

        selection = self.disks_view.get_selection()
        self.selection_signal = selection.connect("changed", self.on_disk_selection_changed)

    def load_devices(self):
        self.device_list.clear()

        self.load_disks()
        self.load_group_devices()

    def load_disks(self):
        """ Load disks
        """

        icon_theme = Gtk.IconTheme.get_default()
        icon_disk = Gtk.IconTheme.load_icon(icon_theme, "drive-harddisk", 32, 0)
        icon_disk_usb = Gtk.IconTheme.load_icon(icon_theme, "drive-removable-media", 32, 0)

        disks = self.blivet_gui.client.remote_call("get_disks")

        if disks:
            self.device_list.append([None, None, "<b>%s</b>" % _("Disks")])

        for disk in disks:
            if disk.removable:
                self.device_list.append([disk, icon_disk_usb, str(disk.name + "\n<i><small>" +
                                                                  str(disk.model) + "</small></i>")])
            else:
                self.device_list.append([disk, icon_disk, str(disk.name + "\n<i><small>" +
                                                              str(disk.model) + "</small></i>")])

    def load_group_devices(self):
        """ Load LVM2 VGs, Btrfs Volumes and MDArrays
        """

        gdevices = self.blivet_gui.client.remote_call("get_group_devices")

        icon_theme = Gtk.IconTheme.get_default()
        icon_group = Gtk.IconTheme.load_icon(icon_theme, "drive-multidisk", 32, 0)

        if gdevices["lvm"]:
            self.device_list.append([None, None, "<b>%s</b>" % _("LVM")])
            for device in gdevices["lvm"]:
                self.device_list.append([device, icon_group, str(device.name + "\n<i><small>LVM2 VG</small></i>")])

        if gdevices["raid"]:
            self.device_list.append([None, None, "<b>%s</b>" % _("RAID")])
            for device in gdevices["raid"]:
                self.device_list.append([device, icon_group, str(device.name + "\n<i><small>MDArray</small></i>")])

        if gdevices["btrfs"]:
            self.device_list.append([None, None, "<b>%s</b>" % _("Btrfs Volumes")])
            for device in gdevices["btrfs"]:
                self.device_list.append([device, icon_group, str(device.name + "\n<i><small>Btrfs Volume</small></i>")])

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
        for idx, device in enumerate(self.device_list):
            if device[0] and device[0].name == selected_device:
                self.disks_view.set_cursor(idx)
                break
        else:
            self.disks_view.set_cursor(1)

    def select_device_by_name(self, device_name):
        for idx, device in enumerate(self.device_list):
            if device[0] and device[0].name == device_name:
                self.disks_view.set_cursor(idx)

    def on_disk_selection_changed(self, selection):
        """ Onselect action for devices
        """

        model, treeiter = selection.get_selected()

        if treeiter and model:

            # 'Disks', 'LVM2 Volume Groups' and 'LVM2 Physical Volumes' are just
            # labels. If user select one of these, we need to unselect this and
            # select previous choice
            if not model[treeiter][0]:
                selection.handler_block(self.selection_signal)
                selection.unselect_iter(treeiter)
                selection.handler_unblock(self.selection_signal)
                selection.select_iter(self.last_iter)
                treeiter = self.last_iter

            else:
                self.last_iter = treeiter

            if self.device_list.iter_is_valid(treeiter):
                self.selected_device = model[treeiter][0]
                self.blivet_gui.update_partitions_view()
                self.blivet_gui.update_physical_view()
