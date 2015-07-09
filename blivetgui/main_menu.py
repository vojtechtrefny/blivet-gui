# -*- coding: utf-8 -*-
# main_menu.py
# Main menu
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

from gi.repository import Gtk

from .dialogs.other_dialogs import AboutDialog

import os, subprocess

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

class MainMenu(object):
    """ Main menu for blivet-gui
    """

    def __init__(self, blivet_gui):

        self.blivet_gui = blivet_gui

        menuitem_reload = self.blivet_gui.builder.get_object("menuitem_reload")
        menuitem_reload.connect("activate", self.blivet_gui.reload)

        # menuitem_actions = self.blivet_gui.builder.get_object("menuitem_actions")
        # menuitem_actions.connect("activate", ) #FIXME

        menuitem_quit = self.blivet_gui.builder.get_object("menuitem_quit")
        menuitem_quit.connect("activate", self.blivet_gui.quit)

        menuitem_help = self.blivet_gui.builder.get_object("menuitem_help")
        menuitem_help.connect("activate", self.on_help_item)

        menuitem_about = self.blivet_gui.builder.get_object("menuitem_about")
        menuitem_about.connect("activate", self.on_about_item)

    def on_about_item(self, *_args):
        """ Onselect action for 'About'
        """

        AboutDialog(self.blivet_gui.main_window, self.blivet_gui.version)

    def on_help_item(self, *_args):
        """ Onselect action for 'Help'
        """

        if not os.access('/usr/share/help/C/blivet-gui/index.page', os.R_OK):
            msg = _("Documentation for blivet-gui hasn't been found.\n\n" \
                    "Online version of documentation is available at " \
                    "http://vojtechtrefny.github.io/blivet-gui")

            self.blivet_gui.show_warning_dialog(msg)
            return

        try:
            fnull = open(os.devnull, "w")

            user = os.getenv("PKEXEC_UID")

            if user:
                subprocess.Popen(["yelp", "/usr/share/help/C/blivet-gui/index.page"],
                                 stdout=fnull, stderr=subprocess.STDOUT,
                                 preexec_fn=lambda: (os.setuid(int(user))))

            else:
                subprocess.Popen(["yelp", "/usr/share/help/C/blivet-gui/index.page"],
                                 stdout=fnull, stderr=subprocess.STDOUT)

        except OSError:
            msg = _("You need \"Yelp\" to see the documentation.\n\n" \
                    "Online version of documentation is available at " \
                    "http://vojtechtrefny.github.io/blivet-gui")

            self.blivet_gui.show_error_dialog(msg)
