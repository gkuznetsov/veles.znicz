# -*-coding: utf-8 -*-
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on Feb 15, 2016

███████████████████████████████████████████████████████████████████████████████

Licensed to the Apache Software Foundation (ASF) under one
or more contributor license agreements.  See the NOTICE file
distributed with this work for additional information
regarding copyright ownership.  The ASF licenses this file
to you under the Apache License, Version 2.0 (the
"License"); you may not use this file except in compliance
with the License.  You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on an
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
KIND, either express or implied.  See the License for the
specific language governing permissions and limitations
under the License.

███████████████████████████████████████████████████████████████████████████████
"""


import json
import logging
import cv2
import numpy
import os
from psutil import virtual_memory
import scipy.misc

import veles
from veles.config import root
import veles.error as error
from veles.downloader import Downloader
from veles.loader import ImageLoader, CLASS_NAME
from veles.loader.file_image import FileListImageLoader
from veles.loader.fullbatch_image import FullBatchImageLoader
from veles.prng.random_generator import RandomGenerator
from veles.external.progressbar import ProgressBar, Bar, Percentage


class LoaderChannelsTest(FullBatchImageLoader, FileListImageLoader):
    MAPPING = "interactive_image"
    DISABLE_INTERFACE_VERIFICATION = True

    def __init__(self, workflow, **kwargs):
        super(LoaderChannelsTest, self).__init__(workflow, **kwargs)
        self.path_to_bboxes = kwargs["path_to_bboxes"]
        self.new_class_keys = {0: []}
        self.bboxes = {}

    def derive_from(self, loader):
        super(LoaderChannelsTest, self).derive_from(loader)
        self.color_space = loader.color_space
        self._original_shape = loader.original_shape
        self.path_to_mean = loader.path_to_mean
        self.add_sobel = loader.add_sobel
        self.mirror = loader.mirror
        self.scale = loader.scale
        self.scale_maintain_aspect_ratio = loader.scale_maintain_aspect_ratio
        self.rotations = loader.rotations
        self.crop = loader.crop
        self.crop_number = loader.crop_number
        self._background = loader._background
        self.background_image = loader.background_image
        self.background_color = loader.background_color
        self.smart_crop = loader.smart_crop

    def load_data(self):
        try:
            super(ImageLoader, self).load_data()
        except AttributeError:
            pass
        with open(self.path_to_bboxes, "r") as fin:
            self.bboxes = json.load(fin)
        if self.restored_from_snapshot and not self.testing:
            self.info("Scanning for changes...")
            progress = ProgressBar(maxval=self.total_samples, term_width=40)
            progress.start()
            for keys in self.class_keys:
                for key in keys:
                    progress.inc()
                    im_size, _ = self.get_effective_image_info(key)
                    if im_size != self.uncropped_shape:
                        raise error.BadFormatError(
                            "%s changed the effective size (now %s, was %s)" %
                            (key, im_size, self.uncropped_shape))
            progress.finish()
            return
        for keys in self.class_keys:
            del keys[:]
        for index, class_name in enumerate(CLASS_NAME):
            keys = set(self.get_keys(index))
            self.class_keys[index].extend(keys)
            self.class_lengths[index] = len(keys) * len(self.bboxes)
            self.class_keys[index].sort()

        if self.uncropped_shape == tuple():
            raise error.BadFormatError(
                "original_shape was not initialized in get_keys()")
        self.info(
            "Found %d samples of shape %s (%d TEST, %d VALIDATION, %d TRAIN)",
            self.total_samples, self.shape, *self.class_lengths)

        # Perform a quick (unreliable) test to determine if we have labels
        keys = next(k for k in self.class_keys if len(k) > 0)
        self._has_labels = self.load_keys(
            (keys[RandomGenerator(None).randint(len(keys))],),
            None, None, None, None)
        self._resize_validation_keys(self.load_labels())
        # Allocate data
        required_mem = self.total_samples * numpy.prod(self.shape) * \
            numpy.dtype(self.source_dtype).itemsize
        if virtual_memory().available < required_mem:
            gb = 1.0 / (1000 * 1000 * 1000)
            self.critical("Not enough memory (free %.3f Gb, required %.3f Gb)",
                          virtual_memory().free * gb, required_mem * gb)
            raise MemoryError("Not enough memory")
        # Real allocation will still happen during the second pass
        self.create_originals(self.shape)
        self.original_label_values.mem = numpy.zeros(
            self.total_samples, numpy.float32)

        has_labels = self._fill_original_data()

        # Delete labels mem if no labels was extracted
        if numpy.prod(has_labels) == 0 and sum(has_labels) > 0:
            raise error.BadFormatError(
                "Some classes do not have labels while other do")
        if sum(has_labels) == 0:
            del self.original_labels[:]

    def _fill_original_data(self):
        pbar = ProgressBar(
            term_width=50, maxval=self.total_samples * self.samples_inflation,
            widgets=["Loading %dx%d images " % (self.total_samples,
                                                self.crop_number),
                     Bar(), ' ', Percentage()],
            log_level=logging.INFO, poll=0.5)
        pbar.start()
        offset = 0
        has_labels = []
        data = self.original_data.mem
        label_values = self.original_label_values.mem
        for keys in self.class_keys:
            if len(keys) == 0:
                continue
            if self.samples_inflation == 1:
                labels = [None] * self.total_samples
                has_labels.append(self.load_keys(
                    keys, pbar, data[offset:], labels,
                    label_values[offset:]))
                offset += len(keys)
            else:
                labels = [None] * self.total_samples * self.samples_inflation
                offset, hl = self._load_distorted_keys(
                    keys, data, labels, label_values, offset, pbar)
                has_labels.append(hl)
            self.original_labels[offset - len(labels):offset] = labels
        pbar.finish()
        return has_labels

    def _load_image(self, key, crop=True):
        """Returns the data to serve corresponding to the given image key and
        the label value (from 0 to 1).
        """
        data = self.get_image_data(key)
        size_, color_ = self.get_image_info(key)
        return data, size_, color_

    def crop_image(self, frame, bbx):
        bbx = numpy.array(bbx, numpy.int32)
        ymin, ymax = bbx[:2]
        xmin, xmax = bbx[2:]
        self.debug(
            "bbox: x_min %s x_max %s y_min %s y_max %s"
            % (xmin, xmax, ymin, ymax))
        return frame[ymin:ymax, xmin:xmax]

    def get_images_from_bboxes(self, sample, bboxes):
        images = []
        for bbx in bboxes:
            cropted_image = self.crop_image(sample, bbx)
            images.append(cropted_image)
        return images

    def load_keys(self, keys, pbar, data, labels, label_values, crop=True):
        """Loads data from the specified keys.
        """
        index = 0
        has_labels = False
        for key in keys:
            img, sz, clr = self._load_image(key)
            lbl, has_labels = self._load_label(key, has_labels)
            images = self.get_images_from_bboxes(img, self.bboxes)
            for obj in images:
                bbx = self.get_image_bbox(key, sz)
                img, label_value, _ = self.preprocess_image(
                    obj, clr, crop, bbx)
                if data is not None:
                    data[index] = img
                    self.new_class_keys[0].append(key)
                if labels is not None:
                    labels[index] = lbl
                if label_values is not None:
                    label_values[index] = label_value
                index += 1
                if pbar is not None:
                    pbar.inc()
        return has_labels


def create_forward(workflow, normalizer, labels_mapping, loader_config):
    # Disable plotters:
    workflow.plotters_are_enabled = False

    # Link downloader
    workflow.start_point.unlink_after()
    workflow.downloader = Downloader(
        workflow,
        url="https://s3-eu-west-1.amazonaws.com/veles."
            "forge/TvChannels/channels_test.tar",
        directory=root.common.dirs.datasets,
        files=["channels_test"])
    workflow.downloader.link_from(workflow.start_point)
    workflow.repeater.link_from(workflow.downloader)

    # Cnanging Channels Loader to another Loader:
    new_loader = workflow.change_unit(
        workflow.loader.name,
        LoaderChannelsTest(workflow, **loader_config))

    workflow.loader = new_loader

    # Link attributes:
    # TODO: remove link attributes after adding in change_unit() function
    # TODO: data links transmission
    workflow.forwards[0].link_attrs(
        new_loader, ("input", "minibatch_data"))

    workflow.evaluator.link_attrs(
        new_loader,
        ("batch_size", "minibatch_size"),
        ("labels", "minibatch_labels"),
        ("max_samples_per_epoch", "total_samples"),
        "class_lengths", ("offset", "minibatch_offset"))
    workflow.decision.link_attrs(
        new_loader, "minibatch_class", "last_minibatch",
        "minibatch_size", "class_lengths", "epoch_ended", "epoch_number")

    workflow.evaluator.link_attrs(new_loader, ("class_keys", "new_class_keys"))

    # Set normalizer from previous Loader to new one:
    new_loader._normalizer = normalizer

    # Set labels_mapping and class_keys in Evaluator to correct writting the
    # results:
    workflow.evaluator.labels_mapping = labels_mapping


if __name__ == "__main__":
    parameters = {
        "dry_run": "init",
        "snapshot":
        "https://s3-eu-west-1.amazonaws.com/veles.forge/TvChannels/"
        "channels_validation_0.40_train_0.07.4.pickle.gz",
        "stealth": True,
        "device": 0}
    path_to_model = "veles/znicz/tests/research/TvChannels/channels.py"
    data_path = os.path.join(root.common.dirs.datasets, "channels_test")

    # Load workflow from snapshot
    launcher = veles(path_to_model, **parameters)  # pylint: disable=E1102

    # Swith to testing mode:
    launcher.testing = True
    loader_conf = {"minibatch_size": 1,
                   "shuffle_limit": 0,
                   "normalization_type": "mean_disp",
                   "add_sobel": True,
                   "file_subtypes": ["png"],
                   "background_image":
                   numpy.zeros([256, 256, 4], dtype=numpy.uint8),
                   "mirror": False,
                   "color_space": "HSV",
                   "scale": (256, 256),
                   "background_color": (0, 0, 0, 0),
                   "scale_maintain_aspect_ratio": True,
                   "base_directory": os.path.join(data_path, "pictures"),
                   "path_to_test_text_file":
                   [os.path.join(data_path, "channels_test.txt")],
                   "path_to_bboxes":
                   os.path.join(data_path, "bboxes_auto.json"),

                   }
    create_forward(
        launcher.workflow, normalizer=launcher.workflow.loader.normalizer,
        labels_mapping=launcher.workflow.loader.reversed_labels_mapping,
        loader_config=loader_conf)

    # Initialize and run new workflow:
    launcher.boot()

    # Write results:
    results = launcher.workflow.gather_results()

    output = results["Output"]
    base_path_to_labeled_pictures = os.path.join(data_path, "out_pictures")

    for path_to_original, value in output.items():
        label, bbox_number = value
        bbox = launcher.workflow.loader.bboxes[bbox_number]
        bbox = numpy.array(bbox, numpy.int32)
        y_min, y_max = bbox[:2]
        x_min, x_max = bbox[2:]
        name_image = os.path.basename(path_to_original)[:-4]
        name_dir = os.path.dirname(path_to_original)
        new_path = os.path.join(
            os.path.dirname(name_dir), "out_pictures/" + name_image + ".png")
        image, size, color = launcher.workflow.loader._load_image(
            path_to_original)

        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 3)
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(
            image, label, (x_min - 50, y_min - 50), font, 2,
            (255, 255, 255), 2, cv2.LINE_AA)

        print("Saved image to %s" % new_path)
        scipy.misc.imsave(new_path, image)

    out_file = os.path.join(data_path, "result.txt")
    with open(out_file, "w") as fout:
        json.dump(results, fout, sort_keys=True)
    print("Successfully wrote %d results to %s", len(results), out_file)
