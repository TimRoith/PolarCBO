import numpy as np
import csv
import os
import multiprocessing as mp
from contextlib import closing
import time
import getopt

#%% custom imports
from inspect import getsourcefile
import os.path as path, sys
current_dir = path.dirname(path.abspath(getsourcefile(lambda:0)))
sys.path.insert(0, current_dir[:current_dir.rfind(path.sep)])

import optimizers as op
import test_functions as tf
import utils as ut

#%%
cur_path = os.path.dirname(os.path.realpath(__file__))

#%% set parameters
conf = ut.config()
conf.num_steps = 100
conf.tau=0.01
conf.x_max =7
conf.x_min = -7
conf.random_seed = 309
conf.d = 2
conf.beta=1.0
conf.sigma=1.0
conf.kappa = 0.5
conf.heavy_correction = False
conf.num_particles = 300
conf.factor = 1.0
conf.noise = ut.normal_noise(tau=conf.tau)
conf.eta = 0.5
conf.num_cores = 8
conf.num_runs = 3

# target function
z = np.array([[-2,0],[3,1],[-4,-2]])
alphas = np.array([1,1,1])
conf.V = tf.Ackley_multimodal(alpha=alphas,z=z)
conf.minima = conf.V.minima

#%%
try:
    opts, args = getopt.getopt(sys.argv[1:],
                               "k:n:d:r:s:pc:v",
                               ["kappa=","num_particles=","dimension=", 
                                "num_runs=", "num_steps=",
                                "parallel","num_cores=","verbose"])
except getopt.GetoptError:
    sys.exit(2)
for opt, arg in opts:
    if opt in ("-k", "--kappa"):
        conf.kappa = float(arg)
    elif opt in ("-n", "--num_particles"):
        conf.num_particles = int(arg)
    elif opt in ("-r", "--num_runs"):
        conf.num_runs = int(arg)
    elif opt in ("-s", "--num_steps"):
            conf.num_steps = int(arg)
    elif opt in ("-p", "--parallel"):
        parallel = True
    elif opt in ("-c", "--num_cores"):
        conf.num_cores = int(arg)

#%%
def run(num_run):
    np.random.seed(seed=num_run**4)
    x = ut.init_particles(num_particles=conf.num_particles, d=conf.d,\
                               x_min=conf.x_min, x_max=conf.x_max)
        
    opt = op.KernelCBO(x, conf.V, conf.noise, sigma=conf.sigma, tau=conf.tau,\
                       kernel=ut.Gaussian_kernel(kappa=conf.kappa))
    beta_sched = ut.beta_eff(opt, eta=conf.eta, factor=conf.factor)
    
    #%% main loop
    for i in range(conf.num_steps):
        # update step
        time = conf.tau*(i+1)
        opt.step(time=time)
        beta_sched.update()
        if i%100 == 0:
            print("Run: " + str(num_run) + " starts iteration: " + str(i), flush=True)
    
      
    for d in range(conf.d):
        mm = num_run*conf.d + d
        mp_arr[mm*conf.num_particles:(mm+1)*conf.num_particles] = opt.m_beta[:,d]

#%%
num_cores = min(mp.cpu_count(),conf.num_cores)

def init_arr(mp_arr_):
    global mp_arr
    mp_arr = mp_arr_

def main():    
    mp_arr = mp.Array('d', conf.num_runs * conf.num_particles * conf.d) # shared, can be used from multiple processes
    pool = mp.Pool(num_cores, initializer=init_arr, initargs=(mp_arr,))
    
    with closing(pool):
        pool.imap_unordered(run, range(conf.num_runs))
    pool.close()
    pool.join()
    return mp_arr
    
if __name__ == '__main__':    
    arr = main()
    
    #%% set up csv file and save parameters
    time_str = time.strftime("%Y%m%d-%H%M%S")
    fname = "data/Ackley" + str(conf.d) + "d-kappa-" + str(conf.kappa) + "-" + "J-" + str(conf.num_particles) + "-" + time_str + '.csv'
    with open(fname, 'w') as f:
        writer = csv.writer(f, lineterminator = '\n')
        conf_vars = vars(conf)
        for p in conf_vars:
            var = conf_vars[p]
            if isinstance(var, np.ndarray):
                for i in range(var.shape[0]):
                    writer.writerow([p] + list(var[i,:]))
            else:
                writer.writerow([p, str(var)])
            
        for num_run in range(conf.num_runs):
            for d in range(conf.d):
                mm = num_run * conf.d + d
                row = arr[mm*conf.num_particles:((mm+1)*conf.num_particles)]
                row = [num_run] + list(row)
                writer.writerow(row)