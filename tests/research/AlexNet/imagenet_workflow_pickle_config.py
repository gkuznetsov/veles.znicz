#!/usr/bin/python3 -O
"""
Created on Nov 20, 2014

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""

import os

from veles.config import root

base_lr = 0.01
wd = 0.0005

root.common.precision_type = "float"
root.common.precision_level = 0
root.common.engine.backend = "cuda"

root.imagenet.root_name = "imagenet"
root.imagenet.series = "img"
root.imagenet.root_path = os.path.join(
    root.common.test_dataset_root, "AlexNet", "%s" % root.imagenet.root_name)

root.imagenet.lr_adjuster.lr_parameters = {
    "lrs_with_lengths":
    [(1, 100000), (0.1, 100000), (0.1, 100000), (0.01, 100000000)]}
root.imagenet.lr_adjuster.bias_lr_parameters = {
    "lrs_with_lengths":
    [(1, 100000), (0.1, 100000), (0.1, 100000), (0.01, 100000000)]}

root.imagenet.loader.update({
    "sx": 256,
    "sy": 256,
    "crop": (227, 227),
    "mirror": True,
    "channels": 3,
    "color_space": "RGB",
    "minibatch_size": 256,
    "normalization_type": "none",
    "shuffle_limit": 10000000,
    "original_labels_filename":
    os.path.join(
        root.imagenet.root_path,
        "original_labels_%s_%s.pickle"
        % (root.imagenet.root_name, root.imagenet.series)),
    "samples_filename":
    os.path.join(
        root.imagenet.root_path,
        "original_data_%s_%s.dat"
        % (root.imagenet.root_name, root.imagenet.series)),
    "matrixes_filename":
    os.path.join(
        root.imagenet.root_path,
        "matrixes_%s_%s.pickle"
        % (root.imagenet.root_name, root.imagenet.series)),
    "count_samples_filename":
    os.path.join(
        root.imagenet.root_path,
        "count_samples_%s_%s.json"
        % (root.imagenet.root_name, root.imagenet.series)),
})


root.imagenet.update({
    "decision": {"fail_iterations": 10000,
                 "max_epochs": 10000},
    "snapshotter": {"prefix": "imagenet", "interval": 1, "time_interval": 0},
    "add_plotters": True,
    "loss_function": "softmax",
    "lr_adjuster": {"lr_policy_name": "arbitrary_step",
                    "bias_lr_policy_name": "arbitrary_step"},
    "loader_name": "imagenet_pickle_loader",
    "weights_plotter": {"limit": 64},
    "layers": [{"type": "conv_str",
                "->": {"n_kernels": 96, "kx": 11, "ky": 11,
                       "padding": (0, 0, 0, 0), "sliding": (4, 4),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},
               {"type": "max_pooling",
                "->": {"kx": 3, "ky": 3, "sliding": (2, 2)}},
               {"type": "norm", "n": 5, "alpha": 0.0001, "beta": 0.75},

               {"type": "zero_filter",
                "grouping": 2},
               {"type": "conv_str",
                "->": {"n_kernels": 256, "kx": 5, "ky": 5,
                       "padding": (2, 2, 2, 2), "sliding": (1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 1},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},
               {"type": "max_pooling", "->": {"kx": 3, "ky": 3,
                "sliding": (2, 2)}},
               {"type": "norm", "n": 5, "alpha": 0.0001, "beta": 0.75},

               {"type": "zero_filter", "grouping": 2},
               {"type": "conv_str",
                "->": {"n_kernels": 384, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1), "sliding": (1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},

               {"type": "zero_filter", "grouping": 2},
               {"type": "conv_str",
                "->": {"n_kernels": 384, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1), "sliding": (1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 1},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},

               {"type": "zero_filter", "grouping": 2},
               {"type": "conv_str",
                "->": {"n_kernels": 256, "kx": 3, "ky": 3,
                       "padding": (1, 1, 1, 1), "sliding": (1, 1),
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 1},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},
               {"type": "max_pooling",
                "->": {"kx": 3, "ky": 3, "sliding": (2, 2)}},

               {"type": "all2all_relu",
                "->": {"output_sample_shape": 4096,
                       "weights_filling": "gaussian", "weights_stddev": 0.005,
                       "bias_filling": "constant", "bias_stddev": 1},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},
               {"type": "dropout", "dropout_ratio": 0.5},

               {"type": "all2all_relu",
                "->": {"output_sample_shape": 4096,
                       "weights_filling": "gaussian", "weights_stddev": 0.005,
                       "bias_filling": "constant", "bias_stddev": 1},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}},
               {"type": "dropout", "dropout_ratio": 0.5},

               {"type": "softmax",
                "->": {"output_sample_shape": 1000,
                       "weights_filling": "gaussian", "weights_stddev": 0.01,
                       "bias_filling": "constant", "bias_stddev": 0},
                "<-": {"learning_rate": base_lr,
                       "learning_rate_bias": base_lr * 2,
                       "weights_decay": wd, "weights_decay_bias": 0,
                       "gradient_moment": 0.9, "gradient_moment_bias": 0.9}}]})
