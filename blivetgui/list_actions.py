# -*- coding: utf-8 -*-
# list_partitions.py
# List of actions currently scheduled using blivet-gui
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

from gi.repository import Gtk, GdkPixbuf

import gettext

#------------------------------------------------------------------------------#

_ = lambda x: gettext.translation("blivet-gui", fallback=True).gettext(x) if x != "" else ""

#------------------------------------------------------------------------------#

class ListActions(object):
    """ List of childs of selected device

        ..note:: There are two types of 'actions': 'blivet actions' -- simply instances of
                 blivet.DeviceAction and 'blivet-gui actions' created as a reaction on user
                 action, eg. adding new device or deleting one. One blivet-gui action can
                 consist of more blivet actions (eg. adding a new partition creates two
                 blivet actions -- creating of a partition device and creatig format for it)

    """

    def __init__(self, blivet_gui):

        self.blivet_gui = blivet_gui

        # list of blivet actions
        self.history = []

        # number af scheduled actions
        self.actions = 0
        self.actions_list = Gtk.TreeStore(GdkPixbuf.Pixbuf, str)

        self.actions_view = self.create_actions_view()

        icon_theme = Gtk.IconTheme.get_default()
        icon_add = Gtk.IconTheme.load_icon(icon_theme, "list-add", 16, 0)
        icon_delete = Gtk.IconTheme.load_icon(icon_theme, "edit-delete", 16, 0)
        icon_edit = Gtk.IconTheme.load_icon(icon_theme, "edit-select-all", 16, 0)

        self.action_icons = {"add" : icon_add, "delete" : icon_delete, "edit" : icon_edit}

    def create_actions_view(self):
        """ Create treeview for actions

            :returns: treeview
            :rtype: Gtk.TreeView

        """

        treeview = Gtk.TreeView(model=self.actions_list)
        treeview.set_vexpand(True)
        treeview.set_hexpand(True)

        renderer_pixbuf = Gtk.CellRendererPixbuf()
        column_pixbuf = Gtk.TreeViewColumn(None, renderer_pixbuf, pixbuf=0)
        treeview.append_column(column_pixbuf)

        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn(None, renderer_text, text=1)
        treeview.append_column(column_text)

        treeview.set_headers_visible(False)
        treeview.expand_all()

        return treeview

    def append(self, action_type, action_desc, blivet_actions):
        """ Append newly scheduled actions to the list of actions

            :param action_type: type of action (delete/add/edit)
            :type action_type: str
            :param action_desc: description of scheduled action
            :type partition_name: str
            :param blivet_actions: list of actions
            :type blivet_actions: list of blivet.DeviceAction

        """

        # update number of actions label
        self.actions += 1
        # self.blivet_gui.actions_label.set_text(_("Pending actions ({0})").format(self.actions))

        # add new actions to the view
        parent_iter = self.actions_list.append(None, [self.action_icons[action_type], action_desc])

        for action in blivet_actions:
            self.actions_list.append(parent_iter, [None, str(action)])

        # update list of actions
        self.history.append(blivet_actions)

        # activate 'actions-related' options
        self.blivet_gui.activate_options(["apply", "clear", "undo"])

    def pop(self):
        """ Remove last action from the list of actions

            :returns: list of blivet actions belonging to the last action
            :rtype: list of blivet.DeviceAction

        """

        # upate number of actions label
        self.actions -= 1
        # self.blivet_gui.actions_label.set_text(_("Pending actions ({0})").format(self.actions))

        # remove actions from view
        self.actions_list.remove(self.actions_list.get_iter(len(self.actions_list)-1))

        # deactivate 'actions-related' options (if there are no actions)
        if not self.actions:
            self.blivet_gui.deactivate_options(["clear", "apply", "undo"])

        return self.history.pop()

    def clear(self):
        """ Delete all actions in actions view
        """

        # upate number of actions label
        self.actions = 0
        # self.blivet_gui.actions_label.set_text(_("Pending actions ({0})").format(self.actions))

        # remove all actions from view
        self.actions_list.clear()

        # remove all actions from list of actions
        self.history = []

        self.blivet_gui.deactivate_options(["clear", "apply", "undo"])
