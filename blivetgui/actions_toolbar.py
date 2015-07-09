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
#------------------------------------------------------------------------------#

from gi.repository import Gtk

import gettext

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

class ActionsToolbar(object):
    """ Create toolbar with action buttons
    """

    def __init__(self, blivet_gui):
        self.blivet_gui = blivet_gui

        # Dict to translate button names (str) to buttons (Gtk.ToolButton)
        self.buttons = {}

        toolbutton_add = self.blivet_gui.builder.get_object("toolbutton_add")
        toolbutton_add.connect("clicked", self.blivet_gui.add_partition)
        self.buttons["add"] = toolbutton_add

        toolbutton_remove = self.blivet_gui.builder.get_object("toolbutton_remove")
        toolbutton_remove.connect("clicked", self.blivet_gui.delete_selected_partition)
        self.buttons["delete"] = toolbutton_remove

        toolbutton_edit = self.blivet_gui.builder.get_object("toolbutton_edit")
        toolbutton_edit.connect("clicked", self.blivet_gui.edit_device)
        self.buttons["edit"] = toolbutton_edit

        toolbutton_unmount = self.blivet_gui.builder.get_object("toolbutton_unmount")
        toolbutton_unmount.connect("clicked", self.blivet_gui.umount_partition)
        self.buttons["unmount"] = toolbutton_unmount

        toolbutton_decrypt = self.blivet_gui.builder.get_object("toolbutton_decrypt")
        toolbutton_decrypt.connect("clicked", self.blivet_gui.decrypt_device)
        self.buttons["decrypt"] = toolbutton_decrypt

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

    def deactivate_all(self):
        """ Deactivate all partition based buttons
        """

        for button in self.buttons:
            self.buttons[button].set_sensitive(False)
