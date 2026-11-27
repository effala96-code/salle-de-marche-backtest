import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq, newton


def _d1_d2(S, K, r, q, sigma, tau):
    sigma_sqrt = sigma * np.sqrt(tau)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * tau) / sigma_sqrt
    return d1, d1 - sigma_sqrt


def bs_price(S, K, r, q, sigma, tau, option_type='call'):
    if tau <= 0:
        return max(S - K, 0.0) if option_type == 'call' else max(K - S, 0.0)
    if sigma <= 0:
        forward = S * np.exp((r - q) * tau)
        payoff = max(forward - K, 0.0) if option_type == 'call' else max(K - forward, 0.0)
        return np.exp(-r * tau) * payoff

    d1, d2 = _d1_d2(S, K, r, q, sigma, tau)
    df_r = np.exp(-r * tau)
    df_q = np.exp(-q * tau)
    if option_type == 'call':
        return S * df_q * norm.cdf(d1) - K * df_r * norm.cdf(d2)
    return K * df_r * norm.cdf(-d2) - S * df_q * norm.cdf(-d1)


def bs_greeks(S, K, r, q, sigma, tau):
    if tau <= 0 or sigma <= 0:
        delta_call = 1.0 if S > K else 0.0
        return {
            'delta_call': delta_call,
            'delta_put': delta_call - 1.0,
            'gamma': 0.0,
            'vega': 0.0,
            'theta_call': 0.0,
            'theta_put': 0.0,
            'rho_call': 0.0,
            'rho_put': 0.0,
        }

    d1, d2 = _d1_d2(S, K, r, q, sigma, tau)
    df_r = np.exp(-r * tau)
    df_q = np.exp(-q * tau)
    pdf_d1 = norm.pdf(d1)
    delta_call = df_q * norm.cdf(d1)
    delta_put = df_q * (norm.cdf(d1) - 1.0)
    gamma = df_q * pdf_d1 / (S * sigma * np.sqrt(tau))
    vega = S * df_q * pdf_d1 * np.sqrt(tau)
    theta_common = -(S * df_q * pdf_d1 * sigma) / (2.0 * np.sqrt(tau))
    theta_call = theta_common - r * K * df_r * norm.cdf(d2) + q * S * df_q * norm.cdf(d1)
    theta_put = theta_common + r * K * df_r * norm.cdf(-d2) - q * S * df_q * norm.cdf(-d1)
    rho_call = K * tau * df_r * norm.cdf(d2)
    rho_put = -K * tau * df_r * norm.cdf(-d2)
    return {
        'delta_call': delta_call,
        'delta_put': delta_put,
        'gamma': gamma,
        'vega': vega,
        'theta_call': theta_call,
        'theta_put': theta_put,
        'rho_call': rho_call,
        'rho_put': rho_put,
    }


def implied_volatility(market_price, S, K, r, q, tau, option_type='call', sigma_init=0.2, tol=1e-8, maxiter=100):
    price_func = lambda sigma: bs_price(S, K, r, q, sigma, tau, option_type) - market_price
    try:
        iv = newton(
            price_func,
            sigma_init,
            fprime=lambda sigma: bs_greeks(S, K, r, q, sigma, tau)['vega'],
            tol=tol,
            maxiter=maxiter,
        )
        if iv > 0:
            return iv
    except (RuntimeError, OverflowError, ZeroDivisionError):
        pass

    try:
        return brentq(price_func, 1e-12, 5.0, xtol=tol, maxiter=maxiter)
    except ValueError:
        return np.nan
