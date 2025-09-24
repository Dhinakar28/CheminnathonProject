# Quick programmatic runner for the train pipeline to ensure artifacts are created and prints appear
from types import SimpleNamespace
from src import train
import os

args = SimpleNamespace()
args.file = os.path.join('data','raw','ai4i2020.csv')
args.target = 'Air temperature'
args.outdir = 'models_quick'
args.test_size = 0.2
args.n_estimators = 10
args.n_jobs = 1

if __name__ == '__main__':
    print('Starting programmatic train runner...')
    train.train(args)
    print('\nContents of outdir:')
    for root, dirs, files in os.walk(args.outdir):
        for f in files:
            print(os.path.join(root, f))
    print('Done')
