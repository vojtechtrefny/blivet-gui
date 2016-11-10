# -*- coding: utf-8 -*-
# gui_utils.py
# Utils for GUI
#
# Copyright (C) 2015  Red Hat, Inc.
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

import os
import shutil

# ---------------------------------------------------------------------------- #


def command_exists(command):
    """ Find if given command exists
    """

    ret = shutil.which(command)

    if ret is not None:
        return True
    else:
        return False


def locate_ui_file(filename):
    """ Locate Glade ui files
    """

    path = [os.path.split(os.path.abspath(__file__))[0] + '/../data/ui/',
            '/usr/share/blivet-gui/ui/']

    for folder in path:
        filepath = folder + filename
        if os.access(filepath, os.R_OK):
            return filepath

    raise RuntimeError("Unable to find glade file %s" % filename)


def locate_css_file(filename):
    """ Locate CSS files
    """

    path = [os.path.split(os.path.abspath(__file__))[0] + '/../data/css/',
            '/usr/share/blivet-gui/css/']

    for folder in path:
        filepath = folder + filename
        if os.access(filepath, os.R_OK):
            return filepath

    raise RuntimeError("Unable to find css file %s" % filename)
