#!/usr/bin/python3
"""
Created on Mar 11, 2013

Entry point.

@author: Kazantsev Alexey <a.kazantsev@samsung.com>
"""
import logging
import filters
import sys
import mnist
import all2all
import numpy
import opencl
import pickle
import os
import evaluator
import argparse
import threading
import gd
import text

g_pt = 0
class PickleTest(filters.SmartPickling):
    """Pickle test.
    """
    def __init__(self, unpickling = 0, a = "A", b = "B", c = "C"):
        global g_pt
        g_pt += 1
        super(PickleTest, self).__init__(unpickling)
        if unpickling:
            return
        self.a = a
        self.b = b
        self.c = c


def do_pickle_test():
    # Test for correct behavior of filters.SmartPickling
    pt = PickleTest(a = "AA", c = "CC")
    if g_pt != 1:
        raise Exception("Pickle test failed.")
    pt.d = "D"
    pt.h_ = "HH"
    try:
        os.mkdir("cache")
    except OSError:
        pass
    fout = open("cache/test.pickle", "wb")
    pickle.dump(pt, fout)
    fout.close()
    del(pt)
    fin = open("cache/test.pickle", "rb")
    pt = pickle.load(fin)
    fin.close()
    if g_pt != 2:
        raise Exception("Pickle test failed.")
    if pt.d != "D" or pt.c != "CC" or pt.b != "B" or pt.a != "AA" or pt.h_:
        raise Exception("Pickle test failed.")


def fork_snapshot(obj, file, wait_for_completion = 1):
    """Makes snapshot of obj to the file.

    Wont work with OpenCL buffer mapping during pickle.
    """
    pid = os.fork()
    if pid:
        if wait_for_completion:
            os.waitpid(pid, 0)
        return
    pickle.dump(obj, file)
    file.flush()
    sys.exit()


class EndPoint(filters.Filter):
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
    def __init__(self, snapshot_object = None, flog = None, flog_args = None, unpickling = 0):
        super(EndPoint, self).__init__(unpickling=unpickling)
        self.sem_ = threading.Semaphore(0)
        self.n_passes_ = 0
        self.max_passes = 50000
        if unpickling:
            return
        self.status = None
        self.n_passes = 0
        self.snapshot_frequency = 500
        self.snapshot_filename = "cache/snapshot.%d.pickle"
        self.snapshot_object = snapshot_object
        self.flog_ = flog
        self.flog_args_ = flog_args

    def initialize(self):
        self.sem_.release()

    def run(self):
        self.n_passes_ += 1
        self.n_passes += 1
        print("Iterations (session, total): (%d, %d)\n" % (self.n_passes_, self.n_passes))
        if self.n_passes % self.snapshot_frequency == 0:
            fnme = self.snapshot_filename % (self.n_passes, )
            print("Snapshotting to %s" % (fnme, ))
            fout = open(fnme, "wb")
            pickle.dump((self.snapshot_object, numpy.random.get_state()), fout)
            fout.close()
        if self.n_passes >= 500 and self.__dict__.get("max_ok", 0) < self.status.n_ok:
            self.max_ok = self.status.n_ok
            print("Snapshotting to snapshot.best")
            fout = open("snapshot.best.tmp", "wb")
            pickle.dump((self.snapshot_object, numpy.random.get_state()), fout)
            fout.close()
            try:
                os.unlink("snapshot.best.old")
                os.rename("snapshot.best", "snapshot.best.old")
            except OSError:
                pass
            os.rename("snapshot.best.tmp", "snapshot.best")
        if self.flog_:
            self.flog_(*self.flog_args_)
        if self.n_passes_ < self.max_passes and not self.status.completed:
            return
        self.sem_.release()
        return 1

    def wait(self):
        """Waits on semaphore.
        """
        self.sem_.acquire()


class Repeater(filters.Filter):
    """Propagates notification if any of the inputs are active.
    """
    def __init__(self, unpickling = 0):
        super(Repeater, self).__init__(unpickling=unpickling)
        if unpickling:
            return

    def gate(self, src):
        """Gate is always open.
        """
        return 1


class UseCase1(filters.SmartPickling):
    """Use case 1.

    Attributes:
        device_list: list of an OpenCL devices as DeviceList object.
        start_point: Filter.
        end_point: EndPoint.
        aa1: aa1.
        aa2: aa2.
        sm: softmax.
        ev: evaluator.
        gdsm: gdsm.
        gd2: gd2.
        gd1: gd1.
    """
    def __init__(self, cpu = False, unpickling = 0):
        super(UseCase1, self).__init__(unpickling=unpickling)
        if unpickling:
            return

        dev = None
        if not cpu:
            self.device_list = opencl.DeviceList()
            dev = self.device_list.get_device()

        # Setup notification flow
        self.start_point = filters.Filter()

        m = mnist.MNISTLoader()
        m.link_from(self.start_point)

        rpt = Repeater()
        rpt.link_from(m)

        aa1 = all2all.All2AllTanh(output_shape=[80], device=dev)
        aa1.input = m.output
        aa1.link_from(rpt)

        aa2 = all2all.All2AllTanh(output_shape=[40], device=dev)
        aa2.input = aa1.output
        aa2.link_from(aa1)

        sm = all2all.All2AllSoftmax(output_shape=[10], device=dev)
        sm.input = aa2.output
        sm.link_from(aa2)

        ev = evaluator.BatchEvaluator(device=dev)
        ev.y = sm.output
        ev.labels = m.labels
        ev.link_from(sm)

        self.end_point = EndPoint(self)
        self.end_point.status = ev.status
        self.end_point.link_from(ev)

        gdsm = gd.GDSM(device=dev)
        gdsm.weights = sm.weights
        gdsm.bias = sm.bias
        gdsm.h = sm.input
        gdsm.y = sm.output
        gdsm.err_y = ev.err_y
        gdsm.link_from(self.end_point)

        gd2 = gd.GDTanh(device=dev)
        gd2.weights = aa2.weights
        gd2.bias = aa2.bias
        gd2.h = aa2.input
        gd2.y = aa2.output
        gd2.err_y = gdsm.err_h
        gd2.link_from(gdsm)

        gd1 = gd.GDTanh(device=dev)
        gd1.weights = aa1.weights
        gd1.bias = aa1.bias
        gd1.h = aa1.input
        gd1.y = aa1.output
        gd1.err_y = gd2.err_h
        gd1.link_from(gd2)

        rpt.link_from(gd1)

        self.aa1 = aa1
        self.aa2 = aa2
        self.sm = sm
        self.ev = ev
        self.gdsm = gdsm
        self.gd2 = gd2
        self.gd1 = gd1

    def run(self, resume = False, global_alpha = 0.9, global_lambda = 0.0, threshold = 1.0, test_only = False):
        # Start the process:
        self.ev.threshold = threshold
        self.gdsm.global_alpha = global_alpha
        self.gdsm.global_lambda = global_lambda
        self.gd2.global_alpha = global_alpha
        self.gd2.global_lambda = global_lambda
        self.gd1.global_alpha = global_alpha
        self.gd1.global_lambda = global_lambda
        self.ev.origin = self.aa1.input
        print()
        print("Initializing...")
        self.start_point.initialize_dependent()
        self.end_point.wait()
        print()
        print("Running...")
        self.start_point.run_dependent()
        self.end_point.wait()


def strf(x):
    return "%.4f" % (x, )


class UseCase2(filters.SmartPickling):
    """Use case 2.

    Attributes:
        device_list: list of an OpenCL devices as DeviceList object.
        start_point: Filter.
        end_point: EndPoint.
        t: t.
    """
    def __init__(self, cpu = True, unpickling = 0):
        super(UseCase2, self).__init__(unpickling=unpickling)
        if unpickling:
            return

        dev = None
        if not cpu:
            self.device_list = opencl.DeviceList()
            dev = self.device_list.get_device()

        # Setup notification flow
        self.start_point = filters.Filter()

        #m = mnist.MNISTLoader()
        t = text.TXTLoader()
        self.t = t
        #sys.exit()
        print("1")
        t.link_from(self.start_point)
        print("2")

        rpt = Repeater()
        rpt.link_from(t)

        aa1 = all2all.All2AllTanh(output_shape=[5], device=dev)
        aa1.input = t.output2
        aa1.link_from(rpt)

        out = all2all.All2AllSoftmax(output_shape=[3], device=dev)
        out.input = aa1.output
        out.link_from(aa1)

        ev = evaluator.BatchEvaluator(device=dev)
        ev.y = out.output
        ev.labels = t.labels
        ev.link_from(out)

        gdsm = gd.GDSM(device=dev)
        gdsm.weights = out.weights
        gdsm.bias = out.bias
        gdsm.h = out.input
        gdsm.y = out.output
        gdsm.err_y = ev.err_y

        gd1 = gd.GDTanh(device=dev)
        gd1.weights = aa1.weights
        gd1.bias = aa1.bias
        gd1.h = aa1.input
        gd1.y = aa1.output
        gd1.err_y = gdsm.err_h
        gd1.link_from(gdsm)

        rpt.link_from(gd1)

        self.end_point = EndPoint(self, self.do_log, (out, gdsm, gd1))
        self.end_point.status = ev.status
        self.end_point.link_from(ev)
        gdsm.link_from(self.end_point)

        self.sm = out
        self.gdsm = gdsm
        self.gd1 = gd1

        print("3")

    def do_log(self, out, gdsm, gd1):
        return
        flog = open("logs/out.log", "a")
        flog.write("Iteration %d" % (self.end_point.n_passes, ))
        flog.write("\nSoftMax layer input:\n")
        for sample in out.input.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nSoftMax layer output:\n")
        for sample in out.output.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nSoftMax layer weights:\n")
        for sample in out.weights.v:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nSoftMax layer bias:\n")
        flog.write(" ".join(strf(x) for x in out.bias.v))
        flog.write("\n(min, max)(input, output, weights, bias) = ((%f, %f), (%f, %f), (%f, %f), (%f, %f)\n" % \
                   (out.input.batch.min(), out.input.batch.max(), \
                    out.output.batch.min(), out.output.batch.max(), \
                    out.weights.v.min(), out.weights.v.max(), \
                    out.bias.v.min(), out.bias.v.max()))
        flog.write("\n")
        flog.close()

        flog = open("logs/gdsm.log", "a")
        flog.write("Iteration %d" % (self.end_point.n_passes, ))
        flog.write("\nGD SoftMax err_y:\n")
        for sample in gdsm.err_y.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD SoftMax err_h:\n")
        for sample in gdsm.err_h.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD SoftMax weights:\n")
        for sample in gdsm.weights.v:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD SoftMax bias:\n")
        flog.write(" ".join(strf(x) for x in gdsm.bias.v))
        flog.write("\n(min, max)(err_y, err_h, weights, bias) = ((%f, %f), (%f, %f), (%f, %f), (%f, %f)\n" % \
                   (gdsm.err_y.batch.min(), gdsm.err_y.batch.max(), \
                    gdsm.err_h.batch.min(), gdsm.err_h.batch.max(), \
                    gdsm.weights.v.min(), gdsm.weights.v.max(), \
                    gdsm.bias.v.min(), gdsm.bias.v.max()))
        flog.write("\n")
        flog.close()

        flog = open("logs/gd1.log", "a")
        flog.write("Iteration %d" % (self.end_point.n_passes, ))
        flog.write("\nGD1 err_y:\n")
        for sample in gd1.err_y.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD1 err_h:\n")
        for sample in gd1.err_h.batch:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD1 weights:\n")
        for sample in gd1.weights.v:
            flog.write(" ".join(strf(x) for x in sample))
            flog.write("\n")
        flog.write("\nGD1 bias:\n")
        flog.write(" ".join(strf(x) for x in gd1.bias.v))
        flog.write("\n(min, max)(err_y, err_h, weights, bias) = ((%f, %f), (%f, %f), (%f, %f), (%f, %f)\n" % \
                   (gd1.err_y.batch.min(), gd1.err_y.batch.max(), \
                    gd1.err_h.batch.min(), gd1.err_h.batch.max(), \
                    gd1.weights.v.min(), gd1.weights.v.max(), \
                    gd1.bias.v.min(), gd1.bias.v.max()))
        flog.write("\n")
        flog.close()

    def run(self, resume = False, global_alpha = 0.9, global_lambda = 0.0, threshold = 1.0, test_only = False):
        # Start the process:
        self.sm.threshold = threshold
        self.gdsm.global_alpha = global_alpha
        self.gdsm.global_lambda = global_lambda
        self.gd1.global_alpha = global_alpha
        self.gd1.global_lambda = global_lambda
        print()
        print("Initializing...")
        self.start_point.initialize_dependent()
        self.end_point.wait()
        #for l in self.t.labels.batch:
        #    print(l)
        #sys.exit()
        print()
        print("Running...")
        self.start_point.run_dependent()
        self.end_point.wait()


def main():
    do_pickle_test()

    # Main program
    logging.debug("Entered")

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", type=str, help="resume from snapshot", \
                        default="", dest="resume")
    parser.add_argument("-cpu", action="store_true", help="use numpy only", \
                        default=False, dest="cpu")
    parser.add_argument("-global_alpha", type=float, help="global gradient descent speed", \
                        default=0.9, dest="global_alpha")
    parser.add_argument("-global_lambda", type=float, help="global weights regularisation constant", \
                        default=0.0, dest="global_lambda")
    parser.add_argument("-threshold", type=float, help="softmax threshold", \
                        default=1.0, dest="threshold")
    parser.add_argument("-t", action="store_true", help="test only", \
                        default=False, dest="test_only")
    args = parser.parse_args()

    numpy.random.seed(numpy.fromfile("seed", numpy.integer))

    uc = None
    if args.resume:
        try:
            print("Resuming from snapshot...")
            fin = open(args.resume, "rb")
            (uc, random_state) = pickle.load(fin)
            numpy.random.set_state(random_state)
            fin.close()
        except IOError:
            print("Could not resume from %s" % (args.resume, ))
            uc = None
    if not uc:
        #uc = UseCase1(args.cpu)
        uc = UseCase2(args.cpu)
    print("Launching...")
    uc.run(args.resume, global_alpha=args.global_alpha, global_lambda=args.global_lambda, \
           threshold=args.threshold, test_only=args.test_only)

    print()
    print("Snapshotting...")
    fout = open("cache/snapshot.pickle", "wb")
    #fork_snapshot((uc, numpy.random.get_state()), fout)
    pickle.dump((uc, numpy.random.get_state()), fout)
    fout.close()
    print("Done")

    logging.debug("Finished")


if __name__ == '__main__':
    main()
