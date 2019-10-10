import sys
import tensorflow as tf
import datetime
import pickle
import os
import numpy as np
import random
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("last2")
logger.setLevel(logging.INFO)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
#logger.setFormatter(formatter)

sys.path.append('..')
sys.path.append('.')
from utils import Utils, Config, HOME
from network import Network
from distance import distance_cal
from last2 import create_net, DataSet2

def run(cfg, iterations):

    cfg.num_output = [3]
    cfg.mode = -1
    logger.info("LR {} num_out {} mode {}".format(cfg.lr, cfg.num_output, cfg.mode))

    net = create_net(cfg)
    init = net[0]
    saver = net[1]
    input_dic = net[2]
    outputs = net[3][0]
    losses = net[4][0]
    opts = net[5][0]
    xyz = net[6][0]

    avg_file = Utils.avg_file_name(cfg.netFile)

    tr = DataSet2(cfg.tr_data[0], cfg)
    tr.get_avg(avg_file)
    tr.subtract_avg(avg_file)


    with tf.compat.v1.Session() as sess:
        sess.run(init)
        if cfg.mode == 0:
            saver.save(sess, cfg.netFile)
            exit(0)

        if cfg.mode > 0:
            saver.restore(sess, cfg.netFile)

        t00 = datetime.datetime.now()
        st1 = ''

        mode = cfg.mode
        print(outputs)

        for a in range(iterations):
            # filename = '/home/weihao/Projects/tmp/rst_learn.csv'.format(cfg.mode)

            for lp in range(cfg.loop):
                tr_pre = tr.prepare(2000, clear=True)
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
                sz = 100000
                for c in range(0, length, sz):
                    dd = data[c:c +sz]
                    th = truth[c:c + sz]
                    feed = {input_dic['data_1']: np.array(dd)}
                    A = sess.run(xyz, feed_dict=feed)
                    for d in range(len(th)):
                        xyz1 = A[d, :]
                        t1 = th[d]
                        id1 = t1[0][0]
                        ip1 = t1[0][1]
                        id2 = t1[1][0]
                        ip2 = t1[1][1]
                        P1 = tr.poses[id1]
                        xyz1 = Utils.xyz_tran_R(xyz1)
                        xyz1 = Utils.transfor_T(P1, xyz1, w2c=False)
                        if id1 not in xyz0:
                            xyz0[id1] = {}
                        if ip1 not in xyz0[id1]:
                            xyz0[id1][ip1] = []
                        xyz0[id1][ip1].append(xyz1)
                        if id2 not in xyz0:
                            xyz0[id2] = {}
                        if ip2 not in xyz0[id2]:
                            xyz0[id2][ip2] = []
                        xyz0[id2][ip2].append(xyz1)

                count = 0
                for img_id in xyz0:
                    for p_id in xyz0[img_id]:
                        count += 1
                        xyz1 = xyz0[img_id][p_id]
                        if len(xyz1)>1:
                            xyz1 = np.array(xyz1)
                            t_loss += np.linalg.norm(np.std(xyz1, axis=0))
                            t_count += 1
                            xyz0[img_id][p_id] = np.mean(xyz1, axis=0)
                        else:
                            xyz0[img_id][p_id] = xyz1[0]
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
                for c in range(0, length, cfg.batch_size):
                    dd = data[c:c + cfg.batch_size]
                    th = []
                    # for d in range(c, c+dd.shape[0]):
                    for d in truth[c:c + cfg.batch_size]:
                        t = d[2]
                        t = Utils.transfor_T(tr.poses[d[0][0]], t, w2c=True)
                        t = Utils.xyz_tran(t)
                        th.append(t)
                    th = np.array(th)

                    feed = {input_dic['data_1'.format(mode)]: np.array(dd), outputs: th}
                    A, _, B = sess.run([losses, opts, xyz], feed_dict=feed)
                    te_loss += A
                    diff_loss1 += np.sum((B[:, :2]-th[:, :2])*(B[:, :2]-th[:,:2]))
                    diff_loss2 += np.sum((B[:, 2]-th[:, 2])*(B[:, 2]-th[:, 2]))
                    te_count += len(th)

                # print(count, t_count, t_loss/t_count, te_count, te_loss/te_count)

            logger.info("Err {2} {0:.6f} {1:.6f} {3} {4} {5}".
                        format(t_loss/t_count, te_loss/te_count, a,
                               dist, diff_loss1/te_count, diff_loss2/te_count))
            saver.save(sess, cfg.netFile)


if __name__ == '__main__':

    config_file = "config.json"

    cfg = Config(config_file)
    cfg.num_output = list(map(int, cfg.num_output.split(',')))

    iterations = 10000

    if len(sys.argv)>1:
        cfg.mode = int(sys.argv[1])

    if len(sys.argv)>2:
        iterations = int(sys.argv[2])

    run(cfg, iterations)