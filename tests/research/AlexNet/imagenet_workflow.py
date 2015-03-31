#!/usr/bin/python3 -O
"""
Created on Dec 19, 2014

Model created for object recognition. Database - Imagenet (1000 classes).
Self-constructing Model. It means that Model can change for any Model
(Convolutional, Fully connected, different parameters) in configuration file.

Copyright (c) 2014 Samsung R&D Institute Russia
"""


from veles.config import root
from veles.znicz.standard_workflow import StandardWorkflow

from .imagenet_pickle_loader import ImagenetLoader  # pylint: disable=W0611
from veles.znicz.loader import loader_lmdb  # pylint: disable=W0611


root.common.ThreadPool.maxthreads = 3


class ImagenetWorkflow(StandardWorkflow):
    """
    Imagenet Workflow
    """
    def create_workflow(self):
        self.link_repeater(self.start_point)
        self.link_loader(self.start_point)
        avatar = self.link_avatar()
        self.link_forwards(("input", "minibatch_data"), avatar)
        self.link_evaluator(self.forwards[-1])
        self.link_decision(self.evaluator)
        parallel_units = [self.link_snapshotter(self.decision)]
        if root.imagenet.add_plotters:
            parallel_units.extend(link(self.decision) for link in (
                self.link_error_plotter,
                self.link_err_y_plotter))
            parallel_units.append(self.link_weights_plotter(
                root.imagenet.weights_plotter.limit,
                "weights", self.decision))

        last_gd = self.link_gds(*parallel_units)
        self.link_lr_adjuster(last_gd)
        self.link_loop(self.lr_adjuster)
        self.link_end_point(self.lr_adjuster)


def run(load, main):
    load(ImagenetWorkflow,
         loader_name=root.imagenet.loader_name,
         loader_config=root.imagenet.loader,
         decision_config=root.imagenet.decision,
         snapshotter_config=root.imagenet.snapshotter,
         layers=root.imagenet.layers,
         loss_function=root.imagenet.loss_function)
    main()
