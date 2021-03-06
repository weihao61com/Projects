import torch
import sys
import numpy as np
from rnn import RNN
import os
import datetime

this_file_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append('{}/..'.format(this_file_path))

from dataset import DataSet, Config
from utils import Utils


def ToTensor(array):
    return torch.tensor(array)


def run_test(mrnn, tr, cfg, hidden):
    rst_dic = {}
    truth_dic = {}

    tr_pre_data = tr.prepare(multi=-1)
    while tr_pre_data:
        for b in tr_pre_data:
            length = len(b[0])
            x = ToTensor(b[0].reshape(length, cfg.feature_len, cfg.att).astype(np.float32))
            outputs = mrnn.run(x, hidden)
            for a in range(len(b[2])):
                if not b[2][a] in rst_dic:
                    rst_dic[b[2][a]] = []
                rst_dic[b[2][a]].append(outputs[a, :, :])
                truth_dic[b[2][a]] = b[1][a]

        results = []
        truth = []

        #filename = '/home/weihao/tmp/{}.csv'.format(fname)
        #if sys.platform == 'darwin':
        #    filename = '/Users/weihao/tmp/{}.csv'.format(fname)
        #fp = open(filename, 'w')
        for id in rst_dic:
            dst = np.array(rst_dic[id])
            result = np.median(dst, axis=0)
            results.append(result)
            truth.append(truth_dic[id])
            # if random.random() < 0.2:
            #     r = np.linalg.norm(t - result)
            #     mm = result[-1]
            #     if len(mm) == 3:
            #         fp.write('{},{},{},{},{},{},{}\n'.
            #                  format(t[0], mm[0], t[1], mm[1], t[2], mm[2], r))
            #     else:
            #         fp.write('{},{},{}\n'.
            #                  format(t[0], mm[0], r))
        #fp.close()
        tr_pre_data = tr.get_next()

    return Utils.calculate_stack_loss_avg(np.array(results), np.array(truth))



def main(args):

    config_file = args.config
    test = args.test

    cfg = Config(config_file)

    tr = None
    if test is None:
        tr = DataSet(cfg.tr_data, cfg)
        te = DataSet(cfg.te_data, cfg, sub_sample=1)
        tr0 = DataSet([cfg.tr_data[0]], cfg, sub_sample=1)
        cfg.att = te.sz[1]
    else:
        if test == 'te':
            te = DataSet([cfg.te_data[0]], cfg)
        else:
            te = DataSet([cfg.tr_data[0]], cfg)
        cfg.att = te.sz[1]

    iterations = 10000
    loop = cfg.loop
    print "input attribute", cfg.att, "LR", cfg.lr, 'feature', cfg.feature_len

    n_att = cfg.att
    n_length = cfg.feature_len
    n_hidden = 256
    n_output = cfg.num_output

    mrnn = RNN(n_att, n_length, n_hidden, n_output, cfg.lr)
    # print("Model's state_dict:")
    # for param_tensor in mrnn.state_dict():
    #     print(param_tensor, "\t", mrnn.state_dict()[param_tensor].size())
    hidden = ToTensor(np.ones(n_hidden).astype(np.float32))

    if test:
        mrnn.load_state_dict(torch.load(cfg.netTest[:-3]))
        run_test(mrnn, te, cfg, hidden)
        tr_loss, tr_median = run_test(mrnn, te, cfg, hidden)
        for a in range(len(tr_loss)):
            print a, tr_loss[a], tr_median[a]

        exit(0)

    if cfg.renetFile:
        mrnn.load_state_dict(torch.load(cfg.renetFile[:-3]))

    t00 = datetime.datetime.now()

    T = 0
    T_err=0
    for a in range(iterations):

        tr_pre_data = tr.prepare(multi=1)
        while tr_pre_data:
            for b in tr_pre_data:
                length = len(b[0])
                x = ToTensor(b[0].reshape(length, cfg.feature_len, cfg.att).astype(np.float32))
                y = ToTensor(b[1].astype(np.float32))
                err = mrnn.train(y, x, hidden)
                if a%loop==0 and a>0:
                    t1 = datetime.datetime.now()
                    print a, (t1 - t00).total_seconds()/3600.0, T_err/T
                    T_err=0
                    T = 0
                    torch.save(mrnn.state_dict(), cfg.netFile[:-3])
                T_err += err
                T += 1

            tr_pre_data = tr.get_next()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', help='config', default='t_config.json')
    parser.add_argument('-t', '--test', help='test', default=None)
    args = parser.parse_args()

    main(args)