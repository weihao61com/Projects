from scipy import stats
from matplotlib.figure import figaspect
import matplotlib.pyplot as plt
import numpy as np
import sys

filename = '/home/weihao/tmp/r.txt'
if sys.platform=='darwin':
    filename = '/Users/weihao/tmp/r.txt'

def p_fit(x, y):
    v = np.polyfit(x, y, 2)
    return v

w, h = figaspect(0.5)
fig = plt.figure(figsize=(w, h))
usecols = (1,9,10,11,12,13,14)
if len(sys.argv)>1:
    usecols = map(int, sys.argv[1].split(','))

if len(sys.argv)>2:
    filename = sys.argv[2]

da = np.loadtxt(filename, usecols=usecols)

print 'max', max(da[:, 0])

zone = len(usecols) - 1

r = int(np.ceil(np.sqrt(zone)))
c = int(np.ceil(zone/float(r)))

#da[:, 0] = da[:, 0] - max(da[:, 0])
mx = max(da[:, 0])

#print da
for a in range(zone):
    length = int(len(da)/2)
    v = p_fit(da[length:, 0], da[length:, a+1])
    pre1 = v[0] * da[:, 0] *da[:, 0] + v[1] * da[:, 0] + v[2]

    ax1 = fig.add_subplot(c, r, a+1)
    ax1.scatter(da[:, 0], da[:, a+1],  color='black', s=5)
    ax1.plot(da[:, 0], pre1, color='blue', linewidth=2)
    #ymin = np.min(da[:, a+1])
    #ymax = np.max(da[:, a+1])
    #ax1.set_ylim([ymin, ymax])

    #
    # slope1, intercept1, r_value, p_value, std_err = stats.linregress(da[:, 0], da[:, 2])
    # pre2 = da[:, 0] *slope1 + intercept1
    #
    # ax1 = fig.add_subplot(1, 2, 2)
    # ax1.scatter(da[:, 0], da[:, 2],  color='black')
    # ax1.plot(da[:, 0], pre2, color='blue', linewidth=3)

    print v, pre1[-1], -v[1]/2/v[0], v[2]-v[1]*v[1]/4/v[0], 'k=', 2*mx*v[0]+v[1]
#print slope1, intercept1
#print pre1[-1], pre2[-1]
plt.show()