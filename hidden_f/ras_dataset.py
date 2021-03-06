import sys
import os
import cv2
import pickle

this_file_path = os.path.dirname(os.path.realpath(__file__))
HOME = '{}/../..'.format(this_file_path)
sys.path.append('{}/my_nets'.format(HOME))

from image_pairing.imagery_utils import SiftFeature
import datetime


def ModifiedKeyPoint(f):
    # pt, angle, size, response, class_id, octave
    return (f.pt[0], f.pt[1], f.angle, f.size, f.response, f.class_id, f.octave)


class RAS_D:
    def __init__(self):
        self.poses = None
        self.cam = None
        self.features = {}
        self.sf = SiftFeature()
        self.matches = {}

        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        self.matcher = cv2.FlannBasedMatcher(index_params, search_params)

    def set_poses(self, poses, cam):
        self.poses = poses
        self.cam = cam

    def get_feature(self, pose):
        try:
            img = cv2.imread(pose.filename)
        except:
            raise Exception("failed load file {}".format(pose.filename))

        return self.sf.get_sift_feature(img)

    def clear(self):
        self.modify_features()
        self.sf = None
        self.matcher = None
        for id in self.features:
            for img in self.features[id]:
                self.features[id][img][1] = None

    def modify_features(self):
        for seq in self.features:
            features = self.features[seq]
            A = {}
            for img_id in features:
                fs = features[img_id]
                keypoints = []
                for f in fs[0]:
                    keypoints.append(ModifiedKeyPoint(f))
                A[img_id] = [keypoints, fs[1]]
            self.features[seq] = A

    def process(self, range2, range1=None, range3=None):
        if range3 is None:
            range3 = 0
        if range1 is None:
            range1 = -range2

        length = 0
        nt = 0
        t0 = datetime.datetime.now()

        for seq in self.poses:
            poses = self.poses[seq]
            print(seq, len(poses))
            self.features[seq] = {}
            self.matches[seq] = {}
            for id in poses:
                self.features[seq][id] = self.get_feature(poses[id])
                if len(self.features[seq])%200==0:
                    print(seq, len(self.features[seq]), len(self.features[seq][id][0]), datetime.datetime.now()-t0)

            features = self.features[seq]
            print('matching', datetime.datetime.now()-t0)
            t0 = datetime.datetime.now()

            for id1 in poses:
                for id2 in poses:
                    if abs(id2 - id1) <= range3:
                        continue

                    if range1 <= id2 - id1 <= range2:
                        pts1 = []

                        f1 = features[id1]
                        f2 = features[id2]
                        matches = self.matcher.knnMatch(f1[1], f2[1], k=2)
                        for m,n in matches:
                            if m.distance < 0.8 * n.distance:
                                values = (m.queryIdx, m.trainIdx, n.trainIdx,
                                          m.distance, n.distance)
                                pts1.append(values)

                        #
                        #
                        # # ratio test as per Lowe's paper
                        # for i, (m, n) in enumerate(matches):
                        #     if m.distance < 0.8 * n.distance:
                        #         # values = (curent_feature[0][m.trainIdx],
                        #         #          self.feature[0][m.queryIdx],
                        #         #          self.feature[0][n.queryIdx],
                        #         #          m.distance, n.distance)
                        #         values = (f1[0][m.queryIdx],
                        #                   f2[0][m.trainIdx],
                        #                   f2[0][n.trainIdx],
                        #                   m.distance, n.distance)
                        #         pts1.append(values)

                        length += len(pts1)
                        nt += 1

                        if nt % 1000 == 0:
                            print(nt, id1, datetime.datetime.now() - t0, int(length/nt), length)
                            t0 = datetime.datetime.now()
                        self.matches[seq][(id1, id2)] = pts1
        print(nt, datetime.datetime.now() - t0, length/nt)
