# -*- coding: utf-8 -*-
# list_partitions.py
# Load and display partitions for selected device
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

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

class ListPartitions(object):
    """ List of childs of selected device
    """

    def __init__(self, blivet_gui):

        self.blivet_gui = blivet_gui

        self.kickstart_mode = self.blivet_gui.kickstart_mode

        self.partitions_list = self.blivet_gui.builder.get_object("liststore_logical")
        self.partitions_view = self.blivet_gui.builder.get_object("treeview_logical")

        self.select = self.partitions_view.get_selection()
        self.on_partition_selection_changed(self.select)

        self.select = self.partitions_view.get_selection()
        self.select.connect("changed", self.on_partition_selection_changed)

        self.selected_partition = None

    def update_partitions_list(self, selected_device):
        """ Update partition view with selected disc children (partitions)

            :param selected_device: selected device from list (eg. disk or VG)
            :type device_name: blivet.Device

        """

        def childs_loop(childs, parent):
            extended_iter = None
            unadded_logical = []

            for child in childs:

                if hasattr(child, "isExtended") and child.isExtended:
                    extended_iter = self.add_partition_to_view(child, parent)

                elif hasattr(child, "isLogical") and child.isLogical:

                    if not extended_iter:
                        unadded_logical.append(child)

                    else:
                        parent_iter = self.add_partition_to_view(child, extended_iter)

                        if child.type not in ("free space",):

                            partitions = self.blivet_gui.client.remote_call("get_partitions", child)

                            if len(partitions) != 0:
                                childs_loop(partitions, parent_iter)

                elif child.type not in ("free space",):

                    partitions = self.blivet_gui.client.remote_call("get_partitions", child)

                    if len(partitions) != 0:
                        parent_iter = self.add_partition_to_view(child, parent)
                        childs_loop(partitions, parent_iter)
                    else:
                        self.add_partition_to_view(child, parent)

                else:
                    self.add_partition_to_view(child, parent)

            if len(unadded_logical) != 0 and extended_iter:
                # if blivet creates extended partition it is sometimes huges mess
                # and we need to be sure they are added in proper way
                for logical in unadded_logical:
                    self.add_partition_to_view(logical, extended_iter)

        self.partitions_list.clear()

        partitions = self.blivet_gui.client.remote_call("get_partitions", selected_device)

        childs_loop(partitions, None)

        # select first line in partitions view
        self.select.select_path("0")

        # expand all expanders
        self.partitions_view.expand_all()

    def add_partition_to_view(self, partition, parent):
        """ Add partition into partition_list

        """

        name = partition.name

        if len(name) > 18:
            name = name[:15] + "..."

        if partition.type == "free space":
            iter_added = self.partitions_list.append(parent, [partition, name, "free_space", "--", str(partition.size), "--"])

        elif partition.type == "partition" and hasattr(partition, "isExtended") \
             and partition.isExtended:
            iter_added = self.partitions_list.append(None, [partition, name, partition.type, _("extended"), str(partition.size), "--"])

        elif partition.type == "lvmvg":
            iter_added = self.partitions_list.append(parent, [partition, name, partition.type, "--", str(partition.size), "--"])

        elif partition.format.mountable:
            iter_added = self.partitions_list.append(parent, [partition, name, partition.type, partition.format.type,
                                                                  str(partition.size), partition.format.systemMountpoint])

        else:
            iter_added = self.partitions_list.append(parent, [partition, name, partition.type, partition.format.type,
                                                              str(partition.size), "--"])

        return iter_added

    def on_right_click_event(self, treeview, event):
        """ Right click event on partition treeview
        """

        if event.button == 3:

            selection = treeview.get_selection()

            if not selection:
                return False

            self.blivet_gui.popup_menu.menu.popup(None, None, None, None, event.button, event.time)

            return True

    def _allow_delete_device(self, device):
        """ Is this device deletable?

            :param device: selected device
            :type device: blivet.Device
            :returns: device possible to delete
            :rtype: bool

        """

        if device.type in ("free space",) or not device.isleaf:
            return False

        else:
            if self.kickstart_mode or not device.format.type:
                return True

            elif device.format.type == "swap":
                return not device.format.status

            else:
                if not device.format.mountable:
                    return True

                else:
                    return not device.format.status

    def _allow_edit_device(self, device):
        """ Is this device editable?

            :param device: selected device
            :type device: blivet.Device
            :returns: device possible to edit
            :rtype: bool

        """

        if device.type not in ("partition", "lvmvg", "lvmlv"):
            return False

        else:
            if device.type == "partition" and device.isExtended:
                return device.format.resizable

            elif self.kickstart_mode:
                return device.format.mountable

            else:
                if device.type in ("lvmvg",):
                    return device.exists

                elif device.format.type in ("btrfs", "lvmpv", "luks", "mdmember"):
                    return False

                else:
                    return not device.format.status

    def activate_action_buttons(self, selected_device):
        """ Activate buttons in toolbar based on selected device

            :param selected_device: Selected partition
            :type selected_device: Gtk.TreeModelRow

        """

        device = selected_device[0]

        self.blivet_gui.deactivate_all_actions()

        if device.type not in ("free space",):
            self.blivet_gui.activate_device_actions(["info"])

        if self._allow_delete_device(device):
            self.blivet_gui.activate_device_actions(["delete"])

        if self._allow_edit_device(device):
            self.blivet_gui.activate_device_actions(["edit"])

        if device.type in ("free space", "btrfs volume", "lvmlv", "lvmthinpool"):
            self.blivet_gui.activate_device_actions(["add"])

        if device.format:
            if device.format.type == "luks" and not device.format.status and device.format.exists:
                self.blivet_gui.activate_device_actions(["decrypt"])

            elif device.format.mountable and device.format.systemMountpoint:
                self.blivet_gui.activate_device_actions(["unmount"])

    def on_partition_selection_changed(self, selection):
        """ On selected partition action
        """

        model, treeiter = selection.get_selected()

        if treeiter != None:
            self.blivet_gui.deactivate_all_actions()
            self.activate_action_buttons(model[treeiter])
            self.selected_partition = model[treeiter]
            self.blivet_gui.device_canvas.update_visualisation()
