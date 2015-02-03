"""
Created on Jan 26, 2015

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


import os
import tarfile
import wget
import zipfile
from zope.interface import implementer

from veles.config import root
from veles.distributable import TriviallyDistributable
from veles.units import Unit, IUnit


if not hasattr(zipfile, "BadZipFile"):
    zipfile.BadZipFile = zipfile.error


@implementer(IUnit)
class Downloader(Unit, TriviallyDistributable):
    """
    Retrieves data through the specified URL to the file system.
    It uses wget as a quick and dirty solution.

    Attributes:
        url: url from download the data
        directory: directory to download the data
        files: list of files, which is obligatory to load
    """
    def __init__(self, workflow, **kwargs):
        kwargs["view_group"] = kwargs.get("view_group", "SERVICE")
        super(Downloader, self).__init__(workflow, **kwargs)
        self.url = kwargs["url"]
        self.files = kwargs.get("files", [])
        self.directory = kwargs.get(
            "directory", root.common.test_dataset_root)

    @property
    def directory(self):
        return self._directory

    @directory.setter
    def directory(self, value):
        if not isinstance(value, str):
            raise TypeError("Directory value must be a string")
        if not os.path.exists(value):
            raise ValueError("Directory %s does not exist" % value)
        if not os.access(value, os.W_OK):
            raise ValueError("Can not write to directory %s" % value)
        self._directory = value

    @property
    def files(self):
        return self._files

    @files.setter
    def files(self, value):
        if not isinstance(value, list):
            raise TypeError("Files value must be a list of strings")
        self._files = value

    def initialize(self, **kwargs):
        try:
            super(Downloader, self).initialize(**kwargs)
        except AttributeError:
            pass
        if all([os.path.exists(os.path.join(self.directory, data_file))
                for data_file in self.files]):
            return
        self.info("Downloading from %s to %s..." % (self.url, self.directory))
        downloaded_file = wget.download(self.url, self.directory)
        file_is_archive = True
        try:
            with zipfile.ZipFile(downloaded_file) as zip_file:
                zip_file.extractall(self.directory)
        except zipfile.BadZipFile:
            with tarfile.open(downloaded_file) as tar_file:
                tar_file.extractall(self.directory)
        except tarfile.ReadError:
            file_is_archive = False
            self.warning("Downloaded file is not a zip or tar")
        if file_is_archive:
            os.remove(downloaded_file)

    def run(self):
        pass
