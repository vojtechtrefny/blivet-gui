# -*- coding: utf-8 -*-
# osinstall.py
# blivet-gui code for running in Anaconda installer
#
# Copyright (C) 2016  Red Hat, Inc.
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

from .blivetgui import BlivetGUI
from .list_devices import ListDevices
from .list_partitions import ListPartitions
from .list_parents import ListParents
from .list_actions import ListActions
from .actions_menu import ActionsMenu
from .actions_toolbar import DeviceToolbar
from .visualization.logical_view import LogicalView
from .visualization.physical_view import PhysicalView
from .blivet_utils import BlivetUtils
from .dialogs import message_dialogs

from .gui_utils import locate_ui_file

from contextlib import contextmanager


class BlivetUtilsAnaconda(BlivetUtils):

    def __init__(self, storage):
        # pylint: disable=super-init-not-called

        self.storage = storage


class BlivetGUIAnacondaClient(object):

    def __init__(self, storage):
        self.utils = BlivetUtilsAnaconda(storage)

    def remote_call(self, method, *args):

        utils_method = getattr(self.utils, method, None)
        if utils_method is None:
            raise RuntimeError("Unknown utils method %s" % method)

        return utils_method(*args)


class BlivetGUIAnaconda(BlivetGUI):

    installer_mode = True

    def __init__(self, client, spoke, spoke_container):
        # pylint: disable=super-init-not-called

        self.spoke = spoke
        self.client = client

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("blivet-gui")
        self.builder.add_from_file(locate_ui_file("blivet-gui.ui"))

        # get the main vbox from blivet-gui and add it into given Gtk.Container
        vbox = self.builder.get_object("vbox")
        vbox.reparent(spoke_container)

        # ActionsMenu
        self.popup_menu = ActionsMenu(self)

        # ActionsToolbar
        self.device_toolbar = DeviceToolbar(self)

        # ListDevices
        self.list_devices = ListDevices(self)

        # ListPartitions
        self.list_partitions = ListPartitions(self)

        # ListParents
        self.list_parents = ListParents(self)

        # ListActions
        self.label_actions = self.builder.get_object("label_actions")
        self.label_actions.connect("activate-link", self.show_actions)
        self.list_actions = ListActions(self)

        # Vizualisation
        self.logical_view = LogicalView(self)
        self.builder.get_object("image_window").add(self.logical_view.hbox)

        self.physical_view = PhysicalView(self)
        self.builder.get_object("scrolledwindow_physical").add(self.physical_view.vbox)

        # select first device in ListDevice
        self.list_devices.disks_view.set_cursor(1)
        self.main_window.show_all()
        self.list_devices.disks_view.set_cursor(0)

    def activate_action_buttons(self, activate):
        pass  # there are no action buttons in installer gui

    @property
    def main_window(self):
        return self.spoke.main_window

    @contextmanager
    def enlightbox(self):
        self.main_window.lightbox_on()

        yield

        self.main_window.lightbox_off()

    def show_error_dialog(self, error_message):
        with self.enlightbox():
            message_dialogs.ErrorDialog(self.main_window, error_message, decorated=False)

    def show_warning_dialog(self, warning_message):
        with self.enlightbox():
            message_dialogs.WarningDialog(self.main_window, warning_message, decorated=False)

    def show_confirmation_dialog(self, title, question):
        with self.enlightbox():
            dialog = message_dialogs.ConfirmDialog(self.main_window, title, question, decorated=False)
            response = dialog.run()

        return response
