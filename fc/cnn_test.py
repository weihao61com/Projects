import sys
from fc_dataset import *

sys.path.append( '..')
from utils import Utils

HOME = '/home/weihao/Projects/Posenet/'

if __name__ == '__main__':

    config_file = "config_cnn.json"

    data_type = 'te'
    if len(sys.argv)>2:
        data_type = sys.argv[2]

    if len(sys.argv)>3:
        config_file = sys.argv[3]

    loop = 1
    if len(sys.argv)>1:
        loop = int(sys.argv[1])

    js = Utils.load_json_file(config_file)

    te_data = []
    for key in js:
        if key.startswith(data_type):
            te_data.append(HOME + js[key])

    netFile = HOME + '/' + js['netTest'] + '/fc'
    batch_size = int(js['batch_size'])
    feature_len = int(js['feature'])
    num_output = int(js["num_output"])

    te_set = DataSet(te_data, batch_size, feature_len)

    input = tf.placeholder(tf.float32, [None, feature_len, 4, 1])

    net = cNet({'data': input})

    xy = net.layers['output']

    saver = tf.train.Saver()

    with tf.Session() as sess:
        saver.restore(sess, netFile)

        rst = {}
        truth = {}
        for _ in range(loop):
            nt = 0
            te_pre_data = te_set.prepare_cnn(rd=False)
            for b in te_pre_data:
                feed = {input: b[0]}
                result = sess.run(xy, feed_dict=feed)
                for a in range(len(result)):
                    if not nt in rst:
                        rst[nt] = []
                    rst[nt].append(result[a])
                    truth[nt] = b[1][a]
                    nt += 1

        fp = open('/home/weihao/tmp/test.csv', 'w')
        d = []
        for a in range(len(truth)):
            r, mm = cal_diff(truth[a], rst[a])
            if a==0:
                print truth[a]
                print mm, r
                for b in rst[a]:
                    print np.linalg.norm(b-truth[a]), b
            t = truth[a]
            #fp.write('{},{},{},{},{},{},{}\n'.
            #         format(t[0], t[1], t[2], mm[0], mm[1], mm[2], r))
            if random.random()<0.1:
                fp.write('{},{},{},{},{},{},{}\n'.
                     format(t[0], mm[0],t[1], mm[1],t[2], mm[2], r))
            d.append(r)
        fp.close()
        md = np.median(d)
        print len(truth), np.mean(d), md, np.sqrt(md)

