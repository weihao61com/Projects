import pickle
from run_colmap import run_colmap, get_poses
from run_colmap_seq import run_colmap_seq
from db import process_db
import numpy as np
import os
import sys
import datetime

this_file_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append('{}/..'.format(this_file_path))
from utils import Utils


def get_ids(image_name):
    strs = image_name.split('_')
    pid = int(strs[0])
    strs = strs[1].split('-')
    strs = strs[1].split('.')
    id=int(strs[0])
    return pid, id


def get_truth(poses_dic, image1, image2):
    pid1, id1 = get_ids(image1)
    pid2, id2 = get_ids(image2)

    #if abs(id1-id2)==15:
    pose1 = poses_dic[pid1][id1]
    pose2 = poses_dic[pid2][id2]
    R = np.linalg.inv(pose1.m3x3).dot(pose2.m3x3)

    return Utils.rotationMatrixToEulerAngles(R)
    #return None

if __name__ == "__main__":

    key = 'heads'  # office" #heads
    mode = 'Test'
    max_image = 400000
    # negative for sequence
    max_match_per_image = 20 # -3
    min_matching_point = 20
    seq = None

    T0 = datetime.datetime.now()
    if len(sys.argv)>1:
        key = sys.argv[1]
    if len(sys.argv)>2:
        mode = sys.argv[2]
    if len(sys.argv)>3:
        max_match_per_image = int(sys.argv[3])
    if len(sys.argv)>4:
        seq = int(sys.argv[4])

    project_dir = '/home/weihao/Projects'

    if seq is None:
        run_colmap(project_dir, key, mode, max_image, max_match_per_image)
        output_file = '{}/tmp/{}_{}.csv'.format(project_dir, key, mode)
        if max_match_per_image>0:
            filename = '{}/p_files/{}_{}_cm_m{}.p'.format(project_dir, mode, key, max_match_per_image)
        else:
            filename = '{}/p_files/{}_{}_cm_s{}.p'.format(project_dir, mode, key, -max_match_per_image)
    else:
        run_colmap_seq(project_dir, key, mode, max_image, max_match_per_image, seq)
        output_file = '{}/tmp/{}_{}_{}.csv'.format(project_dir, key, mode, seq)
        filename = None

    process_db(project_dir, key, mode, max_match_per_image, min_matching_point)

    db_p = '{}/colmap_features/{}_{}/pairs.p'.format(project_dir, key, mode)

    with open(db_p, 'r') as fp:
        data = pickle.load(fp)

    poses_dic, cam = get_poses(project_dir, key, mode)

    output = []
    w2 = cam.cx
    h2 = cam.cy
    fp = open(output_file, 'w')
    rs = []

    print len(data)

    for d in data:
        image1 = d[0]
        image2 = d[1]
        truth = get_truth(poses_dic, image1, image2)
        if truth is not None:
            angles = d[2]
            pts1 = d[3]
            pts2 = d[4]
            num_point = int(d[5])
            a0 = pts1[:, 0]
            a1 = pts1[:, 1]
            a2 = pts2[:, 0]
            a3 = pts2[:, 1]
            features = np.zeros((len(pts1), 4))
            features[:, 0] = (a0 - w2) / w2
            features[:, 1] = (a1 - h2) / h2
            features[:, 2] = (a2 - w2) / w2
            features[:, 3] = (a3 - h2) / h2
            output.append([features, truth*180/np.pi])
            # features = np.zeros((len(pts1), 4))
            # features[:, 2] = (a0 - w2) / w2
            # features[:, 3] = (a1 - h2) / h2
            # features[:, 0] = (a2 - w2) / w2
            # features[:, 1] = (a3 - h2) / h2
            # output.append([features, -truth*180/np.pi])

            dr = truth - angles
            r0 = np.linalg.norm(dr) * 180 / np.pi
            rs.append(r0)

            fp.write('{},{},{},{},{},{},{},{},{},{},{}\n'.
                     format(image1,image2,
                            truth[0], truth[1], truth[2],
                            angles[0], angles[1], angles[2],
                             r0, len(pts1), num_point))
    fp.close()

    print "output", output_file, filename
    print 'median', len(rs), np.median(rs)

    if filename is not None:
        if filename is not None:
            with open(filename, 'w') as fp:
                pickle.dump(output, fp)

    print "processed ", key, mode, max_image, max_match_per_image, \
        min_matching_point, datetime.datetime.now()-T0