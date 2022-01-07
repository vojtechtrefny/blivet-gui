# utils.py
# Classes working directly with blivet instance
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

import blivet

from blivet.devices import PartitionDevice, LUKSDevice, LVMVolumeGroupDevice, BTRFSVolumeDevice, BTRFSSubVolumeDevice, MDRaidArrayDevice
from blivet.formats import DeviceFormat
from blivet.size import Size

from blivet.devicelibs.crypto import LUKS_METADATA_SIZE

from .communication.proxy_utils import ProxyDataContainer

import traceback
import parted
import subprocess

from .logs import set_logging, log_utils_call
from .i18n import _
from . import __version__

# ---------------------------------------------------------------------------- #

PARTITION_TYPE = {"primary": parted.PARTITION_NORMAL,
                  "logical": parted.PARTITION_LOGICAL,
                  "extended": parted.PARTITION_EXTENDED}

# ---------------------------------------------------------------------------- #


def lsblk():
    p = subprocess.run(["lsblk", "-a", "-o", "+FSTYPE,LABEL,UUID,MOUNTPOINT"],
                       stdout=subprocess.PIPE, check=False)
    return p.stdout.decode()


class FreeSpaceDevice(object):
    """ Special class to represent free space on disk (device)
        (blivet doesn't have class/device to represent free space)
    """

    def __init__(self, free_size, dev_id, start, end, parents, logical=False):
        """

        :param free_size: size of free space
        :type free_size: blivet.size.Size
        :param start: start block
        :type end: int
        :param end: end block
        :type end: int
        :param parents: list of parent devices
        :type parents: blivet.devices.lib.ParentList
        :param logical: is this free space inside extended partition
        :type logical: bool

        """

        self.name = _("free space")
        self.size = free_size
        self.id = dev_id

        self.start = start
        self.end = end

        self.is_logical = logical
        self.is_extended = False
        self.is_primary = not logical
        self.is_free_space = True
        self.is_disk = False
        self.direct = False
        self._resizable = False
        self.format_immutable = False

        self.format = DeviceFormat(exists=True)
        self.type = "free space"
        self.children = []
        self.parents = blivet.devices.lib.ParentList(items=parents)

        self.disk = self._get_disk()

    def _get_disk(self):
        parents = self.parents

        while parents:
            if parents[0].is_disk:
                return parents[0]

            parents = parents[0].parents

        return None

    @property
    def protected(self):
        return self.parents[0].protected

    @property
    def is_empty_disk(self):
        return len(self.parents) == 1 and self.parents[0].type in ("disk", "nvdimm") and \
            not self.parents[0].children and self.parents[0].format.type and \
            self.parents[0].format.type not in ("iso9660",)

    @property
    def is_uninitialized_disk(self):
        return len(self.parents) == 1 and self.parents[0].type in ("disk", "nvdimm") and \
            not self.parents[0].children and not self.parents[0].format.type

    @property
    def is_free_region(self):
        return not (self.is_empty_disk or self.is_uninitialized_disk)

    def __str__(self):
        return "existing " + str(self.size) + " free space"


class BlivetUtils(object):
    """ Class with utils directly working with blivet itselves
    """

    installer_mode = False

    def __init__(self, ignored_disks=None, exclusive_disks=None):

        self.ignored_disks = ignored_disks
        self.exclusive_disks = exclusive_disks

        self._resizable_filesystems = None

        # create our log now, creating blivet.Blivet instance may fail
        # and log some basic information -- version and lsblk output
        _log_file, self.log = set_logging(component="blivet-gui-utils")
        self.log.info("BlivetUtils, version: %s", __version__)
        self.log.info("lsblk output:\n%s", lsblk())

        self.storage = blivet.Blivet()

        # logging
        set_logging(component="blivet")
        set_logging(component="program")

        # allow creating of ntfs format
        blivet.formats.fs.NTFS._formattable = True
        blivet.formats.fs.NTFS._supported = True

        self.blivet_reset()
        self._update_min_sizes_info()

    @property
    def resizable_filesystems(self):
        if self._resizable_filesystems is None:
            self._resizable_filesystems = []
            for cls in blivet.formats.device_formats.values():
                if cls._resizable:
                    self._resizable_filesystems.append(cls._type)

        return self._resizable_filesystems

    def get_disks(self):
        """ Return list of all disk devices on current system

            :returns: list of all "disk" devices
            :rtype: list

        """

        return [device for device in self.storage.disks if device.type != "mdarray"]

    def get_group_devices(self):
        """ Return list of LVM2 Volume Group devices

            :returns: list of LVM2 VG devices
            :rtype: list

        """

        devices = {}
        devices["lvm"] = self.storage.vgs
        devices["raid"] = self.storage.mdarrays
        devices["btrfs"] = self.storage.btrfs_volumes

        return devices

    def get_free_info(self):
        """ Get list of free 'devices' (PVs and disk regions) that can be used
            as parents for newly added devices
        """

        free_devices = []

        # free pvs
        for pv in self.storage.pvs:
            if not pv.children:
                free_devices.append(("lvmpv", FreeSpaceDevice(pv.size, self.storage.next_id, None, None, [pv])))

        # free disks and disk regions
        for disk in self.storage.disks:
            if disk.format.type not in ("disklabel",):
                continue

            free_space = blivet.partitioning.get_free_regions([disk], align=True)

            for free in free_space:
                free_size = blivet.size.Size(free.length * free.device.sectorSize)

                if free_size > blivet.size.Size("2 MiB"):  # skip very small free regions
                    free_devices.append(("free", FreeSpaceDevice(free_size, self.storage.next_id, free.start, free.end, [disk])))

        return free_devices

    def get_group_device(self, blivet_device):
        """ Get 'group' device based on underlying device (lvmpv/btrfs/mdmember/luks partition)
        """

        # already a group device
        if blivet_device.type in ("btrfs volume", "lvmvg", "mdarray"):
            return blivet_device

        # encrypted group device -> get the luks device instead
        if blivet_device.format.type in ("luks", "integrity"):
            blivet_device = self.get_luks_device(blivet_device)

        if not blivet_device.format or blivet_device.format.type not in ("lvmpv", "btrfs", "mdmember", "luks"):
            return None
        if len(blivet_device.children) != 1:
            return None

        group_device = blivet_device.children[0]
        return group_device

    def get_luks_device(self, blivet_device):
        """ Get luks or integrity device based on underlying partition
        """

        if not blivet_device.format or blivet_device.format.type not in ("luks", "integrity"):
            return None
        if len(blivet_device.children) != 1:
            return None

        if blivet_device.children[0].type == "integrity/dm-crypt" and blivet_device.children[0].children:
            # LUKS + integrity
            luks_device = blivet_device.children[0].children[0]
        else:
            # only integrity device
            luks_device = blivet_device.children[0]

        return luks_device

    def get_children(self, blivet_device):
        """ Get partitions (children) of selected device

            :param blivet_device: blivet device
            :type blivet_device: blivet.device.Device
            :returns: list of child devices
            :rtype: list of blivet.device.Device

        """

        if not blivet_device:
            return []

        childs = blivet_device.children

        if blivet_device.type == "lvmvg" and blivet_device.free_space > blivet.size.Size(0):
            childs.append(FreeSpaceDevice(blivet_device.free_space, self.storage.next_id, None, None, [blivet_device]))

        return childs

    def get_disk_children(self, blivet_device):
        if not blivet_device.is_disk:
            raise TypeError("device %s is not a disk" % blivet_device.name)

        if blivet_device.is_disk and not blivet_device.format.type:
            if blivet_device.format.name != "Unknown":
                # disk with unsupported format
                return ProxyDataContainer(partitions=[blivet_device], extended=None, logicals=None)
            else:
                # empty disk without disk label
                partitions = [FreeSpaceDevice(blivet_device.size, self.storage.next_id, 0, blivet_device.current_size, [blivet_device], False)]
                return ProxyDataContainer(partitions=partitions, extended=None, logicals=None)

        if blivet_device.format and blivet_device.format.type not in ("disklabel", "btrfs", "luks", None):
            # special occasion -- raw device format
            return ProxyDataContainer(partitions=[blivet_device], extended=None, logicals=None)

        if blivet_device.format and blivet_device.format.type == "btrfs" and blivet_device.children:
            # btrfs volume on raw device
            btrfs_volume = blivet_device.children[0]
            return ProxyDataContainer(partitions=[btrfs_volume], extended=None, logicals=None)

        if blivet_device.format and blivet_device.format.type in ("luks", "integrity"):
            if blivet_device.children:
                luks = self.get_luks_device(blivet_device)
            else:
                luks = blivet_device

            return ProxyDataContainer(partitions=[luks], extended=None, logicals=None)

        partitions = blivet_device.children
        # extended partition
        extended = self._get_extended_partition(blivet_device, partitions)
        # logical partitions + 'logical' free space
        logicals = self._get_logical_partitions(blivet_device, partitions) + self._get_free_logical(blivet_device)
        # primary partitions + 'primary' free space
        primaries = self._get_primary_partitions(blivet_device, partitions) + self._get_free_primary(blivet_device)

        def _sort_partitions(part):  # FIXME: move to separate 'utils' file
            if part.type not in ("free space", "partition"):
                raise ValueError
            if part.type == "free space":
                return part.start
            else:
                return part.parted_partition.geometry.start

        if extended:
            partitions = sorted(primaries + [extended], key=_sort_partitions)
        else:
            partitions = sorted(primaries, key=_sort_partitions)
        logicals = sorted(logicals, key=_sort_partitions)

        return ProxyDataContainer(partitions=partitions, extended=extended, logicals=logicals)

    def _get_extended_partition(self, blivet_device, partitions=None):
        if not blivet_device.is_disk or not blivet_device.format or blivet_device.format.type != "disklabel":
            return None

        extended = None
        if partitions is None:
            partitions = blivet_device.children
        for part in partitions:
            if part.type == "partition" and part.is_extended:
                extended = part
                break  # only one extended partition

        return extended

    def _get_logical_partitions(self, blivet_device, partitions=None):
        if not blivet_device.is_disk or not blivet_device.format or blivet_device.format.type != "disklabel":
            return []

        logicals = []
        if partitions is None:
            partitions = blivet_device.children
        for part in partitions:
            if part.type == "partition" and part.is_logical:
                logicals.append(part)

        return logicals

    def _get_primary_partitions(self, blivet_device, partitions=None):
        if not blivet_device.is_disk or not blivet_device.format or blivet_device.format.type != "disklabel":
            return []

        primaries = []
        if partitions is None:
            partitions = blivet_device.children
        for part in partitions:
            if part.type == "partition" and part.is_primary:
                primaries.append(part)

        return primaries

    def _get_free_logical(self, blivet_device):
        if not blivet_device.is_disk or not blivet_device.format or blivet_device.format.type != "disklabel":
            return []

        extended = blivet_device.format.extended_partition
        if not extended:
            return []

        free_logical = []

        free_regions = blivet.partitioning.get_free_regions([blivet_device], align=True)
        for region in free_regions:
            region_size = blivet.size.Size(region.length * region.device.sectorSize)
            if region_size < blivet.size.Size("4 MiB"):
                continue

            if region.start >= extended.geometry.start and \
               region.end <= extended.geometry.end:
                free_logical.append(FreeSpaceDevice(region_size, self.storage.next_id, region.start, region.end, [blivet_device], True))

        return free_logical

    def _get_free_primary(self, blivet_device):
        if not blivet_device.is_disk or not blivet_device.format or blivet_device.format.type != "disklabel":
            return []

        free_primary = []
        extended = blivet_device.format.extended_partition
        free_regions = blivet.partitioning.get_free_regions([blivet_device], align=True)

        for region in free_regions:
            region_size = blivet.size.Size(region.length * region.device.sectorSize)
            if region_size < blivet.size.Size("4 MiB"):
                continue

            if extended and not (region.start >= extended.geometry.start and
               region.end <= extended.geometry.end):
                free_primary.append(FreeSpaceDevice(region_size, self.storage.next_id, region.start, region.end, [blivet_device], False))
            elif not extended:
                free_primary.append(FreeSpaceDevice(region_size, self.storage.next_id, region.start, region.end, [blivet_device], False))

        return free_primary

    def get_roots(self, blivet_device):
        """ Get list of parents for selected device with its structure """

        roots = set([])

        if blivet_device.type == "lvmvg":
            for pv in blivet_device.pvs:
                roots.add(self._get_root_device(pv))
        elif blivet_device.type in ("mdarray", "btrfs volume"):
            for member in blivet_device.members:
                roots.add(self._get_root_device(member))
        elif blivet_device.type in ("luks/dm-crypt", "integrity/dm-crypt"):
            roots.add(self._get_root_device(blivet_device.raw_device))

        return roots

    def _get_root_device(self, blivet_device):
        if blivet_device.is_disk:
            return blivet_device

        elif blivet_device.type in ("mdarray",):
            return blivet_device

        elif blivet_device.type in ("lvmlv", "lvmthinlv"):
            return blivet_device.vg

        elif blivet_device.parents and blivet_device.parents[0].type in ("mdarray", "mdmember"):
            return blivet_device.parents[0]

        elif blivet_device.type in ("luks/dm-crypt", "integrity/dm-crypt"):
            return self._get_root_device(blivet_device.raw_device)

        # loop devices don't have the "disk" property so just return its
        # parent (FileDevice instance)
        elif blivet_device.type == "loop":
            return blivet_device.parents[0]

        else:
            return blivet_device.disk

    def get_free_device(self, blivet_device):
        """ Get FreeSpaceDevice object for selected device (e.g. VG) """

        # VG -- just get free space in it
        if blivet_device.type == "lvmvg":
            return FreeSpaceDevice(free_size=blivet_device.free_space,
                                   dev_id=self.storage.next_id,
                                   start=None, end=None,
                                   parents=[blivet_device])
        # LV -- we are adding a snapshot --> we need free space in the VG
        elif blivet_device.type == "lvmlv":
            return FreeSpaceDevice(free_size=blivet_device.vg.free_space,
                                   dev_id=self.storage.next_id,
                                   start=None, end=None,
                                   parents=[blivet_device])
        # Thin Pool -- size of the thin LVs/snapshots is limited by the size of the pool
        elif blivet_device.type == "lvmthinpool":
            return FreeSpaceDevice(free_size=blivet_device.size,
                                   dev_id=self.storage.next_id,
                                   start=None, end=None,
                                   parents=[blivet_device])
        # Btrfs Volume -- size of the subvolumes/snapshots is limited by the size of the volume
        elif blivet_device.type == "btrfs volume":
            return FreeSpaceDevice(free_size=blivet_device.size,
                                   dev_id=self.storage.next_id,
                                   start=None, end=None,
                                   parents=[blivet_device])
        # something else, just return size of the device and hope for the best
        else:
            return FreeSpaceDevice(free_size=blivet_device.size,
                                   dev_id=self.storage.next_id,
                                   start=None, end=None,
                                   parents=[blivet_device])

    def _delete_disk_label(self, disk_device):
        """ Delete current disk label

            :param disk_device: blivet device
            :type disk_device: blivet.Device

        """

        try:
            if disk_device.format.exists:
                disk_device.format.teardown()
            action = blivet.deviceaction.ActionDestroyFormat(disk_device)
            self.storage.devicetree.actions.add(action)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=[action], message=None, exception=None, traceback=None)

    def _delete_format(self, blivet_device):
        actions = []

        try:
            if not blivet_device.format_immutable:
                ac_fmt = blivet.deviceaction.ActionDestroyFormat(blivet_device)
                self.storage.devicetree.actions.add(ac_fmt)
                actions.append(ac_fmt)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None,
                                  traceback=None)

    def _delete_device(self, blivet_device):
        actions = []

        if blivet_device.children:
            for device in blivet_device.children:
                res = self._delete_device(device)
                if not res.success:
                    return res
                else:
                    actions.extend(res.actions)

        try:
            if not blivet_device.format_immutable:
                ac_fmt = blivet.deviceaction.ActionDestroyFormat(blivet_device)
                self.storage.devicetree.actions.add(ac_fmt)
                actions.append(ac_fmt)

            ac_dev = blivet.deviceaction.ActionDestroyDevice(blivet_device)
            self.storage.devicetree.actions.add(ac_dev)
            actions.append(ac_dev)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None,
                                  traceback=None)

    def delete_device(self, blivet_device, delete_parents):
        """ Delete device

            :param blivet_device: blivet device
            :type blivet_device: blivet.Device
            :param delete_parents: delete parent devices too?
            :type delete_parents: bool

        """

        log_msg = "Deleting device '%s':\n" % blivet_device.name
        log_utils_call(log=self.log, message=log_msg,
                       user_input={"device": blivet_device, "delete_parents": delete_parents})

        actions = []

        if blivet_device.is_disk:
            result = self._delete_disk_label(blivet_device)
            return result

        result = self._delete_device(blivet_device)
        if not result.success:
            return result
        else:
            actions.extend(result.actions)

        # for encrypted partitions/lvms delete the luks-formatted partition too
        if blivet_device.type in ("luks/dm-crypt", "integrity/dm-crypt"):
            for parent in blivet_device.parents:
                result = self._delete_device(parent)
                if not result.success:
                    return result
                else:
                    actions.extend(result.actions)

        # destroy action for MD array is no-op, the array is destroyed by removing
        # the mdmember format from the parents
        if blivet_device.type == "mdarray":
            for parent in blivet_device.parents:
                if parent.format.exists:
                    try:
                        parent.format.teardown()
                    except Exception as e:  # pylint: disable=broad-except
                        return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                                  traceback=traceback.format_exc())
                result = self._delete_format(parent)
                if not result.success:
                    return result
                else:
                    actions.extend(result.actions)

        # for btrfs volumes delete parents partition after deleting volume
        if blivet_device.type in ("btrfs volume", "mdarray", "lvmvg") and delete_parents:
            for parent in blivet_device.parents:
                if parent.is_disk:
                    result = self._delete_disk_label(parent)
                else:
                    result = self._delete_device(parent)

                if not result.success:
                    return result
                else:
                    actions.extend(result.actions)

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None, traceback=None)

    def _has_snapshots(self, blivet_device):

        for lvs in blivet_device.vg.children:
            if lvs.is_snapshot_lv and lvs.origin == blivet_device:
                return True

        return False

    def _update_min_sizes_info(self):
        """ Update information of minimal size for resizable devices
        """

        for device in self.storage.devices:
            if device.type in ("partition", "lvmlv", "lvmpv", "luks/dm-crypt"):
                # skip mounted devices
                if hasattr(device.format, "system_mountpoint") and device.format.system_mountpoint:
                    continue
                if device.format.type and hasattr(device.format, "update_size_info"):
                    try:
                        device.format.update_size_info()
                    except blivet.errors.FSError:
                        pass

    def device_resizable(self, blivet_device):
        """ Is given device resizable

            :param blivet_device: blivet device
            :type blivet_device: blivet.Device
            :returns: device resizable, min_size, max_size, size
            :rtype: tuple

        """

        if not blivet_device._resizable:
            msg = _("Resizing of {type} devices is currently not supported").format(type=blivet_device.type)
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.protected:
            msg = _("Protected devices cannot be resized")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.format_immutable:
            msg = _("Immutable formats cannot be resized")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.children:
            msg = _("Devices with children cannot be resized")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif not blivet_device.format.type:
            # unformatted devices are not resizable (except extended partitions)
            if (blivet_device.type == "partition" and blivet_device.is_extended and (blivet_device.max_size > blivet_device.size or
               blivet_device.min_size < blivet_device.size)):
                return ProxyDataContainer(resizable=True, error=None, min_size=blivet_device.min_size,
                                          max_size=blivet_device.max_size)
            else:
                msg = _("Unformatted devices are not resizable")
                return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                          max_size=blivet_device.size)

        elif blivet_device.format.type not in self.resizable_filesystems:
            # unfortunately we can't use format._resizable here because blivet uses it to both mark
            # formats as not resizable and force users to call update_size_info on resizable formats
            msg = _("Resizing of {type} format is currently not supported").format(type=blivet_device.format.type)
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif not blivet_device.format._resize.available:
            msg = _("Tools for resizing format {type} are not available.").format(type=blivet_device.format.type)
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif not blivet_device.format.exists:
            # TODO: we could support this by simply changing formats target size but we'd need
            #       a workaround for the missing action
            msg = _("Formats scheduled to be created cannot be resized")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.format.type and not hasattr(blivet_device.format, "update_size_info"):
            msg = _("Format {type} doesn't support updating its size limit information").format(format_type=blivet_device.format.type)
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif hasattr(blivet_device.format, "system_mountpoint") and blivet_device.format.system_mountpoint:
            msg = _("Mounted devices cannot be resized")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.type in ("lvmlv",) and self._has_snapshots(blivet_device):
            msg = _("Logical Volumes with snapshots cannot be resized.")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        elif blivet_device.type == "luks/dm-crypt" and blivet_device.raw_device.format.luks_version == "luks2":
            msg = _("Resizing of LUKS2 devices is currently not supported.")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

        if not self.installer_mode:
            try:
                blivet_device.format.update_size_info()

                if blivet_device.type == "luks/dm-crypt":
                    blivet_device.raw_device.format.update_size_info()

            except blivet.errors.FSError as e:
                msg = _("Failed to update filesystem size info: {error}").format(error=str(e))
                return ProxyDataContainer(resizable=False, error=msg,
                                          min_size=blivet.size.Size("1 MiB"),
                                          max_size=blivet_device.size)

        if blivet_device.resizable and blivet_device.format.resizable:

            if blivet_device.type == "luks/dm-crypt":
                min_size = blivet_device.min_size
                max_size = blivet_device.raw_device.max_size - LUKS_METADATA_SIZE
            else:
                min_size = blivet_device.min_size
                max_size = blivet_device.max_size

            return ProxyDataContainer(resizable=True, error=None, min_size=min_size,
                                      max_size=max_size)

        else:
            if not blivet_device.resizable:
                msg = _("Device is not resizable.")
            elif not blivet_device.format.resizable:
                msg = _("Format is not resizable after updating its size limit information.")
            return ProxyDataContainer(resizable=False, error=msg, min_size=blivet.size.Size("1 MiB"),
                                      max_size=blivet_device.size)

    def format_device(self, user_input):
        log_msg = "Formatting device '%s'\n" % user_input.edit_device.name
        log_utils_call(log=self.log, message=log_msg,
                       user_input=user_input)

        fmt_actions = []

        fmt_actions.append(blivet.deviceaction.ActionDestroyFormat(user_input.edit_device))

        if user_input.filesystem:
            fmt_actions.extend(self._create_format(user_input, user_input.edit_device))

        try:
            for ac in fmt_actions:
                self.storage.devicetree.actions.add(ac)
            return ProxyDataContainer(success=True, actions=fmt_actions, message=None, exception=None, traceback=None)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

    def resize_device(self, user_input):
        device = user_input.edit_device

        log_msg = "Resizing device '%s'\n" % device.name
        log_utils_call(log=self.log, message=log_msg,
                       user_input=user_input)

        if not user_input.resize or user_input.size == device.size:
            return ProxyDataContainer(success=True, actions=None, message=None, exception=None, traceback=None)

        resize_actions = []

        # align size first
        if device.type == "partition":
            aligned_size = device.align_target_size(user_input.size)
        elif device.type == "luks/dm-crypt":
            aligned_size = device.raw_device.align_target_size(user_input.size)
        else:
            aligned_size = user_input.size

        # resize format
        if device.format.resizable:
            resize_actions.append(blivet.deviceaction.ActionResizeFormat(device, aligned_size))

        # resize device
        if device.type == "luks/dm-crypt":
            resize_actions.append(blivet.deviceaction.ActionResizeDevice(device, aligned_size))
            resize_actions.append(blivet.deviceaction.ActionResizeFormat(device.raw_device, aligned_size))
            resize_actions.append(blivet.deviceaction.ActionResizeDevice(device.raw_device, aligned_size + LUKS_METADATA_SIZE))
        else:
            resize_actions.append(blivet.deviceaction.ActionResizeDevice(device, aligned_size))

        # reverse order if grow
        if aligned_size > device.current_size:
            resize_actions.reverse()

        try:
            for ac in resize_actions:
                self.storage.devicetree.actions.add(ac)
            blivet.partitioning.do_partitioning(self.storage)
            return ProxyDataContainer(success=True, actions=resize_actions, message=None, exception=None, traceback=None)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

    def relabel_format(self, user_input):
        label_ac = blivet.deviceaction.ActionConfigureFormat(device=user_input.edit_device,
                                                             attr="label",
                                                             new_value=user_input.label)

        try:
            self.storage.devicetree.actions.add(label_ac)
        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())
        else:
            return ProxyDataContainer(success=True, actions=[label_ac], message=None,
                                      exception=None, traceback=None)

    def edit_lvmvg_device(self, user_input):
        """ Edit LVM Volume group
        """

        actions = []

        if user_input.action_type == "add":
            for parent in user_input.parents_list:
                result = self._add_lvmvg_parent(user_input.edit_device, parent)

                if result.success:
                    actions.extend(result.actions)
                else:
                    return result

        elif user_input.action_type == "remove":
            for parent in user_input.parents_list:
                result = self._remove_lvmvg_parent(user_input.edit_device, parent)

                if result.success:
                    actions.extend(result.actions)
                else:
                    return result

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None, traceback=None)

    def _pick_device_name(self, name, parent_device=None, snapshot=False):
        """ Pick name for device.
            If user chose a name, check it and (if necessary) change it

            :param name: name selected by user
            :type name: str
            :param parent_device: parent device
            :type parent_device: blivet.Device
            :returns: new (valid) name
            :rtype: str

        """

        if not name:
            if parent_device:
                # parent name is part of the child name only on LVM
                if parent_device.type == "lvmvg":
                    name = self.storage.suggest_device_name(parent=parent_device, swap=False)
                else:
                    name = self.storage.suggest_device_name(swap=False)
            elif snapshot:
                name = self.storage.suggest_device_name(parent=parent_device, swap=False, prefix="snapshot")
            else:
                name = self.storage.suggest_container_name()

        else:
            # if name exists add -XX suffix
            if name in self.storage.names or (parent_device and parent_device.name + "-" + name in self.storage.names):
                for i in range(100):
                    if name + "-" + str(i) not in self.storage.names:
                        name = name + "-" + str(i)
                        break

            # if still exists let blivet pick it
            if name in self.storage.names:
                name = self._pick_device_name(name=None, parent_device=parent_device)

        return name

    def _create_format(self, user_input, device):

        fmt_type = user_input.filesystem
        if fmt_type == "btrfs":
            actions = self._create_btrfs_format(user_input, device)
            return actions

        if fmt_type is not None:
            if fmt_type == "ntfs":
                fmt_options = "-f"
            else:
                fmt_options = ""

            new_fmt = blivet.formats.get_format(fmt_type=user_input.filesystem,
                                                label=user_input.label,
                                                mountpoint=user_input.mountpoint,
                                                create_options=fmt_options)
            return [blivet.deviceaction.ActionCreateFormat(device, new_fmt)]

    def _create_btrfs_format(self, user_input, device):
        actions = []

        # format the device to btrfs
        btrfs_fmt = blivet.formats.get_format(fmt_type="btrfs")
        actions.append(blivet.deviceaction.ActionCreateFormat(device, btrfs_fmt))

        if getattr(user_input, "create_volume", True):
            device.format = btrfs_fmt
            new_btrfs = BTRFSVolumeDevice(parents=[device])
            new_btrfs.format = blivet.formats.get_format("btrfs", label=user_input.label, mountpoint=user_input.mountpoint)
            actions.append(blivet.deviceaction.ActionCreateDevice(new_btrfs))

        return actions

    def _align_partition(self, user_input):
        if hasattr(user_input, "advanced"):
            partition_type = user_input.advanced["parttype"] or "primary"
        else:
            partition_type = "primary"

        start = user_input.size_selection.parents[0].free_space.start
        end = user_input.size_selection.parents[0].free_space.end
        size = user_input.size_selection.total_size
        disk = user_input.size_selection.parents[0].parent_device
        size_sectors = size // disk.format.sector_size

        if partition_type == "logical":
            extended = disk.format.extended_partition
            if not extended:
                # this should never happen
                raise ValueError("Trying to add a logical partition to a disk without extended partition.")

            if disk.format.logical_partitions:
                # start 1 MiB after last logical partition
                last_logical = sorted(disk.format.logical_partitions, key=lambda x: x.geometry.start)[-1]
                start = int((last_logical.geometry.end) + (Size("1 MiB") / disk.format.sector_size))
            else:
                # first logical partition -- start 1 MiB after extended partition start
                start = int((extended.geometry.start) + (Size("1 MiB") / disk.format.sector_size))

        # align the start sector up
        constraint = disk.format.parted_device.optimalAlignedConstraint
        start = constraint.startAlign.alignUp(constraint.startRange, start)

        # we moved start of the partition, it's possible we don't have enough free space now
        if start + size_sectors > end:
            size_sectors -= ((start + size_sectors) - end)
        size = size_sectors * disk.format.sector_size

        # align total size for the disklabel
        size = blivet.partitioning.align_size_for_disklabel(size, disk.format)

        return (start, size)

    def _create_partition(self, user_input):
        actions = []

        if hasattr(user_input, "advanced"):
            partition_type = user_input.advanced["parttype"] or "primary"
        else:
            partition_type = "primary"

        # align selected free space start and partition size
        start, size = self._align_partition(user_input)

        # create new partition
        new_part = PartitionDevice(name="req%d" % self.storage.next_id,
                                   size=size,
                                   start=start,
                                   parents=[i.parent_device for i in user_input.size_selection.parents],
                                   part_type=PARTITION_TYPE[partition_type])
        actions.append(blivet.deviceaction.ActionCreateDevice(new_part))

        # encrypted partition -- create a luks device and format it to desired format
        if user_input.encrypt:
            part_fmt = blivet.formats.get_format(fmt_type="luks",
                                                 passphrase=user_input.passphrase,
                                                 luks_version=user_input.encryption_type,
                                                 device=new_part.path)
            actions.append(blivet.deviceaction.ActionCreateFormat(new_part, part_fmt))

            luks_dev = LUKSDevice("luks-%s" % new_part.name, size=new_part.size, parents=[new_part])
            actions.append(blivet.deviceaction.ActionCreateDevice(luks_dev))

            if user_input.filesystem:
                actions.extend(self._create_format(user_input, luks_dev))

        # non-encrypted partition -- just format the partition
        else:
            if partition_type != "extended":
                if user_input.filesystem:
                    actions.extend(self._create_format(user_input, new_part))

        return actions

    def _create_lvmthinlv(self, user_input):
        actions = []

        # parent device is thinpool but name should be derived from the VG
        device_name = self._pick_device_name(user_input.name,
                                             user_input.size_selection.parents[0].parent_device.vg)

        new_part = self.storage.new_lv(thin_volume=True,
                                       name=device_name,
                                       size=user_input.size_selection.total_size,
                                       parents=[i.parent_device for i in user_input.size_selection.parents])
        actions.append(blivet.deviceaction.ActionCreateDevice(new_part))

        if user_input.filesystem:
            actions.extend(self._create_format(user_input, new_part))

        return actions

    def _create_lvmlv(self, user_input):
        actions = []

        vg_device = user_input.size_selection.parents[0].parent_device
        device_name = self._pick_device_name(user_input.name, vg_device)

        # no LVPVSpec for linear LVs
        if user_input.raid_level in ("linear", None):
            new_lv = self.storage.new_lv(name=device_name,
                                         size=user_input.size_selection.total_size,
                                         parents=[vg_device],
                                         seg_type=user_input.raid_level)
            actions.append(blivet.deviceaction.ActionCreateDevice(new_lv))

            # encrypted lvmpv
            if user_input.encrypt:
                luks_fmt = blivet.formats.get_format(fmt_type="luks",
                                                     passphrase=user_input.passphrase,
                                                     luks_version=user_input.encryption_type,
                                                     device=new_lv.path)
                actions.append(blivet.deviceaction.ActionCreateFormat(new_lv, luks_fmt))

                luks_dev = LUKSDevice("luks-%s" % new_lv.name, size=new_lv.size, parents=[new_lv])
                actions.append(blivet.deviceaction.ActionCreateDevice(luks_dev))
        else:
            raise NotImplementedError("RAID LVs not supported.")

        if user_input.filesystem:
            if user_input.encrypt:
                # encrypted lv --> create format on the luks device
                actions.extend(self._create_format(user_input, luks_dev))
            else:
                # 'normal' lv --> create format on the lv
                actions.extend(self._create_format(user_input, new_lv))

        return actions

    def _create_lvmpv(self, user_input):
        actions = []

        # align selected free space start and partition size
        start, size = self._align_partition(user_input)

        new_part = PartitionDevice(name="req%d" % self.storage.next_id,
                                   size=size,
                                   start=start,
                                   parents=[i.parent_device for i in user_input.size_selection.parents])
        actions.append(blivet.deviceaction.ActionCreateDevice(new_part))

        # encrypted lvmpv
        if user_input.encrypt:
            part_fmt = blivet.formats.get_format(fmt_type="luks",
                                                 passphrase=user_input.passphrase,
                                                 luks_version=user_input.encryption_type,
                                                 device=new_part.path)
            actions.append(blivet.deviceaction.ActionCreateFormat(new_part, part_fmt))

            luks_dev = LUKSDevice("luks-%s" % new_part.name, size=new_part.size, parents=[new_part])
            actions.append(blivet.deviceaction.ActionCreateDevice(luks_dev))

            luks_fmt = blivet.formats.get_format(fmt_type="lvmpv")
            actions.append(blivet.deviceaction.ActionCreateFormat(luks_dev, luks_fmt))

        else:
            part_fmt = blivet.formats.get_format(fmt_type="lvmpv")
            actions.append(blivet.deviceaction.ActionCreateFormat(new_part, part_fmt))

        return actions

    def _create_lvmvg(self, user_input):
        actions = []

        device_name = self._pick_device_name(user_input.name)

        new_vg = LVMVolumeGroupDevice(name=device_name,
                                      parents=[i.parent_device for i in user_input.size_selection.parents],
                                      pe_size=user_input.advanced["pesize"])
        actions.append(blivet.deviceaction.ActionCreateDevice(new_vg))

        return actions

    def _create_lvmthinpool(self, user_input):
        actions = []

        vg_device = user_input.size_selection.parents[0].parent_device

        device_name = self._pick_device_name(user_input.name, vg_device)

        new_thin = self.storage.new_lv(thin_pool=True,
                                       name=device_name,
                                       size=user_input.size_selection.total_size,
                                       parents=[vg_device])

        actions.append(blivet.deviceaction.ActionCreateDevice(new_thin))

        return actions

    def _create_lvm(self, user_input):
        actions = []

        for parent in user_input.size_selection.parents:
            # _create_lvmpv needs user_input but we actually don't have it for individual
            # pvs so we need to 'create' it
            size_selection = ProxyDataContainer(total_size=parent.selected_size, parents=[parent])
            pv_input = ProxyDataContainer(size_selection=size_selection,
                                          encrypt=user_input.encrypt,
                                          passphrase=user_input.passphrase,
                                          encryption_type=user_input.encryption_type)
            pv_actions = self._create_lvmpv(pv_input)

            # we need to try to register create actions immediately, if something fails, fail now
            for ac in pv_actions:
                self.storage.devicetree.actions.add(ac)
            actions.extend(pv_actions)

        # we don't have a list of newly created pvs but we have the list of actions
        vg_parents = [ProxyDataContainer(parent_device=ac.device, selected_size=ac.device.size)
                      for ac in actions if ac.is_format and ac._format.type == "lvmpv"]
        vg_input = ProxyDataContainer(name=user_input.name,
                                      size_selection=ProxyDataContainer(total_size=user_input.size_selection.total_size,
                                                                        parents=vg_parents),
                                      advanced=user_input.advanced)
        vg_actions = self._create_lvmvg(vg_input)
        actions.extend(vg_actions)

        return actions

    def _create_snapshot(self, user_input):
        actions = []

        origin_lv = user_input.size_selection.parents[0].parent_device
        device_name = self._pick_device_name(user_input.name, origin_lv.vg)

        if user_input.device_type == "lvm snapshot":
            snapshot_size = user_input.size_selection.total_size
            new_snap = self.storage.new_lv(name=device_name,
                                           parents=[origin_lv.parents[0]],
                                           origin=origin_lv,
                                           size=snapshot_size)
        elif user_input.device_type == "lvm thinsnapshot":
            new_snap = self.storage.new_lv(name=device_name,
                                           parents=[origin_lv.pool],
                                           origin=origin_lv,
                                           seg_type="thin")

        actions.append(blivet.deviceaction.ActionCreateDevice(new_snap))

        return actions

    def _create_mdraid(self, user_input):
        actions = []

        device_name = self._pick_device_name(user_input.name)

        for parent in user_input.size_selection.parents:
            # _create_partition needs user_input but we actually don't have it for individual
            # parent partitions so we need to 'create' it
            size_selection = ProxyDataContainer(total_size=parent.selected_size, parents=[parent])
            part_input = ProxyDataContainer(size_selection=size_selection,
                                            filesystem="mdmember",
                                            encrypt=False,
                                            label=None, mountpoint=None)
            part_actions = self._create_partition(part_input)

            # we need to try to create partitions immediately, if something fails, fail now
            for ac in part_actions:
                self.storage.devicetree.actions.add(ac)
            actions.extend(part_actions)

        md_parents = [ac.device for ac in actions if ac.is_format and ac._format.type == "mdmember"]
        if user_input.advanced:
            chunk_size = user_input.advanced["chunk_size"]
        else:
            chunk_size = None
        new_md = MDRaidArrayDevice(parents=md_parents,
                                   name=device_name,
                                   level=user_input.raid_level,
                                   member_devices=len(md_parents),
                                   total_devices=len(md_parents),
                                   chunk_size=chunk_size)
        actions.append(blivet.deviceaction.ActionCreateDevice(new_md))

        if user_input.encrypt:
            luks_fmt = blivet.formats.get_format(fmt_type="luks",
                                                 passphrase=user_input.passphrase,
                                                 luks_version=user_input.encryption_type,
                                                 device=new_md.path)
            actions.append(blivet.deviceaction.ActionCreateFormat(new_md, luks_fmt))

            luks_dev = LUKSDevice("luks-%s" % new_md.name, size=new_md.size, parents=[new_md])
            actions.append(blivet.deviceaction.ActionCreateDevice(luks_dev))

        if user_input.filesystem:
            if user_input.encrypt:
                # encrypted mdraid --> create format on the luks device
                actions.extend(self._create_format(user_input, luks_dev))
            else:
                # 'normal' mdraid --> create format on the mdraid
                actions.extend(self._create_format(user_input, new_md))

        return actions

    def _create_btrfs_volume(self, user_input):
        actions = []
        device_name = self._pick_device_name(user_input.name)

        for parent in user_input.size_selection.parents:
            # _create_partition needs user_input but we actually don't have it for individual
            # parent partitions so we need to 'create' it
            size_selection = ProxyDataContainer(total_size=parent.selected_size, parents=[parent])
            part_input = ProxyDataContainer(size_selection=size_selection,
                                            filesystem="btrfs",
                                            encrypt=user_input.encrypt,
                                            passphrase=user_input.passphrase,
                                            encryption_type=user_input.encryption_type,
                                            label=None,
                                            mountpoint=None,
                                            create_volume=False)
            part_actions = self._create_partition(part_input)

            # we need to try to create partitions immediately, if something
            # fails, fail now
            for ac in part_actions:
                self.storage.devicetree.actions.add(ac)
            actions.extend(part_actions)

        btrfs_parents = [ac.device for ac in actions if (ac.is_format and ac.is_create) and ac._format.type == "btrfs"]
        new_btrfs = BTRFSVolumeDevice(device_name,
                                      parents=btrfs_parents,
                                      data_level=user_input.raid_level,
                                      metadata_level=user_input.raid_level)
        new_btrfs.format = blivet.formats.get_format("btrfs", label=device_name, mountpoint=user_input.mountpoint)
        actions.append(blivet.deviceaction.ActionCreateDevice(new_btrfs))

        return actions

    def _create_btrfs_subvolume(self, user_input):
        actions = []
        device_name = self._pick_device_name(user_input.name, user_input.size_selection.parents[0].parent_device)

        new_btrfs = BTRFSSubVolumeDevice(device_name, parents=[i.parent_device for i in user_input.size_selection.parents])
        new_btrfs.format = blivet.formats.get_format("btrfs", mountpoint=user_input.mountpoint)
        actions.append(blivet.deviceaction.ActionCreateDevice(new_btrfs))

        return actions

    add_dict = {"partition": _create_partition,
                "lvm": _create_lvm,
                "lvmlv": _create_lvmlv,
                "lvmthinlv": _create_lvmthinlv,
                "lvmthinpool": _create_lvmthinpool,
                "lvmvg": _create_lvmvg,
                "lvmpv": _create_lvmpv,
                "btrfs volume": _create_btrfs_volume,
                "btrfs subvolume": _create_btrfs_subvolume,
                "mdraid": _create_mdraid,
                "lvm snapshot": _create_snapshot,
                "lvm thinsnapshot": _create_snapshot}

    def add_device(self, user_input):
        """ Create new device

            :param user_input: selected parameters from AddDialog
            :type user_input: class UserInput
            :returns: new device name
            :rtype: str

        """

        log_msg = "Adding a new '%s' device:\n" % user_input.device_type
        log_utils_call(log=self.log, message=log_msg,
                       user_input=user_input)

        add_function = self.add_dict[user_input.device_type]

        try:
            actions = add_function(self, user_input)
        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None,
                                      exception=e, traceback=traceback.format_exc())
        try:
            for ac in actions:
                if not ac._applied:
                    self.storage.devicetree.actions.add(ac)

            blivet.partitioning.do_partitioning(self.storage)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None,
                                      exception=e, traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=actions, message=None,
                                  exception=None, traceback=None)

    def _remove_lvmvg_parent(self, container, parent):
        """ Add parent fromexisting lvmg

            :param container: existing lvmvg
            :type container: class blivet.LVMVolumeGroupDevice
            :param parent: parent
            :type parent: class blivet.Device

        """

        try:
            ac_rm = blivet.deviceaction.ActionRemoveMember(container, parent)
            self.storage.devicetree.actions.add(ac_rm)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=[ac_rm], message=None, exception=None, traceback=None)

    def _add_lvmvg_parent(self, container, parent):
        """ Add new parent to existing lvmg

            :param container: existing lvmvg
            :type container: class blivet.LVMVolumeGroupDevice
            :param parent: new parent -- existing device or free space
            :type parent: class blivet.Device or class blivetgui.utils.FreeSpaceDevice

        """

        actions = []

        if parent.type == "free space":
            dev = PartitionDevice(name="req%d" % self.storage.next_id,
                                  size=parent.size,
                                  parents=[i for i in parent.parents])
            ac_part = blivet.deviceaction.ActionCreateDevice(dev)

            fmt = blivet.formats.get_format(fmt_type="lvmpv")
            ac_fmt = blivet.deviceaction.ActionCreateFormat(dev, fmt)

            actions.extend([ac_part, ac_fmt])

            for ac in (ac_part, ac_fmt):
                self.storage.devicetree.actions.add(ac)

            blivet.partitioning.do_partitioning(self.storage)
            parent = dev

        try:
            ac_add = blivet.deviceaction.ActionAddMember(container, parent)
            self.storage.devicetree.actions.add(ac_add)

            actions.append(ac_add)

        except Exception as e:  # pylint: disable=broad-except
            return ProxyDataContainer(success=False, actions=None, message=None, exception=e,
                                      traceback=traceback.format_exc())

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None, traceback=None)

    def get_actions(self):
        """ Return list of currently registered actions
        """

        return self.storage.devicetree.actions.find()

    def get_mountpoints(self):
        """ Return list of current mountpoints
        """

        return list(self.storage.mountpoints.keys())

    def get_supported_filesystems(self, installer_mode=False):
        _fs_types = []

        additional_fs = ["swap", "lvmpv"]
        if installer_mode:
            additional_fs.extend(["biosboot", "prepboot"])

        for cls in blivet.formats.device_formats.values():
            obj = cls()

            supported_fs = (obj.type not in ("tmpfs",) and
                            obj.supported and obj.formattable and
                            (isinstance(obj, blivet.formats.fs.FS) or
                             obj.type in additional_fs))
            if supported_fs:
                _fs_types.append(obj)

        return sorted(_fs_types, key=lambda fs: fs.type)

    def get_default_filesystem(self):
        return self.storage.default_fstype

    def get_system_mountpoints(self, blivet_device):
        return blivet.mounts.mounts_cache.get_mountpoints(blivet_device.path,
                                                          getattr(blivet_device.format, "subvolspec", None))

    def create_disk_label(self, blivet_device, label_type):
        """ Create disklabel

            :param blivet_device: blivet device
            :type blivet_device: blivet.Device
            :param label_type: type of label to create
            :type label_type: str

        """

        log_msg = "Creating a new disklabel on '%s':\n" % blivet_device.name
        log_utils_call(log=self.log, message=log_msg,
                       user_input={"device": blivet_device, "label_type": label_type})

        actions = []

        if blivet_device.format.type:
            actions.append(blivet.deviceaction.ActionDestroyFormat(blivet_device))

        new_label = blivet.formats.get_format("disklabel", device=blivet_device.path,
                                              label_type=label_type)
        actions.append(blivet.deviceaction.ActionCreateFormat(blivet_device, new_label))

        for ac in actions:
            self.storage.devicetree.actions.add(ac)

        return ProxyDataContainer(success=True, actions=actions, message=None, exception=None, traceback=None)

    def luks_decrypt(self, blivet_device, passphrase):
        """ Decrypt selected luks device

            :param blivet_device: device to decrypt
            :type blivet_device: LUKSDevice
            :param passphrase: passphrase
            :type passphrase: str

        """

        log_msg = "Opening LUKS device '%s':\n" % blivet_device
        log_utils_call(log=self.log, message=log_msg,
                       user_input={"device": blivet_device})

        blivet_device.format.passphrase = passphrase

        try:
            if self.installer_mode:
                blivet_device.setup()
            blivet_device.format.setup()

        except blivet.errors.LUKSError:
            return False

        else:
            # save passphrase for future use (in Anaconda only)
            blivet_device.original_format.passphrase = passphrase
            self.storage.save_passphrase(blivet_device)
            self.storage.devicetree.populate()
            return True

    def blivet_cancel_actions(self, actions):
        """ Cancel scheduled actions
        """

        log_msg = "Cancelling scheduled actions:\n"
        log_utils_call(log=self.log, message=log_msg,
                       user_input={"actions": actions})

        actions.reverse()
        for action in actions:
            if action in self.storage.devicetree.actions:
                # XXX: it's possible that something (like anaconda running
                # actions.prune() without telling me) already removed this action
                self.storage.devicetree.actions.remove(action)

    def blivet_reset(self):
        """ Blivet.reset()
        """

        log_msg = "Running reset\n"
        log_utils_call(log=self.log, message=log_msg,
                       user_input=None)

        if self.ignored_disks is not None:
            self.storage.ignored_disks = self.ignored_disks
        if self.exclusive_disks is not None:
            self.storage.exclusive_disks = self.exclusive_disks

        self.storage.reset()

    def blivet_do_it(self, progress_report_hook):
        """ Blivet.do_it()
        """

        log_msg = "Running do_it\n"
        log_utils_call(log=self.log, message=log_msg,
                       user_input=None)

        progress_clbk = lambda clbk_data: progress_report_hook(clbk_data.msg)

        callbacks_reg = blivet.callbacks.create_new_callbacks_register(report_progress=progress_clbk)

        try:
            self.storage.do_it(callbacks=callbacks_reg)

        except Exception as e:  # pylint: disable=broad-except
            return (True, ProxyDataContainer(success=False, exception=e, traceback=traceback.format_exc()))

        else:
            return (True, ProxyDataContainer(success=True))
