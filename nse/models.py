import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
    
#===========================================================================
# 2d fourier layers
#===========================================================================
class SpectralConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, modes1, modes2):
        super(SpectralConv2d, self).__init__()

        """
        2D Fourier layer. It does FFT, linear transform, and Inverse FFT.    
        """

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.modes1 = modes1    # Number of Fourier modes to multiply, at most floor(N/2) + 1
        self.modes2 = modes2

        self.scale = (1 / (in_channels * out_channels))
        self.weights1 = nn.Parameter(self.scale * torch.rand(in_channels, out_channels, self.modes1, self.modes2, dtype=torch.cfloat))
        self.weights2 = nn.Parameter(self.scale * torch.rand(in_channels, out_channels, self.modes1, self.modes2, dtype=torch.cfloat))

    # Complex multiplication
    def compl_mul2d(self, input, weights):
        # (batch, in_channel, x, y), (in_channel, out_channel, x, y) -> (batch, out_channel, x, y)
        return torch.einsum("bixt,ioxt->boxt", input, weights)

    def forward(self, x):
        batchsize = x.shape[0]
        #Compute Fourier coeffcients up to factor of e^(- something constant)
        x_ft = torch.fft.rfft2(x)

        # Multiply relevant Fourier modes
        out_ft = torch.zeros(batchsize, self.out_channels,  x.size(-2), x.size(-1)//2 + 1, dtype=torch.cfloat, device=x.device)
        out_ft[:, :, :self.modes1, :self.modes2] = \
            self.compl_mul2d(x_ft[:, :, :self.modes1, :self.modes2], self.weights1)
        out_ft[:, :, -self.modes1:, :self.modes2] = \
            self.compl_mul2d(x_ft[:, :, -self.modes1:, :self.modes2], self.weights2)

        #Return to physical space
        x = torch.fft.irfft2(out_ft, s=(x.size(-2), x.size(-1)))
        return x


class FNO_layer(nn.Module):
    def __init__(self, modes1, modes2, width, last=False):
        super(FNO_layer, self).__init__()
        """ ...
        """
        self.last = last

        self.conv = SpectralConv2d(width, width, modes1, modes2)
        self.w = nn.Conv2d(width, width, 1)
        # self.bn = torch.nn.BatchNorm2d(width)

    def forward(self, x):
        """ x: (batch, hidden_channels, dim_x, dim_t)"""

        x1 = self.conv(x)
        x2 = self.w(x)
        x = x1 + x2
        if not self.last:
            x = F.gelu(x)
            
        return x


class FNO(nn.Module):
    def __init__(self, modes1, modes2, width, L):
        super(FNO, self).__init__()

        """
        The overall network. It contains L layers of the Fourier layer.
        1. Lift the input to the desire channel dimension by self.fc0 .
        2. L layers of the integral operators u' = (W + K)(u).
            W defined by self.w; K defined by self.conv .
        3. Project from the channel space to the output space by self.fc1 and self.fc2 .
        """

        self.modes1 = modes1
        self.modes2 = modes2
        self.width = width
        self.L = L
        self.padding = 6
        self.fc0 = nn.Linear(4, self.width)       # input dim

        self.net = [ FNO_layer(modes1, modes2, width) for i in range(self.L-1) ]
        self.net += [ FNO_layer(modes1, modes2, width, last=True) ]
        self.net = nn.Sequential(*self.net)

        self.fc1 = nn.Linear(self.width, 128)
        self.fc2 = nn.Linear(128, 5)
        
        # self.fc3 = nn.Linear(ny*nx*3, 2)
        # self.fcC = C_net(activate=nn.ReLU(), num_hiddens=[ny*nx*3, 1024, 512, 64, 2])

    def forward(self, x):
        """ 
        - x: (batch, dim_x, dim_y, feature)
        """
        # y = self.fcC(x[:, :, :, :3].reshape(x.size()[0], -1))
        # grid = self.get_grid(x.shape, x.device)
        # x = torch.cat((x, grid), dim=-1)
        x = self.fc0(x)
        x = x.permute(0, 3, 1, 2)
        # x = F.pad(x, [0,self.padding]) # pad the domain if input is non-periodic

        x = self.net(x)

        # x = x[..., :-self.padding]
        x = x.permute(0, 2, 3, 1) # pad the domain if input is non-periodic
        x = self.fc1(x)
        x = F.gelu(x)
        # y = self.fc3(x.view(x.size()[0], -1))
        x = self.fc2(x)
        Cd = torch.mean(x[:, :, :, 3].reshape(x.shape[0], -1), 1)
        Cl = torch.mean(x[:, :, :, 4].reshape(x.shape[0], -1), 1)
        
        return x[:, :, :, :3], Cd, Cl

    def get_grid(self, shape, device):
        batchsize, size_x, size_t = shape[0], shape[1], shape[2]
        gridx = torch.tensor(np.linspace(0, 1, size_x), dtype=torch.float)
        gridx = gridx.reshape(1, size_x, 1, 1).repeat([batchsize, 1, size_t, 1])
        gridt = torch.tensor(np.linspace(0, 1, size_t), dtype=torch.float)
        gridt = gridt.reshape(1, 1, size_t, 1).repeat([batchsize, size_x, 1, 1])
        return torch.cat((gridx, gridt), dim=-1).to(device)      
    

class policy_net_cnn(nn.Module):
    def __init__(self):
        super(policy_net_cnn, self).__init__()
        width = 5
        self.nn = nn.Sequential(
            nn.Conv2d(3, 64, width, padding=2),
            nn.Tanh(),
            nn.Conv2d(64, 16, width, padding=2),
            nn.Tanh(),
            nn.Conv2d(16, 1, width, padding=2),
            # nn.Tanh()
        )

    def forward(self, x):
        # print(x.shape)
        x = x.permute(0, 3, 1, 2)
        x = self.nn(x).mean()
        # print(x.shape, x)
        return x