# encoding: utf-8
"""
.. invisible:
     _   _ _____ _     _____ _____
    | | | |  ___| |   |  ___/  ___|
    | | | | |__ | |   | |__ \ `--.
    | | | |  __|| |   |  __| `--. \
    \ \_/ / |___| |___| |___/\__/ /
     \___/\____/\_____|____/\____/

Created on Jul 15, 2014

This script make bounding boxes (bboxes) includes objects of class from
raw bboxes.

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
        xmin = round(x_center - (width - 1) / 2.)
        xmax = round(x_center + (width - 1) / 2.)
        ymin = round(y_center - (height - 1) / 2.)
        ymax = round(y_center + (height - 1) / 2.)
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

    def area(self):
        return (self.xmax - self.xmin + 1) * (self.ymax - self.ymin + 1)

    def draw_on_pic(self, img, bgr_color=None, text=None, line_width=1):
        """
        Returns:
            ndarray: a pic with BBOX drawn on.
        """
        if bgr_color is None:
            bgr_color = numpy.random.randint(low=100, high=255,
                                             size=3).tolist()

        out_pic = img.copy()

        if text is not None:
            cv2.putText(out_pic, text, (int(self.xmin), int(self.ymin) - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, bgr_color)
        return cv2.rectangle(out_pic, (int(self.xmin), int(self.ymin)),
                             (int(self.xmax), int(self.ymax)), bgr_color,
                             line_width)


def bbox_overlap(bbox_a, bbox_b):
    """
    Returns overlapping AREA of `bbox_a` and `bbox_b`

    Args:
        bbox_a(:class:`numpy.ndarray`): [ymin_a, xmin_a, ymax_a, xmax_a]
        bbox_b(:class:`numpy.ndarray`): [ymin_b, xmin_b, ymax_b, xmax_b]
    Returns:
        int
    """
    ymin_a, xmin_a, ymax_a, xmax_a = bbox_a
    ymin_b, xmin_b, ymax_b, xmax_b = bbox_b

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
    ymin_a, xmin_a, ymax_a, xmax_a = bbox_a
    ymin_b, xmin_b, ymax_b, xmax_b = bbox_b

    area_a = (xmax_a - xmin_a + 1) * (ymax_a - ymin_a + 1)
    area_b = (xmax_b - xmin_b + 1) * (ymax_b - ymin_b + 1)

    union_area = area_a + area_b - overlap_area
    if union_area == 0:
        return 0
    else:
        return overlap_area / union_area


def bbox_has_inclusion(bbox_a, bbox_b, area_ratio=0.9):
    """
    Args:
        bbox_a(:class:`numpy.ndarray`): [ymin_a, xmin_a, ymax_a, xmax_a]
        bbox_b(:class:`numpy.ndarray`): [ymin_b, xmin_b, ymax_b, xmax_b]
    Returns:
        bool
    """
    ymin_a, xmin_a, ymax_a, xmax_a = bbox_a
    ymin_b, xmin_b, ymax_b, xmax_b = bbox_b

    area_a = (xmax_a - xmin_a + 1) * (ymax_a - ymin_a + 1)
    area_b = (xmax_b - xmin_b + 1) * (ymax_b - ymin_b + 1)

    min_area = min(area_a, area_b)

    return (bbox_overlap(bbox_a, bbox_b) >= min_area * area_ratio,
            area_a > area_b)


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


def merge_bboxes_to_one(bboxes, probs, img_size, padding_ratio=0.05):
    """
    This function merges  a bounding box based on bounding boxes from dets.
    It averages coordinates of `dets` proportional to their score.

    Args:
        bboxes (ndarray): each row is ['ymin', 'xmin', 'ymax', 'xmax']
        probs (ndarray): each i'th row  is score of i'th bbox
        img_size (ndarray): include size of image from which bboxes was
            extracted (first element -- height, second -- width)
        thr (float): threshold parameter:in shaping final bbox involve only
            boxes with score >= thr
        padding_ratio (float): padding ratio ()
    Returns:
        final_bbox (ndarray): merged bounding box `[ymin, xmin, ymax, xmax]`
        final_prob(float): max probability
    """
    # Merging BBOX
    pic_height, pic_width = img_size
    final_bbox = numpy.zeros(shape=4)
    assert probs.min() >= 0
    if probs.max() == 0:
        for i in range(bboxes.shape[0]):
            final_bbox += bboxes[i] / bboxes.shape[0]
    else:
        cum_prob = 0
        for i in range(bboxes.shape[0]):
            prob = probs[i]
            cum_prob += prob
            final_bbox += prob * bboxes[i]
        final_bbox = final_bbox / cum_prob

    # Padding
    ymin, xmin, ymax, xmax = final_bbox
    width = xmax - xmin + 1
    height = ymax - ymin + 1

    ymin = max(0, ymin - height * padding_ratio)
    xmin = max(0, xmin - width * padding_ratio)
    ymax = min(pic_height - 1, ymax + height * padding_ratio)
    xmax = min(pic_width - 1, xmax + width * padding_ratio)

    final_bbox = numpy.array((ymin, xmin, ymax, xmax))

    return final_bbox, numpy.max(probs)


def bbox_is_small(bbox, h_min, w_min, min_area=None):
    """
    Returns True if BBOX is smaller than min params.
    """
    [ymin, xmin, ymax, xmax] = list(bbox)
    width = (xmax - xmin + 1)
    if width < w_min:
        return True
    height = (ymax - ymin + 1)
    if height < h_min:
        return True
    area = width * height

    if min_area is not None:
        if area < min_area:
            return True
    return False


def merge_bboxes_by_probs(bboxes, probs, img_size, primary_thr=0,
                          secondary_thr=0.02, overlap_thr=0.3,
                          max_bboxes=None, use_inclusions=False):
    """
    This function makes some bounding boxes based on bounding boxes from dets.
    It  makes next steps iteratively:
    1. Findes bbox with max score
    2. Findes bboxes, which intersects with bbox from step 1 and intersect
        area more then threshold
    3. Merges bboxes from steps 1 and 2, for other bboxes go to step 1.

    Args:
        bboxes (ndarray): each row is ['ymin', 'xmin', 'ymax', 'xmax']
        probs (ndarray): each i'th row  is score of i'th bbox
        img_size (ndarray): include size of image from which bboxes was
            extracted (first element -- height, second -- width)
        primary_thr (float): in result_bboxes are included only bboxes with
            score >= primary_thr
        secondary_thr (float): thr for merge_bboxes_to_one
        overlap_thr (float): threshold for step 2
        max_bboxes(int): max num of bboxes to return
    Returns:
        result_bboxes(ndarray): bounding boxes after merge
        result_probs(ndarray): scores for merged BBOXes
    """

    # indices of bboxes (with ascending probability > secondary_thr)
    bbox_ids = list(numpy.argsort(probs))

    # remove all raw_bboxes with prob < secondary_thr
    for i in range(len(bbox_ids) - 1, -1, -1):
        if probs[bbox_ids[i]] < secondary_thr:
            bbox_ids.pop(i)
        elif bbox_is_small(bboxes[bbox_ids[i]], h_min=20, w_min=20):
            bbox_ids.pop(i)

    result_bboxes = []
    result_probs = []

    while len(bbox_ids) > 0:
        main_index = len(bbox_ids) - 1

        if max_bboxes is not None:
            if len(result_bboxes) >= max_bboxes:
                break
        if probs[bbox_ids[main_index]] < primary_thr:
            break
        # find all BBOXes, overlapping with top-scored one
        overlapping_indices = []
        for i in range(main_index, -1, -1):
            if bbox_overlap_ratio(bboxes[bbox_ids[main_index]],
                                  bboxes[bbox_ids[i]]) >= overlap_thr:
                overlapping_indices.append(i)
            elif use_inclusions:
                if bbox_has_inclusion(bboxes[bbox_ids[main_index]],
                                      bboxes[bbox_ids[i]])[0]:
                    overlapping_indices.append(i)

        ids_to_merge = [bbox_ids[i] for i in overlapping_indices]

        # merging them
        bboxes_to_merge = bboxes[ids_to_merge]
        probs_to_merge = probs[ids_to_merge]

        merged_bbox, merged_prob = merge_bboxes_to_one(
            bboxes_to_merge, probs_to_merge, img_size)

        result_bboxes.append(merged_bbox)
        result_probs.append(merged_prob)

        # removing merged BBOXes from raw bbox pool
        overlapping_indices = sorted(overlapping_indices, reverse=True)
        for i in overlapping_indices:
            bbox_ids.pop(i)

    return numpy.array(result_bboxes), numpy.array(result_probs)


def merge_bboxes_by_dict(bbox_dict, pic_size,
                         primary_thr=0.1, secondary_thr=0.001,
                         max_bboxes=None, use_inclusions=True):
    """
    Takes BBOX dict: keys are BBOXes in VELES format, values are prediction
        scores. Merges overlapping BBOXes and adjusts their coordinates.

    Args:
        bbox_dict(dict): BBOX dict, keys are BBOXes (x_cen, y_cen, w, h),
            values are probability score vectors
        pic_path(str): path to picture to detect (to get known its shape)
        max_bboxes(int): how many top-scored BBOXes to return at max
        primary_thr(float): not to return merged BBOXes with smaller prob score
        secondary_thr(float): BBOXes with smaller prob scores cannot be merged
            into greater prob ones.

    Returns:
        list: a list of BBOXes with their prob scores
            (label, score, [ymin, xmin, ymax, xmax])
    """
    assert len(bbox_dict) > 0
    bboxes = []
    probs = []

    for key, val in bbox_dict.items():
        x_center, y_center, w, h = key
        try:
            assert x_center + w / 2 < pic_size[1] + 1
            assert x_center - w / 2 > -1
            assert y_center + h / 2 < pic_size[0] + 1
            assert y_center - h / 2 > -1
        except AssertionError:
            import pdb
            pdb.set_trace()
        bbox = BBox.from_center_view(x_center, y_center, w, h).to_caffe_view()
        bboxes.append(bbox)
        probs.append(val)

    bboxes = numpy.array(bboxes)
    probs = numpy.array(probs)

    bboxes_with_probs = []

    for label_idx in range(probs.shape[1]):
        bboxes_for_label, probs_for_label = merge_bboxes_by_probs(
            bboxes, probs[:, label_idx], pic_size,
            max_bboxes=max_bboxes, use_inclusions=use_inclusions,
            primary_thr=primary_thr, secondary_thr=secondary_thr)

        for bbox_index in range(bboxes_for_label.shape[0]):
            current_bbox = bboxes_for_label[bbox_index]
            current_prob = probs_for_label[bbox_index]
            bboxes_with_probs.append((label_idx, current_prob,
                                      list(current_bbox)))

    bboxes_with_probs = sorted(bboxes_with_probs, reverse=True,
                               key=lambda x: x[1])
    if max_bboxes is not None:
        bboxes_with_probs = bboxes_with_probs[:max_bboxes]

    return remove_inner_bboxes(bboxes_with_probs)


def remove_inner_bboxes(bboxes_with_probs):
    if len(bboxes_with_probs) == 1:
        return bboxes_with_probs
    nested = set()
    for index1, bbp1 in enumerate(bboxes_with_probs):
        if index1 in nested:
            continue
        bbox1 = bbp1[2]
        for index2, bbp2 in enumerate(bboxes_with_probs):
            if index2 in nested or index1 == index2 or bbp1[0] != bbp2[0]:
                continue
            bbox2 = bbp2[2]
            incl, which = bbox_has_inclusion(bbox1, bbox2, area_ratio=0.9)
            if incl:
                nested.add(index2 if which else index1)
    return [bboxes_with_probs[i] for i in range(len(bboxes_with_probs))
            if i not in nested]


def postprocess_bboxes_of_the_same_label(bboxes_with_probs):
    if len(bboxes_with_probs) == 1:
        return bboxes_with_probs
    changed = True
    transformed_bboxes = {bbox[2]: 1 for bbox in bboxes_with_probs}
    while changed:
        changed = False
        found = True
        while found:
            # Stage 1: merge nested bboxes of the same label
            found = False
            for index1, bbp1 in enumerate(bboxes_with_probs):
                bbox1 = bbp1[2]
                for index2, bbp2 in enumerate(bboxes_with_probs):
                    if index1 == index2 or bbp1[0] != bbp2[0]:
                        continue
                    bbox2 = bbp2[2]
                    incl, which = bbox_has_inclusion(
                        BBox.from_center_view(*bbox1).to_caffe_view(),
                        BBox.from_center_view(*bbox2).to_caffe_view(),
                        area_ratio=0.3)
                    if not incl:
                        continue
                    index_small, index_big = ((index1, index2)[int(b)]
                                              for b in (which, not which))
                    bbox_small, bbox_big = ((bbox1, bbox2)[int(b)]
                                            for b in (which, not which))
                    cbbox = tuple(reversed(bbox_small[:2])) * 2
                    bbox_big = BBox.from_center_view(*bbox_big).to_caffe_view()
                    merged_bbox = tuple((min(bbox_big[i], cbbox[i])
                                         for i in range(2))) + \
                        tuple((max(bbox_big[i], cbbox[i])
                               for i in range(2, 4)))
                    merged_bbox = ((merged_bbox[1] + merged_bbox[3]) / 2,
                                   (merged_bbox[0] + merged_bbox[2]) / 2,
                                   merged_bbox[3] - merged_bbox[1],
                                   merged_bbox[2] - merged_bbox[0])
                    bboxes_with_probs[index_big] = (
                        bbp1[0], max(bbp1[1], bbp2[1]), merged_bbox)
                    bboxes_with_probs = bboxes_with_probs[:index_small] + \
                        bboxes_with_probs[(index_small + 1):]
                    transformed_bboxes[merged_bbox] = \
                        transformed_bboxes[bbox1] + transformed_bboxes[bbox2]
                    found = True
                    changed = True
                    break
                if found:
                    break
        # Stage 2: merge near bboxes of the same label, if one is small
        found = True
        while found:
            found = False
            for index1, bbp1 in enumerate(bboxes_with_probs):
                bbox1 = bbp1[2]
                for index2, bbp2 in enumerate(bboxes_with_probs):
                    if index1 == index2 or bbp1[0] != bbp2[0]:
                        continue
                    bbox2 = bbp2[2]
                    incl, which = bbox_has_inclusion(
                        BBox.from_center_view(*bbox1).to_caffe_view(),
                        BBox.from_center_view(*bbox2).to_caffe_view(),
                        area_ratio=0)
                    if not incl:
                        continue
                    index_small, index_big = ((index1, index2)[int(b)]
                                              for b in (which, not which))
                    bbox_small, bbox_big = ((bbox1, bbox2)[int(b)]
                                            for b in (which, not which))
                    area_small = bbox_small[2] * bbox_small[3]
                    area_big = bbox_big[2] * bbox_big[3]
                    if area_small / area_big > 0.75:
                        continue
                    cbbox = tuple(reversed(bbox_small[:2])) * 2
                    bbox_big = BBox.from_center_view(*bbox_big).to_caffe_view()
                    merged_bbox = tuple((min(bbox_big[i], cbbox[i])
                                         for i in range(2))) + \
                        tuple((max(bbox_big[i], cbbox[i])
                               for i in range(2, 4)))
                    merged_bbox = ((merged_bbox[1] + merged_bbox[3]) / 2,
                                   (merged_bbox[0] + merged_bbox[2]) / 2,
                                   merged_bbox[3] - merged_bbox[1],
                                   merged_bbox[2] - merged_bbox[0])
                    bboxes_with_probs[index_big] = (
                        bbp1[0], max(bbp1[1], bbp2[1]), merged_bbox)
                    bboxes_with_probs = bboxes_with_probs[:index_small] + \
                        bboxes_with_probs[(index_small + 1):]
                    transformed_bboxes[merged_bbox] = \
                        transformed_bboxes[bbox1] + transformed_bboxes[bbox2]
                    found = True
                    changed = True
                    break
                if found:
                    break
    # Stage 3: take into account the number of transformed bboxes by each label
    for index, bbox in enumerate(bboxes_with_probs):
        bboxes_with_probs[index] = (
            bbox[0], 1.0 - (1.0 - bbox[1]) / transformed_bboxes[bbox[2]],
            bbox[2])
    return bboxes_with_probs
