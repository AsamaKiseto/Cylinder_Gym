import sys
sys.path.append("..")
sys.path.append("../env")

from env.Cylinder_Rotation_Env import Cylinder_Rotation_Env
import numpy as np
import matplotlib.pyplot as plt 
import torch
from fenics import * 
from timeit import default_timer

import argparse

def get_args(argv=None):
    parser = argparse.ArgumentParser(description='Put your hyperparameters')
    
    parser.add_argument('--N0', default=100, type=int, help='number of data set')
    parser.add_argument('--phase', default=1, type=int, help='mode of phase for data')

    return parser.parse_args(argv)

# env init
env = Cylinder_Rotation_Env(params={'dtr': 0.01, 'T': 1, 'rho_0': 1, 'mu' : 1/1000,
                                    'traj_max_T': 20, 'dimx': 128, 'dimy': 64,
                                    'min_x' : 0,  'max_x' : 2.2, 
                                    'min_y' : 0,  'max_y' : 0.41, 
                                    'r' : 0.05,  'center':(0.2, 0.2),
                                    'min_w': -1, 'max_w': 1,
                                    'min_velocity': -1, 'max_velocity': 1,
                                    'U_max': 1.5, })

if __name__ == '__main__':
    print('start')
    # argparser
    args = get_args()
    
    # env params
    print(env.params)

    # param setting
    phase = args.phase
    N0 = args.N0     # N0 set of data
    if phase == 2:
        N0 = 1
    dt = env.params['dtr'] * env.params['T']
    nT = 4 // dt
    nx = env.params['dimx']
    ny = env.params['dimy']
    print(f'dt: {dt} | nt: {nT}')

    # data generate
    obs = np.zeros((N0, nT+1, nx, ny, 3))
    print(f'state_data_size :{obs.shape}')
    C_D, C_L, reward = np.zeros((N0, nT)), np.zeros((N0, nT)), np.zeros((N0, nT))
    ang_vel = 3 * (2 * np.random.rand(N0, nT) - 1)
    for k in range(N0):
        start = default_timer()
        obs[k, 0] = env.reset()
        
        ang_v = ang_vel[k]
        for i in range(nT):
            obs[k, i+1], reward[k, i], C_D[k, i], C_L[k, i] = env.step(ang_v[i])
        
        end = default_timer()

        print(f'# {k} | time: {end-start}')
        # print(f'ang_vel: {ang_v}')
        # print(f'reward :{reward[k]}')

    # np to tensor
    obs_tensor = torch.Tensor(obs)
    reward_tensor = torch.Tensor(reward)
    C_D_tensor = torch.Tensor(C_D)
    C_L_tensor = torch.Tensor(C_L)
    ang_vel_tensor = torch.Tensor(ang_vel)

    data = [obs_tensor, reward_tensor, C_D_tensor, C_L_tensor, ang_vel_tensor]

    # save data
    if phase==1:
        torch.save(data, './data/nse_data_N0_{}_nT_{}'.format(N0, nT))
    elif phase==2:
        torch.save(data, './data/nse_control_samples')
    