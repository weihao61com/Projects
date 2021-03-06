# import os
import tensorflow as tf
from fc_dataset import *

this_file_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append('{}/..'.format(this_file_path))
from utils import Utils

HOME = '/home/weihao/Projects/'
if sys.platform=='darwin':
    HOME = '/Users/weihao/Projects/'

if __name__ == '__main__':
    config_file = HOME + "/my_nets/fc/config.json"

    data_type = 'te'
    if len(sys.argv)>2:
        data_type = sys.argv[2]

    if len(sys.argv)>3:
        config_file = sys.argv[3]

    loop = 1
    if len(sys.argv)>1:
        loop = int(sys.argv[1])

    multi = -1
    cfg = Config(config_file)

    data = cfg.te_data
    if data_type == 'tr':
        data = cfg.tr_data

    te_set = DataSet(data, cfg)

    #netFile = HOME + 'NNs/' + js['netTest'] + '/fc'
    #batch_size = int(js['batch_size'])
    #feature_len = int(js['feature'])
    #num_output = int(js["num_output"])
    #nodes = map(int, js["nodes"].split(','))
    #nodes = cfg.nodes
    #nodes.append(cfg.num_output)

    t_scale= cfg.t_scale
    net_type = cfg.net_type

    if net_type == 'cnn':
        input = tf.placeholder(tf.float32, [None, cfg.feature_len, 4, 1])
        net = cNet({'data': input})
        net.real_setup(cfg.nodes[0], cfg.num_output)
    else:
        input = tf.placeholder(tf.float32, [None, cfg.feature_len * 4])
        net = sNet3({'data': input})
        net.real_setup(cfg.nodes[0], cfg.num_output)

    xy = net.layers['output']

    saver = tf.train.Saver()

    with tf.Session() as sess:
        saver.restore(sess, cfg.netFile)

        rst = {}
        truth = {}
        for _ in range(loop):
            te_pre_data = te_set.prepare(rd=False,multi=multi)
            for b in te_pre_data:
                feed = {input: b[0]}
                result = sess.run(xy, feed_dict=feed)
                ids = b[2]
                for a in range(len(result)):
                    nt = ids[a]
                    if not nt in rst:
                        rst[nt] = []
                    rst[nt].append(result[a])
                    truth[nt] = b[1][a]

        fp = open('{}/../tmp/test.csv'.format(HOME), 'w')
        d = []
        for a in range(len(truth)):
            r, mm = cal_diff(truth[a], rst[a])
            if a==0:
                print truth[a], mm, r
                diff = []
                for b in rst[a]:
                    # print np.linalg.norm(b-truth[a]), b, truth[a]
                    diff.append(b-truth[a])
                diff = np.array(diff)
                for b in range(diff.shape[1]):
                    hist, bins = np.histogram(diff[:,b])


            t = truth[a]
            #fp.write('{},{},{},{},{},{},{}\n'.
            #         format(t[0], t[1], t[2], mm[0], mm[1], mm[2], r))
            if random.random()<0.2:
                if cfg.num_output==3:
                    fp.write('{},{},{},{},{},{},{}\n'.
                         format(t[0], mm[0],t[1], mm[1],t[2], mm[2], r))
                else:
                    fp.write('{},{},{}\n'.
                         format(t[0], mm[0], r))
            d.append(r*r)
        fp.close()
        md = np.median(d)
        print len(truth), np.mean(d), np.sqrt(md)

