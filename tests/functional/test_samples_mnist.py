#!/usr/bin/python3 -O
"""
Created on April 2, 2014

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""


import logging
import numpy
import unittest

from veles.config import root
import veles.opencl as opencl
import veles.prng as rnd
from veles.snapshotter import Snapshotter
from veles.tests import timeout
import veles.znicz.samples.mnist as mnist
import veles.tests.dummy_workflow as dummy_workflow


class TestSamplesMnist(unittest.TestCase):
    def setUp(self):
        root.common.unit_test = True
        root.common.plotters_disabled = True
        self.device = opencl.Device()

    @timeout(12000)
    def test_samples_mnist(self):
        logging.info("Will test mnist fully connected workflow from samples")
        rnd.get().seed(numpy.fromfile("%s/veles/znicz/tests/research/seed" %
                                      root.common.veles_dir,
                                      dtype=numpy.int32, count=1024))
        root.update = {
            "all2all": {"weights_stddev": 0.05},
            "decision": {"fail_iterations": (0),
                         "snapshot_prefix": "samples_mnist_test"},
            "loader": {"minibatch_size": 88},
            "samples_mnist_test": {"learning_rate": 0.028557478339518444,
                                   "weights_decay": 0.00012315096341168246,
                                   "layers": [364, 10]},
            "mnist": {"factor_ortho": 0.001}}

        self.w = mnist.MnistWorkflow(dummy_workflow.DummyWorkflow(),
                                     layers=root.samples_mnist_test.layers,
                                     device=self.device)
        self.w.decision.max_epochs = 5
        self.w.snapshotter.interval = 5
        self.assertEqual(self.w.evaluator.labels,
                         self.w.loader.minibatch_labels)
        self.w.initialize(device=self.device,
                          learning_rate=root.samples_mnist_test.learning_rate,
                          weights_decay=root.samples_mnist_test.weights_decay)
        self.assertEqual(self.w.evaluator.labels,
                         self.w.loader.minibatch_labels)
        self.w.run()
        file_name = self.w.snapshotter.file_name

        err = self.w.decision.epoch_n_err[1]
        self.assertEqual(err, 650)
        self.assertEqual(5, self.w.loader.epoch_number)

        logging.info("Will load workflow from %s" % file_name)
        self.wf = Snapshotter.import_(file_name)
        self.assertTrue(self.wf.decision.epoch_ended)
        self.wf.decision.max_epochs = None
        self.wf.decision.complete <<= False
        self.assertEqual(self.wf.evaluator.labels,
                         self.wf.loader.minibatch_labels)
        self.wf.initialize(device=self.device,
                           learning_rate=root.samples_mnist_test.learning_rate,
                           weights_decay=root.samples_mnist_test.weights_decay)
        self.assertEqual(self.wf.evaluator.labels,
                         self.wf.loader.minibatch_labels)
        self.wf.run()

        err = self.wf.decision.epoch_n_err[1]
        self.assertEqual(err, 364)
        self.assertEqual(15, self.wf.loader.epoch_number)
        logging.info("All Ok")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()