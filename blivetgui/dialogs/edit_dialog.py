# -*- coding: utf-8 -*-
# edit_dialog.py
# Gtk.Dialog for editting devices
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

import gettext

from gi.repository import Gtk, Pango

from .add_dialog import SizeChooserArea

#------------------------------------------------------------------------------#

_ = lambda x: gettext.ldgettext("blivet-gui", x)

#------------------------------------------------------------------------------#

SUPPORTED_FS = ["ext2", "ext3", "ext4", "xfs", "reiserfs", "swap", "vfat"]

#------------------------------------------------------------------------------#


class PartitionEditDialog(Gtk.Dialog):
    """ Dialog window allowing user to edit partition including selecting size,
        fs, label etc.
    """

    class UserSelection(object):
        def __init__(self, edit_device, resize, size, fmt, filesystem, mountpoint):

            self.edit_device = edit_device
            self.resize = resize
            self.size = size
            self.format = fmt
            self.filesystem = filesystem
            self.mountpoint = mountpoint

    def __init__(self, parent_window, edited_device, resize_info, kickstart=False):
        """

            :param parent_window: parent window
            :type parent_window: Gtk.Window
            :param partition_name: name of device
            :type partition_name: str
            :param resize_info: is partition resizable, error, min_size, max_size
            :type resize_info: namedtuple
            :param kickstart: kickstart mode
            :type kickstart: bool

        """

        self.edited_device = edited_device
        self.resize_info = resize_info
        self.kickstart = kickstart
        self.parent_window = parent_window

        Gtk.Dialog.__init__(self, _("Edit device"), None, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_transient_for(self.parent_window)
        self.set_resizable(False) # auto shrink after removing/hiding widgets

        self.widgets_dict = {}

        self.grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)
        self.grid.set_border_width(10)

        box = self.get_content_area()
        box.add(self.grid)

        self.size_area = self.add_size_chooser()

        self.show_all()

        self.format_check, self.filesystems_combo = self.add_fs_chooser()

        self.mountpoint_entry = self.add_mountpoint()

        if not self.resize_info.resizable:
            self.hide_widgets(["size"])
            self.size_area.frame.set_tooltip_text(_("This device cannot be resized."))
            self.add_resize_info()
            self.show_widgets(["info"])

        if self.edited_device.type == "partition" and self.edited_device.isExtended:
            self.set_widgets_sensitive(["fs"], False)
            self.format_check.set_tooltip_text(_("Extended partitions cannot be formatted."))

        if self.kickstart:
            self.show_widgets(["mountpoint"])

        self.show_widgets(["fs"])

    def add_resize_info(self):

        width = self.size_area.frame.size_request().width

        label_info = Gtk.Label()
        label_info.set_size_request(width, -1)
        label_info.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        label_info.set_line_wrap(True)

        if self.resize_info.error:
            label_info.set_markup(_("<b>This device cannot be resized:</b>\n<i>{0}</i>").format(self.resize_info.error))

        else:
            label_info.set_markup(_("<b>This device cannot be resized.</b>"))

        table = Gtk.Table(1, 1, False)
        table.attach(label_info, 0, 1, 0, 1, Gtk.AttachOptions.SHRINK | Gtk.AttachOptions.FILL)

        self.grid.attach(table, 0, 1, 6, 1)

        self.widgets_dict["info"] = [table, label_info]

    def add_size_chooser(self):

        size_area = SizeChooserArea(dialog=self, dialog_type="edit", parent_device=None,
                                    max_size=self.resize_info.max_size,
                                    min_size=self.resize_info.min_size,
                                    edited_device=self.edited_device)

        self.grid.attach(size_area.frame, 0, 0, 6, 1)

        self.widgets_dict["size"] = [size_area]

        return size_area

    def add_fs_chooser(self):

        label_format = Gtk.Label(label=_("Format?:"), xalign=1)
        label_format.get_style_context().add_class("dim-label")
        self.grid.attach(label_format, 0, 2, 1, 1)

        format_check = Gtk.CheckButton()
        self.grid.attach(format_check, 1, 2, 1, 1)
        format_check.connect("toggled", self.on_format_changed)

        label_fs = Gtk.Label(label=_("Filesystem:"), xalign=1)
        label_fs.get_style_context().add_class("dim-label")
        self.grid.attach(label_fs, 0, 3, 1, 1)

        filesystems_combo = Gtk.ComboBoxText()
        filesystems_combo.set_entry_text_column(0)
        filesystems_combo.set_sensitive(False)

        self.widgets_dict["fs"] = [label_format, format_check, label_fs, filesystems_combo]

        for fs in SUPPORTED_FS:
            filesystems_combo.append_text(fs)

        self.grid.attach(filesystems_combo, 1, 3, 2, 1)

        return (format_check, filesystems_combo)

    def add_mountpoint(self):

        label_mountpoint = Gtk.Label(label=_("Mountpoint:"), xalign=1)
        label_mountpoint.get_style_context().add_class("dim-label")
        self.grid.attach(label_mountpoint, 0, 4, 1, 1)

        mountpoint_entry = Gtk.Entry()
        self.grid.attach(mountpoint_entry, 1, 4, 2, 1)

        self.widgets_dict["mountpoint"] = [label_mountpoint, mountpoint_entry]

        return mountpoint_entry

    def on_format_changed(self, event):

        if self.format_check.get_active():
            self.filesystems_combo.set_sensitive(True)

        else:
            self.filesystems_combo.set_sensitive(False)

    def update_size_areas(self, size):
        """ Update all size areas to selected size
            (used for raids where all parents has same size)

            .. note:: Copied from AddDialog for future use
        """

        pass

    def show_widgets(self, widget_types):

        for widget_type in widget_types:
            if widget_type == "mountpoint" and not self.kickstart:
                continue

            elif widget_type == "size":
                for widget in self.widgets_dict[widget_type]:
                    widget.set_sensitive(True)

            else:
                for widget in self.widgets_dict[widget_type]:
                    widget.show()

    def hide_widgets(self, widget_types):

        for widget_type in widget_types:
            if widget_type == "mountpoint" and not self.kickstart:
                continue

            elif widget_type == "size":
                for widget in self.widgets_dict[widget_type]:
                    widget.set_sensitive(False)

            else:
                for widget in self.widgets_dict[widget_type]:
                    widget.hide()

    def set_widgets_sensitive(self, widget_types, sensitivity):

        for widget_type in widget_types:
            for widget in self.widgets_dict[widget_type]:
                widget.set_sensitive(sensitivity)

    def get_selection(self):

        if self.kickstart:
            mountpoint = self.mountpoint_entry.get_text()

        else:
            mountpoint = None

        if self.resize_info.resizable:
            resize, size = self.size_area.get_selection()

        else:
            resize = False
            size = None

        return self.UserSelection(edit_device=self.edited_device,
                                  resize=resize,
                                  size=size,
                                  fmt=self.format_check.get_active(),
                                  filesystem=self.filesystems_combo.get_active_text(),
                                  mountpoint=mountpoint)

class LVMEditDialog(Gtk.Dialog):
    """ Dialog window allowing user to edit lvmvg
    """

    class UserSelection(object):
        def __init__(self, edit_device, action_type, parents_list):

            self.edit_device = edit_device
            self.action_type = action_type
            self.parents_list = parents_list

    def __init__(self, parent_window, edited_device, free_pvs, free_disks_regions, removable_pvs):
        """

            :param parent_window: parent window
            :type parent_window: Gtk.Window
            :param edited_device: device selected to edit
            :type edited_device: class blivet.Device

        """

        self.edited_device = edited_device
        self.parent_window = parent_window
        self.free_pvs = free_pvs
        self.free_disks_regions = free_disks_regions
        self.removable_pvs = removable_pvs

        Gtk.Dialog.__init__(self, _("Edit device"), None, 0,
                            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                             Gtk.STOCK_OK, Gtk.ResponseType.OK))

        self.set_transient_for(self.parent_window)
        self.set_resizable(False) # auto shrink after removing/hiding widgets

        self.widgets_dict = {}

        self.grid = Gtk.Grid(column_homogeneous=False, row_spacing=10, column_spacing=5)
        self.grid.set_border_width(10)

        box = self.get_content_area()
        box.add(self.grid)

        self.add_parent_list()
        self.button_add, self.button_remove = self.add_toggle_buttons()

        self.show_all()

        self.add_store = self.add_parents()
        self.remove_store = self.remove_parents()

    def add_parent_list(self):

        parents_store = Gtk.ListStore(str, str, str)

        for parent in self.edited_device.parents:
            parents_store.append([parent.name, "lvmpv", str(parent.size)])

        parents_view = Gtk.TreeView(model=parents_store)
        renderer_text = Gtk.CellRendererText()

        column_name = Gtk.TreeViewColumn(_("Device"), renderer_text, text=0)
        column_type = Gtk.TreeViewColumn(_("Type"), renderer_text, text=1)
        column_size = Gtk.TreeViewColumn(_("Size"), renderer_text, text=2)

        parents_view.append_column(column_name)
        parents_view.append_column(column_type)
        parents_view.append_column(column_size)

        parents_view.set_headers_visible(True)

        label_list = Gtk.Label(label=_("Parent devices:"), xalign=1)
        label_list.get_style_context().add_class("dim-label")

        self.grid.attach(label_list, 0, 1, 1, 1)
        self.grid.attach(parents_view, 1, 1, 3, 3)

    def add_toggle_buttons(self):

        button_add = Gtk.ToggleButton(_("Add parent"))
        self.grid.attach(button_add, 0, 4, 1, 1)

        button_remove = Gtk.ToggleButton(_("Remove parent"))
        self.grid.attach(button_remove, 1, 4, 1, 1)

        button_add.connect("toggled", self.on_button_toggled, "add", button_remove)
        button_remove.connect("toggled", self.on_button_toggled, "remove", button_add)

        return button_add, button_remove

    def add_parents(self):

        if len(self.free_disks_regions) + len(self.free_pvs) == 0:
            label_none = Gtk.Label(label=_("There are currently no empty physical volumes or\n"\
                                           "disks with enough empty space to create one."))
            self.grid.attach(label_none, 0, 5, 4, 1)

            self.widgets_dict["add"] = [label_none]

            return None

        else:
            parents_store = Gtk.ListStore(object, object, bool, str, str, str)
            parents_view = Gtk.TreeView(model=parents_store)

            renderer_toggle = Gtk.CellRendererToggle()
            renderer_toggle.connect("toggled", self.on_cell_toggled, parents_store)

            renderer_text = Gtk.CellRendererText()

            column_toggle = Gtk.TreeViewColumn("Add?", renderer_toggle, active=2)
            column_name = Gtk.TreeViewColumn(_("Device"), renderer_text, text=3)
            column_type = Gtk.TreeViewColumn(_("Type"), renderer_text, text=4)
            column_size = Gtk.TreeViewColumn(_("Size"), renderer_text, text=5)

            parents_view.append_column(column_toggle)
            parents_view.append_column(column_name)
            parents_view.append_column(column_type)
            parents_view.append_column(column_size)

            parents_view.set_headers_visible(True)

            label_list = Gtk.Label(label=_("Available devices:"), xalign=1)
            label_list.get_style_context().add_class("dim-label")

            self.grid.attach(label_list, 0, 5, 1, 1)
            self.grid.attach(parents_view, 1, 5, 4, 3)

            for pv, free in self.free_pvs:
                parents_store.append([pv, free, False, pv.name, "lvmpv", str(free.size)])

            for free in self.free_disks_regions:

                disk = free.parents[0]

                if free.isFreeRegion:
                    parents_store.append([disk, free, False, disk.name, "disk region",
                                          str(free.size)])

                else:
                    parents_store.append([disk, free, False, disk.name, "disk", str(free.size)])

            self.widgets_dict["add"] = [label_list, parents_view]

            return parents_store

    def on_cell_toggled(self, toggle, path, store):
        store[path][2] = not store[path][2]

    def on_cell_radio_toggled(self, toggle, path, store):
        for row in store:
            row[2] = (row.path == Gtk.TreePath(path))

    def remove_parents(self):

        if len(self.removable_pvs) == 0:
            label_none = Gtk.Label(label=_("It's currently not possible to remove\n"\
                                           "a physical volume from existing volume group."))
            self.grid.attach(label_none, 0, 5, 4, 1)

            self.widgets_dict["remove"] = [label_none]

            return None

        else:
            parents_store = Gtk.ListStore(object, object, bool, str, str, str)
            parents_view = Gtk.TreeView(model=parents_store)

            parents_view.set_tooltip_text(_("Currently is possible to remove only one parent "\
                                            "at time."))

            renderer_radio = Gtk.CellRendererToggle()
            renderer_radio.connect("toggled", self.on_cell_radio_toggled, parents_store)
            renderer_radio.set_radio(True)

            renderer_text = Gtk.CellRendererText()

            column_radio = Gtk.TreeViewColumn("Remove?", renderer_radio, active=2)
            column_name = Gtk.TreeViewColumn(_("Device"), renderer_text, text=3)
            column_type = Gtk.TreeViewColumn(_("Type"), renderer_text, text=4)
            column_size = Gtk.TreeViewColumn(_("Size"), renderer_text, text=5)

            parents_view.append_column(column_radio)
            parents_view.append_column(column_name)
            parents_view.append_column(column_type)
            parents_view.append_column(column_size)

            parents_view.set_headers_visible(True)

            label_list = Gtk.Label(label=_("Available devices:"), xalign=1)
            label_list.get_style_context().add_class("dim-label")

            self.grid.attach(label_list, 0, 5, 1, 1)
            self.grid.attach(parents_view, 1, 5, 4, 3)

            for pv in self.removable_pvs:
                parents_store.append([pv, None, False, pv.name, "lvmpv", str(pv.size)])

            self.widgets_dict["remove"] = [label_list, parents_view]

            return parents_store

    def on_button_toggled(self, clicked_button, button_type, other_button):

        if clicked_button.get_active():
            other_button.set_active(False)
            self.show_widgets([button_type])

        else:
            self.hide_widgets([button_type])

    def show_widgets(self, widget_types):

        for widget_type in widget_types:
            for widget in self.widgets_dict[widget_type]:
                widget.show()

    def hide_widgets(self, widget_types):

        for widget_type in widget_types:
            for widget in self.widgets_dict[widget_type]:
                widget.hide()

    def get_selection(self):

        parents_list = []

        if self.button_add.get_active():
            action_type = "add"

            if self.add_store:
                for row in self.add_store:
                    if row[2] and row[0].type == "partition":
                        parents_list.append(row[0])

                    if row[2] and row[0].type == "disk":
                        parents_list.append(row[1])

        elif self.button_remove.get_active():
            action_type = "remove"
            if self.remove_store:
                for row in self.remove_store:
                    if row[2]:
                        parents_list.append(row[0])

        else:
            action_type = None

        return self.UserSelection(edit_device=self.edited_device,
                                  action_type=action_type,
                                  parents_list=parents_list)
