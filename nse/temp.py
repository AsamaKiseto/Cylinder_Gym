import sys
sys.path.append("..")
sys.path.append("../env")

from env.Cylinder_Rotation_Env import Cylinder_Rotation_Env
import numpy as np
import torch
from timeit import default_timer

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from fenics import plot

# env init
env = Cylinder_Rotation_Env(params={'dtr': 1, 'T': 0.01, 'rho_0': 1, 'mu' : 1/1000,
                                    'traj_max_T': 20, 'dimx': 128, 'dimy': 64,
                                    'min_x' : 0,  'max_x' : 2.2, 
                                    'min_y' : 0,  'max_y' : 0.41, 
                                    'r' : 0.05,  'center':(0.2, 0.2),
                                    'min_w': -1, 'max_w': 1,
                                    'min_velocity': -1, 'max_velocity': 1,
                                    'U_max': 1.5, })

print(env.params)

# env params
dT = env.params['T']
nx = env.params['dimx']
ny = env.params['dimy']
print('dT: {}, nx: {}, ny: {}'.format(dT, nx, ny))
nT = 400

logs = torch.load("logs/control_ol")
f = logs["f_optim"][0]
f = f.to(torch.device('cpu')).detach().numpy()
obs = np.zeros(( nT+1, nx, ny, 5))
C_D, C_L = np.zeros(nT), np.zeros(nT)

obs[0] = env.reset()
for t in range(nT):
    obs[t], _, C_D[t], C_D[t] = env.step(f[t//20])

# np to tensor
obs_tensor = torch.Tensor(obs)
C_D_tensor = torch.Tensor(C_D)
C_L_tensor = torch.Tensor(C_L)
f_tensor = torch.Tensor(f)

data = [obs_tensor, C_D_tensor, C_L_tensor, f]

# save data
torch.save(data, './data/nse_data_control_test')