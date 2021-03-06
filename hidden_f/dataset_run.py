import numpy as np
import sys
from random import randint, random

#from cv_location import VisualOdometry2
#from imagery_utils import SiftFeature, pose_realign
#from pose_ana import *
import datetime
import pickle
import cv2
import os
import rotation_averaging.util

HOME = '/home/weihao/Projects'
if sys.platform=='darwin':
    HOME = '/Users/weihao/Projects'

sys.path.append('{}/my_nets'.format(HOME))
from utils import PinholeCamera, Utils

p_file = 'rgbd_dataset_freiburg3_long_office_household_Train_ras_s1_3.p'
p_file = 'kitti_02_Test_ras_s3_3.p'
filename = '{}/p_files/{}'.format(HOME, p_file)

#filename = '{}/p_files/rgbd_dataset_freiburg3_nostructure_texture_near_withloop_Test_cv_s1_2.p'.format(HOME)
if len(sys.argv)>1:
    filename = sys.argv[1]
output_file = '{}/tmp/feature.csv'.format(HOME)

print('imput', filename)
print('output', output_file)

if 'kitti' in filename:
    focal = 719  # 719
    cam = PinholeCamera(1241.0, 376.0, focal, focal, 607.1928, 185.2157)
else:
    focal = 525.0
    cam = PinholeCamera(640.0, 480.0, focal, focal, 320.0, 240.0)


#focal = 719  # 719
#cam = PinholeCamera(1241.0, 376.0, focal, focal, 607.1928, 185.2157)

w2 = cam.cx
h2 = cam.cy

fp = open(output_file, 'w')

with open(filename, 'rb') as f:
    data = pickle.load(f)

dv = []
for data_id in data.poses:
    poses = data.poses[data_id]
    for id in poses:
        Q = poses[id].Q4[:3, :3]
        P = rotation_averaging.util.fix_matrix(Q)
        c = Utils.cos(Q, Q)
        dv.append(c[0])
        # data.poses[data_id][id].Q4[:3, :3] = P

dv = np.array(dv)*180/np.pi
print(np.mean(dv), np.median(dv), np.std(dv))

dv = []
rs = []
angs = []
rs0 = []
rs1 = []
rs2 = []
att = 0
for data_id in data.matches:
    matches = data.matches[data_id]
    features = data.features[data_id]
    poses = data.poses[data_id]
    for m_img in matches:
        img1 = m_img[0]
        img2 = m_img[1]
        match = matches[m_img]
        d0 = []
        att += len(match)
        #if img2-img1!=9:
        #    continue

        for m in match:
            point1 = m[0]
            point2 = m[1]
            feature1 = features[img1][0][point1]
            feature2 = features[img2][0][point2]
            # descriptor1 = features[img1][1][point1]
            # descriptor2 = features[img2][1][point2]
            d0.append([feature1[0], feature1[1], feature2[0],feature2[1]])

        d0 = np.array(d0)
        px_last = d0[:, :2]
        px_new = d0[:, 2:4]
        if d0.shape[0]==5:
            print(d0.shape)

        E, mask = cv2.findEssentialMat(px_new, px_last, cameraMatrix=cam.mx,
                                       method=cv2.RANSAC)
        mh, R, t, mask0 = cv2.recoverPose(E, px_new, px_last, cameraMatrix=cam.mx)

        b = Utils.get_A(R)
        #if np.max(abs(b))>9:
        #    print(img1, img2, a, b)

        #b = Utils.rotationMatrixToEulerAngles(R)*180/np.pi
        p1 = poses[img1]
        p2 = poses[img2]
        a, t = Utils.get_relative(p1, p2)

        P = np.linalg.inv(p1.Q4[:3, :3]).dot(p2.Q4[:3, :3])
        c = Utils.cos(P[:3, :3], P[:3, :3])
        dv.append(c[0])

        e = []
        for c in b:
            if c<-90:
                c = 180 + c
            if c>90:
                c = 180-c
            e.append(c)
        b = e
        dr = a - b
        r0 = np.linalg.norm(dr)
        #if r0>180:
        #    r0 = r0 - 180
        #elif r0>90:
        #    r0 = 180 - r0
        rs.append(r0*r0)
        rs0.append(abs(dr[0]))
        rs1.append(abs(dr[1]))
        rs2.append(abs(dr[2]))
        angs.append(np.linalg.norm(a))

        #if random() > 2000.0/len(matches):
        #    continue
        #if img2-img1!=1:
        #    continue
        fp.write('{},{},{},{},{},{},{},{},{}\n'.
                 format(img1, img2, a[0], b[0], a[1], b[1], a[2], b[2], r0))

dv = np.array(dv)*180/np.pi
print(np.mean(dv), np.median(dv), np.std(dv))

print( 'att', att/len(matches))
angs = np.array(angs)
rs0 = np.array(rs0)
rs1 = np.array(rs1)
rs2 = np.array(rs2)

#rs = np.sqrt(rs)
print ('name, median, Anger-error, mx, my, mz')
print ('{0}, {1:.4f} {2:.4f} {3:.4f} {4:.4f} {5:.4f}'.format(
    os.path.basename(filename), np.sqrt(np.median(rs)), np.median(angs),
    np.median(rs0),np.median(rs1),np.median(rs2)))
print ('Average(RMS), {0:.4f} {1:.4f} {2:.4f} {3:.4f} {4:.4f}'.format(
    np.sqrt(np.mean(rs)), np.sqrt(np.mean(angs*angs)),
    np.sqrt(np.mean(rs0*rs0)),np.sqrt(np.mean(rs1*rs1)),
    np.sqrt(np.mean(rs2*rs2))))
#print '{0}, {1:.4f} '.format(
#    os.path.basename(filename), np.mean(np.sqrt(rs)))
fp.close()

rs = sorted(rs)
length = len(rs)
fp = open(output_file + '.csv', 'w')
for a in range(length):
    fp.write('{},{}\n'.format(rs[a], float(a) / length))
fp.close()