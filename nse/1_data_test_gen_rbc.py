import sys
sys.path.append("..")
sys.path.append("../env")

import numpy as np
from os import path
import math

import torch
from timeit import default_timer
import math
import torch.nn as nn
from env.RBC_env import RBC

simulator = RBC()

N0 = 30
nx = simulator.params['dimx']
ny = simulator.params['dimy']
dt = simulator.params['dt']
nt = int(1 // dt) + 2
print(f'N0: {N0}, nt: {nt}, nx: {nx}, ny: {ny}')

temp , velo , p = np.zeros((N0, nt, nx, ny)), np.zeros((N0, nt, nx, ny, 2)), np.zeros((N0, nt, nx, ny))
ctr1 = np.random.rand(int(N0//3)) * 2 + 1
# ctr1 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 2
# ctr2 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 4
# ctr3 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 6
ctr1 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 2
ctr2 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 3
ctr3 = (2 * np.random.rand(int(N0//3)) - 1) * 0.5 + 4
ctr = np.concatenate([ctr1, ctr2, ctr3])

N0 = 1
ctr = np.array([0.0])
temp , velo , p = np.zeros((N0, nt, ny, nx)), np.zeros((N0, nt, ny, nx, 2)), np.zeros((N0, nt, ny, nx))

for k in range(N0):
    print(f'start # {k}')
    t1 = default_timer()
    simulator.reset(ctr[k], const=1.0)

    for init_i in range(2):
        simulator.step()

    for i in range(nt):
        temp[k, i], velo[k, i], p[k, i], _  = simulator.step()

    t2 = default_timer()
    print(f'# {k} finish | {t2 - t1}')

temp = torch.Tensor(temp).unsqueeze(-1)
velo = torch.Tensor(velo)
p = torch.Tensor(p).unsqueeze(-1)
ctr = torch.Tensor(ctr).reshape(N0, 1).repeat(1, nt)

obs = torch.cat((velo, p), dim=-1)

data = [obs, temp , ctr]
torch.save(data, 'data/test_data/rbc_test')