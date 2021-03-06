import sys
from fc_dataset import *
import tensorflow as tf
import datetime

HOME = '{}/Projects/'.format(os.getenv('HOME'))
sys.path.append('{}/my_nets'.format(HOME))
sys.path.append('{}/my_nets/fc'.format(HOME))

from utils import Utils
from fc_dataset import DataSet

if __name__ == '__main__':

    config_file = "config_stack.json"

    data_type = 'te'
    if len(sys.argv) > 1:
        data_type = sys.argv[1]

    if len(sys.argv) > 2:
        config_file = sys.argv[2]

    multi = -1
    if len(sys.argv) > 3:
        multi = int(sys.argv[3])

    js = Utils.load_json_file(config_file, False)

    te_data = []
    for key in js:
        if key.startswith(data_type):
            te_data.append(HOME + js[key])

    netFile = HOME + 'NNs/' + js['netTest'] + '/fc'

    batch_size = js['batch_size']
    feature_len = js['feature']
    stack = js['stack']
    num_output = js["num_output"]

    te = DataSet(te_data, batch_size, feature_len + stack)

    att = te.sz[1]

    print "input shape", att, 'feature', feature_len

    inputs = {}

    inputs[0] = tf.placeholder(tf.float32, [None, feature_len * att])
    output = tf.placeholder(tf.float32, [None, num_output])
    for a in range(stack):
        inputs[a + 1] = tf.placeholder(tf.float32, [None, att])

    input_dic = {}
    for a in range(stack + 1):
        input_dic['input{}'.format(a)] = inputs[a]

    net = StackNet(input_dic)
    net.real_setup(stack, False)

    xy = {}
    for a in range(stack+1):
        xy[a] = net.layers['output{}'.format(a)]

    init = tf.global_variables_initializer()
    saver = tf.train.Saver()

    with tf.Session() as sess:
        sess.run(init)
        saver.restore(sess, netFile)

        t00 = datetime.datetime.now()

        te_pre_data = te.prepare(multi=multi)
        te_loss, te_median = run_data_stack_avg2(te_pre_data, input_dic, sess, xy, stack)

        t1 = datetime.datetime.now()
        str = "RST: {0:.1f} " \
              " {1:.4f} {2:.4f} {3:.4f} {4:.4f} {5:.4f} {6:.4f}".format(
            (t1 - t00).total_seconds(),
            te_loss[stack - 3],
            te_loss[stack - 2],
            te_loss[stack - 1],
            te_median[stack - 3],
            te_median[stack - 2],
            te_median[stack - 1])
        print str
