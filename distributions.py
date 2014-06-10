import numpy as np
from numpy import newaxis as nax
from numpy.linalg import det, inv
from scipy import stats

class Distribution(object):
    def log_pdf(self, X):
        pass

    def pdf(self, X, normalized):
        pass

    def distances(self, X):
        pass

    def max_likelihood(self, X, weights):
        pass

class Gaussian(Distribution):
    def __init__(self, mean, cov):
        self.mean = mean
        self.cov = cov

    @property
    def dim(self):
        return len(self.mean)

    def distances(self, X):
        diff = X - self.mean
        return 0.5 * np.diag(diff.dot(inv(self.cov)).dot(diff.T))

    def max_likelihood(self, X, weights):
        self.mean = np.sum(weights[:,nax] * X, axis=0) / np.sum(weights)
        diff = X - self.mean
        self.cov = diff.T.dot(weights[:,nax] * diff) / np.sum(weights)

    def log_pdf(self, X):
        d = self.mean.shape[0]
        diff = X - self.mean
        return - 0.5 * d * np.log(2*np.pi) - 0.5 * np.log(det(self.cov)) \
                - 0.5 * np.diag(diff.dot(inv(self.cov)).dot(diff.T))

    def pdf(self, X, normalized=True):
        d = self.mean.shape[0]
        diff = X - self.mean
        if normalized:
            return 1. / np.sqrt((2*np.pi)**d * det(self.cov)) \
                    * np.exp(-0.5 * np.diag(diff.dot(inv(self.cov)).dot(diff.T)))
        else:
            return np.exp(-0.5 * np.diag(diff.dot(inv(self.cov)).dot(diff.T)))

    def sample(self, size=1):
        return np.random.multivariate_normal(self.mean, self.cov, size)


# for euclidian K-means or isotropic Gaussian
class SquareDistance(Distribution):
    def __init__(self, mean, sigma2=None):
        self.mean = mean
        self.sigma2 = sigma2

    @property
    def cov(self):
        return self.sigma2 * np.eye(2)

    @property
    def dim(self):
        return len(self.mean)

    def distances(self, X):
        diff = X - self.mean
        return np.sum(diff * diff, axis=1)

    def max_likelihood(self, X, weights):
        if weights.dtype == np.bool:
            self.mean = X[weights,:].mean(axis=0)
        else:
            self.mean = np.sum(weights[:,nax] * X, axis=0) / np.sum(weights)

        if self.sigma2 is not None:
            diff = X - self.mean
            dists = np.sum(diff * diff, axis=1)
            self.sigma2 = 0.5 * dists.dot(weights) / np.sum(weights)

    def log_pdf(self, X):
        assert self.sigma2 is not None, 'only for isotropic Gaussian'
        d = self.mean.shape[0]
        diff = X - self.mean
        dists = np.sum(diff*diff, axis=1)
        return - 0.5 * d * np.log(2*np.pi) - 0.5 * d * np.log(self.sigma2) \
                - 0.5 * dists / self.sigma2

    def pdf(self, X, normalized=True):
        assert self.sigma2 is not None, 'only for isotropic Gaussian'
        d = self.mean.shape[0]
        diff = X - self.mean
        dists = np.sum(diff*diff, axis=1)

        if normalized:
            return 1. / np.sqrt((2*np.pi*self.sigma2)**d) \
                    * np.exp(-0.5 * dists / self.sigma2)
        else:
            return np.exp(-0.5 * dists / self.sigma2)

class KL(Distribution):
    '''Basically a multinomial.'''
    def __init__(self, mean):
        self.mean = mean

    @property
    def dim(self):
        return len(self.mean)

    def distances(self, X):
        return - X.dot(np.log(self.mean))

    def max_likelihood(self, X, weights):
        if weights.dtype == np.bool:
            self.mean = X[weights,:].mean(axis=0)
        else:
            self.mean = np.sum(weights[:,nax] * X, axis=0) / np.sum(weights)

    def online_update(self, x, step):
        self.mean = (1 - step) * self.mean + step * x

    def log_pdf(self, X):
        # log p(x|theta) = sum_j x_j log(theta_j)
        return X.dot(np.log(self.mean))

    def pdf(self, X, normalized=True):
        return np.exp(X.dot(np.log(self.mean)))

    def new_sufficient_statistics(self, x, cluster_id, K):
        return KLSufficientStatistics(x, cluster_id, K, self.mean.shape[0])

    def online_max_likelihood(self, rho_obs, phi):
        self.mean = rho_obs.rho.dot(phi) / rho_obs.rho0.dot(phi)

class DurationDistribution(Distribution):
    def __init__(self, D):
        self.D = D

    def log_pmf(self, X):
        pass

    def log_vec(self):
        return self.log_pmf(np.arange(1,self.D+1))

class PoissonDuration(DurationDistribution):
    def __init__(self, lmbda, D):
        super(PoissonDuration, self).__init__(D)
        self.lmbda = lmbda

    def log_pmf(self, X):
        return stats.poisson.logpmf(X, self.lmbda)

    def sample(self, size=None):
        return stats.poisson.rvs(self.lmbda, size=size)

class NegativeBinomial(DurationDistribution):
    def __init__(self, r, p, D):
        super(NegativeBinomial, self).__init__(D)
        self.r = r
        self.p = p

    def log_pmf(self, X):
        return stats.nbinom.logpmf(X, self.r, self.p)

    def sample(self, size=None):
        return stats.nbinom.rvs(self.r, self.p, size=size)

# Sufficient Statistics classes

class SufficientStatistics(object):
    def __init__(self, cluster_id, K):
        self.cluster_id = cluster_id
        self.K = K

    def online_update(self, x, r, step):
        pass

class KLSufficientStatistics(SufficientStatistics):
    def __init__(self, x, cluster_id, K, size):
        super(KLSufficientStatistics, self).__init__(cluster_id, K)
        # 1{Z_t = i}
        self.rho0 = np.zeros(self.K)
        # 1{Z_t = i} x_t
        self.rho = np.zeros((size, self.K))
        self.rho[:,self.cluster_id] = x

    def online_update(self, x, r, step):
        self.rho0 = (1 - step) * self.rho0.dot(r)
        self.rho0[self.cluster_id] += step
        self.rho = (1 - step) * self.rho.dot(r)
        self.rho[:,self.cluster_id] += step * x
