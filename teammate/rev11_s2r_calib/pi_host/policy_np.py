"""sac_rev11 액터 (SB3 deterministic): u = tanh(mu(ReLU(W2 ReLU(W1 obs + b1) + b2))). numpy only."""
import numpy as np


class ActorNP:
    def __init__(self, path):
        w = np.load(path)
        self.W1, self.b1 = w["latent_pi.0.weight"], w["latent_pi.0.bias"]
        self.W2, self.b2 = w["latent_pi.2.weight"], w["latent_pi.2.bias"]
        self.Wm, self.bm = w["mu.weight"], w["mu.bias"]

    def __call__(self, obs):
        h = np.maximum(0.0, self.W1 @ obs + self.b1)
        h = np.maximum(0.0, self.W2 @ h + self.b2)
        return float(np.tanh((self.Wm @ h + self.bm)[0]))
