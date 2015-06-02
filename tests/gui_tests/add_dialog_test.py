# -*- coding: utf-8 -*-
#!/usr/bin/python3

import unittest

from unittest.mock import Mock

from blivetgui.dialogs.add_dialog import SizeChooserArea, AdvancedOptions, SUPPORTED_UNITS

from blivet.size import Size

class SizeChooserAreaTest(unittest.TestCase):

    def setUp(self):
        parent_device = Mock()
        parent_device.name = "sda"
        free_device = Mock(size=Size("100 GiB"))
        dialog = Mock(update_size_areas=Mock(return_value=True))

        self.size_area = SizeChooserArea(dialog=dialog, dialog_type="add", parent_device=parent_device,
            max_size=Size("100 GiB"), min_size=Size("1 MiB"), free_device=free_device)

    def test_unit_change(self):
        original_size = self.size_area.get_selected_size()

        for idx, unit in enumerate(SUPPORTED_UNITS):
            self.size_area.unit_chooser.set_active(idx)
            self.assertEqual(unit, self.size_area.selected_unit)

            new_size = Size(str(self.size_area.spin_size.get_value()) + " " + unit)
            self.assertEqual(original_size, new_size)

    def test_scale_spin(self):
        old_value = self.size_area.scale.get_value()
        new_value = old_value // 2

        self.size_area.scale.set_value(new_value)
        self.assertEqual(new_value, self.size_area.spin_size.get_value())

        self.size_area.spin_size.set_value(old_value)
        self.assertEqual(old_value, self.size_area.scale.get_value())

    def test_get_size(self):
        selected_size = Size(str(self.size_area.spin_size.get_value()) + " " + self.size_area.selected_unit)
        self.assertEqual(selected_size, self.size_area.get_selected_size())

    def test_set_size(self):
        selected_size = (self.size_area.max_size - self.size_area.min_size) // 2
        self.size_area.set_selected_size(selected_size)
        self.assertEqual(selected_size, self.size_area.get_selected_size())

    def test_widget_status(self):
        self.size_area.hide()
        for widget in self.size_area.widgets:
            self.assertFalse(widget.get_visible())

        self.size_area.show()
        for widget in self.size_area.widgets:
            self.assertTrue(widget.get_visible())

        self.size_area.set_sensitive(False)
        for widget in self.size_area.widgets:
            self.assertFalse(widget.get_sensitive())

        self.size_area.set_sensitive(True)
        for widget in self.size_area.widgets:
            self.assertTrue(widget.get_sensitive())

class AdvancedOptionsTest(unittest.TestCase):

    add_dialog = Mock(show_widgets=Mock(return_value=True), hide_widgets=Mock(return_value=True))
    def test_lvm_options(self):
        # test lvm options are displayed for lvm/lvmvg type
        parent_device = Mock(format=Mock(labelType="gpt"))
        free_device = Mock(isLogical=False)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="lvm",
            parent_device=parent_device, free_device=free_device, has_extended=False)

        self.assertFalse(hasattr(advanced_options, "partition_combo"))
        self.assertTrue(hasattr(advanced_options, "pesize_combo"))

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="lvmvg",
            parent_device=parent_device, free_device=free_device, has_extended=False)

        self.assertFalse(hasattr(advanced_options, "partition_combo"))
        self.assertTrue(hasattr(advanced_options, "pesize_combo"))

    def test_partition_options(self):
        # test partition options are displayed for partition type

        parent_device = Mock(format=Mock(labelType="msdos"))
        free_device = Mock(isLogical=False)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="partition",
            parent_device=parent_device, free_device=free_device, has_extended=False)

        self.assertTrue(hasattr(advanced_options, "partition_combo"))
        self.assertFalse(hasattr(advanced_options, "pesize_combo"))

    def test_normal_partition(self):
        # "standard" situation -- disk with msdos part table, no existing extended partition
        # → both "primary and extended" types should be allowed

        parent_device = Mock(format=Mock(labelType="msdos"))
        free_device = Mock(isLogical=False)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="partition",
            parent_device=parent_device, free_device=free_device, has_extended=False)

        part_types = advanced_options.partition_combo.get_model()

        self.assertEqual(len(part_types), 2)
        self.assertEqual(part_types[0][1], "primary")
        self.assertEqual(part_types[1][1], "extended")

    def test_logical_partition(self):
        # adding partition to free space inside extended partition -> only "logical allowed"

        parent_device = Mock(format=Mock(labelType="msdos"))
        free_device = Mock(isLogical=True)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="partition",
            parent_device=parent_device, free_device=free_device, has_extended=True)

        part_types = advanced_options.partition_combo.get_model()

        self.assertEqual(len(part_types), 1)
        self.assertEqual(part_types[0][1], "logical")

    def test_extended_partition(self):
        # extended partition already exists -> allow only "primary" type

        parent_device = Mock(format=Mock(labelType="msdos"))
        free_device = Mock(isLogical=False)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="partition",
            parent_device=parent_device, free_device=free_device, has_extended=True)

        part_types = advanced_options.partition_combo.get_model()

        self.assertEqual(len(part_types), 1)
        self.assertEqual(part_types[0][1], "primary")

    def test_gpt_partitions(self):
        # adding partition on gpt disk -> only "primary" type allowed
        parent_device = Mock(format=Mock(labelType="gpt"))
        free_device = Mock(isLogical=False)

        advanced_options = AdvancedOptions(add_dialog=self.add_dialog, device_type="partition",
            parent_device=parent_device, free_device=free_device, has_extended=False)

        part_types = advanced_options.partition_combo.get_model()

        self.assertEqual(len(part_types), 1)
        self.assertEqual(part_types[0][1], "primary")

if __name__ == "__main__":
    unittest.main()
