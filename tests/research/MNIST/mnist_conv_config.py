#!/usr/bin/python3 -O

"""
Created on Mart 21, 2014

Configuration file for Mnist. Configuration parameters were found by Genetic
Algorithm. Model - convolutional neural network.

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


from veles.config import root


root.mnistr.lr_adjuster.lr_parameters = {
    "base_lr": 0.01, "gamma": 0.0001, "pow_ratio": 0.75}
root.mnistr.lr_adjuster.bias_lr_parameters = {
    "base_lr": 0.01, "gamma": 0.0001, "pow_ratio": 0.75}

root.mnistr.update({
    "loss_function": "softmax",
    "loader_name": "mnist_loader",
    "lr_adjuster": {"do": True, "lr_policy_name": "inv",
                    "bias_lr_policy_name": "inv"},
    "decision": {"max_epochs": 10000000,
                 "fail_iterations": 100},
    "snapshotter": {"prefix": "mnist_conv", "time_interval": 0,
                    "compress": ""},
    "loader": {"minibatch_size": 6, "force_cpu": False,
               "normalization_type": "linear"},
    "weights_plotter": {"limit": 64},
    "layers": [{"type": "conv",
                "->": {"n_kernels": 64, "kx": 5, "ky": 5,
                       "sliding": (1, 1), "weights_filling": "uniform",
                       "weights_stddev": 0.0944569801138958,
                       "bias_filling": "constant",
                       "bias_stddev": 0.048000},
                "<-": {"learning_rate": 0.03,
                       "learning_rate_bias": 0.358000,
                       "gradient_moment": 0.36508255921752014,
                       "gradient_moment_bias": 0.385000,
                       "weights_decay": 0.0005,
                       "weights_decay_bias": 0.1980997902551238,
                       "factor_ortho": 0.001}},

               {"type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"type": "conv",
                "->": {"n_kernels": 87, "kx": 5, "ky": 5, "sliding": (1, 1),
                       "weights_filling": "uniform",
                       "weights_stddev": 0.067000,
                       "bias_filling": "constant", "bias_stddev": 0.444000},
                "<-": {"learning_rate": 0.03, "learning_rate_bias": 0.381000,
                       "gradient_moment": 0.115000,
                       "gradient_moment_bias": 0.741000,
                       "weights_decay": 0.0005, "factor_ortho": 0.001,
                       "weights_decay_bias": 0.039000}},

               {"type": "max_pooling",
                "->": {"kx": 2, "ky": 2, "sliding": (2, 2)}},

               {"type": "all2all_relu",
                "->": {"output_sample_shape": 791,
                       "weights_stddev": 0.039000, "bias_filling": "constant",
                       "weights_filling": "uniform", "bias_stddev": 1.000000},

                "<-": {"learning_rate": 0.03, "learning_rate_bias": 0.196000,
                       "gradient_moment": 0.810000,
                       "gradient_moment_bias": 0.619000,
                       "weights_decay": 0.0005, "factor_ortho": 0.001,
                       "weights_decay_bias": 0.11487830567238211}},

               {"type": "softmax",
                "->": {"output_sample_shape": 10, "weights_filling": "uniform",
                       "weights_stddev": 0.024000,
                       "bias_filling": "constant", "bias_stddev": 0.255000},
                "<-": {"learning_rate": 0.03, "learning_rate_bias": 0.488000,
                       "gradient_moment": 0.133000,
                       "gradient_moment_bias": 0.8422143625658985,
                       "weights_decay": 0.0005,
                       "weights_decay_bias": 0.476000}}]})
