#!/usr/bin/python3.3 -O
"""
Created on Mart 21, 2014

Example of Mnist config.

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


import os

from veles.config import root


# optional parameters

train_dir = os.path.join(root.common.test_dataset_root, "cifar/10")
validation_dir = os.path.join(root.common.test_dataset_root,
                              "cifar/10/test_batch")

root.update = {"conv":  {"weights_filling": "uniform",
                         "weights_stddev": 0.05},
               "decision": {"fail_iterations": 1000,
                            "snapshot_prefix": "cifar_conv",
                            "do_export_weights": True},
               "loader": {"minibatch_maxsize": 100},
               "image_saver": {"out_dirs":
                               [os.path.join(root.common.cache_dir,
                                             "tmp/test"),
                                os.path.join(root.common.cache_dir,
                                             "tmp/validation"),
                                os.path.join(root.common.cache_dir,
                                             "tmp/train")]},
               "weights_plotter": {"limit": 64},
               "cifar": {"learning_rate": 0.001,
                         "weights_decay": 0.004,
                         "layers":
                         [{"type": "conv", "n_kernels": 32,
                           "kx": 5, "ky": 5, "padding": (2, 2, 2, 2)},
                          {"type": "max_pooling",
                           "kx": 3, "ky": 3, "sliding": (2, 2)},
                          {"type": "conv", "n_kernels": 32,
                           "kx": 5, "ky": 5, "padding": (2, 2, 2, 2)},
                          {"type": "avg_pooling",
                           "kx": 3, "ky": 3, "sliding": (2, 2)},
                          {"type": "conv", "n_kernels": 64,
                           "kx": 5, "ky": 5, "padding": (2, 2, 2, 2)},
                          {"type": "avg_pooling",
                           "kx": 3, "ky": 3, "sliding": (2, 2)},
                          {"type": "softmax", "output_shape": 10}],
                         "path_for_load_data": {"train": train_dir,
                                                "validation": validation_dir}}}
