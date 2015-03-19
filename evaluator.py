"""
Created on Apr 1, 2013

Defines units which evaluate the target quality function during the neural
network training.

Copyright (c) 2013 Samsung Electronics Co., Ltd.
"""

from __future__ import division

import numpy
from zope.interface import implementer

from veles.distributable import TriviallyDistributable
import veles.error as error
from veles.memory import assert_addr, ravel, Vector
from veles.accelerated_units import AcceleratedUnit, IOpenCLUnit, ICUDAUnit
from veles.opencl_types import numpy_dtype_to_opencl


class EvaluatorBase(AcceleratedUnit):
    """Base class for evaluators.
    """
    def __init__(self, workflow, **kwargs):
        kwargs["view_group"] = kwargs.get("view_group", "EVALUATOR")
        super(EvaluatorBase, self).__init__(workflow, **kwargs)
        self.error_function_averaged = kwargs.get(
            "error_function_averaged", True)
        self.err_output = Vector()
        self.krn_constants_i_ = None
        self.krn_constants_f_ = None
        self.demand("output", "batch_size")

    def initialize(self, device, **kwargs):
        super(EvaluatorBase, self).initialize(device, **kwargs)

        dtype = self.output.dtype
        self.krn_constants_i_ = numpy.zeros(1, numpy.int32)
        self.krn_constants_f_ = numpy.zeros(1, dtype)
        self.err_output.reset(numpy.zeros_like(self.output.mem, dtype))

        for vec in self.output, self.err_output:
            vec.initialize(self.device)


@implementer(IOpenCLUnit, ICUDAUnit)
class EvaluatorSoftmax(EvaluatorBase, TriviallyDistributable):
    """Evaluator for nn softmax output from the batch labels.

    Must be assigned before initialize():
        output
        labels
        batch_size
        max_idx

    Updates after run():
        err_output
        n_err
        confusion_matrix
        max_err_output_sum

    Creates within initialize():
        err_output
        n_err
        confusion_matrix
        max_err_output_sum

    Attributes:
        labels: labels for Batch.
        output: output of the network_common as Batch.
        err_output: backpropagation errors based on labels.
        batch_size: number of elements in output to evaluate.
        confusion_matrix: confusion matrix for the output.
        compute_confusion_matrix: compute confusion matrix or not.
        max_idx: indexes of element with maximum real value for each sample.
        max_err_output_sum: maximum of backpropagated error sum by sample.
    """
    def __init__(self, workflow, **kwargs):
        super(EvaluatorSoftmax, self).__init__(workflow, **kwargs)
        self.compute_confusion_matrix = kwargs.get(
            "compute_confusion_matrix", True)
        self.confusion_matrix = Vector()
        self.n_err = Vector()
        self.max_err_output_sum = Vector()
        self.demand("labels", "max_idx")

    def initialize(self, device, **kwargs):
        super(EvaluatorSoftmax, self).initialize(device=device, **kwargs)
        self.sources_["evaluator"] = {}

        dtype = self.output.dtype

        self.n_err.reset(numpy.zeros(1, dtype=numpy.int32))

        out_size = self.output.mem.size // self.output.mem.shape[0]
        self.confusion_matrix.reset(numpy.zeros([out_size] * 2, numpy.int32)
                                    if self.compute_confusion_matrix else None)

        self.max_err_output_sum.reset(numpy.zeros(1, dtype))

        self.init_vectors(self.confusion_matrix, self.n_err, self.max_idx,
                          self.labels, self.max_err_output_sum)

    def _gpu_init(self):
        dtype = self.output.dtype
        block_size = min(self.err_output.shape[0], 256)
        defines = {
            "BLOCK_SIZE": block_size,
            "BATCH": self.err_output.shape[0],
            "Y": self.err_output.sample_size
        }
        self.build_program(defines, "%s_%d_%d" %
                           (self.__class__.__name__,
                            self.output.shape[0],
                            self.output.sample_size),
                           dtype=dtype)
        self.assign_kernel("ev_sm")
        self.set_args(self.output, self.max_idx, self.labels,
                      self.err_output, self.n_err, self.confusion_matrix,
                      self.max_err_output_sum)
        return block_size

    def ocl_init(self):
        block_size = self._gpu_init()
        self._global_size = [block_size]
        self._local_size = [block_size]

    def cuda_init(self):
        block_size = self._gpu_init()
        self._global_size = (1, 1, 1)
        self._local_size = (block_size, 1, 1)

    def _gpu_run(self):
        self.unmap_vectors(
            self.err_output, self.output, self.max_idx, self.labels,
            self.n_err, self.confusion_matrix, self.max_err_output_sum)

        self.krn_constants_i_[0] = self.batch_size
        self.set_arg(7, self.krn_constants_i_[0:1])
        self.krn_constants_f_[0] = (
            1.0 / self.batch_size if self.error_function_averaged else 1.0)
        self.set_arg(8, self.krn_constants_f_[0:1])

        self.execute_kernel(self._global_size, self._local_size)

    def ocl_run(self):
        return self._gpu_run()

    def cuda_run(self):
        return self._gpu_run()

    def cpu_run(self):
        self.err_output.map_invalidate()
        for vec in self.output, self.max_idx, self.labels:
            vec.map_read()
        for vec in self.n_err, self.confusion_matrix, self.max_err_output_sum:
            vec.map_write()

        batch_size = self.batch_size
        labels = self.labels.mem
        confusion_matrix = self.confusion_matrix.mem

        n_ok = 0
        multiplier = 1.0 / batch_size if self.error_function_averaged else 1.0
        for i in range(batch_size):  # loop by batch
            if labels[i] < 0:
                self.err_output.mem[i] = 0.0
                continue
            output = ravel(self.output[i])
            err_output = ravel(self.err_output[i])

            max_idx = self.max_idx[i]
            confusion_matrix[max_idx, labels[i]] += 1
            if max_idx == labels[i]:
                n_ok += 1

            # Compute softmax output error gradient
            err_output[:] = output[:]
            err_output[labels[i]] -= 1.0
            err_output *= multiplier
            if err_output.dtype in (numpy.complex64, numpy.complex128):
                self.max_err_output_sum[0] = max(
                    self.max_err_output_sum[0], numpy.linalg.norm(err_output))
            else:
                self.max_err_output_sum[0] = max(
                    self.max_err_output_sum[0], (numpy.fabs(err_output)).sum())
        # Set errors for excessive samples to zero
        if batch_size < self.err_output.mem.shape[0]:
            self.err_output.mem[batch_size:] = 0.0
        self.n_err[0] += batch_size - n_ok


@implementer(IOpenCLUnit, ICUDAUnit)
class EvaluatorMSE(EvaluatorBase, TriviallyDistributable):
    """Evaluator for nn softmax output from the batch labels.

    Must be assigned before initialize():
        output
        target
        batch_size
        labels (may be None)
        class_targets (may be None)

    Updates after run():
        err_output
        confusion_matrix
        max_err_output_sum
        n_err (only if labels and class_targets is not None)

    Creates within initialize():
        err_output
        n_err (only if labels and class_targets is not None)
        max_err_output_sum

    Attributes:
        output: output of the network_common as Batch.
        target: target for the current Batch.
        err_output: backpropagation errors.
        batch_size: number of elements in output to evaluate.
        metrics: [0] - sum of sample's mse, [1] - max of sample's mse,
                 [2] - min of sample's mse.
        mse: array of mse for each sample in minibatch.
        krn_constants_i_: numpy array for constant arguments to kernel.
        labels: labels for a Batch (may be None).
        class_targets: target for each class (may be None).
        n_err: number of wrong recognized samples
            (if labels and class_targets is not None).
    """
    def __init__(self, workflow, **kwargs):
        super(EvaluatorMSE, self).__init__(workflow, **kwargs)
        self.metrics = Vector()
        self.mse = Vector()
        self.labels = None
        self.class_targets = None
        self.n_err = Vector()
        self.squared_mse = kwargs.get("squared_mse", False)
        self.demand("target")

    def initialize(self, device, **kwargs):
        super(EvaluatorMSE, self).initialize(device=device, **kwargs)

        if self.target.size != self.output.size:
            raise error.BadFormatError(
                "target.size != output.size (%s != %s)" %
                (self.target.size, self.output.size))

        self.sources_["evaluator"] = {}

        dtype = self.output.dtype

        self.metrics.reset(numpy.zeros(3, dtype=dtype))
        self.metrics[2] = 1.0e30  # mse_min
        self.mse.reset(numpy.zeros(self.err_output.mem.shape[0], dtype))
        self.n_err.reset(numpy.zeros(2, dtype=numpy.int32))
        self.init_vectors(self.n_err, self.target, self.metrics, self.mse)
        if self.class_targets:
            self.class_targets.initialize(self.device)

    def _gpu_init(self):
        dtype = self.output.dtype
        block_size = min(self.err_output.shape[0], 128)
        defines = {
            'BLOCK_SIZE': block_size,
            'BATCH': self.err_output.shape[0],
            'Y': self.err_output.sample_size,
            'SAMPLE_SIZE': 'Y',
            'SQUARED_MSE': int(self.squared_mse)
        }
        if self.class_targets:
            self.sources_["mse_find_closest"] = {}
            defines.update({
                'N_TARGETS': self.class_targets.shape[0],
                'target_dtype': numpy_dtype_to_opencl(self.class_targets.dtype)
            })

        self.build_program(defines, "%s_%d_%d" %
                           (self.__class__.__name__,
                            self.output.shape[0],
                            self.output.sample_size),
                           dtype=dtype)

        self.assign_kernel("ev_mse")
        self.set_args(self.output, self.target, self.err_output,
                      self.metrics, self.mse.devmem)

        if self.labels and self.class_targets:
            assert(self.labels.dtype == self.n_err.dtype == numpy.int32)
            self.krn_find_closest_ = self.get_kernel("mse_find_closest")
            self.krn_find_closest_.set_args(
                self.output.devmem,
                self.class_targets.devmem,
                self.labels.devmem,
                self.n_err.devmem)

        return block_size

    def ocl_init(self):
        block_size = self._gpu_init()
        self._local_size = [block_size]
        self._global_size = self._local_size
        self._global_size_find_closest_ = lambda: (self.batch_size,)
        self._local_size_find_closest = None

    def cuda_init(self):
        block_size = self._gpu_init()
        self._local_size = (block_size, 1, 1)
        self._global_size = (1, 1, 1)
        self._global_size_find_closest_ = lambda: (self.batch_size, 1, 1)
        self._local_size_find_closest = (1, 1, 1)

    def _gpu_run(self):
        self.unmap_vectors(self.err_output, self.output, self.target,
                           self.metrics, self.mse)

        batch_size = self.batch_size
        self.krn_constants_i_[0] = batch_size
        self.set_arg(5, self.krn_constants_i_[0:1])
        self.krn_constants_f_[0] = (
            1.0 / self.batch_size if self.error_function_averaged else 1.0)
        self.set_arg(6, self.krn_constants_f_[0:1])

        self.execute_kernel(self._global_size, self._local_size)

        if self.labels and self.class_targets:
            self.unmap_vectors(self.class_targets, self.labels, self.n_err)
            self.execute_kernel(self._global_size_find_closest_(),
                                self._local_size_find_closest,
                                self.krn_find_closest_)

    def ocl_run(self):
        return self._gpu_run()

    def cuda_run(self):
        return self._gpu_run()

    def cpu_run(self):
        self.output.map_read()
        self.target.map_read()
        self.metrics.map_write()
        self.err_output.map_invalidate()
        self.mse.map_invalidate()

        assert(self.output.size == self.target.size == self.err_output.size)
        batch_size = self.batch_size
        err_output = self.err_output.matrix[:batch_size]
        assert_addr(err_output, self.err_output.mem)
        output = self.output.matrix[:batch_size]
        assert_addr(output, self.output.mem)
        target = self.target.matrix[:batch_size]
        assert_addr(target, self.target.mem)
        mse = self.mse.mem[:batch_size]
        assert_addr(mse, self.mse.mem)

        err_output[:] = output - target
        self.err_output.mem[batch_size:] = 0
        mse[:] = numpy.square(err_output).sum(axis=1) / err_output.shape[1]
        if self.error_function_averaged:
            err_output *= 1.0 / batch_size
        if not self.squared_mse:
            numpy.sqrt(mse, mse)
        self.mse.mem[batch_size:] = 0

        self.metrics.mem[0] += mse.sum()
        self.metrics.mem[1] = max(self.metrics.mem[1], mse.max())
        self.metrics.mem[2] = min(self.metrics.mem[2], mse.min())

        if self.labels and self.class_targets:
            self.class_targets.map_read()
            self.labels.map_read()
            self.n_err.map_write()
            class_targets = self.class_targets.matrix
            labels = self.labels.mem
            for i, sample in enumerate(output):
                lbl = numpy.linalg.norm(class_targets - sample,
                                        axis=1).argmin()
                if lbl != labels[i]:
                    self.n_err.mem[0] += 1
