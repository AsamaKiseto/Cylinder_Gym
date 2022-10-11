import numpy as np
import matplotlib.pyplot as plt 
import torch

from scripts.models import *
from scripts.nse_model import *
from scripts.utils import *
from scripts.draw_utils import *

dt = 0.01
tg = 5
nt = 80
t_nn = (np.arange(nt) + 1) * 0.01 * tg
t = (np.arange(nt * tg) + 1) * 0.01 

# ex_nums = ['data_based', 'baseline', 'pe_20', 'pe_30', 'pe_40', 'pe_50', 'weght1', 'weght2']
ex_nums = ['data_based', 'baseline', 'data_based_bn', 'baseline_bn']
scale = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
# label = ['data-based', 'phys-included']
n_model = len(ex_nums)

def calMean(data_list):
    ans = []
    for data in data_list:
        data = data.reshape(10, 10, -1).mean(1)
        ans.append(data)
    return ans
        

if __name__ == '__main__':
    # load test data
    data_path = 'data/test_data/nse_data_reg_dt_0.01_fb_0.0'
    # data_path = 'data/nse_data_reg_dt_0.01_fr_1.0'

    # data_path = 'data/nse_data_reg'
    print('load data')
    data = LoadData(data_path)
    data.split(1, tg)
    N0, nt, nx, ny = data.get_params()
    print('load data finished')

    print(N0, nt, nx, ny)
    shape = [nx, ny]

    for k in range(n_model):
        operator_path = 'logs/phase1_' + ex_nums[k] + '_grid_pi'
        model = LoadModel(operator_path, shape)
        data.normalize('logs_unif', model.data_norm)
        print(model.data_norm)
        obs, Cd, Cl, ctr = data.get_data()
        in_nn = obs[:, 0]
        
        error_1step, Lpde_obs, Lpde_pred = torch.zeros(N0, nt), torch.zeros(N0, nt), torch.zeros(N0, nt) 
        error_cul, Lpde_pred_cul = torch.zeros(N0, nt), torch.zeros(N0, nt)
        
        model.set_init(in_nn)

        error_1step, Lpde_obs, Lpde_pred = model.cal_1step(obs, Cd, Cl, ctr)
        error_cul, Lpde_pred_cul = model.process(obs, Cd, Cl, ctr)
        # print(f'Lpde_nn: {Lpde_pred_cul[-1]}')
        
        print(f'error_1step: {error_1step[0]}')
        print(f'error_cul: {error_cul[0]}')
        # print(f'Lpde_obs: {Lpde_obs[-1]}')
        # print(f'Lpde_pred: {Lpde_pred[-1]}')

        data.unnormalize()
        log_data = [error_1step, Lpde_obs, Lpde_pred, error_cul, Lpde_pred_cul]
        torch.save(log_data, 'logs/phase1_test_' + ex_nums[k])

    for k in range(n_model):
        # fig setting
        fig, ax = plt.subplots(nrows=4, ncols=2, figsize=(15,12), dpi=1000)
        ax = ax.flatten()
        for i in range(4):
            ax[i] = plt.subplot2grid((4, 2), (i, 0), colspan=2)
            ax[i].grid(True, lw=0.4, ls="--", c=".50")
            ax[i].set_xlim(0, nt * tg * dt)
            ax[i].set_yscale('log')
            
        ax[0].set_title("Error/Loss in Different Scales", fontsize=15)
        ax[0].set_ylabel("One-step data loss", fontsize=15)
        ax[1].set_ylabel("Cumul data loss", fontsize=15)
        ax[2].set_ylabel("phys loss of obs", fontsize=15)
        ax[3].set_ylabel("phys loss of pred", fontsize=15)
        ax[3].set_xlabel("t", fontsize=15)
        
        log_path = 'logs/phase1_test_' + ex_nums[k]
        data_list = torch.load(log_path)
        error_1step, Lpde_obs, Lpde_pred, error_cul, Lpde_pred_cul = calMean(data_list)
        
        for i in range(10):
            ax[0].plot(t_nn, error_1step[i], label=scale[i])
            ax[1].plot(t_nn, error_cul[i], label=scale[i])
            ax[2].plot(t_nn, Lpde_obs[i], label=scale[i])
            ax[3].plot(t_nn, Lpde_pred[i], label=scale[i])

        for i in range(4):
            ax[i].legend()

        plt.savefig(f'logs/pics/coef_phase1_{ex_nums[k]}.jpg')
        