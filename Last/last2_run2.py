import sys
import tensorflow as tf
import datetime
import pickle
import os
import numpy as np
import random
import logging

#logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)
#logger = logging.getLogger("last2")
logging.basicConfig(format='%(asctime)s %(message)s')
logger = logging.getLogger("last2")

# logging.basicConfig(format='%(asctime)s - %(name)s ')
# logger = logging.getLogger("last2")
# logger.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
#logger.setFormatter(formatter)

sys.path.append('..')
sys.path.append('.')
from utils import Utils, Config, HOME
from network import Network
from distance import distance_cal
from last2 import create_net, DataSet2

def run(cfg, t):

    cfg.num_output = [2, 1]
    print("LR {} num_out {} mode {}".format(cfg.lr, cfg.num_output, cfg.mode))

    net = create_net(cfg)
    init = net[0]
    saver = net[1]
    input_dic = net[2]
    outputs = net[3]
    # losses = net[4]
    # opts = net[5]
    xyz = net[6]

    avg_file = Utils.avg_file_name(cfg.netFile)

    if t=='tr':
        tr = DataSet2(cfg.tr_data[0], cfg)
    else:
        tr = DataSet2(cfg.te_data[0], cfg)

    tr.subtract_avg(avg_file)
    T0 = datetime.datetime.now()

    with tf.compat.v1.Session() as sess:
        sess.run(init)
        saver.restore(sess, cfg.netFile)

        tr_pre = tr.prepare(None, clear=True)
        te_count = 0
        c2_loss1 = 0
        c2_loss2 = 0
        w_deviation = 0
        t1_count = 0
        w_distance_truth = 0
        t2_count = 0
        w_distance_2 = 0
        t3_count = 0
        t4_loss = 0
        t4_count = 0

        data = tr_pre[0]
        truth = tr_pre[1]
        length = data.shape[0]
        print("Total data", length)
        batch_size = 10000
        xyz0 = {}
        trt0 = {}
        hist = np.zeros(200)
        dr = 1
        hist1 = np.zeros(200)
        dr1 = .1
        removed = 0

        for c in range(0, length, batch_size):
            dd = data[c:c + batch_size]
            th = []
            for d in truth[c:c + batch_size]:
                th.append(d[2])
            te_count += len(th)

            th = np.array(th)
            th1 = th[:, :2]
            th2 = th[:, 2]

            th2 = np.array(th2).reshape((len(dd), 1))
            dd = np.array(dd)
            feed = {input_dic['data_1']: dd, input_dic['data_2']: dd}
            #        outputs[0]: th1, outputs[1]: th2}
            A = sess.run(xyz, feed_dict=feed)
            diff1 = A[0] - th1
            c2_loss1 += np.sum(diff1*diff1)
            diff2 = A[1] - th2
            c2_loss2 += np.sum(diff2*diff2)
            A = np.concatenate((A[0], A[1]), axis=1)

            for a in range(len(th)):
                xyz3 = A[a, :]
                t1 = truth[c+a]
                id1 = t1[0][0]
                ip1 = t1[0][1]
                id2 = t1[1][0]
                ip2 = t1[1][1]
                P1 = tr.poses[id1]
                xyz2 = Utils.xyz_tran_R(xyz3)
                if xyz2[2] > 500:
                    removed += 1
                    #print('removed: ', id1, id2, ip1, ip2, xyz3, xyz2[2])
                    continue
                xyz1 = Utils.transfor_T(P1, xyz2, w2c=False)
                xyzt = np.array(t1[2])
                xyzt = Utils.xyz_tran_R(xyzt)
                xyzt = Utils.transfor_T(P1, xyzt, w2c=False)
                if id1 not in xyz0:
                    xyz0[id1] = {}
                    trt0[id1] = {}
                if ip1 not in xyz0[id1]:
                    xyz0[id1][ip1] = []
                    trt0[id1][ip1] = xyzt
                xyz0[id1][ip1].append(xyz1)
                #if abs(xyz1[0])>1e8:
                #    print('1  ', xyz1, xyz2, xyz3, xyzt, id1, ip1, id2, ip2)
                #
                # if id1 == 72 and ip1 == 6186:
                #     print('1  ', xyz1, xyzt, id2, ip2)
                # if id2 == 72 and ip2 == 6186:
                #     print('2  ', xyz1, xyzt, id1, ip1)
                if id2 not in xyz0:
                    xyz0[id2] = {}
                    trt0[id2] = {}
                if ip2 not in xyz0[id2]:
                    xyz0[id2][ip2] = []
                    trt0[id2][ip2] = xyzt
                xyz0[id2][ip2].append(xyz1)

        print("Removed", removed)
        for img_id in xyz0:
            for p_id in xyz0[img_id]:
                xyz1 = xyz0[img_id][p_id]
                if len(xyz1) > 1:
                    xyz1 = np.array(xyz1)
                    a2 = np.std(xyz1, axis=0)
                    d0 = np.linalg.norm(a2)
                    #if d0 > 5000:
                    #    print(img_id, p_id, d0)
                    w_deviation += d0
                    t1_count += 1
                    d1 = np.mean(xyz1, axis=0)
                    xyz0[img_id][p_id] = [d1, d0]
                    diff = trt0[img_id][p_id] - d1
                    dist = np.linalg.norm(diff)
                    ch = int(dist/dr)
                    if ch > 199:
                        ch = 199
                    hist[ch] += 1
                    w_distance_truth += dist
                    t2_count += 1
                else:
                    xyz0[img_id][p_id] = xyz1[0]
        with open('/home/weihao/tmp/hist.csv', 'w') as fp:
            for ch in range(len(hist)):
                fp.write("{}, {}\n".format(ch, hist[ch]))

        for a in range(len(th)):
            t1 = truth[c + a]
            id1 = t1[0][0]
            ip1 = t1[0][1]
            id2 = t1[1][0]
            ip2 = t1[1][1]
            diff = xyz0[id1][ip1][0] - xyz0[id2][ip2][0]
            dist = np.linalg.norm(diff)
            ch = int(dist / dr1)
            if ch > 199:
                ch = 199
            hist1[ch] += 1
            w_distance_2 += dist
            t3_count += 1
        with open('/home/weihao/tmp/hist_1.csv', 'w') as fp:
            for ch in range(len(hist1)):
                fp.write("{}, {}\n".format(ch, hist1[ch]))

    T = datetime.datetime.now()
    # deviation, dist, to_truth
    print("deviation, distance, to_truth, d1, d2")
    print("Err {0} {1} {2:.6f} {3:.6f} {4:.6f} {5:.6f} {6:.6f}".
                format(T-T0, te_count,
                       w_deviation/t1_count, w_distance_2/t3_count, w_distance_truth/t2_count,
                       c2_loss1 / te_count, c2_loss2 / te_count
                       ))


if __name__ == '__main__':

    config_file = "config.json"

    cfg = Config(config_file)
    cfg.num_output = list(map(int, cfg.num_output.split(',')))

    t = 'te'
    if len(sys.argv)>1:
        t = sys.argv[1]

    run(cfg, t)
