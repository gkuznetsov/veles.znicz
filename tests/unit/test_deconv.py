# -*- coding: utf-8 -*-
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on May 28, 2014

Unit test for deconvolutional unit.

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


import numpy
import os
from veles.backends import NumpyDevice

from veles.config import root
import veles.memory as memory
import veles.opencl_types as opencl_types
import veles.prng as rnd
from veles.memory import Array
from veles.tests import AcceleratedTest, assign_backend
from veles.tests.doubling_reset import patch
import veles.znicz.conv as conv
from veles.znicz.deconv import Deconv
from veles.znicz.gd_deconv import GDDeconv
from veles.znicz.tests.unit.gd_numdiff import GDNumDiff


class PatchedDeconv(Deconv):
    def __init__(self, workflow, **kwargs):
        super(PatchedDeconv, self).__init__(workflow, **kwargs)
        patch(self, self.output, lambda: self.output_shape_source.shape,
              lambda: self.input.dtype)


class TestDeconv(AcceleratedTest, GDNumDiff):
    ABSTRACT = True

    def setUp(self):
        super(TestDeconv, self).setUp()
        self.this_dir = os.path.dirname(__file__)
        if not len(self.this_dir):
            self.this_dir = "."
        self.precision_threshold = {
            numpy.float64: 1.5e-4,
            numpy.float32: 1.5e-2,
            numpy.float16: 1.5e-1}[self.dtype]

    def test_fixed(self):
        inp = numpy.ones([1, 4, 4, 1], dtype=self.dtype)
        forward = conv.Conv(self.parent, kx=3, ky=3, n_kernels=1,
                            padding=(0, 0, 0, 0), sliding=(1, 1),
                            include_bias=False)
        forward.input = Array(inp)
        forward.initialize(self.device)
        forward.weights.map_invalidate()
        forward.weights.mem[:] = 1.0
        forward.run()

        de = PatchedDeconv(self.parent, unsafe_padding=True)
        de.link_conv_attrs(forward)
        de.input = forward.output
        de.output_shape_source = forward.input
        de.weights = forward.weights
        de.initialize(self.device)
        de.run()
        de.output.map_read()
        nz = numpy.count_nonzero(de.output.mem - inp * 9)
        self.assertEqual(nz, 0)

    def test_compute_padding(self):
        sx = 128
        for kx, slide in ((2, 1), (3, 1), (4, 1), (4, 2), (5, 1),
                          (6, 1), (6, 2), (6, 3), (7, 1),
                          (8, 1), (8, 2), (8, 4),
                          (9, 1), (9, 3),
                          (10, 1), (10, 2), (10, 5), (11, 1),
                          (12, 1), (12, 2), (12, 3), (12, 4), (12, 6),
                          (13, 1), (14, 1), (14, 2), (14, 7),
                          (15, 1), (15, 3), (15, 5),
                          (16, 1), (16, 2), (16, 4), (16, 8),
                          (17, 1),
                          (18, 1), (18, 2), (18, 3), (18, 6), (18, 9),
                          (19, 1),
                          (20, 1), (20, 2), (20, 4), (20, 5), (20, 10)):
            self._test_compute_padding(sx, sx, kx, kx, (slide, slide))

    def _test_compute_padding(self, sx, sy, kx, ky, sliding):
        padding = PatchedDeconv.compute_padding(sx, sy, kx, ky, sliding)
        a = numpy.zeros([sy + padding[1] + padding[3],
                         sx + padding[0] + padding[2]], dtype=numpy.int32)
        b = numpy.ones([ky, kx], dtype=numpy.int32)
        for y in range(0, a.shape[0] - ky + 1, sliding[1]):
            for x in range(0, a.shape[1] - kx + 1, sliding[0]):
                a[y:y + ky, x:x + kx] += b
        c = a[padding[1]:sy - padding[3], padding[0]:sx - padding[2]]
        self.assertEqual(c.min(), c.max(), "Unequal distribution")
        self.assertEqual(c.min(), (kx // sliding[1]) * (ky // sliding[0]),
                         "Wrong value")

    def test_gd_deconv(self):
        self._test_gd_deconv_transposed(False)
        self._test_gd_deconv_transposed(True)

    def _test_gd_deconv_transposed(self, weights_transposed):
        self.info("GDDeconv err_input overflow test...")
        _, first, forward = self._test_deconv(self.device, None,
                                              weights_transposed)

        first.weights.map_read()
        weights = first.weights.mem.copy()
        first.input.map_read()
        target = first.input.mem.copy()
        forward.output.map_read()
        out = forward.output.mem.copy()
        err_output = out - target
        forward.input.map_read()
        inp = forward.input.mem.copy()

        gd = GDDeconv(first.workflow, learning_rate=-1.0, weights_decay=0.0,
                      gradient_moment=0.9,
                      weights_transposed=weights_transposed)
        gd.link_conv_attrs(first)
        gd.weights = first.weights
        gd.input = forward.input
        gd.err_output = memory.Array(err_output)
        gd.initialize(self.device)
        self.assertEqual(gd.err_input.shape, first.output.shape)
        gd.run()
        gd.err_input.map_read()
        nz = numpy.count_nonzero(numpy.isnan(gd.err_input.mem))
        self.assertEqual(nz, 0, "NaNs encountered in err_input")

        self.info("GDDeconv numeric derivative test...")
        gd.weights.map_read()
        nz = numpy.count_nonzero(numpy.isnan(gd.weights.mem))
        self.assertEqual(nz, 0, "NaNs encountered in weights")
        err_input = gd.err_input.mem.copy()
        weights_derivative = gd.weights.mem - weights

        gd.err_input_alpha = 0.21436598
        gd.err_input_beta = 0.123456789
        gd.weights.map_invalidate()
        gd.weights.mem[:] = weights
        gd.err_output.map_invalidate()
        gd.err_output.mem[:] = err_output
        gd.run()
        gd.err_input.map_read()
        max_diff = numpy.fabs(
            gd.err_input.mem -
            (err_input * gd.err_input_beta +
             err_input * gd.err_input_alpha)).max()
        self.assertLess(max_diff, self.precision_threshold,
                        "err_input alpha/beta test failed")

        self.numdiff_check_gd(forward, inp, weights, None, target,
                              err_input, weights_derivative, None,
                              self.info, self.assertLess,
                              mean=False,
                              threshold=self.precision_threshold)

    def _test_deconv(self, device, forward, weights_transposed):
        rnd.get().seed("%s/seed" % self.this_dir,
                       dtype=numpy.int32, count=1024)

        dtype = opencl_types.dtypes[root.common.engine.precision_type]

        if forward is None:
            batch_size = 3
            workflow = self.parent
            forward = conv.Conv(workflow, n_kernels=9, kx=6, ky=6,
                                padding=(4, 4, 4, 4), sliding=(2, 2),
                                include_bias=False,
                                weights_transposed=weights_transposed)
            inp = memory.Array(numpy.zeros([batch_size * 2, 18, 18, 4],
                                           dtype=dtype))
            inp.initialize(device)
            inp.map_write()
            inp.unit_test_mem = inp.mem
            inp.mem = inp.unit_test_mem[:batch_size]
            memory.assert_addr(inp.unit_test_mem, inp.mem)
            rnd.get().fill(inp.mem)
            inp.unit_test_mem[batch_size:] = numpy.nan
            forward.input = inp
            forward.initialize(device)
            forward.run()

        forward.output.map_read()
        sh = list(forward.output.mem.shape)
        sh[0] <<= 1
        out = memory.Array(numpy.zeros(sh, dtype=dtype))
        out.initialize(forward.device)
        out.map_write()
        out.unit_test_mem = out.mem
        sh[0] >>= 1
        out.mem = out.unit_test_mem[:sh[0]]
        memory.assert_addr(out.mem, out.unit_test_mem)
        out.mem[:] = forward.output.mem[:]
        out.unit_test_mem[sh[0]:] = numpy.nan

        backward = PatchedDeconv(forward.workflow,
                                 weights_transposed=weights_transposed)
        backward.link_conv_attrs(forward)
        backward.weights = forward.weights
        backward.input = out
        backward.output_shape_source = forward.input
        backward.conv = forward
        backward.initialize(device)

        self.assertEqual(backward.output.shape, forward.input.shape,
                         "Shape test failed")

        backward.run()

        backward.output.map_read()

        nz = numpy.count_nonzero(numpy.isnan(backward.output.mem))
        self.assertEqual(nz, 0, "NaNs encountered")

        if not isinstance(device, NumpyDevice):
            nz = numpy.count_nonzero(numpy.isnan(
                backward.output.unit_test_mem[backward.output.shape[0]:]))
            self.assertEqual(nz, backward.output.unit_test_mem.size >> 1,
                             "Written some values outside of the target array")

        return backward.output.mem.copy(), forward, backward


@assign_backend("ocl")
class OpenCLTestDeconv(TestDeconv):
    pass


@assign_backend("cuda")
class CUDATestDeconv(TestDeconv):
    pass


if __name__ == "__main__":
    AcceleratedTest.main()
