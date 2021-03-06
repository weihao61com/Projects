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

    iterations = 1
    cfg.num_output = [2, 1]
    # cfg.mode = -1
    # logging.info("LR {} num_out {} mode {}".format(cfg.lr, cfg.num_output, cfg.mode))
    print("LR {} num_out {} mode {}".format(cfg.lr, cfg.num_output, cfg.mode))

    net = create_net(cfg)
    init = net[0]
    saver = net[1]
    input_dic = net[2]
    outputs = net[3]
    losses = net[4]
    opts = net[5]
    xyz = net[6]

    avg_file = Utils.avg_file_name(cfg.netFile)

    if t=='te':
        tr = DataSet2(cfg.te_data[0], cfg)
    else:
        tr = DataSet2(cfg.tr_data[0], cfg)
    if cfg.mode==0:
        tr.get_avg(avg_file)
    else:
        tr.subtract_avg(avg_file)
    T0 = datetime.datetime.now()

    with tf.compat.v1.Session() as sess:
        sess.run(init)
        if cfg.mode == 0:
            saver.save(sess, cfg.netFile)
            exit(0)

        saver.restore(sess, cfg.netFile)

        # mode = cfg.mode
        # print(outputs)
        # fp = None
        # if lp == 0:
        fp = open('/home/weihao/tmp/xyz.csv', 'w')
        for a in range(iterations):
            # filename = '/home/weihao/Projects/tmp/rst_learn.csv'.format(cfg.mode)

            for lp in range(1):
                tr_pre = tr.prepare(200000, clear=True)
                t_loss = 0
                t_count = 0
                te_loss = 0
                te_count = 0
                diff_loss1 = 0
                diff_loss2 = 0

                data = tr_pre[0]
                truth = tr_pre[1]
                length = data.shape[0]
                xyz0 = {}
                trt0 = {}
                sz = 100000
                for c in range(0, length, sz):
                    dd = data[c:c +sz]
                    th = truth[c:c + sz]
                    dd = np.array(dd)
                    feed = {input_dic['data_1']: dd, input_dic['data_2']: dd}
                    A = sess.run(xyz, feed_dict=feed)
                    A = np.concatenate((A[0], A[1]), axis=1)
                    for d in range(len(th)):
                        xyz1 = A[d, :]
                        t1 = th[d]
                        id1 = t1[0][0]
                        ip1 = t1[0][1]
                        id2 = t1[1][0]
                        ip2 = t1[1][1]
                        #if id1 == 1 and ip1 < 200:
                        #    print(ip1, t1[2])
                        #if id2 == 1 and ip2 < 200:
                        #    print(ip2, t1[2])
                        P1 = tr.poses[id1]
                        xyz1 = Utils.xyz_tran_R(xyz1)
                        xyz1 = Utils.transfor_T(P1, xyz1, w2c=False)
                        xyzt = np.array(t1[2])
                        xyzt = Utils.xyz_tran_R(xyzt)
                        xyzt = Utils.transfor_T(P1, xyzt, w2c=False)
                        if id1 not in xyz0:
                            xyz0[id1] = {}
                            trt0[id1] = {}
                        if ip1 not in xyz0[id1]:
                            xyz0[id1][ip1] = []
                            trt0[id1][ip1] = []
                        xyz0[id1][ip1].append(xyz1)
                        trt0[id1][ip1].append(xyzt)
                        if id2 not in xyz0:
                            xyz0[id2] = {}
                            trt0[id2] = {}
                        if ip2 not in xyz0[id2]:
                            xyz0[id2][ip2] = []
                            trt0[id2][ip2] = []
                        xyz0[id2][ip2].append(xyz1)
                        trt0[id2][ip2].append(xyzt)

                count = 0
                for img_id in xyz0:
                    for p_id in xyz0[img_id]:
                        count += 1
                        xyz1 = xyz0[img_id][p_id]
                        if len(xyz1)>1:
                            xyz1 = np.array(xyz1)
                            a2 = np.std(xyz1, axis=0)
                            t_loss += np.linalg.norm(a2)
                            t_count += 1
                            xyz0[img_id][p_id] = np.mean(xyz1, axis=0)
                            a0 = trt0[img_id][p_id]
                            a0 = np.mean(a0, axis=0)
                            a1 = xyz0[img_id][p_id]
                            if fp is not None:
                                if random.random()<0.01:
                                    fp.write('{},{},{},'.format(a0[0], a1[0], a2[0]))
                                    fp.write('{},{},{},'.format(a0[1], a1[1], a2[1]))
                                    fp.write('{},{},{}'.format(a0[2], a1[2], a2[2]))
                                    fp.write('\n')
                        else:
                            xyz0[img_id][p_id] = xyz1[0]
                # if fp:
                #    fp.close()
                dist = 0
                for c in range(length):
                    t1 = truth[c]
                    img_id = t1[0][0]
                    p_id = t1[0][1]
                    x1 = xyz0[img_id][p_id]
                    img_id = t1[1][0]
                    p_id = t1[1][1]
                    x2 = xyz0[img_id][p_id]
                    dist += np.linalg.norm(x1-x2)
                    xyz1 = (x1+x2)/2
                    # xyz1 = Utils.transfor_T(tr.poses[img_id], xyz1, w2c=True)
                    truth[c] = t1[:3] + (xyz1,)
                dist /= length

                # print(count, t_count, t_loss/t_count, te_count, te_loss/te_count)
            T = datetime.datetime.now()
            # print("Err {0} {1} {2:.6f} {3:.6f} {4:.6f} {5:.6f} {6:.6f}".
            #             format(T-T0, a, t_loss/t_count, te_loss/te_count,
            #                    dist, diff_loss1/te_count, diff_loss2/te_count))
        fp.close()

if __name__ == '__main__':

    config_file = "config.json"

    cfg = Config(config_file)
    cfg.num_output = list(map(int, cfg.num_output.split(',')))

    t = 'te'

    if len(sys.argv)>1:
       t = sys.argv[1]


    run(cfg, t)
