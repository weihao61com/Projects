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
from Last.distance import distance_cal
from Last.last2 import create_net, DataSet2

def run(cfg, iterations):

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

    tr = DataSet2(cfg.tr_data[0], cfg)
    if cfg.mode==0:
        tr.get_avg(avg_file)
    else:
        tr.subtract_avg(avg_file)
    T0 = datetime.datetime.now()

    n_cpus = 8
    with tf.Session(config=tf.ConfigProto(
            device_count={"CPU": n_cpus},
            inter_op_parallelism_threads=n_cpus,
            intra_op_parallelism_threads=n_cpus-2,
    )) as sess:
        #with tf.compat.v1.Session() as sess:
        sess.run(init)
        if cfg.mode == 0:
            saver.save(sess, cfg.netFile)
            exit(0)

        saver.restore(sess, cfg.netFile)

        # mode = cfg.mode
        # print(outputs)

        for a in range(iterations):
            # filename = '/home/weihao/Projects/tmp/rst_learn.csv'.format(cfg.mode)
            # w_deviation = 0
            # t_count = 0
            # te_loss = 0
            # te_count = 0
            # diff_loss1 = 0
            # diff_loss2 = 0
            for lp in range(cfg.loop):
                tr_pre = tr.prepare(None, clear=True)
                w_deviation = 0
                t_count = 0
                w_distance_truth = 0
                te_count = 0
                diff_loss1 = 0
                diff_loss2 = 0
                diff_loss1t = 0
                diff_loss2t = 0

                data = tr_pre[0]
                truth = tr_pre[1]
                length = data.shape[0]
                xyz0 = {}
                trt0 = {}
                sz = 100000
                T = datetime.datetime.now()
                print("Ready: ", T-T0)
                for c in range(0, length, sz):
                    dd = data[c:c + sz]
                    th = truth[c:c + sz]
                    dd = np.array(dd)
                    feed = {input_dic['data_1']: dd, input_dic['data_2']: dd}
                    A = sess.run(xyz, feed_dict=feed)
                    A = np.concatenate((A[0], A[1]), axis=1)
                    for d in range(len(th)):
                        xyz3 = A[d, :]
                        t1 = th[d]
                        id1 = t1[0][0]
                        ip1 = t1[0][1]
                        id2 = t1[1][0]
                        ip2 = t1[1][1]

                        P1 = tr.poses[id1]
                        xyz2 = Utils.xyz_tran_R(xyz3)
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
                        if id2 not in xyz0:
                            xyz0[id2] = {}
                            trt0[id2] = {}
                        if ip2 not in xyz0[id2]:
                            xyz0[id2][ip2] = []
                            trt0[id2][ip2] = xyzt
                        xyz0[id2][ip2].append(xyz1)
                T = datetime.datetime.now()
                print("Run:   ", T-T0)

                fp = None
                if lp == 0:
                    fp = open('/home/weihao/tmp/xyz.csv', 'w')
                    fp.write("a,b,c,d\n")
                count = 0
                for img_id in xyz0:
                    count += len(xyz0[img_id])
                count1 = 0
                for img_id in xyz0:
                    P1 = tr.poses[img_id]

                    for p_id in xyz0[img_id]:
                        xyz1 = xyz0[img_id][p_id]
                        if len(xyz1)>1:
                            xyz1 = np.array(xyz1)
                            a2 = np.std(xyz1, axis=0)
                            w_deviation += np.linalg.norm(a2)
                            t_count += 1
                            #xyz0[img_id][p_id] = np.mean(xyz1, axis=0)
                            xyz0[img_id][p_id] = np.median(xyz1, axis=0)


                            if fp is not None:
                                if random.random() < 2000.0 / count:
                                    a0 = Utils.transfor_T(P1, trt0[img_id][p_id], w2c=True)
                                    a1 = Utils.transfor_T(P1, xyz0[img_id][p_id], w2c=True)
                                    if a1[2] < 0.5:
                                        a1[2] = 0.5
                                    a0 = Utils.xyz_tran(a0)
                                    a1 = Utils.xyz_tran(a1)
                                    fp.write('0,{},{},{},{},'.format(a0[0], a1[0], abs(a0[0]-a1[0]), a2[0]))
                                    fp.write('{},{},{},{},'.format(a0[1], a1[1], abs(a0[1]-a1[1]), a2[1]))
                                    fp.write('{},{},{},{} '.format(a0[2], a1[2], abs(a0[2]-a1[2]), a2[2]))
                                    fp.write('\n')

                        else:
                            xyz0[img_id][p_id] = xyz1[0]
                            count1 += 1
                T = datetime.datetime.now()
                print("Avg:   ", T-T0, count1, "from", count, w_deviation/t_count)


                nf = 0
                w_distance_2 = 0
                sum1 = np.array([0.0,0,0])
                sum2 = np.array([0.0,0,0])
                for c in range(length):
                    t1 = truth[c]
                    img_id = t1[0][0]
                    p_id = t1[0][1]
                    x1 = xyz0[img_id][p_id]
                    img_id2 = t1[1][0]
                    p_id2 = t1[1][1]
                    x2 = xyz0[img_id2][p_id2]
                    w_distance_2 += np.linalg.norm(x1-x2)
                    xyz1 = (x1+x2)/2
                    xyz1 = Utils.transfor_T(tr.poses[img_id], xyz1, w2c=True)
                    if xyz1[2] < 0.5:
                        nf += 1
                        xyz1[2] = 0.5
                    xyz1 = Utils.xyz_tran(xyz1)

                    a1 = xyz1
                    a0 = t1[2]

                    truth[c] = t1[:3] + (xyz1,)
                    xyz1 = np.array(xyz1)
                    sum1 += xyz1
                    sum2 += xyz1*xyz1

                    dd = np.linalg.norm(a0 - a1)
                    w_distance_truth += dd
                    te_count += 1
                    if fp is not None:
                        if random.random() < 2000.0 / length:
                            fp.write('1, {},{},'.format(a0[0], a1[0]))
                            fp.write('{},{},'.format(a0[1], a1[1]))
                            fp.write('{},{} '.format(a0[2], a1[2]))
                            fp.write('\n')

                w_distance_2 /= length
                T = datetime.datetime.now()
                print("Less 0:", T-T0, nf, w_distance_2, w_distance_truth/te_count)

                if fp:
                    fp.close()

                sum1 /= length
                sum2 /= length

                sum2 -= sum1*sum1
                sum2 = np.sqrt(sum2)
                #
                min_scales = [0.3, 0.07, 0.6]
                real_scales = [1.0, 1.0, 1.0]
                for c in range(len(min_scales)):
                    if sum2[c]<min_scales[c]:
                        real_scales[c] = 1.1 #min_scales[c]/sum2[c]
                print('Stdev', sum1, sum2)
                print("scale", real_scales)

                for loop in range(30):
                    diff_loss1 = 0
                    diff_loss2 = 0
                    for c in range(0, length, cfg.batch_size):
                        dd = data[c:c + cfg.batch_size]
                        th1 = []
                        th2 = []

                        # for d in range(c, c+dd.shape[0]):
                        for d in truth[c:c + cfg.batch_size]:
                            #t = (d[3]-sum1)*real_scales + sum1
                            t2 = d[3]
                            t3 = d[3]  # - sum1[2]
                            # t = Utils.transfor_T(tr.poses[d[0][0]], t, w2c=True)
                            # t = Utils.xyz_tran(t)
                            t3_2 = (t3[2] - sum1[2])*real_scales[2] + sum1[2]
                            th1.append(t2[:2])
                            th2.append(t3_2)
                        th1 = np.array(th1)
                        th2 = np.array(th2).reshape((len(dd), 1))
                        dd = np.array(dd)
                        feed = {input_dic['data_1']: dd, input_dic['data_2']: dd,
                                outputs[0]: th1, outputs[1]: th2}
                        # A, B, _ = sess.run([losses, xyz, opts], feed_dict=feed)
                        A, _ = sess.run([losses, opts], feed_dict=feed)
                        diff_loss1 += A[0]
                        diff_loss2 += A[1]
                        # diff_loss2t += np.sum((B[1]-th2)*(B[1]-th2))
                        # diff_loss1t += np.sum((B[0]-th1)*(B[0]-th1))
                    if loop%10==0:
                        T = datetime.datetime.now()
                        print("Loop {0} {1} {2} {3}".
                              format(T-T0, loop, diff_loss1/te_count, diff_loss2/te_count))
                # print(count, t_count, t_loss/t_count, te_count, te_loss/te_count)
            T = datetime.datetime.now()
            # deviation, distance, to_trurth
            print("Err {0} {1} {7} {2:.6f} {3:.6f} {4:.6f} {5:.6f} {6:.6f}".
                        format(T-T0, a, w_deviation/t_count, w_distance_2, w_distance_truth/te_count,
                               diff_loss1/te_count, diff_loss2/te_count, te_count))
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
