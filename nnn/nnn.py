import numpy as np
import sys
import datetime
import pickle
import os

HOME = '{}/Projects/'.format(os.getenv('HOME'))
sys.path.append('{}/my_nets'.format(HOME))
sys.path.append('{}/my_nets/fc'.format(HOME))

from utils import Utils
from fc_dataset import DataSet


def add_1(inputs):
    return np.concatenate ((inputs, np.array([[1]*len(inputs)]).T), axis=1)


def sigmoid(x, derivative=False):
    return x * (1 - x) if derivative else 1 / (1 + np.exp(-x))


def relu(x, derivative=False):
    return 1. * (x > 0) if derivative else np.maximum(x, 0)


class NNN:

    def __init__(self, input_dim, output_dim, layers):
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.weights = []
        self.active_function = relu
        layers.append(output_dim)
        self.num_layers = len(layers)
        self.learning_rate = None
        self.beta1 = None
        self.D_weight = []
        self.gradient_momentum = []
        self.g2_momentum = []
        self.Zs = None

        number = self.input_dim + 1
        for a in range(self.num_layers):
            layer = layers[a]
            w = np.random.randn(number, layer)/np.sqrt(number)
            self.weights.append(w)

            self.gradient_momentum.append(np.zeros(w.shape))
            self.g2_momentum.append(np.zeros(w.shape))
            self.D_weight.append(np.zeros(w.shape))
            number = layer + 1

    def setup(self, lr):
        self.beta1 = 0.99
        self.beta2 = 0.999999

        self.learning_rate = lr

    def backward(self, grad):
        self.D_weight[-1] = self.Zs[-1].T.dot(grad)
        weigh_T = self.weights[-1].T
        for a in range(self.num_layers - 1):
            grad = grad.dot(weigh_T)
            grad = grad * self.active_function(self.Zs[-1 - a], True)
            grad = grad[:, :-1]
            self.D_weight[-2 - a] = self.Zs[-2 - a].T.dot(grad)
            weigh_T = self.weights[-2 - a].T

    def train(self, inputs, outputs):

        predicts = self.run(inputs, True)
        grad = outputs - predicts
        loss = np.square(grad).sum()
        self.backward(grad)

        self.update_momentum()
        for a in range(self.num_layers):
            self.weights[a] += self.gradient_momentum[a]*self.learning_rate

        return loss

    def update_momentum(self):
        for a in range(self.num_layers):

            v = self.beta1 * self.gradient_momentum[a]\
                + (1 - self.beta1) * self.D_weight[a]

            #v1 = np.maximum(v, 1e-4)
            #v2 = np.minimum(v, -1e-4)

            self.gradient_momentum[a] = v #v1 * (v>0) + v2 * (v<0)

    def reset(self):

        p = self.gradient_momentum
        w = self.weights
        output = '{0} {1} {2} {3:.6f} {4:.6f} {5:.6f} '.\
            format(p[0][1][10], p[1][10][21], p[2][15][0],
                   w[0][1][10], w[1][10][21], w[2][15][0])

        self.D_weight = []
        for a in range(self.num_layers):
            self.D_weight.append(np.zeros(self.weights[a].shape))
        return output

    def run(self,inputs, save_intermediate=False):
        Z = None
        Zs = [add_1(inputs)]
        for a in range(self.num_layers - 1):
            A = Zs[a].dot(self.weights[a])
            Z = add_1(self.active_function(A))
            Zs.append(Z)
        predicts = Z.dot(self.weights[-1])
        if save_intermediate:
            self.Zs = Zs
        return predicts

    def run_data(self, data):
        results = None
        truth = None

        for b in data:
            inputs = b[0]
            result = self.run(inputs)
            if results is None:
                results = result
                truth = b[1]
            else:
                results = np.concatenate((results, result))
                truth = np.concatenate((truth, b[1]))

        return Utils.calculate_loss(results, truth)


if __name__ == '__main__':

    config_file = "config.json"

    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    js = Utils.load_json_file(config_file)

    tr_data = []
    te_data = []
    for key in js:
        if key.startswith('tr'):
            tr_data.append(HOME + js[key])
        if key.startswith('te'):
            te_data.append(HOME + js['te'])

    netFile = HOME + 'NNs/' + js['net'] + '.p'
    batch_size = int(js['batch_size'])
    feature_len = int(js['feature'])
    lr = float(js['lr'])

    num_output = int(js["num_output"])
    nodes = map(int, js["nodes"].split(','))

    renetFile = None
    if 'retrain' in js:
        renetFile = HOME + 'NNs/' + js['retrain'] + '.p'

    tr = DataSet(tr_data, batch_size, feature_len)
    te_set = DataSet(te_data, batch_size, feature_len)

    sz_in = te_set.sz
    iterations = 10000
    loop = 200
    print "input shape", sz_in, "LR", lr, 'feature', feature_len

    D_in = feature_len* sz_in[1]
    D_out = num_output

    if renetFile is not None:
        with open(renetFile, 'r') as fp:
            nnn = pickle.load(fp)
    else:
        nnn = NNN(D_in, D_out, nodes)

    nnn.setup(lr)

    t00 = datetime.datetime.now()
    str1 = ''
    for a in range(iterations):
        tr_pre_data = tr.prepare(multi=1)
        total_loss, tr_median = nnn.run_data(tr_pre_data)

        te_pre_data = te_set.prepare(multi=1)
        te_loss, te_median = nnn.run_data(te_pre_data)

        t1 = datetime.datetime.now()
        str = "iteration: {0} {1:.6f} {2:.6f} {3:.6f} {4:.6f} {5} ".format(
            a * loop, total_loss, te_loss,
            tr_median, te_median, t1 - t00)
        print str + str1
        t00 = t1

        for t in range(loop):
            str1 = nnn.reset()
            loss = 0
            tr_pre_data = tr.prepare(multi=1)
            while tr_pre_data:
                for b in tr_pre_data:
                    loss += nnn.train(b[0], b[1])
                tr_pre_data = tr.get_next()
            #print t, loss

        with open(netFile, 'w') as fp:
            pickle.dump(nnn, fp)
