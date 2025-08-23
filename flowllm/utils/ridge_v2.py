import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class RidgeV2:

    def __init__(self, bound: int = 4.6, use_ridge_v2=True, **kwargs):
        self.bound: int = bound
        self.use_ridge_v2: bool = use_ridge_v2
        self.kwargs: dict = kwargs
        self.model = Ridge(**self.kwargs)

    def clear(self):
        self.model = Ridge(**self.kwargs)
        return self

    def sigmoid(self, x):
        x = np.asarray(x, dtype=float)
        x = np.clip(x, -self.bound, self.bound)
        return 1 / (1 + np.exp(-x))

    def inv_sigmoid(self, p):
        p = np.asarray(p, dtype=float)
        p = np.clip(p, self.sigmoid(-self.bound), self.sigmoid(self.bound))
        return np.log(p / (1 - p))

    def fit(self, x, y, sample_weight=None):
        if self.use_ridge_v2:
            return self.model.fit(x, self.inv_sigmoid(y), sample_weight=sample_weight)
        else:
            return self.model.fit(x, y, sample_weight=sample_weight)

    def predict(self, x):
        if self.use_ridge_v2:
            return self.sigmoid(self.model.predict(x))
        else:
            return self.model.predict(x)

    def fit_and_predict(self,
                        train_x_nd: np.ndarray,
                        train_y_nd: np.ndarray,
                        test_x_nd: np.ndarray,
                        check_y: bool = True):
        if check_y:
            assert np.all((train_y_nd >= 0) & (train_y_nd <= 1))

        scaler = StandardScaler()
        scaler.fit(train_x_nd)
        train_x_nd = scaler.transform(train_x_nd)
        test_x_nd = scaler.transform(test_x_nd)
        self.model.fit(train_x_nd, train_y_nd)
        pred_y_nd = self.model.predict(test_x_nd)
        return np.minimum(np.maximum(pred_y_nd, 0), 1)
