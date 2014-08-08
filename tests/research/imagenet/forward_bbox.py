# encoding: utf-8
'''
This script make bounding boxes (bboxes) includes objects of class from
raw bboxes.
Created on Jul 15, 2014

'''

import cv2
import numpy


class BBox(object):
    """
    Bounding box class (w/o rotation)
    """
    def __init__(self, y_min, x_min, y_max, x_max):
        self.ymin = y_min
        self.xmin = x_min
        self.ymax = y_max
        self.xmax = x_max

    @staticmethod
    def from_center_view(x_center, y_center, width, height):
        xmin = x_center - int(round((width - 1) / 2.))
        xmax = x_center + int(round((width - 1) / 2.))
        ymin = y_center - int(round((height - 1) / 2.))
        ymax = y_center + int(round((height - 1) / 2.))

        return BBox(ymin, xmin, ymax, xmax)

    @staticmethod
    def from_json_dict(json_dict):
        x_center = json_dict.get("x_center", None)
        if x_center is None:
            x_center = json_dict.get("x")

        y_center = json_dict.get("y_center", None)
        if y_center is None:
            y_center = json_dict.get("y")

        width = json_dict["width"]
        height = json_dict["height"]
        return BBox.from_center_view(x_center, y_center, width, height)

    def __repr__(self):
        return "Ymin:%f\tXmin:%f\tYmax:%f\tXmax:%f" % (self.ymin, self.xmin,
                                                       self.ymax, self.xmax)

    def to_dict(self):
        return {"y_min": self.ymin, "x_min": self.xmin, "y_max": self.ymax,
                "x_max": self.xmax}

    def to_caffe_view(self):
        return [self.ymin, self.xmin, self.ymax, self.xmax]

    def to_json_dict(self):
        return {"y": float(self.ymin + self.ymax) / 2.,
                "x": float(self.xmin + self.xmax) / 2.,
                "width": self.xmax - self.xmin + 1,
                "height": self.ymax - self.ymin + 1,
                "label": None, "angle": 0.}


def bbox_overlap(bbox_a, bbox_b):
    """
    Returns overlapping AREA of `bbox_a` and `bbox_b`

    Args:
        bbox_a(:class:`numpy.ndarray`): [ymin_a, xmin_a, ymax_a, xmax_a]
        bbox_b(:class:`numpy.ndarray`): [ymin_b, xmin_b, ymax_b, xmax_b]
    Returns:
        int
    """
    [ymin_a, xmin_a, ymax_a, xmax_a] = list(bbox_a)
    [ymin_b, xmin_b, ymax_b, xmax_b] = list(bbox_b)

    x_intersection = min(xmax_a, xmax_b) - max(xmin_a, xmin_b) + 1
    y_intersection = min(ymax_a, ymax_b) - max(ymin_a, ymin_b) + 1

    if x_intersection <= 0 or y_intersection <= 0:
        return 0
    else:
        return x_intersection * y_intersection


def bbox_overlap_ratio(bbox_a, bbox_b):
    """
    Returns overlap RATIO of `bbox_a` and `bbox_b`

    Args:
        bbox_a(:class:`numpy.ndarray`): [ymin_a, xmin_a, ymax_a, xmax_a]
        bbox_b(:class:`numpy.ndarray`): [ymin_b, xmin_b, ymax_b, xmax_b]
    Returns:
        float

    """
    overlap_area = bbox_overlap(bbox_a, bbox_b)
    [ymin_a, xmin_a, ymax_a, xmax_a] = list(bbox_a)
    [ymin_b, xmin_b, ymax_b, xmax_b] = list(bbox_b)

    area_a = (xmax_a - xmin_a + 1) * (ymax_a - ymin_a + 1)
    area_b = (xmax_b - xmin_b + 1) * (ymax_b - ymin_b + 1)

    union_area = area_a + area_b - overlap_area
    if union_area == 0:
        return 0
    else:
        return overlap_area / union_area


def draw_bbox(img, bbox, bgr_color=None, prob=None):
    """
    Args:
        img(:class:`ndarray`): a pic in OpenCV format
        bbox(iterable): [ymin, xmin, ymax, xmax]
        bgr_color(tuple): a tuple with BGR colors from 0 to 255 (optional)
        prob(float): bbox probability estimation (optional)
    Returns:
        :class:`ndarray`: a pic with bbox drawn
    """
    if bgr_color is None:
        bgr_color = (255, 255, 255)
    out_pic = img.copy()

    [ymin, xmin, ymax, xmax] = list(bbox)
    if prob is not None:
        cv2.putText(out_pic, "%.4f" % prob, (int(xmin), int(ymin) - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr_color)
    return cv2.rectangle(out_pic, (int(xmin), int(ymin)),
                         (int(xmax), int(ymax)), bgr_color, 1)


def nms_detections(bboxes, probs, overlap_thr=0.7):
    """
    Non-maximum suppression: Greedily select high-scoring detections and
    skip detections that are significantly covered by a previously
    selected detection.

    This version is translated from Matlab code by Tomasz Malisiewicz,
    who sped up Pedro Felzenszwalb's code.

    Args:
        bboxes(ndarray): each row is ['xmin', 'ymin', 'xmax', 'ymax']
        probs(ndarray): scores of `dets` bboxes
        overlap_thr(float): minimum overlap ratio (0.5 default)

    Returns:
        dets(ndarray): remaining after suppression.
    """

    dets = numpy.zeros(shape=(bboxes.shape[0], 5))
    dets[:, 0: 4] = bboxes[:, :]
    dets[:, 4] = probs[:]

    if numpy.shape(dets)[0] < 1:
        return dets

    x1 = dets[:, 0]
    y1 = dets[:, 1]
    x2 = dets[:, 2]
    y2 = dets[:, 3]

    w = x2 - x1
    h = y2 - y1
    area = w * h

    s = dets[:, 4]
    ind = numpy.argsort(s)

    pick = []
    counter = 0
    while len(ind) > 0:
        last = len(ind) - 1
        i = ind[last]
        pick.append(i)
        counter += 1

        xx1 = numpy.maximum(x1[i], x1[ind[:last]])
        yy1 = numpy.maximum(y1[i], y1[ind[:last]])
        xx2 = numpy.minimum(x2[i], x2[ind[:last]])
        yy2 = numpy.minimum(y2[i], y2[ind[:last]])

        w = numpy.maximum(0., xx2 - xx1 + 1)
        h = numpy.maximum(0., yy2 - yy1 + 1)

        o = w * h / area[ind[:last]]

        to_delete = numpy.concatenate(
            (numpy.nonzero(o > overlap_thr)[0], numpy.array([last])))
        ind = numpy.delete(ind, to_delete)

    return dets[pick, :]


def load_synsets(synsets_path):
    """
    Loads synsets from `synsets_path`.

    Returns:
        synsets(:class:`list`):
        synset_names(:class:`list`):
        synset_indexes(:class:`dict`):
    """
    synsets = []
    synset_names = []
    synset_indexes = {}
    for i, line in enumerate(open(synsets_path, 'r').readlines()):
        line = line.replace("\n", "")
        synset_id = line.split(" ")[0]
        synset_name = line[len(synset_id) + 1:]
        synsets.append(synset_id)
        synset_names.append(synset_name)
        synset_indexes[synset_id] = i
    return synsets, synset_names, synset_indexes


'''
This script make bounding boxes (bboxes) includes objects of class from
raw bboxes.
Created on Jul 15, 2014

'''


def merge_bboxes_by_probs_one(bboxes, probs, img_size, thr=0, border_thr=0.05):
    """
    This function merges  a bounding box based on bounding boxes from dets.
    It averages coordinates of dets proportional  their score.

    Args:
        bboxes (ndarray): each row is ['xmin', 'ymin', 'xmax', 'ymax', 'score']
        probs (ndarray): each i'th row  is score of i'th bbox
        img_size (ndarray): include size of image from which bboxes was
            extracted (first element -- height, second -- width)
        thr (float): threshold parameter:in shaping final bbox involve only
            boxes with score >= thr
        border_thr (float): padding ratio
    Returns:
        final (ndarray): bounding box includes region of interest
    """
    pic_height, pic_width = img_size
    final_bbox = numpy.zeros(shape=(1, 4))
    cum_prob = 0
    for i in range(bboxes.shape[0]):
        prob = probs[i]
        if prob >= thr:
            cum_prob += prob
            final_bbox[0, :] += prob * bboxes[i, 0:4]
    final_bbox = final_bbox / cum_prob
    width = final_bbox[0, 2] - final_bbox[0, 0]
    height = final_bbox[0, 3] - final_bbox[0, 1]
    final_bbox[0, 0] = max(0, final_bbox[0, 0] - border_thr * width)
    final_bbox[0, 2] = min(final_bbox[0, 2] + border_thr * width,
                           pic_width)
    final_bbox[0, 1] = max(0, final_bbox[0, 1] - border_thr * height)
    final_bbox[0, 3] = min(final_bbox[0, 3] + border_thr * height,
                           pic_height)
    return final_bbox


def merge_bboxes_by_probs(bboxes, probs, img_size, primary_thr=0,
                          secondary_thr=0, overlap_thr=0.3, max_bboxes=None):
    """
    This function makes some bounding boxes based on bounding boxes from dets.
    It  makes next steps iteratively:
    1. Findes bbox with max score
    2. Findes bboxes, which intersects with bbox from step 1 and intersect
        area more then threshold
    3. Merges bboxes from steps 1 and 2, for other bboxes go to step 1.

    Args:
        bboxes (ndarray): each row is ['xmin', 'ymin', 'xmax', 'ymax', 'score']
        probs (ndarray): each i'th row  is score of i'th bbox
        img_size (ndarray): include size of image from which bboxes was
            extracted (first element -- height, second -- width)
        primary_thr (float): in result_bboxes are included  only bbox with
            score >= primary_thr
        secondary_thr (float): thr for  merge_bboxes_by_probs_one
        overlap_thr (float): threshold for step 2
        max_bboxes(int): max num of bboxes to return
    Returns:
        result_bboxes (ndarray): bounding boxes after merge
    """
    dets = numpy.zeros(shape=(bboxes.shape[0], 5))
    dets[:, 0: 4] = bboxes[:, :]
    dets[:, 4] = probs[:]

#     dets = numpy.zeros(shape=(0, 5))
#     elem = numpy.zeros(shape=(1, 5))
#     for i in range(bboxes.shape[0]):
#         if probs[i] >= primary_thr:
#             elem[0,0: 4] = bboxes[i,:]
#             elem[4] = probs[i]
#             dets = numpy.append(dets, elem, axis=0)
    result_bboxes = numpy.zeros(shape=(0, 5))
    while numpy.shape(dets)[0] != 0:
        cur_bbox = numpy.argmax(dets[:, 4])
        if(dets[cur_bbox, 4] < primary_thr):
            return result_bboxes
        elif max_bboxes is not None:
            if result_bboxes.shape[0] == max_bboxes:
                return result_bboxes

        dets_new = numpy.zeros(shape=(0, 5))
        merge_bboxes = numpy.zeros(shape=(0, 5))
        for i in range(dets.shape[0]):
            r1 = dets[i, 0:4]  # current box coordinates
            r2 = dets[cur_bbox, 0:4]  # candidate for merge coordinates
            area1 = (r2[2] - r2[0]) * (r2[3] - r2[1])
            area2 = (r1[2] - r1[0]) * (r1[3] - r1[1])
            min_area = min(area1, area2)
            area_of_intersect = max(0, min(r1[2], r2[2]) - max(r1[0], r2[0])) \
                * max(0, min(r1[3], r2[3]) - max(r1[1], r2[1]))
            if area_of_intersect >= overlap_thr * min_area:
                merge_bboxes = numpy.append(
                    merge_bboxes, numpy.reshape(dets[i, :], newshape=(1, 5)),
                    axis=0)
            else:
                dets_new = numpy.append(dets_new, numpy.reshape(
                    dets[i, :], newshape=(1, 5)), axis=0)
        rb = merge_bboxes_by_probs_one(merge_bboxes[:, 0: 4],
                                       merge_bboxes[:, 4],
                                       img_size, secondary_thr)
        r = numpy.zeros(shape=(1, 5))
        r[0, 0:4] = rb
        r[0, 4] = max(merge_bboxes[:, 4])
        result_bboxes = numpy.append(result_bboxes, r, axis=0)
        dets = dets_new
    return result_bboxes


def merge_bboxes_by_dict(bbox_dict, pic_size, max_per_class=None):
    """
    Takes BBOX dict: keys are BBOXes in CAFFE format, values are prediction
        scores

    Args:
        bbox_dict(dict): BBOX dict
        pic_path(str): path to picture to detect (to get known its shape)
        max_per_class(int): how many top-scored BBOXes (PER CLASS!) to return

    Returns:
        list: a list of BBOXes with their prob scores
            (label, [ymin, xmin, ymax, xmax, score])
    """
    bboxes = []
    probs = []

    for key, val in bbox_dict.items():
        x_center, y_center, w, h = key
        bbox = BBox.from_center_view(x_center, y_center, w, h).to_caffe_view()
        bboxes.append(bbox)
        probs.append(val)

    bboxes = numpy.array(bboxes)
    probs = numpy.array(probs)

    bboxes_with_probs = []

    for label_idx in range(probs.shape[1]):
        bboxes_for_label = merge_bboxes_by_probs(
            bboxes, probs[:, label_idx], pic_size, max_bboxes=max_per_class)

        for bbox_id in range(bboxes_for_label.shape[0]):
            bboxes_with_probs.append((label_idx,
                                      list(bboxes_for_label[bbox_id])))

    bboxes_with_probs = sorted(bboxes_with_probs, reverse=True,
                               key=lambda x: x[1][4])
    if max_per_class is not None:
        return bboxes_with_probs[:max_per_class]
    else:
        return bboxes_with_probs
