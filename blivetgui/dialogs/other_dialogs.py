# -*- coding: utf-8 -*-
# other_dialogs.py
# misc Gtk.Dialog classes
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

from blivetgui.gui_utils import locate_ui_file

from ..i18n import _

from blivet.platform import platform

# ---------------------------------------------------------------------------- #


class AboutDialog(object):
    """ Standard 'about application' dialog
    """

    def __init__(self, parent_window, version):

        builder = Gtk.Builder()
        builder.set_translation_domain("blivet-gui")
        builder.add_from_file(locate_ui_file('about_dialog.ui'))
        dialog = builder.get_object("about_dialog")

        dialog.set_transient_for(parent_window)
        dialog.set_translator_credits(_("translator-credits"))
        dialog.set_version(version)

        dialog.show_all()
        dialog.run()
        dialog.destroy()


class AddLabelDialog(object):
    """ Dialog window allowing user to add disklabel to disk
    """

    def __init__(self, parent_window):
        """

            :param parent_window: parent window
            :type parent_window: Gtk.Window

        """

        builder = Gtk.Builder()
        builder.set_translation_domain("blivet-gui")
        builder.add_from_file(locate_ui_file('add_disklabel_dialog.ui'))
        self.dialog = builder.get_object("dialog")
        self.pttype_combo = builder.get_object("pttype_combo")

        self.dialog.set_transient_for(parent_window)

        for disklabel in platform.disklabel_types:
            self.pttype_combo.append_text(disklabel)

        self.pttype_combo.set_active(0)

        self.dialog.show_all()

    def run(self):
        response = self.dialog.run()
        label = self.pttype_combo.get_active_text()

        self.dialog.destroy()

        if response == Gtk.ResponseType.OK:
            return label
        else:
            return None


class LuksPassphraseDialog(object):
    """ Dialog window allowing user to enter passphrase to decrypt
    """

    def __init__(self, parent_window):
        """

            :param parent_window: parent window
            :type parent_window: Gtk.Window

        """

        builder = Gtk.Builder()
        builder.set_translation_domain("blivet-gui")
        builder.add_from_file(locate_ui_file('luks_passphrase_dialog.ui'))
        self.dialog = builder.get_object("dialog")

        self.dialog.set_transient_for(parent_window)

        self.entry_passphrase = builder.get_object("entry_passphrase")
        self.dialog.show_all()

    def run(self):

        response = self.dialog.run()
        passphrase = self.entry_passphrase.get_text()
        self.dialog.destroy()

        if response == Gtk.ResponseType.OK:
            return passphrase

        else:
            return None
