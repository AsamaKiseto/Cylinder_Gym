from asyncio import constants
from fenics import *
import numpy as np
import matplotlib.pyplot as plt
from fenics import set_log_level, plot

import torch
from functools import partial



'''
""" The exact solution 
        """
        x = p[..., 0]
        y = p[..., 1]
        pi = np.pi
        u = np.sin(pi*x)*np.cos(pi*y)*np.exp(-pi**2/8*t)
'''



class MyGeometry:
    def __init__(self,  min_x = 0.0, max_x =2.0 , min_y = 0.0,max_y = 1.0, params=None):
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        # self.W = W
        self.params = params

    
    def generate(self, params=None):
        self.n = 64
        self.mesh = RectangleMesh(Point(self.min_x,self.min_y),Point(self.max_x,self.max_y),self.n,self.n)

        bndry = MeshFunction("size_t", self.mesh, self.mesh.topology().dim()-1)
        for f in facets(self.mesh):
            mp = f.midpoint()
            if near(mp[0], self.min_x):  #left
                bndry[f] = 1
            elif near(mp[0], self.max_x):  # right
                bndry[f] = 2
            elif near(mp[1], self.max_y)   :  #top
                bndry[f] = 3
            elif near(mp[1], self.min_y): #bottom
                bndry[f] = 4  
  
        self.bndry = bndry
        self.mesh_coor = self.mesh.coordinates()
        self.num_vertices = self.mesh.num_vertices()
        print('num of vertices',self.num_vertices)

class MyFunctionSpace:
    def __init__(self, geometry, params=None):
        self.geometry = geometry
        self.params = params
    
    def generate(self, params=None):
        self.V = VectorElement("P",self.geometry.mesh.ufl_cell(), degree = 2,dim = 2)
        self.P = FiniteElement( "P",self.geometry.mesh.ufl_cell(), degree = 1)
        self.W = FunctionSpace(self.geometry.mesh, MixedElement([self.V, self.P]))

class MySolver:
    def __init__(self, geometry, function_space, params=None):
        self.geometry = geometry
        self.function_space = function_space
        self.params = params
        self.time = 0
        self.T = self.params['T']
        self.dt = self.params['dt']
        self.epoch = 0
        self.theta = 0.5
        self.pr = 1
        self.Ra = 2E6
        self.nu = 0.1
        self.u_0  = Expression(('0.0','0.0','0.0'),degree = 2)
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.R_star = (self.pr/self.Ra)**(1/2)
        self.P_star = (self.pr*self.Ra)**(-1/2)

    def generate_variable(self):
        self.geometry.generate()
        self.function_space.generate()
        self.V = self.function_space.V
        self.P = self.function_space.P
        self.W = self.function_space.W

    def generate_bc(self, ctr=1.0):
        self.bndry = self.geometry.bndry
        
        # self.const = np.random.rand(1)*0.4 + 1.8
        # self.amp = np.random.rand(1)*0.1
        # self.bc_bottom = Expression('a+b*sin(2*pi*x[0])',a = self.const[0],b = self.amp[0],pi = np.pi,degree = 2)
        self.bc_top = Expression('0.0',degree = 2)
        self.noslip = Constant((0, 0))
        self.u_top = Constant((ctr, 0))
        self.bcv_t = DirichletBC(self.W.sub(0), self.u_top, self.bndry, 3)
        self.bcv_b = DirichletBC(self.W.sub(0), self.noslip, self.bndry, 4)
        self.bcv_l = DirichletBC(self.W.sub(0), self.noslip, self.bndry, 1)
        self.bcv_r = DirichletBC(self.W.sub(0), self.noslip, self.bndry, 2)
        
        self.bcp_t = DirichletBC(self.W.sub(1), Constant(0), self.bndry, 3)
        #self.bcp_b = DirichletBC(self.W.sub(1), self.bc_top, self.bndry, 3)
        self.bcs = [self.bcv_t, self.bcv_b, self.bcv_l, self.bcv_r, self.bcp_t]# ,self.bcp_t,self.bcp_b

    

    def generate_solver(self):
        (self.v_, self.p_) = TestFunctions(self.W)
        self.w = Function(self.W)
        self.w.interpolate(self.u_0)
        (self.v, self.p) = split(self.w)


        self.w_old = Function(self.W)
        self.w_old.interpolate(self.u_0)
        (self.v_old, self.p_old) = split(self.w_old)
        def a(v,u) :
            D = sym(grad(v))
            return (inner(grad(v)*v, u) +self.nu* inner(2*D, 2*sym(grad(u))))*dx

        def b(q,v) :
            return inner(div(v),q)*dx

        self.F0_eq1 = a(self.v_old,self.v_) + b(self.p,self.v_)
        self.F0_eq2 = b(self.p_,self.v)
        self.F0 = self.F0_eq1 + self.F0_eq2 
        self.F1_eq1 = a(self.v,self.v_) + b(self.p,self.v_)
        self.F1_eq2 = b(self.p_,self.v)
        self.F1 = self.F1_eq1 + self.F1_eq2 
        self.F = (inner((self.v-self.v_old),self.v_)/self.dt)*dx + (1.0-self.theta)*self.F0 + self.theta*self.F1
        self.J = derivative(self.F, self.w)
        self.problem =  NonlinearVariationalProblem(self.F, self.w, self.bcs, self.J)
        self.solver = NonlinearVariationalSolver(self.problem)
        self.prm =self. solver.parameters
        #info(prm,True)  #get full info on the parameters
        self.prm['nonlinear_solver'] = 'newton'
        self.prm['newton_solver']['absolute_tolerance'] = 1E-10
        self.prm['newton_solver']['relative_tolerance'] = 1e-10
        self.prm['newton_solver']['maximum_iterations'] = 10
        self.prm['newton_solver']['linear_solver'] = 'mumps'

    def init_solve(self, ctr):
        self.generate_variable()
        self.generate_bc(ctr)
        self.generate_solver()
        self.generate_grid()
        self.time = 0 
        
    def direct_solve(self,epoch):
        for i in range(epoch):
            self.time += self.dt
            self.epoch +=1
            self.solver.solve()
            self.w_old.assign(self.w)
            self.plot_all()

    def step_forward(self):
        self.time += self.dt
        self.epoch +=1
        self.solver.solve()
        self.w_old.assign(self.w)
        temp, velo, p ,const , amp= self.get_obs()
        #self.plot_all()
        return temp , velo , p , const , amp 

    def _get_done(self):
        return self.time > self.T  

    def generate_grid(self):
        gsx = self.params['dimx'] #30
        gsy = self.params['dimy'] #30
        xs = np.linspace(self.geometry.min_x, self.geometry.max_x, gsx)
        ys = np.linspace(self.geometry.min_y, self.geometry.max_y, gsy)
        mx, my = np.meshgrid(xs, ys)
        grids = np.stack((mx, my), 2)
        self.grids = grids
        self.meshgrid = [mx, my]
            
    def get_obs(self):
        nu = self.params['dimy']*self.params['dimx']
        shape = [self.params['dimy'],self.params['dimx'] ]
        
        p = np.array(self.w.compute_vertex_values()[2*nu:3*nu].reshape(shape))
        u =  np.array(self.w.compute_vertex_values()[:1*nu].reshape(shape))
        v =  np.array(self.w.compute_vertex_values()[1*nu:2*nu].reshape(shape))
        velo = np.concatenate([np.expand_dims(u,axis = -1),np.expand_dims(v,axis = -1)],axis = -1)
        return  velo, p 

    def plot_all(self):
        velo, p  = self.get_obs()
        fig = plt.figure()
        plt.axis('equal')
        plt.contourf(self.meshgrid[0],self.meshgrid[1], p, 200, cmap='jet')
        plt.colorbar()
        plt.savefig('pics/img_pressure/pic-{}.png'.format(self.epoch))
        xl, xh  = self.geometry.min_x, self.geometry.max_x
        yl, yh = self.geometry.min_y, self.geometry.max_y
        fig, ax = plt.subplots(figsize=(12,9))
        # fig, ax = plt.figure()
        ax.axis('equal')
        ax.set(xlim=(xl, xh), ylim=(yl, yh))
        ax.quiver(self.meshgrid[0],self.meshgrid[1], velo[:,:,0],velo[:,:,1] , np.sqrt(velo[:,:,0]**2+velo[:,:,1]**2))
        plt.savefig('pics/img_velo/pic-{}.png'.format(self.epoch))