from h2oaiglm.libs.kmeans_cpu import h2oaiglmKMeansCPU
from h2oaiglm.solvers.kmeans_base import KMeansBaseSolver
from ctypes import *

if not h2oaiglmKMeansCPU:
    print('\nWarning: Cannot create a H2OAIKMeans CPU Solver instance without linking Python module to a compiled H2OAIGLM CPU library')
    print('> Setting h2oaiglm.KMeansCPU=None')
    print('> Add CUDA libraries to $PATH and re-run setup.py\n\n')
    KMeansSolverCPU=None
else:
    class KMeansSolverCPU(object):
        def __init__(self, cpu_id, n_cpus, k, max_iterations, threshold, init_from_labels, init_labels, init_data):
            self.solver = KMeansBaseSolver(h2oaiglmKMeansCPU, cpu_id, n_cpus, k, max_iterations, threshold, init_from_labels, init_labels, init_data)

        def KMeansInternal(self, cpu_id, n_cpu, ordin, k, max_iterations, init_from_labels, init_labels, init_data, threshold, mTrain, n, data, labels):
            return self.solver.KMeansInternal(cpu_id, n_cpu, ordin, k, max_iterations, init_from_labels, init_labels, init_data, threshold, mTrain, n, data, labels)
        def fit(self, X, L):
            return self.solver.fit(X,L)
        def sklearnfit(self):
            return self.solver.sklearnfit()
        def predict(self, X):
            return self.solver.predict(X)
        def transform(self, X):
            return self.solver.transform(X)
        def fit_transform(self, X, origL):
            return self.solver.fit_transform(X,origL)
        def fit_predict(self, X, origL):
            return self.solver.fit_predict(X,origL)
        