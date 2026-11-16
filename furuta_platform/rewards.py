"""Reward functions independent of MuJoCo, with named educational terms."""
import math

def reward_terms(state, action, previous_action, c):
    theta, alpha, td, ad = state
    w = c['reward']
    if c.get('reward_version', 'baseline') == 'baseline':
        return {'upright':w['upright']*math.cos(alpha), 'arm':-w['arm']*theta**2,
                'arm_velocity':-w['arm_velocity']*td**2, 'pend_velocity':-w['pend_velocity']*ad**2,
                'effort':-w['effort']*action**2}
    h = (1 + math.cos(alpha))/2
    gate = h**c['reward_shape']['upright_power']
    scales = c['reward_shape']['balance_velocity_scale']
    edge = c['reward_shape']['arm_edge_fraction']
    distance = abs(theta)/c['limits']['arm_rad']
    boundary = min(1., max(0., (distance-edge)/(1-edge)))**2
    return {'upright':w['upright']*h,
            'balance':w['balance']*gate*math.exp(-(ad/scales[1])**2-(td/scales[0])**2),
            'arm_boundary':-w['arm_boundary']*boundary,
            'effort':-w['effort']*action**2,
            'smoothness':-w['smoothness']*(action-previous_action)**2}
