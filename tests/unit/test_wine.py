"""
Created on May 17, 2013

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""
import unittest
import units
import opencl
import text
import threading
import pickle
import numpy
import os
import all2all
import evaluator
import gd
import rnd


class EndPoint(units.Unit):
    """On initialize() and run() releases its semaphore.

    Attributes:
        sem_: semaphore.
        status: has completed attribute.
        n_passes: number of passes.
        n_passes_: number of passes in this session.
        max_passes: maximum number of passes per session before stop.
        snapshot_frequency: frequency of snapshots in number of passes.
        snapshot_object: object to snapshot.
        snapshot_filename: filename with optional %d as snapshot number.
    """
    def __init__(self, snapshot_object=None, unpickling=0):
        super(EndPoint, self).__init__(unpickling=unpickling)
        self.sem_ = threading.Semaphore(0)
        self.n_passes_ = 0
        self.max_passes = 499
        if unpickling:
            return
        self.status = None
        self.n_passes = 0
        self.snapshot_frequency = 500
        self.snapshot_filename = "cache/snapshot.%d.pickle"
        self.snapshot_object = snapshot_object

    def initialize(self):
        self.sem_.release()

    def run(self):
        self.n_passes_ += 1
        self.n_passes += 1
        self.log().debug("Iterations (session, total): (%d, %d)\n" %
                         (self.n_passes_, self.n_passes))
        if self.n_passes % self.snapshot_frequency == 0:
            fnme = self.snapshot_filename % (self.n_passes,)
            self.log().debug("Snapshotting to %s" % (fnme,))
            fout = open(fnme, "wb")
            pickle.dump((self.snapshot_object, numpy.random.get_state()), fout)
            fout.close()
        if self.n_passes >= 500 and \
           self.__dict__.get("max_ok", 0) < self.status.n_ok:
            self.max_ok = self.status.n_ok
            self.log().debug("Snapshotting to snapshot.best")
            fout = open("snapshot.best.tmp", "wb")
            pickle.dump((self.snapshot_object, numpy.random.get_state()), fout)
            fout.close()
            try:
                os.unlink("snapshot.best.old")
                os.rename("snapshot.best", "snapshot.best.old")
            except OSError:
                pass
            os.rename("snapshot.best.tmp", "snapshot.best")
        if self.n_passes_ < self.max_passes and not self.status.completed:
            return
        self.sem_.release()
        return 1

    def wait(self):
        """Waits on semaphore.
        """
        self.sem_.acquire()


class Repeater(units.Unit):
    """Propagates notification if any of the inputs are active.
    """
    def __init__(self, unpickling=0):
        super(Repeater, self).__init__(unpickling=unpickling)
        if unpickling:
            return

    def gate(self, src):
        """Gate is always open.
        """
        return 1


class UseCase2(units.SmartPickler):
    """Wine dataset.
    """
    def __init__(self, cpu=True, unpickling=0):
        super(UseCase2, self).__init__(unpickling=unpickling)
        if unpickling:
            return

        dev = None
        if not cpu:
            self.device_list = opencl.DeviceList()
            dev = self.device_list.get_device()

        # Setup notification flow
        self.start_point = units.Unit()

        t = text.TXTLoader()
        t.link_from(self.start_point)

        rpt = Repeater()
        rpt.link_from(t)

        aa1 = all2all.All2AllTanh(output_shape=[5], device=dev)
        aa1.input = t.output2
        aa1.link_from(rpt)

        sm = all2all.All2AllSoftmax(output_shape=[3], device=dev)
        sm.input = aa1.output
        sm.link_from(aa1)

        ev = evaluator.EvaluatorSoftmax(device=dev)
        ev.y = sm.output
        ev.labels = t.labels
        ev.link_from(sm)

        gdsm = gd.GDSM(device=dev)
        gdsm.weights = sm.weights
        gdsm.bias = sm.bias
        gdsm.h = sm.input
        gdsm.y = sm.output
        gdsm.err_y = ev.err_y

        gd1 = gd.GDTanh(device=dev)
        gd1.weights = aa1.weights
        gd1.bias = aa1.bias
        gd1.h = aa1.input
        gd1.y = aa1.output
        gd1.err_y = gdsm.err_h
        gd1.link_from(gdsm)

        rpt.link_from(gd1)

        self.end_point = EndPoint(self)
        self.end_point.status = ev.status
        self.end_point.link_from(ev)
        gdsm.link_from(self.end_point)

        self.t = t
        self.rpt = rpt
        self.aa1 = aa1
        self.sm = sm
        self.ev = ev
        self.gdsm = gdsm
        self.gd1 = gd1

    def run(self, resume=False, global_alpha=0.9, global_lambda=0.0,
            threshold=1.0, threshold_low=1.0, test_only=False, alphas=False):
        # Start the process:
        if alphas:
            self.gdsm.unlink()
            self.gd1.unlink()
            sm = self.sm
            ev = self.ev
            aa1 = self.aa1
            gdsm = gd.GDASM(device=self.gdsm.device)
            gdsm.weights = sm.weights
            gdsm.bias = sm.bias
            gdsm.h = sm.input
            gdsm.y = sm.output
            gdsm.err_y = ev.err_y
            gdsm.link_from(self.end_point)
            gd1 = gd.GDATanh(device=self.gd1.device)
            gd1.weights = aa1.weights
            gd1.bias = aa1.bias
            gd1.h = aa1.input
            gd1.y = aa1.output
            gd1.err_y = gdsm.err_h
            gd1.link_from(gdsm)
            self.rpt.link_from(gd1)
            self.gdsm = gdsm
            self.gd1 = gd1
        self.sm.threshold = threshold
        self.sm.threshold_low = threshold_low
        self.gdsm.global_alpha = global_alpha
        self.gdsm.global_lambda = global_lambda
        self.gd1.global_alpha = global_alpha
        self.gd1.global_lambda = global_lambda
        self.log().debug()
        self.log().debug("Initializing...")
        self.start_point.initialize_dependent()
        self.end_point.wait()
        # for l in self.t.labels.batch:
        #    self.log().debug(l)
        # sys.exit()
        self.log().debug()
        self.log().debug("Running...")
        self.start_point.run_dependent()
        self.end_point.wait()


class TestWine(unittest.TestCase):
    """Will test the convergence on the Wine dataset.
    """
    def test_cpu(self):
        this_dir = os.getcwd()
        rnd.default.seed(numpy.fromfile("seed", numpy.integer, 1024))
        os.chdir("..")
        uc = UseCase2(cpu=True)
        uc.run()
        os.chdir(this_dir)
        self.assertEqual(uc.end_point.n_passes, 119,
            "Wine should converge in 119 passes on the supplied seed, "
            "but %d passed" % (uc.end_point.n_passes,))

    def test_gpu(self):
        this_dir = os.getcwd()
        rnd.default.seed(numpy.fromfile("seed", numpy.integer, 1024))
        os.chdir("..")
        uc = UseCase2(cpu=False)
        uc.run()
        os.chdir(this_dir)
        self.assertEqual(uc.end_point.n_passes, 119,
            "Wine should converge in 119 passes on the supplied seed, "
            "but %d passed" % (uc.end_point.n_passes,))

    def test_gpu_a(self):
        this_dir = os.getcwd()
        rnd.default.seed(numpy.fromfile("seed", numpy.integer, 1024))
        os.chdir("..")
        uc = UseCase2(cpu=False)
        uc.run(alphas=True)
        os.chdir(this_dir)
        self.assertEqual(uc.end_point.n_passes, 294,
            "Wine should converge in 294 passes on the supplied seed, "
            "but %d passed" % (uc.end_point.n_passes,))


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.test']
    unittest.main()