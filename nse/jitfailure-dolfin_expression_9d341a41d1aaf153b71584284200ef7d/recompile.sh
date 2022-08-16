#!/bin/bash
# Execute this file to recompile locally
c++ -Wall -shared -fPIC -std=c++11 -O3 -fno-math-errno -fno-trapping-math -ffinite-math-only -I/opt/conda/envs/pytorch-py3.8/include -I/opt/conda/envs/pytorch-py3.8/include/eigen3 -I/root/.cache/dijitso/include dolfin_expression_9d341a41d1aaf153b71584284200ef7d.cpp -L/opt/conda/envs/pytorch-py3.8/lib -L/opt/conda/envs/pytorch-py3.8/opt/conda/envs/pytorch-py3.8/lib -L/root/.cache/dijitso/lib -Wl,-rpath,/root/.cache/dijitso/lib -lmpi -lmpicxx -lpetsc -lslepc -lz -lhdf5 -lboost_timer -ldolfin -olibdijitso-dolfin_expression_9d341a41d1aaf153b71584284200ef7d.so