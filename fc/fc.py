import sys
import tensorflow as tf
import datetime
import pickle
import os
import numpy as np
import random

sys.path.append('..')
from utils import Utils, Config, HOME
from network import Network


class DataSet:
    def __init__(self, p_file, cfg):
        with open(os.path.join(HOME, p_file), 'r') as fp:
            self.data = pickle.load(fp)
        self.cfg = cfg

    def get_avg(self, filename):
        x = []
        for d in self.data:
            for a in d[2]:
                x.append(a[1])
                x.append(a[2])

        x = np.array(x)
        avx = np.mean(x, axis=0)
        stx = np.std(x, axis=0)

        print(avg_file)
        with open(filename, 'wb') as fp:
            pickle.dump((avx, stx), fp)

    def subtract_avg(self, filename):
        with open(filename, 'r') as fp:
            av, st = pickle.load(fp)
            for d in self.data:
                for a in range(len(d[2])):
                    x = (np.array(d[2][a][1])-av)/st
                    y = (np.array(d[2][a][2])-av)/st
                    d[2][a] = (d[2][a][0], x, y)

    def prepare(self, count=None):
        if self.cfg.mode == 1:
            return self.prepare1(count)
        elif self.cfg.mode == 2:
            return self.prepare2(count)
        elif self.cfg.mode == 3:
            return self.prepare3(count)
        else:
            raise Exception('Unknown mode {}'.format(cfg.mode))

    def prepare1(self, count):
        nt = 0
        for d in self.data:
            nt += len(d[2])

        if count:
            r = float(count) / nt

        out = []
        for d in self.data:
            P1 = d[0]
            P2 = d[1]
            A, T = Utils.get_relative(P1, P2)
            for a in d[2]:
                if count is None or random.random() < r:
                    xyz = a[0]
                    p1 = a[1]
                    p2 = a[2]
                    xyz = P1.Q4.dot(np.concatenate((xyz, [1])))[:3]
                    data = np.concatenate((A, T, p1, p2))
                    out.append((data, xyz))
        np.random.shuffle(out)

        rst = []
        truth = []
        for b in out:
            rst.append(b[0])
            truth.append(b[1])
        return np.array(rst), np.array(truth)

    def prepare2(self, count):
        nt = 0
        for d in self.data:
            nt += len(d[2])

        if count:
            r = float(count)/nt

        out = []
        for d in self.data:
            P1 = d[0]
            P2 = d[1]
            A, T = Utils.get_relative(P1, P2)
            for a in d[2]:
                if count is None or random.random() < r:
                    xyz = a[0]
                    p1 = a[1]
                    p2 = a[2]
                    xyz = P1.Q4.dot(np.concatenate((xyz, [1])))[:3]
                    data = np.concatenate((xyz, p1, p2))
                    out.append((data, T))
        np.random.shuffle(out)

        rst = []
        truth = []
        for b in out:
            rst.append(b[0])
            truth.append(b[1])
        return np.array(rst), np.array(truth)

    def prepare3(self, count):
        nt = 0
        for d in self.data:
            nt += len(d[2])

        if count:
            r = float(count) / nt

        out = []
        for d in self.data:
            P1 = d[0]
            P2 = d[1]
            A, T = Utils.get_relative(P1, P2)
            for a in d[2]:
                if count is None or random.random() < r:
                    xyz = a[0]
                    p1 = a[1]
                    p2 = a[2]
                    xyz = P1.Q4.dot(np.concatenate((xyz, [1])))[:3]
                    data = np.concatenate((xyz, p1, p2))
                    out.append((data, A))
        np.random.shuffle(out)

        rst = []
        truth = []
        for b in out:
            rst.append(b[0])
            truth.append(b[1])
        return np.array(rst), np.array(truth)


class P1Net1(Network):

    def setup(self):
        pass

    def real_setup(self, nodes, num_output):
        self.feed('data')
        for a in range(len(nodes)):
            name = 'fc_{}'.format(a)
            self.fc(nodes[a], name=name)
        self.fc(num_output, relu=False, name='output')


def avg_file_name(p):
    basename = os.path.basename(p)
    pathname = os.path.dirname(p)
    return pathname + '_' + basename+'_avg.p'


def run_data(data, inputs, sess, xy, fname, cfg):
    rst = data[0]
    truth = data[1]
    feed = {}
    feed[inputs['data']] = np.array(rst)
    r = sess.run(xy, feed_dict=feed)

    rt = 2000.0/len(rst)
    filename = '/home/weihao/tmp/{}.csv'.format(fname)
    if sys.platform == 'darwin':
        filename = '/Users/weihao/tmp/{}.csv'.format(fname)
    fp = open(filename, 'w')
    rs = []
    for d in range(len(rst)):
        mm = r[d, :]
        t = truth[d]
        r0 = np.linalg.norm(mm-t)
        if random.random() < rt:
            for a in range(len(t)):
                if a > 0:
                    fp.write(',')
                fp.write('{},{}'.format(t[a], mm[a]))
            fp.write(',{}\n'.format(r0))
    fp.close()
    diff = r - np.array(truth)
    dist = np.linalg.norm(diff, axis=1)
    return np.mean(dist*dist), np.median(dist)


if __name__ == '__main__':

    config_file = "config.json"

    if len(sys.argv)>1:
        config_file = sys.argv[1]

    cfg = Config(config_file)

    iterations = 100000

    cfg.netFile = '{}_{}'.format(cfg.netFile, cfg.mode)
    if cfg.renetFile:
        cfg.renetFile = '{}_{}'.format(cfg.renetFile, cfg.mode)
    print("LR", cfg.lr, 'num_out', cfg.num_output)

    output = tf.placeholder(tf.float32, [None, cfg.num_output])

    feature_len = 7
    if cfg.mode == 1:
        feature_len = 10

    input = tf.placeholder(tf.float32, [None, feature_len])
    input_dic = {'data': input}
    net = P1Net1(input_dic)
    net.real_setup(cfg.nodes[0], cfg.num_output)

    xy = net.layers['output']
    loss = tf.reduce_sum(tf.square(tf.subtract(xy, output)))

    opt = tf.train.AdamOptimizer(learning_rate=cfg.lr, beta1=0.9,
                        beta2=0.999, epsilon=0.00000001,
                        use_locking=False, name='Adam').\
        minimize(loss)
    # opt = tf.train.GradientDescentOptimizer(learning_rate=cfg.lr).minimize(loss)

    init = tf.global_variables_initializer()
    saver = tf.train.Saver()

    tr = DataSet(cfg.tr_data[0], cfg)
    te = DataSet(cfg.te_data[0], cfg)
    avg_file = avg_file_name(cfg.netFile)
    tr.get_avg(avg_file)
    tr.subtract_avg(avg_file)
    te.subtract_avg(avg_file)

    with tf.Session() as sess:
        sess.run(init)
        if cfg.renetFile:
            saver.restore(sess, cfg.renetFile)

        t00 = datetime.datetime.now()
        st1 = ''
        for a in range(iterations):

            tr_pre_data = tr.prepare(3000)
            tr_loss, tr_median = run_data(tr_pre_data, input_dic, sess, xy, 'tr', cfg)

            te_pre_data = te.prepare(3000)
            te_loss, te_median = run_data(te_pre_data, input_dic, sess, xy, 'te', cfg)

            t1 = (datetime.datetime.now()-t00).seconds/3600.0
            str = "iteration: {0} {1:.3f} {2} {3} {4} {5}".format(
                a*cfg.loop/1000.0, t1, tr_loss, te_loss,
                tr_median, te_median)
            print('{} {}'.format(str, st1))

            t_loss = 0
            t_count = 0
            for lp in range(cfg.loop):
                tr_pre_data = tr.prepare()
                data = tr_pre_data[0]
                truth = tr_pre_data[1]
                length = data.shape[0]

                for c in range(0, length, cfg.batch_size):
                    feed = {input: data[c:c+cfg.batch_size], output: truth[c:c+cfg.batch_size]}
                    _, A = sess.run([opt, loss], feed_dict=feed)
                    t_loss += A
                    t_count += len(data[c:c+cfg.batch_size])
                st1 = '{}'.format(t_loss/t_count)

            saver.save(sess, cfg.netFile)


