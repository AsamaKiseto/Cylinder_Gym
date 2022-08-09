from multiprocessing import reduction
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.utils.data.dataset import random_split
from timeit import default_timer
import sys

import argparse

from models import *
from utils import *

def get_args(argv=None):
    parser = argparse.ArgumentParser(description = 'Put your hyperparameters')

    parser.add_argument('--name', default='nse_operator_fno_test', type=str, help='experiments name')
    
    parser.add_argument('--L', default=2, type=int, help='the number of layers')
    parser.add_argument('--modes', default=16, type=int, help='the number of modes of Fourier layer')
    parser.add_argument('--width', default=32, type=int, help='the number of width of FNO layer')
    
    parser.add_argument('--batch_size', default=64, type=int, help = 'batch size')
    parser.add_argument('--epochs', default=1000, type=int, help = 'Number of Epochs')
    parser.add_argument('--lr', default=1e-3, type=float, help='learning rate')
    parser.add_argument('--wd', default=1e-4, type=float, help='weight decay')
    parser.add_argument('--step_size', default=200, type=int, help='scheduler step size')
    parser.add_argument('--gamma', default=0.5, type=float, help='scheduler factor')
    parser.add_argument('--gpu', default=0, type=int, help='device number')

    parser.add_argument('--tg', default=20, type=int, help = 'time gap')
    parser.add_argument('--Ng', default=1, type=int, help = 'N gap')
    parser.add_argument('--lambda1', default=1, type=float, help='weight of losses1')
    parser.add_argument('--lambda2', default=0.1, type=float, help='weight of losses2')
    parser.add_argument('--lambda3', default=0.01, type=float, help='weight of losses3')
    parser.add_argument('--lambda4', default=0.1, type=float, help='weight of losses4')
    parser.add_argument('--f_channels', default=4, type=int, help='channels of f encode')
    
    return parser.parse_args(argv)

if __name__=='__main__':
    # args parser
    args = get_args()
    print(args)
    
    # param setting
    device = torch.device('cuda:{}'.format(args.gpu) if torch.cuda.is_available() else 'cpu')
    
    model_params = dict()
    model_params['modes'] = args.modes
    model_params['width'] = args.width
    model_params['L'] = args.L
    
    epochs = args.epochs
    batch_size = args.batch_size
    lr = args.lr
    wd = args.wd
    step_size = args.step_size
    gamma = args.gamma

    print(f'epochs: {epochs}, batch_size: {batch_size}, lr: {lr}, step_size: {step_size}, gamma: {gamma}')

    lambda1, lambda2, lambda3, lambda4 = args.lambda1, args.lambda2, args.lambda3, args.lambda4
    f_channels = 4
    print(f'lambda: {lambda1}, {lambda2}, {lambda3}, {lambda4}, f_channels: {f_channels}')

    # logs
    logs = dict()

    logs['args'] = args
    logs['train_loss']=[]
    logs['train_loss_f_t_rec']=[]
    logs['train_loss_u_t_rec']=[]
    logs['train_loss_trans']=[]
    logs['train_loss_trans_latent']=[]

    logs['test_loss']=[]
    logs['test_loss_f_t_rec']=[]
    logs['test_loss_u_t_rec']=[]
    logs['test_loss_trans']=[]
    logs['test_loss_trans_latent']=[]
    logs_fname = './logs/operator_lambda_{}_{}_{}_{}_lr_{}_epochs_{}'.format(lambda1, lambda2, lambda3, lambda4, lr, epochs)
        
    # load data
    data, _, Cd, Cl, ang_vel = torch.load('data/nse_data_N0_256_nT_400')
    tg = args.tg     # sample evrey 20 timestamps
    Ng = args.Ng
    data = data[::Ng, ::tg, :, :, 2:]  
    Cd = Cd[::Ng, ::tg]
    Cl = Cl[::Ng, ::tg]
    ang_vel = ang_vel[::Ng, ::tg]

    # data param
    nx = data.shape[2] 
    ny = data.shape[3]
    s = data.shape[2] * data.shape[3]     # nx * ny
    N0 = data.shape[0]                    # num of data sets
    nt = data.shape[1] - 1                # nt
    
    data = data[:, :nt+1, :, :]
    Cd = Cd[:, :nt]
    Cl = Cl[:, :nt]
    ang_vel = ang_vel[:, :nt]
    Ndata = N0 * nt
    
    print('N0: {}, nt: {}, nx: {}, ny: {}, device: {}'.format(N0, nt, nx, ny, device))
    
    class NSE_Dataset(Dataset):
        def __init__(self, data, Cd, Cl, ang_vel):
            Cd = Cd.reshape(N0, nt, 1, 1, 1).repeat([1, 1, nx, ny, 1]).reshape(-1, nx, ny, 1)
            Cl = Cl.reshape(N0, nt, 1, 1, 1).repeat([1, 1, nx, ny, 1]).reshape(-1, nx, ny, 1)
            ang_vel = ang_vel.reshape(N0, nt, 1, 1, 1).repeat([1, 1, nx, ny, 1]).reshape(-1, nx, ny, 1)
            input_data = data[:, :-1].reshape(-1, nx, ny, 3)
            output_data = data[:, 1:].reshape(-1, nx, ny, 3)

            self.input_data = torch.cat((input_data, ang_vel), dim=-1)
            self.output_data = torch.cat((output_data, Cd, Cl), dim=-1)
            
        def __len__(self):
            return Ndata

        def __getitem__(self, idx):
            x = torch.FloatTensor(self.input_data[idx])
            y = torch.FloatTensor(self.output_data[idx])
            return x, y

    NSE_data = NSE_Dataset(data, Cd, Cl, ang_vel)
    train_data, test_data = random_split(NSE_data, [int(0.8 * Ndata), int(0.2 * Ndata)])
    train_loader = DataLoader(dataset=train_data, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(dataset=test_data, batch_size=batch_size, shuffle=False)
    
    # model setting
    shape = [nx, ny]
    model = FNO_ensemble(model_params, shape, f_channels=f_channels).to(device)
    params_num = count_params(model)
    print(f'param numbers of the model: {params_num}')
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=wd)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=step_size, gamma=gamma)

    for epoch in range(1, epochs+1):
        model.train()
        
        t1 = default_timer()
        train_loss = AverageMeter()
        train_loss1 = AverageMeter()
        train_loss2 = AverageMeter()
        train_loss3 = AverageMeter()
        train_loss4 = AverageMeter()
        test_loss = AverageMeter()
        test_loss1 = AverageMeter()
        test_loss2 = AverageMeter()
        test_loss3 = AverageMeter()
        test_loss4 = AverageMeter()

        for x_train, y_train in train_loader:
            x_train, y_train = x_train.to(device), y_train.to(device)
            
            optimizer.zero_grad()

            # split data read in train_loader
            in_train, f_train = x_train[:, :, :, :-1], x_train[:, 0, 0, -1]
            out_train, Cd_train, Cl_train = y_train[:, :, :, :-2], y_train[:, 0, 0, -2], y_train[:, 0, 0, -1]
            # put data into model
            pred, x_rec, f_rec, trans_out = model(in_train, f_train)
            out_latent = model.stat_en(out_train)
            in_rec = x_rec[:, :, :, :3]
            # prediction items
            out_pred = pred[:, :, :, :3]
            Cd_pred = torch.mean(pred[:, :, :, -2].reshape(batch_size, -1), 1)
            Cl_pred = torch.mean(pred[:, :, :, -1].reshape(batch_size, -1), 1)

            # loss1: prediction loss; loss2: rec loss of state
            # loss3: rec loss of f; loss4: latent loss
            loss1 = rel_error(out_pred, out_train).mean()\
                    + rel_error(Cd_pred, Cd_train).mean()\
                    + rel_error(Cl_pred, Cl_train).mean()
            loss2 = rel_error(in_rec, in_train).mean()
            loss3 = rel_error(f_rec, f_train).mean()
            # loss3 = F.mse_loss(f_rec, f_train, reduction='mean')
            loss4 = rel_error(trans_out, out_latent).mean()
            loss = lambda1 * loss1 + lambda2 * loss2 + lambda3 * loss3 + lambda4 * loss4
            
            loss.backward()
            optimizer.step()

            train_loss.update(loss.item(), x_train.shape[0])
            train_loss1.update(loss1.item(), x_train.shape[0])
            train_loss2.update(loss2.item(), x_train.shape[0])
            train_loss3.update(loss3.item(), x_train.shape[0])
            train_loss4.update(loss4.item(), x_train.shape[0])
        
        logs['train_loss'].append(train_loss.avg)
        logs['train_loss_f_t_rec'].append(train_loss3.avg)
        logs['train_loss_u_t_rec'].append(train_loss2.avg)
        logs['train_loss_trans'].append(train_loss1.avg)
        logs['train_loss_trans_latent'].append(train_loss4.avg)
        
        scheduler.step()
        model.eval()

        with torch.no_grad():
            for x_test, y_test in test_loader:
                x_test, y_test = x_test.to(device), y_test.to(device)

                # split data read in test_loader
                in_test, f_test = x_test[:, :, :, :-1], x_test[:, 0, 0, -1]
                out_test, Cd_test, Cl_test = y_test[:, :, :, :-2], y_test[:, 0, 0, -2], y_test[:, 0, 0, -1]
                # put data into model
                pred, x_rec, f_rec, trans_out = model(in_test, f_test)
                out_latent = model.stat_en(out_test)
                in_rec = x_rec[:, :, :, :3]
                # prediction items
                out_pred = pred[:, :, :, :3]
                Cd_pred = torch.mean(pred[:, :, :, 3].reshape(batch_size, -1), 1)
                Cl_pred = torch.mean(pred[:, :, :, 4].reshape(batch_size, -1), 1)
                loss1 = rel_error(out_pred, out_test).mean()\
                        + rel_error(Cd_pred, Cd_test).mean()\
                        + rel_error(Cl_pred, Cl_test).mean()
                loss2 = rel_error(in_rec, in_test).mean()
                loss3 = rel_error(f_rec, f_test).mean()
                loss4 = rel_error(trans_out, out_latent).mean()
                loss = loss1 + lambda1 * loss2 + lambda2 * loss3 + lambda3 * loss4

                test_loss.update(loss.item(), x_test.shape[0])
                test_loss1.update(loss1.item(), x_test.shape[0])
                test_loss2.update(loss2.item(), x_test.shape[0])
                test_loss3.update(loss3.item(), x_test.shape[0])
                test_loss4.update(loss4.item(), x_test.shape[0])
            
            logs['test_loss'].append(test_loss.avg)
            logs['test_loss_f_t_rec'].append(test_loss3.avg)
            logs['test_loss_u_t_rec'].append(test_loss2.avg)
            logs['test_loss_trans'].append(test_loss1.avg)
            logs['test_loss_trans_latent'].append(test_loss4.avg)
                
        t2 = default_timer()

        print('# {} {:1.3f} | loss1: {:1.2e}  loss2: {:1.2e}  loss3: {:1.2e} loss4: {:1.2e} | loss1: {:1.2e} loss2: {:1.2e}  loss3: {:1.2e} loss4: {:1.2e}'
              .format(epoch, t2-t1, train_loss1.avg, train_loss2.avg, train_loss3.avg, train_loss4.avg, test_loss1.avg, test_loss2.avg, test_loss3.avg, test_loss4.avg))
        
    torch.save([model.state_dict(), logs], logs_fname)