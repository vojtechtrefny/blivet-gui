# -*- coding: utf-8 -*-
# actions_toolbar.py
# Toolbar class
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


class BlivetGUIToolbar(object):

    def __init__(self, blivet_gui):
        self.blivet_gui = blivet_gui
        self.buttons = {}

    def activate_buttons(self, button_names):
        """ Activate selected buttons

            :param button_names: names of buttons to activate
            :type button_names: list of str

        """

        for button in button_names:
            if button in self.buttons.keys():
                self.buttons[button].set_sensitive(True)

    def deactivate_buttons(self, button_names):
        """ Deactivate selected buttons

            :param button_names: names of buttons to deactivate
            :type button_names: list of str

        """

        for button in button_names:
            if button in self.buttons.keys():
                self.buttons[button].set_sensitive(False)


class DeviceToolbar(BlivetGUIToolbar):
    """ Create toolbar with action buttons
    """

    def __init__(self, blivet_gui):
        super(DeviceToolbar, self).__init__(blivet_gui)

        items = [("add", "clicked", self.blivet_gui.add_device),
                 ("delete", "clicked", self.blivet_gui.delete_selected_partition),
                 ("resize", "activate", self.blivet_gui.resize_device),
                 ("format", "activate", self.blivet_gui.format_device),
                 ("unmount", "clicked", self.blivet_gui.umount_partition),
                 ("decrypt", "clicked", self.blivet_gui.decrypt_device),
                 ("info", "clicked", self.blivet_gui.device_information),
                 ("parents", "activate", self.blivet_gui.edit_lvmvg)]

        for item in items:
            menu_item = self.blivet_gui.builder.get_object("button_" + item[0])
            menu_item.connect(item[1], item[2])
            menu_item.set_sensitive(False)

            self.buttons[item[0]] = menu_item

    def deactivate_all(self):
        """ Deactivate all partition based buttons
        """

        for button in self.buttons:
            self.buttons[button].set_sensitive(False)


class ActionsToolbar(BlivetGUIToolbar):

    def __init__(self, blivet_gui):
        super(ActionsToolbar, self).__init__(blivet_gui)

        self.toolbar = self.blivet_gui.builder.get_object("vbox_topbar")

        button_apply = self.blivet_gui.builder.get_object("button_apply")
        button_apply.connect("clicked", self.blivet_gui.apply_event)
        self.buttons["apply"] = button_apply

        button_clear = self.blivet_gui.builder.get_object("button_clear")
        button_clear.connect("clicked", self.blivet_gui.clear_actions)
        self.buttons["clear"] = button_clear

        button_back = self.blivet_gui.builder.get_object("button_back")
        button_back.connect("clicked", self.blivet_gui.actions_undo)
        self.buttons["undo"] = button_back

    def deactivate_all(self):
        pass
