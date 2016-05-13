# -*- coding: utf-8 -*-
# helpers.py
# Helper functions for blivet-gui dialogs
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

import os

from ..i18n import _

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from blivet import devicefactory, formats
# from blivet.devices.btrfs import BTRFSDevice
# from blivet.devices.lvm import LVMVolumeGroupDevice, LVMLogicalVolumeDevice

from blivet.tasks.fslabeling import Ext2FSLabeling, FATFSLabeling, JFSLabeling, ReiserFSLabeling, XFSLabeling, NTFSLabeling

# ---------------------------------------------------------------------------- #


def adjust_scrolled_size(scrolledwindow, width_limit, height_limit):
    """ Adjust size of Gtk.ScrolledWindow -- show scrollbars only when its size
        would be bigger than limits

        :param scrolledwindow: Gtk.ScrolledWindow
        :type scrolledwindow: Gtk.ScrolledWindow
        :param width_limit: width limit px
        :type width_limit: int
        :param height_limit: height limit in px
        :type height_limit: int

    """

    width = scrolledwindow.size_request().width
    height = scrolledwindow.size_request().height

    if width < width_limit and height < height_limit:
        scrolledwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
    elif width < width_limit and height >= height_limit:
        scrolledwindow.set_size_request(width, height_limit)
        scrolledwindow.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    elif width >= width_limit and height < height_limit:
        scrolledwindow.set_size_request(width_limit, height)
        scrolledwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    else:
        scrolledwindow.set_size_request(width_limit, height_limit)
        scrolledwindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)


def is_name_valid(_device_type, _name):
    # temporarily disabled because of changes in blivet
    # if device_type in ("lvmvg", "lvm"):
    #     return LVMVolumeGroupDevice.is_name_valid(name)
    # elif device_type == "lvmlv":
    #     return LVMLogicalVolumeDevice.is_name_valid(name)
    # elif device_type in ("btrfs volume", "btrfs subvolume"):
    #     return BTRFSDevice.is_name_valid(name)
    # else:
    #     return True
    return True  # FIXME


def is_label_valid(format_type, label):
    if format_type in ("ext2", "ext3", "ext4"):
        return Ext2FSLabeling.label_format_ok(label)
    elif format_type == "vfat":
        return FATFSLabeling.label_format_ok(label)
    elif format_type == "jfs":
        return JFSLabeling.label_format_ok(label)
    elif format_type == "raiserfs":
        return ReiserFSLabeling.label_format_ok(label)
    elif format_type == "xfs":
        return XFSLabeling.label_format_ok(label)
    elif format_type == "ntfs":
        return NTFSLabeling.label_format_ok(label)
    else:
        return True


def is_mountpoint_valid(used_mountpoints, mountpoint):
    """ Kickstart mode; check for duplicate mountpoints

        :param used_mountpoints: list of mountpoints currently in use
        :type used_mountpoints: list of str
        :param mountpoint: mountpoint selected by user
        :type mountpoint: str
        :returns: mountpoint validity and error msg
        :rtype: (bool, str or None)
    """

    if not mountpoint:
        return (True, None)

    if not os.path.isabs(mountpoint):
        msg = _("\"{0}\" is not a valid mountpoint.").format(mountpoint)
        return (False, msg)

    if mountpoint not in used_mountpoints:
        return (True, None)

    else:
        msg = _("Selected mountpoint \"{0}\" is already set for another device.").format(mountpoint)
        return (False, msg)


def supported_raids():
    return {"btrfs volume": devicefactory.get_supported_raid_levels(devicefactory.DEVICE_TYPE_BTRFS),
            "mdraid": devicefactory.get_supported_raid_levels(devicefactory.DEVICE_TYPE_MD),
            "lvmlv": devicefactory.get_supported_raid_levels(devicefactory.DEVICE_TYPE_LVM)}


def supported_filesystems():
    _fs_types = []

    for cls in formats.device_formats.values():
        obj = cls()

        supported_fs = (obj.type not in ("tmpfs", "btrfs") and
                        obj.supported and obj.formattable and
                        (isinstance(obj, formats.fs.FS) or
                         obj.type in ("swap", "lvmpv")))
        if supported_fs:
            _fs_types.append(obj.type)

    _fs_types.extend(["unformatted"])

    return sorted(_fs_types)
