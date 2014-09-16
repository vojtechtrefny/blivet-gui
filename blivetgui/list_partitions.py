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

import os

from gi.repository import Gtk, GdkPixbuf, Gdk, GLib

import gettext

import cairo

from utils import *

from dialogs import *

from actions_toolbar import *

from actions_menu import *

from main_menu import *

from processing_window import *

from actions_history import *

from devicevisualization.device_canvas import device_canvas

#------------------------------------------------------------------------------#

APP_NAME = "blivet-gui"

dirname, filename = os.path.split(os.path.abspath(__file__))

gettext.bindtextdomain('blivetgui', dirname + '/i18n')
gettext.textdomain('blivetgui')
_ = gettext.gettext

#------------------------------------------------------------------------------#

class ListPartitions():
	
	def __init__(self, main_window, ListDevices, BlivetUtils, Builder, kickstart_mode=False, disk=None):
		
		GLib.threads_init()
		Gdk.threads_init()
		Gdk.threads_enter()
		
		self.list_devices = ListDevices
		self.b = BlivetUtils
		self.builder = Builder
		
		self.kickstart_mode = kickstart_mode
		
		self.disk = disk
		self.main_window = main_window
		
		# ListStores for partitions and actions
		self.partitions_list = Gtk.TreeStore(object,str,str,str,str,str,str,object)
		self.actions_list = Gtk.ListStore(GdkPixbuf.Pixbuf,str)
		
		self.partitions_view = self.create_partitions_view()
		self.builder.get_object("partitions_viewport").add(self.partitions_view)
		
		self.actions_view = self.create_actions_view()
		self.builder.get_object("actions_viewport").add(self.actions_view)
		
		self.info_label = Gtk.Label()
		self.builder.get_object("pv_viewport").add(self.info_label)
		
		self.darea = device_canvas(blivet_utils=self.b, list_partitions=self)
		self.builder.get_object("image_window").add(self.darea)
		
		self.main_menu = main_menu(self.main_window,self,self.list_devices)	
		self.builder.get_object("vbox").add(self.main_menu.get_main_menu)
	
		self.popup_menu = actions_menu(self)
		self.toolbar = actions_toolbar(self, self.main_window)
		self.builder.get_object("vbox").add(self.toolbar.get_toolbar)
		
		self.select = self.partitions_view.get_selection()
		self.path = self.select.select_path("1")
		
		self.on_partition_selection_changed(self.select)
		self.selection_signal = self.select.connect("changed", self.on_partition_selection_changed)
		
		self.actions = 0
		self.actions_label = self.builder.get_object("actions_page")
		self.actions_label.set_text(_("Pending actions ({0})").format(self.actions))
		
		self.partitions_label = self.builder.get_object("partitions_page")
		self.partitions_label.set_text(_("Partitions").format(self.actions))
		
		self.selected_partition = None
		
		self.history = actions_history(self)
	
	def device_info(self):
		""" Basic information for selected device	
		"""
		
		device_type = self.b.get_device_type(self.disk)
		
		if device_type == "lvmvg":
			pvs = self.b.get_parent_pvs(self.disk)
		
			info_str = _("<b>LVM2 Volume group <i>{0}</i> occupying {1} physical volume(s):</b>\n\n").format(self.disk.name, len(pvs))
		
			for pv in pvs:
				info_str += _("\t• PV <i>{0}</i>, size: {1} on <i>{2}</i> disk.\n").format(pv.name, str(pv.size), pv.disks[0].name)
		
		elif device_type in ["lvmpv", "luks/dm-crypt"]:
			blivet_device = self.disk
			
			if blivet_device.format.type == "lvmpv":
				info_str = _("<b>LVM2 Physical Volume</b>").format()
			
			else:
				info_str = ""
		
		elif device_type == "disk":
			
			blivet_disk = self.disk
			
			info_str = _("<b>Hard disk</b> <i>{0}</i>\n\n\t• Size: <i>{1}</i>\n\t• Model: <i>{2}</i>\n").format(blivet_disk.path, str(blivet_disk.size), blivet_disk.model)
			
		else:
			info_str = ""
		
		self.info_label.set_markup(info_str)
		
		return		
	
	def update_partitions_view(self,selected_device):
		""" Update partition view with selected disc children (partitions)
		
			:param selected_device: selected device from list (eg. disk or VG) 
			:type device_name: blivet.Device
			
		"""
		
		self.disk = selected_device
		
		if self.disk:
			self.device_info()
		
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
						self.add_partition_to_view(child, extended_iter)
					
				elif len(self.b.get_partitions(child)) != 0:
					
					parent_iter = self.add_partition_to_view(child, parent)
					
					childs_loop(self.b.get_partitions(child), parent_iter)
				
				else:
					self.add_partition_to_view(child, parent)

			if len(unadded_logical) != 0 and extended_iter:
				# if blivet creates extended partition it is sometimes huges mess
				# and we need to be sure they are added in proper way
				for logical in unadded_logical:
					self.add_partition_to_view(logical, extended_iter)
		
		self.partitions_list.clear()
		
		partitions = self.b.get_partitions(self.disk)
		
		childs_loop(partitions, None)
		
		# select first line in partitions view
		self.select = self.partitions_view.get_selection()
		self.path = self.select.select_path("0")
		
		# expand all expanders
		self.partitions_view.expand_all()

		# update partitions image

		self.darea.visualize_device(self.partitions_list, self.partitions_view, self.disk)
		
	def add_partition_to_view(self, partition, parent):
		""" Add partition into partition_list
		
		"""
		resize_size = "--"

		if partition.name == _("free space"):
			iter_added = self.partitions_list.append(parent,[partition,partition.name,"--","--",
								 str(partition.size),"--", None, None])
 		elif partition.type == "partition" and hasattr(partition, "isExtended") and partition.isExtended:
			iter_added = self.partitions_list.append(None,[partition,partition.name,_("extended"),"--",
								str(partition.size),"--", None, None])
		elif partition.type == "lvmvg":
			iter_added = self.partitions_list.append(parent,[partition,partition.name,_("lvmvg"),"--",
								str(partition.size),"--", None, None])
		
		elif partition.format.mountable:

			if partition.format.resizable:
				partition.format.updateSizeInfo()
				resize_size = partition.format.minSize
			
			if partition.format.mountpoint != None:
				iter_added = self.partitions_list.append(parent,[partition,partition.name,partition.format.type,
								partition.format.mountpoint,str(partition.size),str(resize_size), None, None])
			
			elif partition.format.mountpoint == None and self.kickstart_mode:
				
				if partition.format.uuid in self.list_devices.old_mountpoints.keys():
					old_mnt = self.list_devices.old_mountpoints[partition.format.uuid]
				else:
					old_mnt = None
				
				iter_added = self.partitions_list.append(parent,[partition,partition.name,partition.format.type,
								partition.format.mountpoint,str(partition.size),str(resize_size), old_mnt, None])
			
			else:
				iter_added = self.partitions_list.append(parent,[partition,partition.name,partition.format.type,
								partition_mounted(partition.path),str(partition.size),str(resize_size), None, None])
		else:
			iter_added = self.partitions_list.append(parent,[partition,partition.name,partition.format.type,"--",
								str(partition.size),str(resize_size), None, None])
		
		return iter_added
		
	def create_partitions_view(self):
		""" Create Gtk.TreeView for device children (partitions)
		"""
		
		if self.disk == None:
			partitions = self.partitions_list
		
		else:
			self.load_partitions()
			partitions = self.partitions_list
			
		treeview = Gtk.TreeView(model=partitions)
		treeview.set_vexpand(True)
		
		renderer_text = Gtk.CellRendererText()
		
		column_text1 = Gtk.TreeViewColumn(_("Partition"), renderer_text, text=1)
		column_text2 = Gtk.TreeViewColumn(_("Filesystem"), renderer_text, text=2)
		column_text3 = Gtk.TreeViewColumn(_("Mountpoint"), renderer_text, text=3)
		column_text4 = Gtk.TreeViewColumn(_("Size"), renderer_text, text=4)
		column_text5 = Gtk.TreeViewColumn(_("Used"), renderer_text, text=5)
		column_text6 = Gtk.TreeViewColumn(_("Current Mountpoint"), renderer_text, text=6)
		
		treeview.append_column(column_text1)
		treeview.append_column(column_text2)
		treeview.append_column(column_text3)
		treeview.append_column(column_text4)
		treeview.append_column(column_text5)
		
		if self.kickstart_mode:
			treeview.append_column(column_text6)
		
		treeview.set_headers_visible(True)
		
		treeview.connect("button-release-event" , self.on_right_click_event)
		
		return treeview
	
	def on_right_click_event(self,treeview, event):
		""" Right click event on partition treeview
		"""
		
		if event.button == 3:
			
			selection = treeview.get_selection()
			
			if selection == None:
				return False
			
			model, treeiter = selection.get_selected()
			
			self.popup_menu.get_menu.popup(None, None, None, None, event.button, event.time)
			
			return True
		
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
	
		return treeview
	
	def clear_actions_view(self):
		""" Delete all actions in actions view
		"""
		
		self.actions = 0
		self.actions_label.set_text(_("Pending actions ({0})").format(self.actions))
		self.actions_list.clear()
		
		self.deactivate_options(["apply", "clear"])
		
		self.update_partitions_view(self.disk)
	
	def update_actions_view(self,action_type=None,action_desc=None):
		""" Update list of scheduled actions
		
			:param action_type: type of action (delete/add/edit)
			:type action_type: str
			:param action_desc: description of scheduled action
			:type partition_name: str
			
		"""
		
		icon_theme = Gtk.IconTheme.get_default()
		icon_add = Gtk.IconTheme.load_icon (icon_theme,"gtk-add",16, 0)
		icon_delete = Gtk.IconTheme.load_icon (icon_theme,"gtk-delete",16, 0)
		icon_edit = Gtk.IconTheme.load_icon (icon_theme,"gtk-edit",16, 0)
		icon_undo = Gtk.IconTheme.load_icon (icon_theme,"edit-undo",16, 0)
		icon_redo = Gtk.IconTheme.load_icon (icon_theme,"edit-redo",16, 0)
		
		action_icons = {"add" : icon_add, "delete" : icon_delete, "edit" : icon_edit,
		"redo" : icon_redo, "undo" : icon_undo }

		if action_type not in ["undo", "redo"]:
		
			self.actions_list.append([action_icons[action_type], action_desc])
			
			# Update number of actions on actions card label
			self.actions += 1

		else:

			self.actions_list.append([action_icons[action_type], action_desc])

			if action_type == "undo":
				self.actions -= 1

			if action_type == "redo":
				self.actions += 1

		self.actions_label.set_text(_("Pending actions ({0})").format(self.actions))

		self.activate_options(["apply", "clear"])
	
	def activate_options(self, activate_list):
		""" Activate toolbar buttons and menu items
		
			:param activate_list: list of items to activate
			:type activate_list: list of str
			
		"""
		
		for item in activate_list:
			self.toolbar.activate_buttons([item])
			self.main_menu.activate_menu_items([item])
			
			if item not in ["apply", "clear", "undo", "redo"]:
				self.popup_menu.activate_menu_items([item])
	
	def deactivate_options(self, deactivate_list):
		""" Deactivate toolbar buttons and menu items
		
			:param deactivate_list: list of items to deactivate
			:type deactivate_list: list of str
			
		"""
		
		for item in deactivate_list:
			self.toolbar.deactivate_buttons([item])
			self.main_menu.deactivate_menu_items([item])
			
			if item not in ["apply", "clear", "undo", "redo"]:
				self.popup_menu.deactivate_menu_items([item])
	
	def deactivate_all_options(self):
		""" Deactivate all partition-based buttons/menu items
		"""
		
		self.toolbar.deactivate_all()
		self.main_menu.deactivate_all()
		self.popup_menu.deactivate_all()
	
	def activate_action_buttons(self,selected_partition):
		""" Activate buttons in toolbar based on selected partition
		
			:param selected_partition: Selected partition
			:type selected_partition: Gtk.TreeModelRow
			
		"""
		
		partition_device = selected_partition[0]
		
		if partition_device == None and selected_partition[1] != _("free space"):
			self.deactivate_all_options()
			return
		
		elif selected_partition[1] == _("free space"):			
			
			self.deactivate_all_options()
			self.activate_options(["add"])
		
		elif selected_partition[2] in ["extended", "lvmvg", "lvmpv"] and partition_device.isleaf:
			
			self.deactivate_all_options()
			self.activate_options(["delete"])
		
		else:
			self.deactivate_all_options()
			
			if partition_device.format.type == None and selected_partition[2] not in ["extended", "lvmvg"]:
				self.activate_options(["delete"])
					
			if partition_device.format.type == "luks" and partition_device.kids == 0:
				self.activate_options(["delete"])
					
			if partition_device.format.type == "luks" and not partition_device.format.status:
				self.activate_options(["decrypt"])
			
			if self.kickstart_mode:
			
				if partition_device.format.mountable:
					self.activate_options(["delete", "edit"])
				
				if partition_device.format.type == "swap":
					self.activate_options(["delete"])
			
			else:
				if partition_device.format.mountable and partition_mounted(partition_device.path) == None:
					self.activate_options(["delete", "edit"])
				
				if partition_device.format.type == "swap" and swap_is_on(partition_device.sysfsPath) == False:
					self.activate_options(["delete"])
					
				if partition_device.format.mountable and partition_mounted(partition_device.path) != None:
					self.activate_options(["unmount"])
	
	def delete_selected_partition(self):
		""" Delete selected partition
		"""
		
		deleted_device = self.selected_partition[0]
		
		dialog = ConfirmDeleteDialog(self.selected_partition[0].name, self.main_window)
		response = dialog.run()

		if response == Gtk.ResponseType.OK:
			
			self.history.add_undo(self.b.return_devicetree)
			self.main_menu.activate_menu_items(["undo"])
			
			self.b.delete_device(self.selected_partition[0])
			
			self.update_actions_view("delete",_("delete partition {0}").format(self.selected_partition[0].name))
			
			self.selected_partition = None
			
		elif response == Gtk.ResponseType.CANCEL:
			pass
		
		dialog.destroy()
		
		self.update_partitions_view(self.disk)
		
		self.list_devices.update_devices_view()
	
	def add_partition(self, ):
		""" Add new partition
		"""
		
		# parent device; free space has always only one parent #FIXME
		parent_device = self.selected_partition[0].parents[0]
		
		parent_device_type = parent_device.type

		if parent_device_type == "partition" and parent_device.format.type == "lvmpv":
			parent_device_type = "lvmpv"
		
		if parent_device_type == "disk" and self.b.has_disklabel(self.disk) != True:
			
			dialog = AddLabelDialog(self.disk, self.main_window)
			
			response = dialog.run()
			
			if response == Gtk.ResponseType.OK:
				
				selection = dialog.get_selection()
				
				self.history.add_undo(self.b.return_devicetree)
				self.main_menu.activate_menu_items(["undo"])
				
				self.b.create_disk_label(self.disk)
				self.update_actions_view("add","create new disklabel on " + str(self.disk) + " device")
				
				dialog.destroy()
			
			elif response == Gtk.ResponseType.CANCEL:		
			
				dialog.destroy()
			
				return
			
			return
		
		dialog = AddDialog(self.main_window, parent_device_type, parent_device, self.selected_partition[0],
					 self.selected_partition[0].size, self.b.get_free_pvs_info(), self.kickstart_mode)

		response = dialog.run()
		
		selection = dialog.get_selection()
		
		if response == Gtk.ResponseType.OK:
			
			user_input = dialog.get_selection()
			
			selected_size = Size(str(user_input[1]) + "MiB")
			
			if selection[2] == None and selection[0] not in ["LVM2 Physical Volume",
													"LVM2 Volume Group", "LVM2 Storage"]:
				# If fs is not selected, show error window and re-run add dialog
				msg = _("Error:\n\nFilesystem type must be specified when creating new partition.")
				AddErrorDialog(dialog, msg)
				dialog.destroy()
				self.add_partition()
			
			elif selection[0] == "LVM2 Volume Group":
				
				self.history.add_undo(self.b.return_devicetree)
				self.main_menu.activate_menu_items(["undo"])
				
				ret = self.b.add_device(parent_devices=user_input[5], device_type=user_input[0],
							fs_type=user_input[2], target_size=selected_size, name=user_input[3],
							label=user_input[4])
				
				if ret != None:
					
					self.update_actions_view("add","add " + str(selected_size) + " " + user_input[0] + " device")
					self.list_devices.update_devices_view()
						
					self.update_partitions_view(self.disk)
				
				else:
					self.update_partitions_view(self.disk)
				
				dialog.destroy()
			
			elif selection[0] == "LVM2 Storage":
				
				self.history.add_undo(self.b.return_devicetree)
				self.main_menu.activate_menu_items(["undo"])
				
				ret1 = self.b.add_device(parent_devices=[parent_device], device_type="LVM2 Physical Volume",
							 fs_type=user_input[2], target_size=selected_size, name=user_input[3],
							 label=user_input[4])
				
				if ret1 != None:
					
					if user_input[2] == None:
						self.list_devices.update_devices_view()
					
					ret2 = self.b.add_device(parent_devices=[ret1], device_type="LVM2 Volume Group",
							 fs_type=user_input[2], target_size=ret1.size, name=user_input[3],
							 label=user_input[4])
				
					if ret2 != None:
						
						if user_input[2] == None:
							
							self.update_actions_view("add","add " + str(selected_size) + " " + user_input[0] + " device")
							self.list_devices.update_devices_view()
							
					self.update_partitions_view(self.disk)
				
				else:
					self.update_partitions_view(self.disk)
				
				dialog.destroy()
				
			else:
				
				# kickstart mode
				
				if self.kickstart_mode:
					if self.check_mountpoint(user_input[5]):
						pass
					else:
						dialog.destroy()
						return
				
				self.history.add_undo(self.b.return_devicetree)
				self.main_menu.activate_menu_items(["undo"])
				
				if user_input[6] and not user_input[7]["passphrase"]:
					msg = _("Error:\n\nPassphrase not specified.")
					AddErrorDialog(dialog, msg)
					dialog.destroy()
					self.add_partition()
				
				# user_input = [device, size, fs, name, label, mountpoint]
				
				ret = self.b.add_device(parent_devices=[parent_device], device_type=user_input[0],
							fs_type=user_input[2], target_size=selected_size, name=user_input[3],
							label=user_input[4], mountpoint=user_input[5], encrypt=user_input[6], 
							encrypt_args=user_input[7])

				if ret != None:
					
					if user_input[2] == None:
					
						self.update_actions_view("add","add " + str(selected_size) + " " + user_input[0] + " device")
						self.list_devices.update_devices_view()
						
					else:
					
						self.update_actions_view("add","add " + str(selected_size) + " " + user_input[2] + " partition")
						
					self.update_partitions_view(self.disk)
				
				else:
					self.update_partitions_view(self.disk)
				
				dialog.destroy()
			
		elif response == Gtk.ResponseType.CANCEL:		
			
			dialog.destroy()
			
			return
		
	def check_mountpoint(self, mountpoint):
		""" Kickstart mode; check for duplicate mountpoints
			
			:param mountpoint: mountpoint selected by user
			:type mountpoint: str
			:returns: mountpoint validity
			:rtype: bool
		"""
		
		if mountpoint == None:
			return True
		
		elif mountpoint not in self.b.storage.mountpoints.keys():
			return True
		
		else:
			
			old_device = self.b.storage.mountpoints[mountpoint]
			
			dialog = KickstartDuplicateMountpointDialog(self.main_window, mountpoint, old_device.name)
		
			response = dialog.run()
		
			if response == Gtk.ResponseType.OK:
				old_device.format.mountpoint = None
				
				dialog.destroy()
				return True
			else:
				dialog.destroy()
				return False
		
		
	def perform_actions(self):
		""" Perform queued actions
		
		.. note::
				New window creates separate thread to run blivet.doIt()
				
		"""
		
		dialog = ProcessingActions(self, self.main_window)
		
		response = dialog.run()
		
		Gdk.threads_leave()
		
		dialog.destroy()
		
		self.clear_actions_view()
		self.history.clear_history()
		
		self.update_partitions_view(self.disk)
	
	def apply_event(self):
		""" Apply event for main menu/toolbar
		
		.. note:: 
				This is neccessary because of kickstart mode -- in "standard" mode
				we need only simple confirmation dialog, but in kickstart mode it
				is neccessary to create file choosing dialog for kickstart file save.
		
		"""
		if self.kickstart_mode:
			
			dialog = KickstartFileSaveDialog(self.main_window)
			
			response = dialog.run()
			
			if response == Gtk.ResponseType.OK:
				
				self.clear_actions_view()
				self.b.create_kickstart_file(dialog.get_filename())
				
			elif response == Gtk.ResponseType.CANCEL:
				dialog.destroy()
				
			dialog.destroy()
			
			self.clear_actions_view()
			self.history.clear_history()
		
		else:
			dialog = ConfirmPerformActions(self.main_window)
			
			response = dialog.run()
			
			if response == Gtk.ResponseType.OK:
				
				dialog.destroy()
				
				self.perform_actions()
				
			elif response == Gtk.ResponseType.CANCEL:
				dialog.destroy()
		
	
	def umount_partition(self):
		""" Unmount selected partition
		"""
		
		mountpoint = self.selected_partition[3]
		
		if os_umount_partition(mountpoint):
			self.update_partitions_view(self.disk)
			
		else:
			UnmountErrorDialog(self.selected_partition[0], self.main_window)
	
	def decrypt_device(self):
		""" Decrypt selected device
		"""
		
		dialog = LuksPassphraseDialog(self.main_window, self.selected_partition[0].name)
			
		response = dialog.run()
		
		if response == Gtk.ResponseType.OK:
			
			ret = self.b.luks_decrypt(self.selected_partition[0], dialog.get_selection())
			
			if ret:
				BlivetError(self.main_window, ret)
				return
			
		elif response == Gtk.ResponseType.CANCEL:
			pass
		
		dialog.destroy()
		
		self.list_devices.update_devices_view()
		self.update_partitions_view(self.disk)
	
	def edit_partition(self):
		""" Edit selected partition
		"""
		
		resizable = self.b.device_resizable(self.selected_partition[0])
		
		dialog = EditDialog(self.main_window, self.selected_partition[0], resizable, self.kickstart_mode)
		dialog.connect("delete-event", Gtk.main_quit)
		
		response = dialog.run()
		
		selection = dialog.get_selection()
		
		if response == Gtk.ResponseType.OK:
		
			user_input = dialog.get_selection()
			
			if user_input[0] == False and user_input[2] == None and user_input[3] == None:
				dialog.destroy()
				
			else:
				
				if self.kickstart_mode:
					if self.check_mountpoint(user_input[3]):
						pass
					else:
						dialog.destroy()
						return
				
				self.history.add_undo(self.b.return_devicetree)
				self.main_menu.activate_menu_items(["undo"])
				
				ret = self.b.edit_partition_device(self.selected_partition[0], user_input)
			
				if ret:
					
					self.update_actions_view("edit","edit " + self.selected_partition[0].name + " partition")
					self.update_partitions_view(self.disk)				
				else:
					self.update_partitions_view(self.disk)
			
				dialog.destroy()
			
		elif response == Gtk.ResponseType.CANCEL:		
			
			dialog.destroy()
			
			return
	
	def clear_actions(self):
		""" Clear all scheduled actions
		"""
		
		self.b.blivet_reset()
		
		self.history.clear_history()
		
		self.list_devices.update_devices_view()
		self.update_partitions_view(self.disk)
		
	def actions_redo(self):
		""" Redo last action
		"""
		
		self.b.override_devicetree(self.history.redo())
		
		self.list_devices.update_devices_view()
		self.update_partitions_view(self.disk)

		self.update_actions_view("redo", "redo")
		
		return
	
	def actions_undo(self):
		""" Undo last action
		"""
		
		self.b.override_devicetree(self.history.undo())
		
		self.list_devices.update_devices_view()
		
		self.update_partitions_view(self.disk)

		self.update_actions_view("undo", "undo")

		if self.actions == 0:
			self.deactivate_options(["clear", "apply"])

		return
	
	def on_partition_selection_changed(self,selection):
		""" On selected partition action
		"""
		
		model, treeiter = selection.get_selected()
		
		self.deactivate_all_options()
		
		if treeiter != None:
			
			self.activate_action_buttons(model[treeiter])
			self.selected_partition = model[treeiter]
			self.darea.update_visualisation()
	
	def reload(self):
		""" Quit blivet-gui
		"""
		
		if self.actions != 0:
			# There are queued actions we don't want do quit now
			
			title = _("Confirm reload storage")
			msg = _("There are pending operations. Are you sure you want to continue?")
			
			dialog = ConfirmDialog(self.main_window, title, msg)
			response = dialog.run()

			if response == Gtk.ResponseType.OK:
				
				self.b.blivet_reload()
				
				self.history.clear_history()
		
				self.list_devices.update_devices_view()
				self.update_partitions_view(self.disk)
			
			dialog.destroy()
		
		else:
			self.b.blivet_reload()
			self.history.clear_history()
		
			self.list_devices.update_devices_view()
			self.update_partitions_view(self.disk)
			
	def quit(self):
		""" Quit blivet-gui
		"""
		
		if self.actions != 0:
			# There are queued actions we don't want do quit now
			dialog = ConfirmQuitDialog(self.main_window, self.actions)
			response = dialog.run()

			if response == Gtk.ResponseType.OK:
				
				Gtk.main_quit()
				
			elif response == Gtk.ResponseType.CANCEL:
				pass
			
			dialog.destroy()
		
		else:
			Gtk.main_quit()