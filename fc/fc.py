import sys
from fc_dataset import *
import tensorflow as tf
import datetime

sys.path.append('..')
from utils import Utils

HOME = '/home/weihao/Projects/'

if __name__ == '__main__':

    config_file = "config.json"

    if len(sys.argv)>1:
        config_file = sys.argv[1]

    js = Utils.load_json_file(config_file)

    tr_data = []
    te_data = []
    for key in js:
        if key.startswith('tr'):
            tr_data.append(HOME + js[key])
        if key.startswith('te'):
            te_data.append(HOME + js['te'])

    netFile = HOME + 'NNs/' + js['net'] + '/fc'
    batch_size = int(js['batch_size'])
    feature_len = int(js['feature'])
    lr = float(js['lr'])

    num_output = int(js["num_output"])
    nodes = map(int, js["nodes"].split(','))
    nodes.append(num_output)

    renetFile = None
    if 'retrain' in js:
        renetFile = HOME + 'NNs/' + js['retrain'] + '/fc'

    net_type = "fc"
    if 'net_type' in js:
        net_type = js['net_type']

    tr = DataSet(tr_data, batch_size, feature_len)
    te_set = DataSet(te_data, batch_size, feature_len)

    sz_in = te_set.sz
    iterations = 10000
    loop = 20
    print "input shape", sz_in, "LR", lr, 'feature', feature_len

    input = tf.placeholder(tf.float32, [None, feature_len* sz_in[1]])
    output = tf.placeholder(tf.float32, [None, num_output])

    if net_type == 'cnn':
        net = cNet({'data': input})
    else:
        net = sNet3({'data': input})
        net.real_setup(nodes)

    xy = net.layers['output']
    #loss = tf.reduce_sum(tf.square(tf.square(tf.subtract(xy, output))))
    loss = tf.reduce_sum(tf.square(tf.subtract(xy, output)))

    opt = tf.train.AdamOptimizer(learning_rate=lr, beta1=0.9,
                        beta2=0.999, epsilon=0.00000001,
                        use_locking=False, name='Adam').\
        minimize(loss)

    init = tf.global_variables_initializer()
    saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(init)
        if renetFile:
            saver.restore(sess, renetFile)

        t00 = datetime.datetime.now()

        for a in range(iterations):

            tr_pre_data = tr.prepare(num_output=num_output)
            total_loss, tr_median = run_data(tr_pre_data, input, sess, xy)

            te_pre_data = te_set.prepare(num_output=num_output)
            te_loss, te_median = run_data(te_pre_data, input, sess, xy)

            t1 = datetime.datetime.now()
            str = "iteration: {} {} {} {} {} {} time {}".format(
                a*loop, total_loss, te_loss, te_loss-total_loss,
                tr_median, te_median, t1 - t00)
            print str
            t00 = t1

            for _ in range(loop):
                tr_pre_data = tr.prepare(num_output=num_output, multi=1) #.get()
                while tr_pre_data:
                    for b in tr_pre_data:
                        feed = {input: b[0], output: b[1]}
                        sess.run(opt, feed_dict=feed)
                    tr_pre_data = tr.get_next()

            saver.save(sess, netFile)

        print netFile
        saver.save(sess, netFile)

