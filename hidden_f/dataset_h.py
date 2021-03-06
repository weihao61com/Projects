import pickle
import numpy as np
import datetime
import random
import sys
import os
import rotation_averaging.util
import cv2


this_file_path = os.path.dirname(os.path.realpath(__file__))
HOME = '{}/../..'.format(this_file_path)
sys.path.append('{}/my_nets'.format(HOME))

from ras_dataset import RAS_D
from image_pairing.pose_ana import \
    load_kitti_poses, load_indoor_7_poses, load_TUM_poses


from utils import Utils


def reverse(v):
    Q = Utils.create_Q(v[:3], v[3:])
    Q = np.linalg.inv(Q)
    A, T = Utils.get_A_T(Q)
    return A + T

def load_data(filename, verbose = True, sub_sample=-1):
    t0 = datetime.datetime.now()
    if type(filename) is str: #unicode:
        avg_param = 0
        nt = 0
        print('FILE', filename)
        with open(filename, 'rb') as fp:
            data = pickle.load(fp)
            length = 0
            for id in data.features:
                features = data.features[id]
                for img in features:
                    d = features[img]
                    avg_param += len(d[0])
                    nt += 1
            #length = len(data)
            avg_param /= nt
            for id in data.matches:
                matches = data.matches[id]
                length += len(matches)


            if sub_sample > 0:
                for id in data.matches:
                    matches = data.matches[id]
                    n_match = {}
                    for img in matches:
                        ms = matches[img]

                        if random.random() < sub_sample:
                            n_match[img] = ms
                    data.matches[id] = n_match
        if verbose:
            print("loading (match,feature)", filename, '\n \t\t', datetime.datetime.now()-t0, \
                length, avg_param)
        return data

    data_out = None
    for f in filename:
        data = load_data(f)
        if data_out is None:
            data_out = data
        else:
            data_out = np.concatenate((data_out, data))

    lenght = len(data_out)
    if lenght > max_len:
        data_out = data_out[:max_len]
    print("Total data", datetime.datetime.now() - t0, lenght, len(data_out))
    return data_out


class DataSet:
    def __init__(self, dataset, cfg, cache=True, sub_sample=-1):
        self.bucket = 0
        self.dataset = dataset
        self.index = -1
        self.batch_size = cfg.memory_size
        self.nPar = cfg.feature_len
        self.nAdd = cfg.add_len
        self.data = None
        self.verbose = True
        self.cache = cache
        self.memories = {}
        self.t_scale = np.array(list(map(float, cfg.t_scale.split(','))))
        self.net_type = cfg.net_type
        self.num_output = cfg.num_output
        self.num_output1 = cfg.num_output1
        self.att = cfg.att
        self.rst = None
        self.rasd = None
        self.out_offset = cfg.out_offset
        self.fc_Nout = cfg.fc_Nout
        self.I = None
        self.cam = None

        self.load_next_data(sub_sample)
        self.sz = None
        for id in self.data:
            self.sz = len(self.data[id][0][0])
            break
        self.id = None
        self.run_cv2()
        features = list(self.rasd.features.values())[0]
        print("features", len(features))
        matches = list(self.rasd.matches.values())[0]
        print("matches", len(matches))
        self.rasd = None
        #self.att = self.sz[1]

    def run_cv2(self):
        data = self.rasd
        dv = []
        for data_id in data.matches:
            matches = data.matches[data_id]
            features = data.features[data_id]
            poses = data.poses[data_id]
            for m_img in matches:
                img1 = m_img[0]
                img2 = m_img[1]
                match = matches[m_img]
                d0 = []
                #att += len(match)
                # if img2-img1!=9:
                #    continue

                for m in match:
                    point1 = m[0]
                    point2 = m[1]
                    feature1 = features[img1][0][point1]
                    feature2 = features[img2][0][point2]
                    # descriptor1 = features[img1][1][point1]
                    # descriptor2 = features[img2][1][point2]
                    d0.append([feature1[0], feature1[1], feature2[0], feature2[1]])

                d0 = np.array(d0)
                px_last = d0[:, :2]
                px_new = d0[:, 2:4]
                if d0.shape[0] <= 5:
                    print(d0.shape)
                    raise Exception("matches length {}".format(len(d0.shape)))

                E, mask = cv2.findEssentialMat(px_new, px_last, cameraMatrix=self.cam.mx,
                                               method=cv2.RANSAC)
                mh, R, t, mask0 = cv2.recoverPose(E, px_new, px_last, cameraMatrix=self.cam.mx)

                b = Utils.get_A(R)
                nid = (m_img[0], m_img[1], data_id)
                self.data[nid] = self.data[nid] + (b,)


    def init_truth(self, dim):
        for id in self.rasd.features:
            features = self.rasd.features[id]
            for image_id in features:
                length = len(features[image_id][0])
                seeds = np.random.random((length, dim)) - 0.5
                self.rasd.features[id][image_id][1] = seeds

    def get_next(self, rd=True, avg=None):
        rt = self.load_next_data()
        if rt == 0:
            return None

        # raise Exception('get_next NIY.')
        if avg and rt==2:
            self.avg_correction(avg)

        if self.index == 0:
            return None

        return self.prepare(rd)

    def get_ids(self):
        ids = []
        for id in self.rasd.poses:
            for p in self.rasd.poses[id]:
                ids.append(self.rasd.poses[id][p].Q4[:3, :3])
        return ids

    def load_next_data(self, sub_sample=-1):
        self.bucket = 0

        if len(self.dataset) == 1 and self.index == 0:
            return 0

        rt = 1
        self.index += 1
        if self.index == len(self.dataset):
            self.verbose = False
            self.index = 0
        if self.index in self.memories:
            data = self.memories[self.index]
        else:
            rasd = load_data(self.dataset[self.index], self.verbose, sub_sample)
            self.cam = rasd.cam
            self.I = []
            for g_id in rasd.poses:
                poses = rasd.poses[g_id]
                print(g_id, len(poses))
                for id in poses:
                    pose = poses[id]
                    self.I.append(pose.Q4[:3, :3])

            data = {}
            g_cnt = 0
            for id in sorted(rasd.matches.keys()):
                matches = rasd.matches[id]
                features = rasd.features[id]
                poses = rasd.poses[id]
                # print(id, g_cnt, len(poses))
                d_id = []

                for ids in matches:
                    img_id1 = ids[0]
                    img_id2 = ids[1]
                    p1 = poses[img_id1]
                    p2 = poses[img_id2]

                    A, T = Utils.get_relative(p1, p2)
                    ar = np.array([A[0], A[1], A[2], T[0], T[1], T[2]])*self.t_scale
                    ft1 = features[img_id1][0]
                    ft2 = features[img_id2][0]
                    if self.att == 4:
                        match = matches[ids]
                        f = []
                        for m in match:
                            f1 = ft1[m[0]]
                            f2 = ft2[m[1]]
                            f.append(np.array([f1[0], f1[1], f2[0], f2[1]]))
                        nid = (ids[0], ids[1], id)
                        data[nid] = (f, ar[self.num_output1:self.num_output])

                    elif self.att==9:
                        raise Exception()
                    else:
                        raise Exception()
            rt = 2

        self.rasd = rasd
        if self.cache:
            self.memories[self.index] = data
        print("total data", len(data))
        self.data = data

        return rt

    def prepare_cnn(self, rd=False):
        pre_data = []
        self.reshuffle_data()
        for d in self.data:
            pre_data.append(self.create_bucket_cnn(d))
        if rd:
            np.random.shuffle(pre_data)
        return pre_data

    def prepare_stack(self, rd=True):
        pre_data = []
        self.reshuffle_data()
        self.id = 0
        for d in self.data:
            data = self.create_stack(d)
            if rd:
                np.random.shuffle(data)
            pre_data.append(data)

        return pre_data

    def create_stack(self, data):
        outputs = []

        for d in data:
            sz = d[0].shape
            if sz[0] < self.nPar + self.nAdd:
                d[0] = np.concatenate((d[0], d[0]))
                sz = d[0].shape
            truth = d[1][:self.num_output]
            d0 = d[0][:self.nPar].reshape(self.nPar * sz[1])
            d1 = d[0][self.nPar:]
            outputs.append([d0, d1, truth])

        return outputs

    def prepare_stage(self, rd=True, rdd=True):
        pre_data = []
        if rdd:
            self.reshuffle_data()
        self.id = 0
        for d in self.data:
            data = self.create_stage_data(d)
            if rd:
                np.random.shuffle(data)
            i0 = []
            i1 = []
            outs = []
            ids = []
            for a in data:
                i0.append(a[0])
                i1.append(a[1])
                outs.append(a[2])
                ids.append(a[3])
            dd = (np.array(i0), np.array(i1), np.array(outs), ids)
            pre_data.append(dd)

        return pre_data

    def prepare_evt(self, rd=True, multi=1, rdd=True):
        pre_data = []
        if rdd:
            self.reshuffle_data()
        self.id = 0
        for d in self.data:
            data = self.create_bucket_evt(d, multi)
            if rd:
                np.random.shuffle(data)
            ins = []
            outs = []
            ids = []
            for ds in data:
                for a in ds:
                    if self.net_type == 'fc':
                        ins.append(a[0])
                    elif self.net_type == 'cnn':
                        ins.append(a[0].reshape(((self.nPar + self.nAdd), self.att,1)))
                    else:
                        raise Exception()
                    outs.append(a[1]*self.t_scale[self.num_output1:self.num_output])
                    ids.append(a[2])
            dd = (np.array(ins), np.array(outs), ids)
            pre_data.append(dd)

        return pre_data

    def updates(self, truth, ids):
        l1 = len(ids)
        l2 = len(ids[0])
        # sz = ids[0].shape
        # key = self.rasd.features.keys()[0]
        for a in range(l1):
            ii = ids[a]
            for b in range(l2-self.out_offset):
                tr =truth[a, b]
                id = ii[b+self.out_offset]
                im1 = id[0][0]
                im2 = id[0][1]
                key = id[0][2]
                ip1 = id[1]
                ip2 = id[2]
                self.rasd.features[key][im1][1][ip1] = tr[:self.fc_Nout]
                self.rasd.features[key][im2][1][ip2] = tr[self.fc_Nout:]
                if key == 1 and im1 == 100 and ip1<3:
                    print('update', ip1, tr[:self.fc_Nout][0])
                if key == 1 and im2 == 100 and ip2<3:
                    print('update', ip2, tr[self.fc_Nout:][0])

    def prepare_ras(self, multi=1, rd=True):
        pre_data = []
        self.id = 0
        for id in self.rasd.matches:
            pre_data += self.create_ras_bucket(id, multi)
        if rd:
            np.random.shuffle(pre_data)
        f = []
        t = []
        id = []
        for b in pre_data:
            f.append(b[0])
            t.append(b[1])
            id.append(b[2])

            #if len(f)>10000:
            #    break

        return np.array(f), np.array(t), id

    def prepare(self, rd=True, multi=1, rdd=True):
        pre_data = []
        if rdd:
            self.reshuffle_data()
        self.id = 0
        #for id in self.data:
        # d = self.data[id]
        data = self.create_bucket(multi)
        if rd:
            np.random.shuffle(data)
        ins = []
        outs = []
        #ids = []
        imgs = []
        for a in data:
            if self.net_type == 'fc':
                ins.append(a[0])
            elif self.net_type == 'cnn':
                ins.append(a[0].reshape(((self.nPar + self.nAdd), self.att,1)))
            else:
                raise Exception()
            outs.append(a[1])

            imgs.append(a[2])
        dd = (np.array(ins), np.array(outs), imgs)
        pre_data.append(dd)

        return pre_data

    def prepare_h(self, rd=True, rdd=True, multi=1):
        if rdd:
            self.reshuffle_data()
        self.id = 0

        data = self.create_bucket_h(multi)
        if rd:
            np.random.shuffle(data)

        return data

    def create_stage_data(self, data):
        multi = 10
        f2 = 1
        N1 = self.nPar
        N2 = int(self.nPar*f2)
        length = multi*(N1+N2)
        outputs = []
        for d in data:
            input = d[0]
            while len(input) < length:
                input = np.concatenate((input, input))

            input = input[:length]
            for m in range(multi):
                start = m*(N1+N2)
                i1 = input[start:start+N1].reshape(N1 * self.sz[1])
                i2 = input[start+N1:start+N1+N2]
                truth = d[1][:self.num_output]
                output = (i1, i2,  truth.reshape(self.num_output), self.id)
                outputs.append(output)

        self.id += 1

        return outputs

    def avg_correction(self, avg_file):
        print('Reading average file', avg_file)
        with open(avg_file, 'rb') as fp:
            A = pickle.load(fp)
        av = A[0]
        st = A[1]
        for id in self.data:
            data = self.data[id]
            for a in range(len(data[0])):
                self.data[id][0][a] -= av
                self.data[id][0][a] /= st
        #self.rasd.matches=None
        #self.rasd.features=None
        # self.rasd.poses=None

    def avg_correction2(self, avg_file):
        self.data = None
        print('Reading average file', avg_file)
        with open(avg_file, 'r') as fp:
            A = cPickle.load(fp)
        av = A[0]
        st = A[1]
        for id in self.rasd.features:
            features = self.rasd.features[id]
            for img_id in features:
                features[img_id][0] -= av
                features[img_id][0] /= st

    def create_bucket_evt(self, data, multi):

        outputs = []

        sz_in = data[0][0].shape

        for d in data:
            bucket = []
            input = d[0]
            if multi > 0:
                num = multi  # *int(np.ceil(len(input)/float(self.nPar)))
            else:
                num = int(np.ceil(len(input) / float(self.nPar + self.nAdd))*abs(multi))
            length = num * (self.nPar + self.nAdd)

            while len(input) < length:
                input = np.concatenate((input, input))
            input = input[:length]
            for a in range(0, len(input), self.nPar+self.nAdd):
                it = input[a:a + self.nPar+self.nAdd]
                #truth = d[1][:self.num_output]
                truth = d[1][self.num_output1:self.num_output]
                Nout = self.num_output - self.num_output1
                output = (it.reshape((self.nPar+self.nAdd) * sz_in[1]),
                          truth.reshape(Nout), self.id)
                bucket.append(output)
            outputs.append(bucket)
            self.id += 1

        return outputs

    def create_ras_bucket(self, id, multi=-1):
        output = []
        nm = 0
        matches = self.rasd.matches[id]
        features = self.rasd.features[id]
        poses = self.rasd.poses[id]
        for ids in matches:

            im1 = ids[0]
            im2 = ids[1]

            p1 = poses[im1]
            p2 = poses[im2]

            A = Utils.get_relative(p1, p2)
            A = A * self.t_scale[:3]
            ms = matches[ids]
            random.shuffle(ms)
            nm += len(ms)

            if multi > 0:
                num = multi  # *int(np.ceil(len(input)/float(self.nPar)))
            else:
                num = int(np.ceil(len(ms) / float(self.nPar + self.nAdd))*abs(multi))
            length = num * (self.nPar + self.nAdd)

            while len(ms) < length:
                ms += ms
            ms = ms[:length]

            for a in range(0, len(ms), self.nPar+self.nAdd):
                it = ms[a:a + self.nPar+self.nAdd]

                ins = []
                trs = []
                id_list = []
                for m in it:
                    p1 = m[0]
                    p2 = m[1]
                    # print im1,im2,p1,p2
                    f1 = features[im1][0][p1]
                    f2 = features[im2][0][p2]
                    if features[im1][1] is None:
                        t1 = None
                        t2 = None
                    else:
                        t1 = features[im1][1][p1]
                        t2 = features[im2][1][p2]
                    ins.append(np.concatenate((f1[:2],f2[:2])))
                    if self.fc_Nout>0:
                        trs.append(np.concatenate((t1,t2)))
                    else:
                        trs.append(A)
                    id_list.append(((ids[0], ids[1], id), p1, p2))
                output.append((ins, trs, id_list))
        # print nm
        return output

    def create_bucket(self, multi):

        outputs = []
        for id in self.data:
            sz_in = self.data[id][0][0].shape[0]
            break
        t_scale = self.t_scale

        for id in self.data:
            input = self.data[id][0]
            truth = self.data[id][1]
            cv_val = self.data[id][2]
            n = np.linalg.norm(truth-cv_val)
            if n > 20:
                continue

            truth *= t_scale[:3]
            cv_val *= t_scale[:3]
            # att = len(input[0]) + len(truth)
            if multi > 0:
                num = multi  # *int(np.ceil(len(input)/float(self.nPar)))
            else:
                num = int(np.ceil(len(input) / float(self.nPar + self.nAdd))*abs(multi))
            length = num * (self.nPar + self.nAdd)

            while len(input) < length:
                input = np.concatenate((input, input))
            input = input[:length]
            for a in range(0, len(input), self.nPar+self.nAdd):
                it = np.array(input[a:a + self.nPar+self.nAdd])
                nt = it.shape[0]
                nt = np.repeat(cv_val.reshape(1,3), nt, axis=0)
                it = np.concatenate((it, nt), axis=1)
                output = (it.reshape((self.nPar+self.nAdd) * (sz_in+3)), truth-cv_val, id)
                outputs.append(output)
        return outputs

    def create_bucket_h(self, multi=1):

        outputs = []
        # for id in self.data:
        #     sz_in = self.data[id][0][0].shape[0]
        #     break

        for id in self.data:
            input = self.data[id][0]
            while len(input) < (self.nPar + self.out_offset)*multi:
                input = np.concatenate((input, input))

            input = input[:(self.nPar + self.out_offset)*multi]


            truth = self.data[id][1]

            for a in range(multi):
                start = a * (self.nPar + self.out_offset)
                input1 = input[start:start+self.out_offset]
                input2 = input[start+self.out_offset:start+self.out_offset+self.nPar]

                output = (input1, input2, truth, id)
                outputs.append(output)
        return outputs

    def create_bucket_cnn(self, data):
        outputs = []
        inputs = []
        for id in data:
            sz_in = data[id][0].shape
            break

        for d in data:
            input = d[0]
            while len(input) < self.nPar:
                input = np.concatenate((input, input))
            input = input[:self.nPar]
            truth = d[1][:self.num_output]
            inputs.append(input.reshape((self.nPar, sz_in[1], 1)))
            outputs.append(truth.reshape(self.num_output))

        return inputs, outputs

    def reshuffle_data(self):
        # from multiprocessing.pool import ThreadPool
        # import multiprocessing

        # pool = ThreadPool(multiprocessing.cpu_count() - 2)
        # pool.map(_reshuffle_b, self.data)
        # pool.close()
        # pool.join()

        Utils.reshuffle_b(self.data)

    def prepare_slow(self):
        pre_data = []
        for a in range(len(self.data)):
            data_gen = self.gen_data(self.nPar)
            sz_in = self.data[0][0][0].shape
            inputs = []
            outputs = []
            self.bucket = a
            while True:
                input_p, output_p = next(data_gen, (None, None))
                if input_p is None:
                    break
                inputs.append(input_p.reshape(self.nPar * sz_in[1]))
                outputs.append(output_p.reshape(self.num_output))

            pre_data.append((inputs, outputs))

        self.bucket = len(pre_data)
        return pre_data

    def gen_data(self, nPar):
        # np.random.seed()
        indices = range(len(self.data[self.bucket]))

        for a in indices:
            input0 = []
            while nPar > len(input0):
                input = self.data[self.bucket][a][0]
                np.random.shuffle(input)
                if len(input0) == 0:
                    if nPar < len(input):
                        input0 = input[:nPar]
                    else:
                        input0 = input
                else:
                    if len(input) + len(input0) > nPar:
                        dl = nPar - len(input0)
                        input0 = np.concatenate((input0, input[:dl, :]))
                    else:
                        input0 = np.concatenate((input0, input))

            output = self.data[self.bucket][a][1][:self.num_output]
            yield input0, output

    def q_fun(self, id, rst_dict):
        rst_dict[id] = self.prepare()

    def set_A_T(self, rst):
        #if len(self.data) != rst.shape[0]:
        #    raise Exception('Wrong number')
        self.rst = rst

    def save_data_2(self, name):
        for id in self.data:
            data = self.data[id]

    def prepare2(self, rd=True):
        data_gen = self.gen_data(rd)
        sz_in = self.data[0][0].shape
        pre_data = []

        while True:
            inputs = []
            outputs = []
            done = False
            for _ in range(self.batch_size):
                input_p, output_p = next(data_gen, (None, _))
                if input_p is None:
                    done = True
                    break
                inputs.append(input_p.reshape(sz_in[0], sz_in[1], 1))
                outputs.append(output_p.reshape(2))

            if len(inputs) > 0:
                pre_data.append((inputs, outputs))
            if done:
                break
        # print 'bucket', len(self.pre_data)
        self.bucket = len(pre_data)
        return pre_data


if __name__ == '__main__':
    range2 = 1
    range3 = -range2

    read_time = False
    key = '02'
    mode = 'Test'
    # key = 'rgbd_dataset_freiburg3_nostructure_texture_near_withloop'
    # mode = 'Test'
    #key = 'rgbd_dataset_freiburg3_long_office_household'
    #mode = 'Train'

    if len(sys.argv)>1:
        key = sys.argv[1]
    if len(sys.argv)>2:
        mode = sys.argv[2]
    if len(sys.argv)>3:
        read_time = True

    print(key, mode, range2, range3)

        # location = '/home/weihao/Projects/cambridge/OldHospital'
        # pose_file = 'dataset_train.txt'
        # poses_dic, cam = load_cambridge_poses(location, pose_file)

    if key.startswith('0'):
        location = '{}/datasets/kitti'.format(HOME)
        poses_dic, cam = load_kitti_poses(location, key)
        key = 'kitti_{}'.format(key)
    elif key.startswith('rgbd'):
        location = '{}/datasets/TUM'.format(HOME)
        poses_dic, cam = load_TUM_poses(location, key)
    else:
        location = "{}/datasets/indoors/{}".format(HOME, key)  # office" #heads
        poses_dic, cam = load_indoor_7_poses(location, "{}Split.txt".format(mode))

    if read_time:
        for id in poses_dic:
            time_table_file = location + '/sequences/' + id + '/times.txt'
            time_table = np.loadtxt(time_table_file)
            poses = poses_dic[id]
            print(len(poses), len(time_table))

    filename = '{}/p_files/{}_{}_ras_s{}_3.p'.format(HOME, key, mode, range2)
    output_file = '{}/tmp/{}_{}.csv'.format(HOME, key, mode)
    print(location)
    print(filename)
    print(output_file)

    rasd = RAS_D()

    rasd.set_poses(poses_dic, cam)
    rasd.process(range2, range3)
    rasd.clear()
    with open(filename, 'wb') as fp:
        pickle.dump(rasd, fp)
