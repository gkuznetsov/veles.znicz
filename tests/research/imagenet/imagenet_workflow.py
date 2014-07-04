#!/usr/bin/python3.3 -O

"""
Created on July 4, 2014

Imagenet recognition.

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


#import logging
import numpy
import os
import pickle
#import sys
from zope.interface import implementer

from veles.config import root
from veles.formats import Vector
import veles.error as error
from veles.mutable import Bool
import veles.opencl_types as opencl_types
import veles.plotting_units as plotting_units
import veles.znicz.all2all as all2all
import veles.znicz.conv as conv
import veles.znicz.decision as decision
import veles.znicz.evaluator as evaluator
import veles.znicz.loader as loader
import veles.znicz.nn_plotting_units as nn_plotting_units
from veles.znicz.nn_units import NNSnapshotter
from veles.znicz.standard_workflow import StandardWorkflow
from veles.mean_disp_normalizer import MeanDispNormalizer

IMAGENET_BASE_PATH = os.path.join(root.common.test_dataset_root,
                                  "imagenet")

root.defaults = {
    "decision": {"fail_iterations": 100000,
                 "use_dynamic_alpha": False,
                 "do_export_weights": True},
    "snapshotter": {"prefix": "imagenet"},
    "loader": {"year": "temp",
               "series": "img",
               "minibatch_size": 100},
    "weights_plotter": {"limit": 64},
    "imagenet": {"layers":
                 [{"type": "conv_relu", "n_kernels": 96,
                   "kx": 11, "ky": 11, "padding": (0, 0, 0, 0),
                   "sliding": (4, 4), "weights_filling": "gaussian",
                   "bias_filling": "constant", "bias_stddev": 0,
                   "weights_stddev": 0.01, "learning_rate": 0.001,
                   "learning_rate_bias": 0.002, "weights_decay": 0.004,
                   "weights_decay_bias": 0.004, "gradient_moment": 0.9,
                   "gradient_moment_bias": 0.9},
                  {"type": "max_pooling",
                   "kx": 3, "ky": 3, "sliding": (2, 2)},
                  {"type": "norm", "alpha": 0.00005, "beta": 0.75, "n": 3},

                  {"type": "conv_relu", "n_kernels": 256,
                   "kx": 5, "ky": 5, "padding": (2, 2, 2, 2),
                   "sliding": (1, 1),
                   "weights_filling": "gaussian", "bias_filling": "constant",
                   "bias_stddev": 0, "weights_stddev": 0.01,
                   "learning_rate": 0.001, "learning_rate_bias": 0.002,
                   "weights_decay": 0.004, "weights_decay_bias": 0.004,
                   "gradient_moment": 0.9, "gradient_moment_bias": 0.9},
                  {"type": "max_pooling", "kx": 3, "ky": 3, "sliding": (2, 2)},

                  {"type": "conv", "n_kernels": 384,
                   "kx": 3, "ky": 3, "padding": (1, 1, 1, 1),
                   "sliding": (1, 1), "weights_filling": "gaussian",
                   "weights_stddev": 0.01, "bias_filling": "constant",
                   "bias_stddev": 0,
                   "learning_rate": 0.001, "learning_rate_bias": 0.002,
                   "weights_decay": 0.004, "weights_decay_bias": 0.004,
                   "gradient_moment": 0.9, "gradient_moment_bias": 0.9},

                  {"type": "conv", "n_kernels": 384,
                   "kx": 3, "ky": 3, "padding": (1, 1, 1, 1),
                   "sliding": (1, 1), "weights_filling": "gaussian",
                   "weights_stddev": 0.01, "bias_filling": "constant",
                   "bias_stddev": 0,
                   "learning_rate": 0.001, "learning_rate_bias": 0.002,
                   "weights_decay": 0.004, "weights_decay_bias": 0.004,
                   "gradient_moment": 0.9, "gradient_moment_bias": 0.9},

                  {"type": "conv_relu", "n_kernels": 256,
                   "kx": 3, "ky": 3, "padding": (1, 1, 1, 1),
                   "sliding": (1, 1), "weights_filling": "gaussian",
                   "weights_stddev": 0.01, "bias_filling": "constant",
                   "bias_stddev": 0,
                   "learning_rate": 0.001, "learning_rate_bias": 0.002,
                   "weights_decay": 0.004, "weights_decay_bias": 0.004,
                   "gradient_moment": 0.9, "gradient_moment_bias": 0.9},
                  {"type": "max_pooling", "kx": 3, "ky": 3, "sliding": (2, 2)},

                  {"type": "all2all_relu", "output_shape": 4096,
                   "weights_filling": "gaussian", "weights_stddev": 0.005,
                   "bias_filling": "constant", "bias_stddev": 0,
                   "learning_rate": 0.001,
                   "learning_rate_bias": 0.002, "weights_decay": 0.004,
                   "weights_decay_bias": 0.004, "gradient_moment": 0.9,
                   "gradient_moment_bias": 0.9},

                  {"type": "dropout", "dropout_ratio": 0.5},

                  {"type": "softmax", "output_shape": 1000,
                   "weights_filling": "gaussian",
                   "weights_stddev": 0.01, "bias_filling": "constant",
                   "bias_stddev": 0,
                   "learning_rate": 0.001, "learning_rate_bias": 0.002,
                   "weights_decay": 0.004, "weights_decay_bias": 0.004,
                   "gradient_moment": 0.9, "gradient_moment_bias": 0.9}]}}

CACHED_DATA_FNME = os.path.join(IMAGENET_BASE_PATH, root.loader.year)
root.loader.names_labels_dir = os.path.join(
    CACHED_DATA_FNME, "names_labels_%s_%s_0.pickle" %
    (root.loader.year, root.loader.series))
root.loader.count_samples_dir = os.path.join(
    CACHED_DATA_FNME, "count_samples_%s_%s_0.pickle" %
    (root.loader.year, root.loader.series))
root.loader.file_samples_dir = os.path.join(
    CACHED_DATA_FNME, "original_data_%s_%s_0.dat" %
    (root.loader.year, root.loader.series))
root.loader.matrixes_dir = os.path.join(
    CACHED_DATA_FNME, "matrixes_%s_%s_0.pickle" %
    (root.loader.year, root.loader.series))
root.loader.labels_int_dir = os.path.join(
    CACHED_DATA_FNME, "labels_int_%s_%s_0.txt" %
    (root.loader.year, root.loader.series))


@implementer(loader.ILoader)
class Loader(loader.Loader):
    """loads imagenet from samples.dat, labels.pickle"""
    def __init__(self, workflow, **kwargs):
        super(Loader, self).__init__(workflow, **kwargs)
        self.mean = Vector()
        self.rdisp = Vector()
        self.file_samples = ""

    def init_unpickled(self):
        super(Loader, self).init_unpickled()
        self.original_labels = [0]

    def __getstate__(self):
        stt = super(Loader, self).__getstate__()
        stt["original_labels"] = None
        stt["file_samples"] = None
        return stt

    def load_data(self):
        names_labels_dir = root.loader.names_labels_dir
        count_samples_dir = root.loader.count_samples_dir
        labels_int_dir = root.loader.labels_int_dir
        matrixes_dir = root.loader.matrixes_dir
        file_samples_dir = root.loader.file_samples_dir
        file_names_labels = open(names_labels_dir, "rb")
        file_labels_int = open(labels_int_dir, "w")
        file_labels_int.write("0     no object\n")
        names_labels = pickle.load(file_names_labels)
        for set_type in ("test", "validation", "train"):
            for i, value in enumerate(names_labels[set_type]):
                self.original_labels.append(i + 1)
                line = "%s     %s\n" % (i + 1, value)
                file_labels_int.write(line)
        file_names_labels.close()
        file_count_samples = open(count_samples_dir, "rb")
        self.class_lengths = pickle.load(file_count_samples)
        file_count_samples.close()
        file_matrixes = open(matrixes_dir, "rb")
        matrixes = pickle.load(file_matrixes)
        self.mean.mem = matrixes[0]
        self.rdisp.mem = matrixes[1].astype(
            opencl_types.dtypes[root.common.precision_type])
        self.file_samples = open(file_samples_dir, "rb")

    def create_minibatches(self):
        self.minibatch_data.reset()
        shape = [self.max_minibatch_size]
        shape.extend(self.mean.shape)
        self.minibatch_data.mem = numpy.zeros(shape, dtype=numpy.uint8)

        self.minibatch_labels.reset()
        if not self.original_labels is False:
            shape = [self.max_minibatch_size]
            self.minibatch_labels.mem = numpy.zeros(shape, dtype=numpy.int32)

        self.minibatch_indices.reset()
        self.minibatch_indices.mem = numpy.zeros(self.max_minibatch_size,
                                                 dtype=numpy.int32)

    def fill_minibatch(self):
        idxs = self.minibatch_indices.mem
        sample_size = self.mean.size

        for i, ii in enumerate(idxs[:self.minibatch_size]):
            self.file_samples.seek(int(ii) * sample_size)
            self.file_samples.readinto(self.minibatch_data[i])

        if not self.original_labels is False:
            for i, ii in enumerate(idxs[:self.minibatch_size]):
                self.minibatch_labels[i] = self.original_labels[int(ii)]


class Workflow(StandardWorkflow):
    """Workflow.
    """
    def __init__(self, workflow, **kwargs):
        layers = kwargs.get("layers")
        device = kwargs.get("device")
        kwargs["layers"] = layers
        kwargs["device"] = device
        super(Workflow, self).__init__(workflow, **kwargs)

        self.saver = None

        self.repeater.link_from(self.start_point)

        self.loader = Loader(self, minibatch_size=root.loader.minibatch_size)

        self.meandispnorm = MeanDispNormalizer(self)
        self.meandispnorm.link_attrs(self.loader,
                                     ("input", "minibatch_data"),
                                     "mean", "rdisp")

        self.loader.link_from(self.repeater)

        self.meandispnorm.link_from(self.loader)

        # Add fwds units
        self.parse_fwds_from_config()

        # Add evaluator for single minibatch
        self.evaluator = evaluator.EvaluatorSoftmax(self, device=device)
        self.evaluator.link_from(self.fwds[-1])
        self.evaluator.link_attrs(self.fwds[-1], "output", "max_idx")
        self.evaluator.link_attrs(self.loader,
                                  ("batch_size", "minibatch_size"),
                                  ("labels", "minibatch_labels"),
                                  ("max_samples_per_epoch", "total_samples"))

        # Add decision unit
        self.decision = decision.DecisionGD(
            self, fail_iterations=root.decision.fail_iterations,
            use_dynamic_alpha=root.decision.use_dynamic_alpha,
            do_export_weights=root.decision.do_export_weights)
        self.decision.link_from(self.evaluator)
        self.decision.link_attrs(self.loader,
                                 "minibatch_class", "minibatch_size",
                                 "last_minibatch", "class_lengths",
                                 "epoch_ended", "epoch_number")
        self.decision.link_attrs(
            self.evaluator,
            ("minibatch_n_err", "n_err"),
            ("minibatch_confusion_matrix", "confusion_matrix"))

        self.snapshotter = NNSnapshotter(self, prefix=root.snapshotter.prefix,
                                         directory=root.common.snapshot_dir)
        self.snapshotter.link_from(self.decision)
        self.snapshotter.link_attrs(self.decision,
                                    ("suffix", "snapshot_suffix"))
        self.snapshotter.gate_skip = \
            (~self.decision.epoch_ended | ~self.decision.improved)

        self.create_gd_units_by_config()

        # Error plotter
        self.plt = []
        styles = ["r-", "b-", "k-"]
        for i in range(1, 3):
            self.plt.append(plotting_units.AccumulatingPlotter(
                self, name="num errors", plot_style=styles[i]))
            self.plt[-1].link_attrs(self.decision, ("input", "epoch_n_err_pt"))
            self.plt[-1].input_field = i
            self.plt[-1].link_from(self.decision
                                   if len(self.plt) == 1 else self.plt[-2])
            self.plt[-1].gate_block = (~self.decision.epoch_ended
                                       if len(self.plt) == 1 else Bool(False))
        self.plt[0].clear_plot = True
        self.plt[-1].redraw_plot = True

        # Weights plotter
        self.plt_mx = []
        prev_channels = 3
        for i in range(0, len(layers)):
            if (not isinstance(self.fwds[i], conv.Conv) and
                    not isinstance(self.fwds[i], all2all.All2All)):
                continue
            plt_mx = nn_plotting_units.Weights2D(
                self, name="%s %s" % (i + 1, layers[i]["type"]),
                limit=root.weights_plotter.limit)
            self.plt_mx.append(plt_mx)
            self.plt_mx[-1].link_attrs(self.fwds[i], ("input", "weights"))
            if isinstance(self.fwds[i], conv.Conv):
                self.plt_mx[-1].get_shape_from = (
                    [self.fwds[i].kx, self.fwds[i].ky, prev_channels])
                prev_channels = self.fwds[i].n_kernels
            if (layers[i].get("output_shape") is not None and
                    layers[i]["type"] != "softmax"):
                self.plt_mx[-1].link_attrs(self.fwds[i],
                                           ("get_shape_from", "input"))
            self.plt_mx[-1].link_from(self.decision)
            self.plt_mx[-1].gate_block = ~self.decision.epoch_ended

        # repeater and gate block
        self.repeater.link_from(self.gds[0])
        self.end_point.link_from(self.gds[0])
        self.end_point.gate_block = ~self.decision.complete
        self.loader.gate_block = self.decision.complete

    def parse_fwds_from_config(self):
        """
        Parsing forward units from config.
        Adds a new fowrard unit to self.fwds, links it with previous fwd unit
        by link_from and link_attrs. If self.fwds is empty, links unit with
        self.loader
        """
        if type(self.layers) != list:
            raise error.BadFormatError("layers should be a list of dicts")
        del self.fwds[:]
        for i in range(len(self.layers)):
            layer = self.layers[i]
            tpe, kwargs = self._get_layer_type_kwargs(layer)
            unit = self.layer_map[tpe][0](self, **kwargs)
            self.add_frwd_unit(unit)

    def add_frwd_unit(self, new_unit):
        """
        Adds a new fowrard unit to self.fwds, links it with previous fwd unit
        by link_from and link_attrs. If self.fwds is empty, links unit with
        self.loader
        """
        if len(self.fwds) > 0:
            prev_forward_unit = self.fwds[-1]
            new_unit.link_attrs(prev_forward_unit, ("input", "output"))
        else:
            assert self.loader is not None
            prev_forward_unit = self.meandispnorm
            new_unit.link_attrs(self.meandispnorm, ("input", "output"))
        new_unit.link_from(prev_forward_unit)
        self.fwds.append(new_unit)

    def initialize(self, device):
        super(Workflow, self).initialize(device=device)


def run(load, main):
    load(Workflow, layers=root.imagenet.layers)
    main()
