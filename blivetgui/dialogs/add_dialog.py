# -*- coding: utf-8 -*-
# add_dialog.py
# Gtk.Dialog for adding new device
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

from __future__ import print_function

import os

import gettext

from gi.repository import Gtk, Gdk

from blivet import size

from ..dialogs import message_dialogs

from ..blivetguiproxy.proxy_utils import ProxyDataContainer

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

SUPPORTED_FS = ["ext2", "ext3", "ext4", "xfs", "reiserfs", "swap", "vfat", "ntfs"]
SUPPORTED_UNITS = ["B", "kB", "MB", "GB", "TB", "kiB", "MiB", "GiB", "TiB"]
SUPPORTED_PESIZE = ["2 MiB", "4 MiB", "8 MiB", "16 MiB", "32 MiB", "64 MiB"]

#------------------------------------------------------------------------------#

def get_size_precision(down_limit, up_limit):
    """ Get precision for scale
    """

    step = 1.0
    digits = 0

    while True:
        if down_limit >= 1.0:
            break

        down_limit *= 10
        step /= 10
        digits += 1

    # always offer at least 10 steps to adjust size
    if up_limit - down_limit < 10*step:
        step /= 10
        digits += 1

    return step, digits

def check_mountpoint(parent_window, used_mountpoints, mountpoint):
    """ Kickstart mode; check for duplicate mountpoints

        :param used_mountpoints: list of mountpoints currently in use
        :type used_mountpoints: list of str
        :param mountpoint: mountpoint selected by user
        :type mountpoint: str
        :returns: mountpoint validity
        :rtype: bool
    """

    if not mountpoint:
        return True

    elif not os.path.isabs(mountpoint):

        msg = _("{0} is not a valid mountpoint.").format(mountpoint)
        message_dialogs.ErrorDialog(parent_window, msg)


    elif mountpoint not in used_mountpoints:
        return True

    else:

        old_device = used_mountpoints[mountpoint]

        title = _("Duplicate mountpoint detected")
        msg = _("Selected mountpoint \"{0}\" is already used for \"{1}\" " \
                "device. Do you want to remove this mountpoint?").format(mountpoint, old_device.name)

        dialog = message_dialogs.ConfirmDialog(parent_window, title, msg)

        response = dialog.run()

        if response:
            old_device.format.mountpoint = None

        return response

class SizeChooserArea(object):

    def __init__(self, dialog, dialog_type, parent_device, max_size, min_size, free_device=None, edited_device=None):
        """

            :param dialog: AddDialog or EditDialog instanace
            :type dialog: blivetgui.add_dialog.AddDialog/EditDialog
            :param device_device: device the free space is on
            :type device_device: blivet.Device
            :param free_device: free space
            :type free_device: blivetgui.utils.FreeSpaceDevice
            :param max_size: maximum size that user can choose
            :type max_size: blivet.Size
            :param min_size: minimum size that user can choose (e.g. min size
                for this device/format type)
            :type min_size: blivet.Size

        """

        self.dialog = dialog
        self.dialog_type = dialog_type
        self.parent_device = parent_device
        self.free_device = free_device
        self.edited_device = edited_device
        self.max_size = max_size
        self.min_size = min_size

        self.widgets = []

        self.selected_unit = None

        self.resize = False

        self.frame = Gtk.Frame()

        if self.dialog_type == "add":
            self.frame.set_label(self.parent_device.name)

        elif self.dialog_type == "edit":
            self.frame.set_label(self.edited_device.name)

        self.frame_grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)

        self.frame.add(self.frame_grid)

        self.widgets.extend([self.frame, self.frame_grid])

        self.scale, self.spin_size, self.unit_chooser = self.add_size_widgets()

    def add_size_widgets(self, unit="MiB"):

        scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL,
                          adjustment=Gtk.Adjustment(0, self.min_size.convertTo(size.parseUnits(unit, False)),
                                                       self.max_size.convertTo(size.parseUnits(unit, False)),
                                                       1, 10, 0))

        scale.set_margin_left(10)
        scale.set_margin_bottom(5)

        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.START)
        scale.set_digits(0)
        scale.add_mark(self.min_size.convertTo(size.parseUnits(unit, False)), Gtk.PositionType.BOTTOM,
            str(self.min_size))

        if self.dialog_type == "add":

            scale.set_value(self.max_size.convertTo(size.parseUnits(unit, False)))

            if self.max_size < self.free_device.size:
                scale.add_mark(self.max_size.convertTo(size.parseUnits(unit, False)),
                    Gtk.PositionType.BOTTOM,
                    str(self.max_size) + " of " + str(self.free_device.size))

            else:
                scale.add_mark(self.max_size.convertTo(size.parseUnits(unit, False)),
                    Gtk.PositionType.BOTTOM,
                    str(self.max_size))

        if self.dialog_type == "edit":

            scale.set_value(self.edited_device.size.convertTo(size.parseUnits(unit, False)))
            scale.add_mark(self.max_size.convertTo(size.parseUnits(unit, False)),
                Gtk.PositionType.BOTTOM,
                str(self.max_size))

        self.frame_grid.attach(scale, 0, 0, 4, 3)

        label_size = Gtk.Label(label=_("Volume size:"), xalign=1)
        label_size.get_style_context().add_class("dim-label")
        self.frame_grid.attach(label_size, 4, 1, 1, 1)

        spin_size = Gtk.SpinButton(adjustment=Gtk.Adjustment(0,
            self.min_size.convertTo(size.parseUnits(unit, False)),
            self.max_size.convertTo(size.parseUnits(unit, False)), 1, 10, 0))

        spin_size.set_numeric(True)

        if self.dialog_type == "add":
            spin_size.set_value(self.max_size.convertTo(size.parseUnits(unit, False)))

        elif self.dialog_type == "edit":
            spin_size.set_value(self.edited_device.size.convertTo(size.parseUnits(unit, False)))

        self.frame_grid.attach(spin_size, 5, 1, 1, 1)

        unit_chooser = self.add_unit_chooser(unit)
        self.frame_grid.attach(unit_chooser, 6, 1, 1, 1)

        scale.connect("value-changed", self.scale_moved, spin_size)
        spin_size.connect("value-changed", self.spin_size_moved, scale)

        scale.set_size_request(250, -1)
        scale.set_margin_right(18)

        self.widgets.extend([scale, label_size, spin_size, unit_chooser])

        return scale, spin_size, unit_chooser

    def add_unit_chooser(self, default_unit):

        unit_chooser = Gtk.ComboBoxText()
        unit_chooser.set_margin_right(10)

        for unit in SUPPORTED_UNITS:
            unit_chooser.append_text(unit)

        self.selected_unit = default_unit

        unit_chooser.set_active(SUPPORTED_UNITS.index(default_unit))
        unit_chooser.connect("changed", self.on_unit_combo_changed)

        return unit_chooser

    def adjust_size_scale(self, selected_size, unit="MiB"):

        self.scale.set_range(self.min_size.convertTo(size.parseUnits(unit, False)),
                             self.max_size.convertTo(size.parseUnits(unit, False)))
        self.scale.clear_marks()

        increment, digits = get_size_precision(self.min_size.convertTo(size.parseUnits(unit, False)),
            self.max_size.convertTo(size.parseUnits(unit, False)))
        self.scale.set_increments(increment, increment*10)
        self.scale.set_digits(digits)

        self.scale.add_mark(0, Gtk.PositionType.BOTTOM,
            format(self.min_size.convertTo(size.parseUnits(unit, False)), "." + str(digits) + "f"))
        self.scale.add_mark(float(self.max_size.convertTo(size.parseUnits(unit, False))), Gtk.PositionType.BOTTOM,
            format(self.max_size.convertTo(size.parseUnits(unit, False)), "." + str(digits) + "f"))

        self.spin_size.set_range(self.min_size.convertTo(size.parseUnits(unit, False)),
                                 self.max_size.convertTo(size.parseUnits(unit, False)))
        self.spin_size.set_increments(increment, increment*10)
        self.spin_size.set_digits(digits)

        self.scale.set_value(selected_size.convertTo(size.parseUnits(unit, False)))

    def set_selected_size(self, selected_size):
        self.scale.set_value(selected_size.convertTo(size.parseUnits(self.selected_unit, False)))

    def get_selected_size(self):
        return size.Size(str(self.scale.get_value()) + " " + self.selected_unit)

    def on_unit_combo_changed(self, combo):

        new_unit = combo.get_active_text()
        old_unit = self.selected_unit
        self.selected_unit = new_unit

        selected_size = size.Size(str(self.scale.get_value()) + " " + old_unit)

        self.adjust_size_scale(selected_size, new_unit)
        return

    def scale_moved(self, scale, spin_size):

        self.resize = True and self.dialog_type == "edit"

        spin_size.set_value(scale.get_value())

        selected_size = size.Size(str(self.scale.get_value()) + " " + self.selected_unit)

        self.dialog.update_size_areas(selected_size)

    def spin_size_moved(self, spin_size, scale):
        scale.set_value(spin_size.get_value())

    def destroy(self):
        for widget in self.widgets:
            widget.hide()
            widget.destroy()

    def show(self):
        for widget in self.widgets:
            widget.show()

    def hide(self):
        for widget in self.widgets:
            widget.hide()

    def set_sensitive(self, sensitivity):
        for widget in self.widgets:
            widget.set_sensitive(sensitivity)

    def get_selection(self):

        selected_size = size.Size(str(self.scale.get_value()) + " " + self.selected_unit)

        if self.dialog_type == "add":
            if selected_size > self.free_device.size:
                selected_size = self.free_device.size

            return [self.parent_device, selected_size]

        if self.dialog_type == "edit":

            return (self.resize, selected_size)

class AdvancedOptions(object):

    def __init__(self, add_dialog, device_type, parent_device, free_device,
        has_extended):

        self.add_dialog = add_dialog
        self.device_type = device_type
        self.parent_device = parent_device
        self.free_device = free_device
        self.has_extended = has_extended

        self.expander = Gtk.Expander(label=_("Show advanced options"))
        self.grid = Gtk.Grid(column_homogeneous=False, row_spacing=10,
            column_spacing=5)
        self.grid.set_border_width(15)
        self.expander.add(self.grid)

        self.widgets = [self.expander, self.grid]

        if self.device_type in ("lvm", "lvmvg"):
            self.pesize_combo = self.lvm_options()

        elif self.device_type == "partition":
            self.partition_combo = self.partition_options()

    def lvm_options(self):

        label_pesize = Gtk.Label(label=_("PE Size:"), xalign=1)
        label_pesize.get_style_context().add_class("dim-label")
        self.grid.attach(label_pesize, 0, 0, 1, 1)

        pesize_combo = Gtk.ComboBoxText()
        pesize_combo.set_entry_text_column(0)
        pesize_combo.set_id_column(0)

        for pesize in SUPPORTED_PESIZE:
            pesize_combo.append_text(pesize)

        pesize_combo.set_active_id("4 MiB")

        self.grid.attach(pesize_combo, 1, 0, 2, 1)

        self.widgets.extend([label_pesize, pesize_combo])

        return pesize_combo

    def partition_options(self):

        label_pt_type = Gtk.Label(label=_("Partition type:"), xalign=1)
        label_pt_type.get_style_context().add_class("dim-label")
        self.grid.attach(label_pt_type, 0, 0, 1, 1)

        partition_store = Gtk.ListStore(str, str)

        types = []

        if self.free_device.isLogical:
            types = [(_("Logical"), "logical")]

        elif self.has_extended:
            types = [(_("Primary"), "primary")]

        elif self.parent_device.format.labelType in ("gpt",):
            types = [(_("Primary"), "primary")]

        else:
            types = [(_("Primary"), "primary"), (_("Extended"), "extended")]

        for part_type in types:
            partition_store.append(part_type)

        partition_combo = Gtk.ComboBox.new_with_model(partition_store)
        partition_combo.set_entry_text_column(0)

        self.grid.attach(partition_combo, 1, 0, 2, 1)
        renderer_text = Gtk.CellRendererText()
        partition_combo.pack_start(renderer_text, True)
        partition_combo.add_attribute(renderer_text, "text", 0)
        partition_combo.set_id_column(1)

        partition_combo.set_active(0)
        partition_combo.connect("changed", self.on_partition_type_changed)

        self.widgets.extend([label_pt_type, partition_combo])

        return partition_combo

    def on_partition_type_changed(self, combo):

        part_type = combo.get_active_id()

        if part_type == "extended":
            self.add_dialog.hide_widgets(["fs", "encrypt", "label"])

        else:
            self.add_dialog.show_widgets(["fs", "encrypt", "label"])

    def destroy(self):
        for widget in self.widgets:
            widget.hide()
            widget.destroy()

    def show(self):
        for widget in self.widgets:
            widget.show()

    def hide(self):
        for widget in self.widgets:
            widget.hide()

    def set_sensitive(self, sensitivity):
        for widget in self.widgets:
            widget.set_sensitive(sensitivity)

    def get_selection(self):

        if self.device_type in ("lvm", "lvmvg"):
            return {"pesize" : size.Size(self.pesize_combo.get_active_text())}

        elif self.device_type in ("partition"):
            return {"parttype" : self.partition_combo.get_active_id()}

class AddDialog(Gtk.Dialog):
    """ Dialog window allowing user to add new partition including selecting
         size, fs, label etc.
    """

    def __init__(self, parent_window, parent_type, parent_device, free_device, free_pvs,
                 free_disks_regions, supported_raids, has_extended, mountpoints,
                 kickstart_mode=False):
        """

            :param str parent_type: type of (future) parent device
            :parama parent_device: future parent device
            :type parent_device: :class:`blivet.Device` instances
            :param free_device: selected free space device
            :type free_device: :class:`blivetgui.utils.FreeSpaceDevice` instances
            :param list free_pvs: list PVs with no VG
            :param free_disks_regions: list of free regions on non-empty disks
            :type free_disks_regions: list of :class:`blivetgui.utils.FreeSpaceDevice` instances
            :param list mountpoints: list of mountpoints in current devicetree
            :param bool kickstart_mode: kickstart mode

          """

        self.parent_window = parent_window

        self.parent_type = parent_type
        self.free_device = free_device
        self.parent_device = parent_device

        self.free_pvs = free_pvs
        self.free_disks_regions = free_disks_regions

        self.kickstart_mode = kickstart_mode

        self.supported_raids = supported_raids
        self.has_extended = has_extended
        self.mountpoints = mountpoints

        Gtk.Dialog.__init__(self, _("Create new device"), None, 0,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_transient_for(self.parent_window)

        self.set_resizable(False) # auto shrink after removing widgets

        self.grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)
        self.grid.set_border_width(10)

        self.box = self.get_content_area()
        self.box.add(self.grid)

        self.widgets_dict = {}

        # do we have free_type_chooser?
        self.free_type_chooser = None

        self.filesystems_combo = self.add_fs_chooser()
        self.label_entry, self.name_entry = self.add_name_chooser()
        self.encrypt_check, self.pass_entry = self.add_encrypt_chooser()
        self.parents_store = self.add_parent_list()

        self.raid_combo, self.raid_changed_signal = self.add_raid_type_chooser()

        if kickstart_mode:
            self.mountpoint_entry = self.add_mountpoint()

        self.devices_combo = self.add_device_chooser()
        self.devices_combo.connect("changed", self.on_devices_combo_changed)

        self.size_areas = []
        self.size_grid, self.size_scroll = self.add_size_areas()

        self.advanced = None

        self.md_type_combo = self.add_md_type_chooser()

        self.show_all()
        self.devices_combo.set_active(0)

        ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        ok_button.connect("clicked", self.on_ok_clicked)

    def add_device_chooser(self):

        map_type_devices = {
            "disk" : [(_("Partition"), "partition"), (_("LVM2 Storage"), "lvm"),
            (_("LVM2 Physical Volume"), "lvmpv")],
            "lvmpv" : [(_("LVM2 Volume Group"), "lvmvg")],
            "lvmvg" : [(_("LVM2 Logical Volume"), "lvmlv"), (_("LVM2 ThinPool"), "lvmthinpool")],
            "luks/dm-crypt" : [(_("LVM2 Volume Group"), "lvmvg")],
            "mdarray" : [(_("LVM2 Volume Group"), "lvmvg")],
            "btrfs volume" : [(_("Btrfs Subvolume"), "btrfs subvolume")],
            "lvmlv" : [(_("LVM2 Snaphost"), "lvm snapshot")],
            "lvmthinpool" : [(_("LVM2 Thin Logical Volume"), "lvmthinlv")]
            }

        label_devices = Gtk.Label(label=_("Device type:"), xalign=1)
        label_devices.get_style_context().add_class("dim-label")
        self.grid.attach(label_devices, 0, 0, 1, 1)

        if self.parent_type == "disk" and self.free_device.isLogical:
            devices = [(_("Partition"), "partition"), (_("LVM2 Storage"), "lvm"),
                       (_("LVM2 Physical Volume"), "lvmpv")]

        elif self.parent_type == "disk" and not self.parent_device.format.type \
            and self.free_device.size > size.Size("256 MiB"):
            devices = [(_("Btrfs Volume"), "btrfs volume")]

        else:
            devices = map_type_devices[self.parent_type]

            if self.parent_type == "disk" and len(self.free_disks_regions) > 1:
                devices.append((_("Software RAID"), "mdraid"))

            if self.parent_type == "disk" and self.free_device.size > size.Size("256 MiB"):
                devices.append((_("Btrfs Volume"), "btrfs volume"))

        devices_store = Gtk.ListStore(str, str)

        for device in devices:
            devices_store.append([device[0], device[1]])

        devices_combo = Gtk.ComboBox.new_with_model(devices_store)
        devices_combo.set_entry_text_column(0)

        if len(devices) == 1:
            devices_combo.set_sensitive(False)

        self.grid.attach(devices_combo, 1, 0, 2, 1)
        renderer_text = Gtk.CellRendererText()
        devices_combo.pack_start(renderer_text, True)
        devices_combo.add_attribute(renderer_text, "text", 0)

        return devices_combo

    def add_parent_list(self):

        parents_store = Gtk.ListStore(object, object, bool, bool, str, str, str)

        parents_view = Gtk.TreeView(model=parents_store)

        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.connect("toggled", self.on_cell_toggled)

        renderer_text = Gtk.CellRendererText()

        column_toggle = Gtk.TreeViewColumn(None, renderer_toggle, active=3)
        column_name = Gtk.TreeViewColumn(_("Device"), renderer_text, text=4)
        column_type = Gtk.TreeViewColumn(_("Type"), renderer_text, text=5)
        column_size = Gtk.TreeViewColumn(_("Size"), renderer_text, text=6)

        parents_view.append_column(column_toggle)
        parents_view.append_column(column_name)
        parents_view.append_column(column_type)
        parents_view.append_column(column_size)

        parents_view.set_headers_visible(True)

        label_list = Gtk.Label(label=_("Available devices:"), xalign=1)
        label_list.get_style_context().add_class("dim-label")

        self.grid.attach(label_list, 0, 2, 1, 1)
        self.grid.attach(parents_view, 1, 2, 4, 3)

        return parents_store

    def update_raid_type_chooser(self):

        device_type = self._get_selected_device_type()
        num_parents = self._get_number_selected_parents()

        if device_type not in self.supported_raids.keys() or num_parents == 1:
            for widget in self.widgets_dict["raid"]:
                widget.hide()

            return

        else:
            # save previously selected raid type
            selected = self.raid_combo.get_active_text()

            self.raid_combo.handler_block(self.raid_changed_signal)
            self.raid_combo.remove_all()

            for raid in self.supported_raids[device_type]:
                if raid.name == "container":
                    continue
                if num_parents >= raid.min_members:
                    self.raid_combo.append_text(raid.name)

            self.raid_combo.handler_unblock(self.raid_changed_signal)

            for widget in self.widgets_dict["raid"]:
                widget.show()

            if selected:
                if self.raid_combo.set_active_id(selected):
                    # set_active_id returns bool
                    return

            if device_type == "btrfs volume":
                self.raid_combo.set_active_id("single")

            else:
                self.raid_combo.set_active_id("linear")

        return

    def on_raid_type_changed(self, _event):
        self.size_grid, self.size_scroll = self.add_size_areas()

    def add_raid_type_chooser(self):

        label_raid = Gtk.Label(label=_("RAID Level:"), xalign=1)
        label_raid.get_style_context().add_class("dim-label")
        self.grid.attach(label_raid, 0, 5, 1, 1)

        raid_combo = Gtk.ComboBoxText()
        raid_combo.set_entry_text_column(0)
        raid_combo.set_id_column(0)

        raid_changed_signal = raid_combo.connect("changed", self.on_raid_type_changed)

        self.grid.attach(raid_combo, 1, 5, 1, 1)

        self.widgets_dict["raid"] = [label_raid, raid_combo]

        return raid_combo, raid_changed_signal

    def on_free_space_type_toggled(self, button, name):
        if button.get_active():
            self.update_parent_list(parent_type=name)
            self.update_raid_type_chooser()

            self.size_grid, self.size_scroll = self.add_size_areas()

            if name == "disks":
                self.hide_widgets(["size"])

            else:
                self.show_widgets(["size"])

    def add_free_type_chooser(self):
        label_empty_type = Gtk.Label(label=_("Volumes based on:"), xalign=1)
        label_empty_type.get_style_context().add_class("dim-label")
        self.grid.attach(label_empty_type, 0, 1, 1, 1)

        button1 = Gtk.RadioButton.new_with_label_from_widget(None, _("Disks"))
        button1.connect("toggled", self.on_free_space_type_toggled, "disks")
        self.grid.attach(button1, 1, 1, 1, 1)

        button2 = Gtk.RadioButton.new_with_label_from_widget(button1, _("Partitions"))
        button2.connect("toggled", self.on_free_space_type_toggled, "partitions")
        self.grid.attach(button2, 2, 1, 1, 1)

        label_empty_type.show()
        button1.show()
        button2.show()

        if self.free_device.isUnitializedDisk:
            button1.toggled()
            button1.set_sensitive(False)
            button2.set_sensitive(False)

        elif self.free_device.isFreeRegion:
            button2.set_active(True)
            button1.set_sensitive(False)
            button2.set_sensitive(False)

        else:
            button2.set_active(True)

        self.free_type_chooser = (label_empty_type, button1, button2)

    def _get_free_type(self):
        if self.free_type_chooser:
            button_disks = self.free_type_chooser[1]
            button_partitions = self.free_type_chooser[2]

        else:
            return None

        if button_disks.get_active():
            return "disks"

        elif button_partitions.get_active():
            return "partitions"

        else:
            return None

    def remove_free_type_chooser(self):
        for widget in self.free_type_chooser:
            widget.destroy()

        self.free_type_chooser = None

    def select_selected_free_region(self):
        """ In parent list select the free region user selected checkbox as checked
        """

        # for devices with only one parent just select the first (and only) one
        if len(self.parents_store) == 1:
            self.parents_store[0][2] = self.parents_store[0][3] = True
            return

        for row in self.parents_store:
            dev = row[0]
            free = row[1]

            if dev.name == self.parent_device.name and \
                (not self.free_device.start or self.free_device.start == free.start):
                row[2] = row[3] = True

        # TODO move selected iter at the top of the list

    def update_parent_list(self, parent_type=None):

        self.parents_store.clear()

        device_type = self._get_selected_device_type()

        if device_type == "lvmvg":
            for pv, free in self.free_pvs:
                self.parents_store.append([pv, free, False, False, pv.name,
                    "lvmpv", str(free.size)])

        elif device_type in ("btrfs volume", "lvm", "mdraid"):

            for free in self.free_disks_regions:

                disk = free.parents[0]

                if free.isFreeRegion and (parent_type == "partitions" or device_type in ("lvm", "mdraid")):
                    self.parents_store.append([disk, free, False, False, disk.name,
                        "disk region", str(free.size)])

                elif not free.isFreeRegion:
                    self.parents_store.append([disk, free, False, False, disk.name,
                        "disk", str(free.size)])

        elif device_type in ("lvm snapshot",):
            self.parents_store.append([self.parent_device, self.free_device, False, False,
                self.free_device.parents[0].name, "lvmvg", str(self.free_device.size)])

        else:
            self.parents_store.append([self.parent_device, self.free_device, False, False,
                self.parent_device.name, "disk", str(self.free_device.size)])

        self.select_selected_free_region()

    def on_cell_toggled(self, _event, path):

        if self.parents_store[path][2]:
            pass

        else:
            self.parents_store[path][3] = not self.parents_store[path][3]

            self.size_grid, self.size_scroll = self.add_size_areas()
            self.update_raid_type_chooser()

    def raid_member_max_size(self):

        device_type = self._get_selected_device_type()
        num_parents = self._get_number_selected_parents()

        if device_type not in self.supported_raids.keys() or num_parents == 1:
            return (False, None)

        elif self.raid_combo.get_active_text() in ("linear", "single"):
            return (False, None)

        else:
            max_size = None

            for row in self.parents_store:

                if row[3]:
                    if not max_size:
                        max_size = row[1].size

                    elif row[1].size < max_size:
                        max_size = row[1].size

            return (True, max_size)

    def update_size_areas(self, selected_size):
        """ Update all size areas to selected size
            (used for raids where all parents has same size)
        """

        device_type = self._get_selected_device_type()
        num_parents = self._get_number_selected_parents()

        if device_type not in self.supported_raids.keys() or num_parents == 1:
            return

        elif self.raid_combo.get_active_text() in ("linear", "single"):
            return

        else:
            for area in self.size_areas:
                area.set_selected_size(selected_size)

    def _destroy_size_areas(self):
        """ Remove existing size areas
        """

        self.widgets_dict["size"] = []

        if self.size_areas:
            for area in self.size_areas:
                area.destroy()

            self.size_scroll.destroy()
            self.size_grid.destroy()

            self.size_areas = []

    def add_size_areas(self):
        device_type = self._get_selected_device_type()

        # remove all existing size areas
        self._destroy_size_areas()

        size_scroll = Gtk.ScrolledWindow()
        size_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        self.grid.attach(size_scroll, 0, 6, 6, 1)
        size_scroll.show()

        size_grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)

        size_scroll.add(size_grid)
        size_grid.show()

        posititon = 0

        raid, max_size = self.raid_member_max_size()

        if device_type in ("lvmpv", "lvm", "lvm snapshot"):
            min_size = size.Size("8 MiB")
        elif device_type == "btrfs volume":
            min_size = size.Size("256 MiB")
        else:
            min_size = size.Size("1 MiB")

        for row in self.parents_store:
            if row[3]:
                if not raid:
                    max_size = row[1].size

                area = SizeChooserArea(dialog=self, parent_device=row[0],
                    free_device=row[1], max_size=max_size, min_size=min_size,
                    dialog_type="add")

                size_grid.attach(area.frame, 0, posititon, 1, 1)

                self.widgets_dict["size"].append(area)
                self.size_areas.append(area)

                posititon += 1

        for area in self.size_areas:
            area.show()

            if device_type in ("lvmvg", "btrfs subvolume") or self._get_free_type() == "disks":
                area.set_sensitive(False)

        size_area_height = size_grid.size_request().height
        size_area_width = size_grid.size_request().width
        screen_height = Gdk.Screen.get_default().get_height()
        screen_width = Gdk.Screen.get_default().get_width()
        dialog_height = self.size_request().height

        size_diff = int((screen_height*0.7) - dialog_height)

        if size_diff < 0:
            # dialog is largen than 70 % of screen
            areas_to_display = len(self.size_areas) - (abs(size_diff) / (size_area_height / len(self.size_areas)))

            if areas_to_display < 1:
                size_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

            else:
                if size_area_height > screen_width*0.7:
                    size_scroll.set_size_request(screen_width*0.7,
                        int(size_area_height/len(self.size_areas))*areas_to_display)
                    size_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

                else:
                    size_scroll.set_size_request(size_area_width,
                        int(size_area_height/len(self.size_areas))*areas_to_display)
                    size_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        else:
            if size_area_width > screen_width*0.7:
                size_scroll.set_size_request(screen_width*0.7, size_area_height)
                size_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)

            else:
                size_grid.set_size_request(size_area_width, size_area_height + 20)
                size_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)

        return size_grid, size_scroll

    def add_md_type_chooser(self):
        label_md_type = Gtk.Label(label=_("MDArray type:"), xalign=1)
        label_md_type.get_style_context().add_class("dim-label")
        self.grid.attach(label_md_type, 0, 7, 1, 1)

        md_type_store = Gtk.ListStore(str, str)

        for md_type in ((_("Partition"), "partition"),
            (_("LVM Physical Volume"), "lvmpv")):
            md_type_store.append(md_type)

        md_type_combo = Gtk.ComboBox.new_with_model(md_type_store)
        md_type_combo.set_entry_text_column(0)

        self.grid.attach(md_type_combo, 1, 7, 2, 1)
        renderer_text = Gtk.CellRendererText()
        md_type_combo.pack_start(renderer_text, True)
        md_type_combo.add_attribute(renderer_text, "text", 0)
        md_type_combo.set_id_column(1)

        md_type_combo.set_active_id("partition")
        md_type_combo.connect("changed", self.on_md_type_changed)

        self.widgets_dict["mdraid"] = [label_md_type, md_type_combo]

        return md_type_combo

    def on_md_type_changed(self, _event):
        if self.md_type_combo.get_active_id() == "partition":
            self.show_widgets(["fs"])

        else:
            self.hide_widgets(["fs"])

    def add_fs_chooser(self):
        label_fs = Gtk.Label(label=_("Filesystem:"), xalign=1)
        label_fs.get_style_context().add_class("dim-label")
        self.grid.attach(label_fs, 0, 8, 1, 1)

        filesystems_combo = Gtk.ComboBoxText()
        filesystems_combo.set_entry_text_column(0)

        for fs in SUPPORTED_FS:
            filesystems_combo.append_text(fs)

        self.grid.attach(filesystems_combo, 1, 8, 2, 1)

        filesystems_combo.connect("changed", self.on_filesystems_combo_changed)

        self.widgets_dict["fs"] = [label_fs, filesystems_combo]

        return filesystems_combo

    def on_filesystems_combo_changed(self, combo):
        selection = combo.get_active_text()

        if selection in ("swap",):
            self.hide_widgets(["label", "mountpoint"])

        else:
            device_type = self._get_selected_device_type()

            if device_type == "partition":
                self.show_widgets(["label", "mountpoint"])
            else:
                self.show_widgets(["mountpoint"])

    def add_name_chooser(self):
        label_label = Gtk.Label(label=_("Label:"), xalign=1)
        label_label.get_style_context().add_class("dim-label")
        self.grid.attach(label_label, 0, 9, 1, 1)

        label_entry = Gtk.Entry()
        self.grid.attach(label_entry, 1, 9, 2, 1)

        self.widgets_dict["label"] = [label_label, label_entry]

        name_label = Gtk.Label(label=_("Name:"), xalign=1)
        name_label.get_style_context().add_class("dim-label")
        self.grid.attach(name_label, 0, 9, 1, 1)

        name_entry = Gtk.Entry()
        self.grid.attach(name_entry, 1, 9, 2, 1)

        self.widgets_dict["name"] = [name_label, name_entry]

        return label_entry, name_entry

    def add_mountpoint(self):
        mountpoint_label = Gtk.Label(label=_("Mountpoint:"), xalign=1)
        mountpoint_label.get_style_context().add_class("dim-label")
        self.grid.attach(mountpoint_label, 0, 10, 1, 1)

        mountpoint_entry = Gtk.Entry()
        self.grid.attach(mountpoint_entry, 1, 10, 2, 1)

        self.widgets_dict["mountpoint"] = [mountpoint_label, mountpoint_entry]

        return mountpoint_entry

    def add_encrypt_chooser(self):
        encrypt_label = Gtk.Label(label=_("Encrypt:"), xalign=1)
        encrypt_label.get_style_context().add_class("dim-label")
        self.grid.attach(encrypt_label, 0, 11, 1, 1)

        encrypt_check = Gtk.CheckButton()
        self.grid.attach(encrypt_check, 1, 11, 1, 1)

        self.widgets_dict["encrypt"] = [encrypt_label, encrypt_check]

        pass_label = Gtk.Label(label=_("Passphrase:"), xalign=1)
        pass_label.get_style_context().add_class("dim-label")
        self.grid.attach(pass_label, 0, 12, 1, 1)

        pass_entry = Gtk.Entry()
        pass_entry.set_visibility(False)
        pass_entry.set_property("caps-lock-warning", True)
        self.grid.attach(pass_entry, 1, 12, 2, 1)

        self.widgets_dict["passphrase"] = [pass_label, pass_entry]

        encrypt_check.connect("toggled", lambda event: [pass_entry.set_visible(not pass_entry.get_visible()),
            pass_label.set_visible(not pass_label.get_visible())])

        return encrypt_check, pass_entry

    def add_advanced_options(self):

        device_type = self._get_selected_device_type()

        if self.advanced:
            self.advanced.destroy()

        if device_type in ("lvm", "lvmvg", "partition"):
            self.advanced = AdvancedOptions(self, device_type, self.parent_device,
                self.free_device, self.has_extended)
            self.widgets_dict["advanced"] = [self.advanced]

            self.grid.attach(self.advanced.expander, 0, 13, 6, 1)

        else:
            self.advanced = None
            self.widgets_dict["advanced"] = []

    def show_widgets(self, widget_types):

        for widget_type in widget_types:
            if widget_type == "mountpoint" and not self.kickstart_mode:
                continue

            elif widget_type == "size":
                for widget in self.widgets_dict[widget_type]:
                    widget.set_sensitive(True)

            else:
                for widget in self.widgets_dict[widget_type]:
                    widget.show()

    def hide_widgets(self, widget_types):

        for widget_type in widget_types:
            if widget_type == "mountpoint" and not self.kickstart_mode:
                continue

            elif widget_type == "size":
                for widget in self.widgets_dict[widget_type]:
                    widget.set_sensitive(False)

            else:
                for widget in self.widgets_dict[widget_type]:
                    widget.hide()

    def on_devices_combo_changed(self, _event):

        device_type = self._get_selected_device_type()

        self.update_parent_list()
        self.add_advanced_options()
        self.size_grid, self.size_scroll = self.add_size_areas()
        self.encrypt_check.set_active(False)

        if self.free_type_chooser and device_type != "btrfs volume":
            self.remove_free_type_chooser()

        if device_type == "partition":
            self.show_widgets(["label", "fs", "encrypt", "mountpoint", "size", "advanced"])
            self.hide_widgets(["name", "passphrase", "mdraid"])

            if self.free_device.isLogical:
                self.hide_widgets(["encrypt", "passphrase"])

        elif device_type == "lvmpv":
            self.show_widgets(["encrypt", "size"])
            self.hide_widgets(["name", "label", "fs", "mountpoint", "passphrase", "advanced", "mdraid"])

        elif device_type == "lvm":
            self.show_widgets(["encrypt", "name", "size", "advanced"])
            self.hide_widgets(["label", "fs", "mountpoint", "passphrase", "mdraid"])

        elif device_type == "lvmvg":
            self.show_widgets(["name", "advanced"])
            self.hide_widgets(["label", "fs", "mountpoint", "encrypt", "size", "passphrase", "mdraid"])

        elif device_type in ("lvmlv", "lvmthinlv"):
            self.show_widgets(["name", "fs", "mountpoint", "size"])
            self.hide_widgets(["label", "encrypt", "passphrase", "advanced", "mdraid"])

        elif device_type == "btrfs volume":
            self.show_widgets(["name", "size", "mountpoint"])
            self.hide_widgets(["label", "fs", "encrypt", "passphrase", "advanced", "mdraid"])
            self.add_free_type_chooser()

        elif device_type == "btrfs subvolume":
            self.show_widgets(["name", "mountpoint"])
            self.hide_widgets(["label", "fs", "encrypt", "size", "passphrase", "advanced", "mdraid"])

        elif device_type == "mdraid":
            self.show_widgets(["name", "size", "mountpoint", "fs", "mdraid"])
            self.hide_widgets(["label", "encrypt", "passphrase", "advanced"])

        elif device_type == "lvm snapshot":
            self.show_widgets(["name", "size"])
            self.hide_widgets(["label", "fs", "encrypt", "passphrase", "advanced", "mdraid", "mountpoint"])

        elif device_type == "lvmthinpool":
            self.show_widgets(["name", "size"])
            self.hide_widgets(["label", "fs", "encrypt", "passphrase", "advanced", "mdraid", "mountpoint"])

        self.update_raid_type_chooser()

    def _get_selected_device_type(self):
        tree_iter = self.devices_combo.get_active_iter()

        if tree_iter != None:
            model = self.devices_combo.get_model()
            device_type = model[tree_iter][1]

            return device_type

        else:
            return None

    def _get_number_selected_parents(self):
        num = 0

        for row in self.parents_store:
            if row[3]:
                num += 1

        return num

    def validate_user_input(self):
        """ Validate data input
        """

        user_input = self.get_selection()

        if not user_input.filesystem and user_input.device_type == "partition" \
           and user_input.advanced["parttype"] != "extended":
            msg = _("Filesystem type must be specified when creating new partition.")
            message_dialogs.ErrorDialog(self, msg)

            return False

        elif not user_input.filesystem and user_input.device_type == "lvmlv":
            msg = _("Filesystem type must be specified when creating new logical volume.")
            message_dialogs.ErrorDialog(self, msg)

            return False

        elif user_input.encrypt and not user_input.passphrase:
            msg = _("Passphrase not specified.")
            message_dialogs.ErrorDialog(self, msg)

            return False

        elif user_input.mountpoint and not os.path.isabs(user_input.mountpoint):
            msg = _("\"{0}\" is not a valid mountpoint.").format(user_input.mountpoint)
            message_dialogs.ErrorDialog(self, msg)

            return False

        elif user_input.device_type == "mdraid" and len(user_input.parents) == 1:
            msg = _("Please select at least two parent devices.")
            message_dialogs.ErrorDialog(self, msg)

            return False

        elif self.kickstart_mode and user_input.mountpoint:
            if check_mountpoint(self, self.mountpoints, user_input.mountpoint):
                return True

            else:
                return False

        else:
            return True

    def on_ok_clicked(self, _event):
        if not self.validate_user_input():
            self.run()

    def get_selection(self):
        device_type = self._get_selected_device_type()

        parents = []
        total_size = 0

        for size_area in self.size_areas:
            parents.append(size_area.get_selection())
            total_size += size_area.get_selection()[1]

        if self.free_type_chooser:
            if self.free_type_chooser[1].get_active():
                btrfs_type = "disks"
            elif self.free_type_chooser[2].get_active():
                btrfs_type = "partitions"
        else:
            btrfs_type = None

        if device_type in ("btrfs volume", "lvmlv", "mdraid"):
            raid_level = self.raid_combo.get_active_text()
        else:
            raid_level = None

        if self.kickstart_mode:
            mountpoint = self.mountpoint_entry.get_text()
        else:
            mountpoint = None

        if self.advanced:
            advanced = self.advanced.get_selection()
        else:
            advanced = None

        if device_type == "mdraid" and self.md_type_combo.get_active_id() == "lvmpv":
            filesystem = "lvmpv"
        else:
            filesystem = self.filesystems_combo.get_active_text()

        return ProxyDataContainer(device_type=device_type,
                                  size=total_size,
                                  filesystem=filesystem,
                                  name=self.name_entry.get_text(),
                                  label=self.label_entry.get_text(),
                                  mountpoint=mountpoint,
                                  encrypt=self.encrypt_check.get_active(),
                                  passphrase=self.pass_entry.get_text(),
                                  parents=parents,
                                  btrfs_type=btrfs_type,
                                  raid_level=raid_level,
                                  advanced=advanced)

class AddLabelDialog(Gtk.Dialog):
    """ Dialog window allowing user to add disklabel to disk
    """

    def __init__(self, parent_window, disk_device, disklabels):
        """

            :param parent_window: parent window
            :type parent_window: Gtk.Window
            :param disk_device: disk
            :type disk_device: blivet.DiskDevice
            :param disklabels: available disklabel types
            :type disklabels: list of str

        """

        self.disk_name = disk_device.name
        self.parent_window = parent_window
        self.disklabels = disklabels

        Gtk.Dialog.__init__(self, _("No partition table found on disk"), None, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_transient_for(self.parent_window)

        self.set_border_width(10)

        self.grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)
        self.grid.set_margin_bottom(15)

        box = self.get_content_area()
        box.add(self.grid)

        self.add_labels()
        self.pts_combo = self.add_pt_chooser()

        self.show_all()

    def add_labels(self):

        info_label = Gtk.Label(label=_("A partition table is required before partitions can be added."))
        self.grid.attach(info_label, 0, 0, 4, 1)

    def add_pt_chooser(self):

        pts_store = Gtk.ListStore(str)

        for label in self.disklabels:
            pts_store.append([label])

        pts_store.append(["btrfs"])

        pts_combo = Gtk.ComboBox.new_with_model(pts_store)

        pts_combo.set_entry_text_column(0)
        pts_combo.set_active(0)

        if len(self.disklabels) > 1:
            pts_combo.set_sensitive(True)

        else:
            pts_combo.set_sensitive(False)

        label_list = Gtk.Label(label=_("Select new partition table type:"))
        label_list.get_style_context().add_class("dim-label")

        self.grid.attach(label_list, 0, 1, 2, 1)
        self.grid.attach(pts_combo, 2, 1, 1, 1)

        renderer_text = Gtk.CellRendererText()
        pts_combo.pack_start(renderer_text, True)
        pts_combo.add_attribute(renderer_text, "text", 0)

        return pts_combo

    def get_selection(self):
        tree_iter = self.pts_combo.get_active_iter()

        if tree_iter != None:
            model = self.pts_combo.get_model()
            label = model[tree_iter][0]

        return label
