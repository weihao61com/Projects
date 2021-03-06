from train_fft import extract_features
from L_fc import nn_fit
from train_fft_test import fft_test
from train_fft_refit import fft_refit
from train_fft_run import fft_run

config = 'config.json'

extract_features(config, 10)
nn_fit(config, False)
fft_test(config)
fft_refit(config)
#fft_run(config, '/Users/weihao/tmp/test')

