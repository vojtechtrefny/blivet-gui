# -*- coding: utf-8 -*-
# exception_handler.py
# Custom exception handler for blivet-gui
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

import subprocess
import sys
import traceback

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from .dialogs import message_dialogs, constants
from .gui_utils import command_exists
from .i18n import _

# ---------------------------------------------------------------------------- #


class BlivetGUIExceptionHandler(object):

    allow_ignore = False

    def __init__(self, main_window, excepthook):
        self.main_window = main_window
        self.excepthook = excepthook

    def handle_exception(self, exc_type, exc_value, exc_traceback):

        tr = "".join(traceback.format_tb(exc_traceback))
        if self.allow_ignore:
            msg = _("Unknow error occured.\n{error}").format(error=str(exc_value))
        else:
            msg = _("Unknow error occured. Blivet-gui will be terminated.\n{error}").format(error=str(exc_value))

        allow_report = command_exists("gnome-abrt")

        dialog = message_dialogs.ExceptionDialog(self.main_window, self.allow_ignore,
                                                 allow_report, msg, tr)
        response = dialog.run()

        if response == constants.DialogResponseType.BACK:
            return
        else:
            # restore handler and re-raise original exception
            sys.excepthook = self.excepthook
            sys.excepthook(exc_type, exc_value, exc_traceback)

            if response == constants.DialogResponseType.REPORT:
                subprocess.call(["gnome-abrt"])

            Gtk.main_quit()
