#!/usr/bin/python3.3 -O
"""
Created on Mar 20, 2013

File for MNIST dataset (NN with RELU activation).

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""


import numpy
import struct
import os

from veles.config import root, get_config
import veles.formats as formats
import veles.error as error
import veles.plotting_units as plotting_units
import veles.znicz.nn_units as nn_units
import veles.znicz.all2all as all2all
import veles.znicz.decision as decision
import veles.znicz.evaluator as evaluator
import veles.znicz.gd as gd
import veles.znicz.loader as loader

mnist_dir = os.path.join(root.common.veles_dir, "veles/znicz/samples/MNIST")

root.update = {"all2all": {"weights_magnitude":
                           get_config(root.all2all.weights_magnitude, 0.05)},
               "decision": {"fail_iterations":
                            get_config(root.decision.fail_iterations, 150),
                            "snapshot_prefix":
                            get_config(root.decision.snapshot_prefix,
                                       "mnist_relu")},
               "global_alpha": get_config(root.global_alpha, 0.01),
               "global_lambda": get_config(root.global_lambda, 0.0),
               "layers_mnist_relu": get_config(root.layers_mnist_relu,
                                               [100, 10]),
               "loader": {"minibatch_maxsize":
                          get_config(root.loader.minibatch_maxsize, 60)},
               "path_for_load_data_test_images":
               get_config(root.path_for_load_data_test_images,
                          os.path.join(mnist_dir, "t10k-images.idx3-ubyte")),
               "path_for_load_data_test_label":
               get_config(root.path_for_load_data_test_label,
                          os.path.join(mnist_dir, "t10k-labels.idx1-ubyte")),
               "path_for_load_data_train_images":
               get_config(root.path_for_load_data_train_images,
                          os.path.join(mnist_dir, "train-images.idx3-ubyte")),
               "path_for_load_data_train_label":
               get_config(root.path_for_load_data_train_label,
                          os.path.join(mnist_dir, "train-labels.idx1-ubyte"))}


class Loader(loader.FullBatchLoader):
    """Loads MNIST dataset.
    """
    def load_original(self, offs, labels_count, labels_fnme, images_fnme):
        """Loads data from original MNIST files.
        """
        self.info("Loading from original MNIST files...")

        # Reading labels:
        fin = open(labels_fnme, "rb")

        header, = struct.unpack(">i", fin.read(4))
        if header != 2049:
            raise error.ErrBadFormat("Wrong header in train-labels")

        n_labels, = struct.unpack(">i", fin.read(4))
        if n_labels != labels_count:
            raise error.ErrBadFormat("Wrong number of labels in train-labels")

        arr = numpy.zeros(n_labels, dtype=numpy.byte)
        n = fin.readinto(arr)
        if n != n_labels:
            raise error.ErrBadFormat("EOF reached while reading labels from "
                                     "train-labels")
        self.original_labels[offs:offs + labels_count] = arr[:]
        if self.original_labels.min() != 0 or self.original_labels.max() != 9:
            raise error.ErrBadFormat("Wrong labels range in train-labels.")

        fin.close()

        # Reading images:
        fin = open(images_fnme, "rb")

        header, = struct.unpack(">i", fin.read(4))
        if header != 2051:
            raise error.ErrBadFormat("Wrong header in train-images")

        n_images, = struct.unpack(">i", fin.read(4))
        if n_images != n_labels:
            raise error.ErrBadFormat("Wrong number of images in train-images")

        n_rows, n_cols = struct.unpack(">2i", fin.read(8))
        if n_rows != 28 or n_cols != 28:
            raise error.ErrBadFormat("Wrong images size in train-images, "
                                     "should be 28*28")

        # 0 - white, 255 - black
        pixels = numpy.zeros(n_images * n_rows * n_cols, dtype=numpy.ubyte)
        n = fin.readinto(pixels)
        if n != n_images * n_rows * n_cols:
            raise error.ErrBadFormat("EOF reached while reading images "
                                     "from train-images")

        fin.close()

        # Transforming images into float arrays and normalizing to [-1, 1]:
        images = pixels.astype(numpy.float32).reshape(n_images, n_rows, n_cols)
        self.info("Original range: [%.1f, %.1f]" %
                  (images.min(), images.max()))
        for image in images:
            formats.normalize(image)
        self.info("Range after normalization: [%.1f, %.1f]" %
                  (images.min(), images.max()))
        self.original_data[offs:offs + n_images] = images[:]
        self.info("Done")

    def load_data(self):
        """Here we will load MNIST data.
        """
        self.original_labels = numpy.zeros([70000], dtype=numpy.int8)
        self.original_data = numpy.zeros([70000, 28, 28], dtype=numpy.float32)

        self.load_original(0, 10000, root.path_for_load_data_test_label,
                           root.path_for_load_data_test_images)
        self.load_original(10000, 60000, root.path_for_load_data_train_label,
                           root.path_for_load_data_train_images)

        self.class_samples[0] = 0
        self.class_samples[1] = 10000
        self.class_samples[2] = 60000


class Workflow(nn_units.NNWorkflow):
    """Workflow for MNIST dataset (handwritten digits recognition).
    """
    def __init__(self, workflow, **kwargs):
        layers = kwargs.get("layers")
        device = kwargs.get("device")
        kwargs["layers"] = layers
        kwargs["device"] = device
        kwargs["name"] = kwargs.get("name", "MNIST")
        super(Workflow, self).__init__(workflow, **kwargs)

        self.rpt.link_from(self.start_point)

        self.loader = Loader(self, name="Mnist fullbatch loader",
                             minibatch_maxsize=root.loader.minibatch_maxsize)
        self.loader.link_from(self.rpt)

        # Add forward units
        del self.forward[:]
        for i in range(0, len(layers)):
            if i < len(layers) - 1:
                aa = all2all.All2AllRELU(
                    self, output_shape=[layers[i]], device=device,
                    weights_magnitude=root.all2all.weights_magnitude)
            else:
                aa = all2all.All2AllSoftmax(
                    self, output_shape=[layers[i]], device=device,
                    weights_magnitude=root.all2all.weights_magnitude)
            self.forward.append(aa)
            if i:
                self.forward[i].link_from(self.forward[i - 1])
                self.forward[i].input = self.forward[i - 1].output
            else:
                self.forward[i].link_from(self.loader)
                self.forward[i].input = self.loader.minibatch_data

        # Add evaluator for single minibatch
        self.ev = evaluator.EvaluatorSoftmax(self, device=device)
        self.ev.link_from(self.forward[-1])
        self.ev.link_attrs(self.forward[-1], ("y", "output"), "max_idx")
        self.ev.link_attrs(self.loader,
                           ("batch_size", "minibatch_size"),
                           ("labels", "minibatch_labels"),
                           ("max_samples_per_epoch", "total_samples"))

        # Add decision unit
        self.decision = decision.Decision(
            self, snapshot_prefix=root.decision.snapshot_prefix,
            fail_iterations=root.decision.fail_iterations)
        self.decision.link_from(self.ev)
        self.decision.link_attrs(self.loader,
                                 "minibatch_class",
                                 "minibatch_last",
                                 "class_samples")
        self.decision.link_attrs(
            self.ev,
            ("minibatch_n_err", "n_err"),
            ("minibatch_confusion_matrix", "confusion_matrix"),
            ("minibatch_max_err_y_sum", "max_err_y_sum"))

        # Add gradient descent units
        del self.gd[:]
        self.gd.extend(list(None for i in range(0, len(self.forward))))
        self.gd[-1] = gd.GDSM(self, device=device)
        self.gd[-1].link_from(self.decision)
        self.gd[-1].link_attrs(self.forward[-1],
                               ("y", "output"),
                               ("h", "input"),
                               "weights", "bias")
        self.gd[-1].link_attrs(self.ev, "err_y")
        self.gd[-1].link_attrs(self.loader, ("batch_size", "minibatch_size"))
        self.gd[-1].gate_skip = self.decision.gd_skip
        for i in range(len(self.forward) - 2, -1, -1):
            self.gd[i] = gd.GDRELU(self, device=device)
            self.gd[i].link_from(self.gd[i + 1])
            self.gd[i].link_attrs(self.forward[i],
                                  ("y", "output"),
                                  ("h", "input"),
                                  "weights", "bias")
            self.gd[i].link_attrs(self.loader, ("batch_size",
                                                "minibatch_size"))
            self.gd[i].link_attrs(self.gd[i + 1], ("err_y", "err_h"))
            self.gd[i].gate_skip = self.decision.gd_skip
        self.rpt.link_from(self.gd[0])

        self.end_point.link_from(self.gd[0])
        self.end_point.gate_block = ~self.decision.complete

        self.loader.gate_block = self.decision.complete

        # Error plotter
        self.plt = []
        styles = ["r-", "b-", "k-"]
        for i in range(1, 3):
            self.plt.append(plotting_units.AccumulatingPlotter(
                self, name="num errors", plot_style=styles[i]))
            self.plt[-1].input = self.decision.epoch_n_err_pt
            self.plt[-1].input_field = i
            self.plt[-1].link_from(self.decision)
            self.plt[-1].gate_block = ~self.decision.epoch_ended
        self.plt[0].clear_plot = True
        self.plt[-1].redraw_plot = True
        # Confusion matrix plotter
        self.plt_mx = []
        for i in range(1, len(self.decision.confusion_matrixes)):
            self.plt_mx.append(plotting_units.MatrixPlotter(
                self, name=(("Test", "Validation", "Train")[i] + " matrix")))
            self.plt_mx[-1].input = self.decision.confusion_matrixes
            self.plt_mx[-1].input_field = i
            self.plt_mx[-1].link_from(self.decision)
            self.plt_mx[-1].gate_block = ~self.decision.epoch_ended
        # err_y plotter
        self.plt_err_y = []
        for i in range(1, 3):
            self.plt_err_y.append(plotting_units.AccumulatingPlotter(
                self, name="Last layer max gradient sum",
                plot_style=styles[i]))
            self.plt_err_y[-1].input = self.decision.max_err_y_sums
            self.plt_err_y[-1].input_field = i
            self.plt_err_y[-1].link_from(self.decision)
            self.plt_err_y[-1].gate_block = ~self.decision.epoch_ended
        self.plt_err_y[0].clear_plot = True
        self.plt_err_y[-1].redraw_plot = True


def run(load, main):
    load(Workflow, layers=root.layers_mnist_relu)
    main()
