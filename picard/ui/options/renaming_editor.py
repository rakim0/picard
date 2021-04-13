# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2006-2008, 2011 Lukáš Lalinský
# Copyright (C) 2008-2009 Nikolai Prokoschenko
# Copyright (C) 2009-2010, 2014-2015, 2018-2021 Philipp Wolfer
# Copyright (C) 2011-2013 Michael Wiencek
# Copyright (C) 2011-2013 Wieland Hoffmann
# Copyright (C) 2013 Calvin Walton
# Copyright (C) 2013 Ionuț Ciocîrlan
# Copyright (C) 2013-2014 Sophist-UK
# Copyright (C) 2013-2015, 2018-2019, 2021 Laurent Monin
# Copyright (C) 2015 Alex Berman
# Copyright (C) 2015 Ohm Patel
# Copyright (C) 2016 Suhas
# Copyright (C) 2016-2017 Sambhav Kothari
# Copyright (C) 2021 Gabriel Ferreira
# Copyright (C) 2021 Bob Swift
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from functools import partial
import os.path

from picard.config import (
    TextOption,
    get_config,
)
from picard.const import DEFAULT_FILE_NAMING_FORMAT
from picard.file import File
from picard.script import (
    ScriptError,
    ScriptParser,
)
from picard.util.settingsoverride import SettingsOverride

from picard.ui import (
    PicardDialog,
    SingletonDialog,
)
from picard.ui.options import (
    OptionsCheckError,
    OptionsPage,
)
from picard.ui.options.scripting import (
    ScriptCheckError,
    ScriptingDocumentationDialog,
)
from picard.ui.ui_options_renaming_editor import Ui_RenamingEditorOptionsPage


class RenamingEditorOptionsPage(PicardDialog, SingletonDialog):

    NAME = "filerenamingeditor"
    TITLE = N_("File Naming Editor")
    PARENT = None
    SORT_ORDER = 40
    ACTIVE = True
    HELP_URL = '/config/options_filerenaming.html'
    STYLESHEET_ERROR = OptionsPage.STYLESHEET_ERROR

    options = [
        TextOption(
            "setting",
            "file_naming_format",
            DEFAULT_FILE_NAMING_FORMAT,
        ),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_RenamingEditorOptionsPage()
        self.ui.setupUi(self)

        self.PARENT = parent

        self.ui.file_naming_editor_save.clicked.connect(self.save_script)
        self.ui.file_naming_editor_cancel.clicked.connect(self.reject)

        self.ui.file_naming_format.setEnabled(True)
        self.ui.file_naming_format_default.setEnabled(True)

        self.ui.file_naming_format.textChanged.connect(self.check_formats)
        self.ui.file_naming_format_default.clicked.connect(self.set_file_naming_format_default)

        self.ui.scripting_documentation_button.clicked.connect(self.show_scripting_documentation)
        self.ui.example_filename_sample_files_button.clicked.connect(self._sample_example_files)
        self._sampled_example_files = []

        # Sync example lists vertical scrolling
        def sync_vertical_scrollbars(widgets):
            """Sync position of vertical scrollbars for listed widgets"""
            def _sync_scrollbar_vert(widget, value):
                widget.blockSignals(True)
                widget.verticalScrollBar().setValue(value)
                widget.blockSignals(False)

            widgets = set(widgets)
            for widget in widgets:
                for other in widgets - {widget}:
                    widget.verticalScrollBar().valueChanged.connect(
                        partial(_sync_scrollbar_vert, other))

        # Sync example lists vertical scrolling
        sync_vertical_scrollbars((self.ui.example_filename_before, self.ui.example_filename_after))

        self.load()

    def save_script(self):
        self.PARENT.ui.file_naming_format.setPlainText(self.ui.file_naming_format.toPlainText())
        self.accept()

    def show_scripting_documentation(self):
        ScriptingDocumentationDialog.show_instance(parent=self)

    def check_formats(self):
        self.test()
        self.update_examples()

    def _example_to_filename(self, file):
        config = get_config()
        settings = SettingsOverride(config.setting, {
            'ascii_filenames': self.PARENT.ui.ascii_filenames.isChecked(),
            'file_naming_format': self.ui.file_naming_format.toPlainText(),
            'move_files': self.PARENT.ui.move_files.isChecked(),
            'move_files_to': os.path.normpath(self.PARENT.ui.move_files_to.text()),
            'rename_files': self.PARENT.ui.rename_files.isChecked(),
            'windows_compatibility': self.PARENT.ui.windows_compatibility.isChecked(),
        })

        try:
            if config.setting["enable_tagger_scripts"]:
                for s_pos, s_name, s_enabled, s_text in config.setting["list_of_scripts"]:
                    if s_enabled and s_text:
                        parser = ScriptParser()
                        parser.eval(s_text, file.metadata)
            filename_before = file.filename
            filename_after = file.make_filename(filename_before, file.metadata, settings)
            if not settings["move_files"]:
                return os.path.basename(filename_before), os.path.basename(filename_after)
            return filename_before, filename_after
        except ScriptError:
            return "", ""
        except TypeError:
            return "", ""

    def _sample_example_files(self):
        # Get a new sample of randomly selected /loaded files to use as renaming examples
        import random
        max_samples = 10  # pick up to 10 samples
        if self.tagger.window.selected_objects:
            # If files/albums/tracks are selected, sample example files from them
            files = self.tagger.get_files_from_objects(self.tagger.window.selected_objects)
            length = min(max_samples, len(files))
            files = [file for file in random.sample(files, k=length)]
        else:
            # If files/albums/tracks are not selected, sample example files from the pool of loaded files
            files = self.tagger.files
            length = min(max_samples, len(files))
            files = [files[key] for key in random.sample(files.keys(), k=length)]

        if not files:
            # If no file has been loaded, use generic examples
            files = self.PARENT.default_examples
        self._sampled_example_files = files
        self.update_examples()

    def update_examples(self):
        self.ui.example_filename_before.clear()
        self.ui.example_filename_after.clear()

        if not self._sampled_example_files:
            self._sample_example_files()
        example_files = self._sampled_example_files

        examples = [self._example_to_filename(example) for example in example_files]
        for before, after in sorted(examples, key=lambda x: x[1]):
            self.ui.example_filename_before.addItem(before)
            self.ui.example_filename_after.addItem(after)

    def load(self):
        self.ui.file_naming_format.setPlainText(self.PARENT.ui.file_naming_format.toPlainText())
        self.update_examples()

    def check(self):
        self.check_format()
        if self.PARENT.ui.move_files.isChecked() and not self.PARENT.ui.move_files_to.text().strip():
            raise OptionsCheckError(_("Error"), _("The location to move files to must not be empty."))

    def check_format(self):
        parser = ScriptParser()
        try:
            parser.eval(self.ui.file_naming_format.toPlainText())
        except Exception as e:
            raise ScriptCheckError("", str(e))
        if self.PARENT.ui.rename_files.isChecked():
            if not self.ui.file_naming_format.toPlainText().strip():
                raise ScriptCheckError("", _("The file naming format must not be empty."))

    def display_error(self, error):
        # Ignore scripting errors, those are handled inline
        if not isinstance(error, ScriptCheckError):
            super().display_error(error)

    def set_file_naming_format_default(self):
        self.ui.file_naming_format.setText(self.options[0].default)

    def test(self):
        self.ui.renaming_error.setStyleSheet("")
        self.ui.renaming_error.setText("")
        try:
            self.check_format()
        except ScriptCheckError as e:
            self.ui.renaming_error.setStyleSheet(self.STYLESHEET_ERROR)
            self.ui.renaming_error.setText(e.info)
            return