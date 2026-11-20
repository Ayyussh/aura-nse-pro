"""Hierarchical Risk Parity (HRP) Portfolio Optimizer.

Implements Marcos López de Prado's modern machine-learning portfolio allocation:
1. Tree Clustering: Builds hierarchical dendrogram from correlation distance matrix
   d_ij = sqrt(0.5 * (1 - rho_ij))
2. Quasi-Diagonalization: Seriation to reorder assets by co-movement hierarchy
3. Recursive Bisection: Allocates capital inversely proportional to cluster variances,
   eliminating the matrix inversion instabilities of classical Markowitz Mean-Variance
4. Institutional Constraints:
   - Max single position allocation (default 20% institutional cap)
   - Min position floor (default 3%)
   - Exact Rupee allocation calculation
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage

logger = logging.getLogger("aura.hrp_optimizer")


@dataclass
class AssetAllocation:
    symbol: str
    weight: float
    weight_pct: float
    rupee_allocation: float
    volatility_annualized: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HRPOptimizationResult:
    status: str  # OPTIMAL, FALLBACK_INVERSE_VOL, SINGLE_ASSET
    total_capital: float
    allocated_capital: float
    num_assets: int
    portfolio_volatility_annualized: float
    diversification_ratio: float
    allocations: List[AssetAllocation]
    weights: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "total_capital": self.total_capital,
            "allocated_capital": self.allocated_capital,
            "num_assets": self.num_assets,
            "portfolio_volatility_annualized": round(self.portfolio_volatility_annualized, 4),
            "diversification_ratio": round(self.diversification_ratio, 2),
            "allocations": [a.to_dict() for a in self.allocations],
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
        }


class HierarchicalRiskParityOptimizer:
    """Computes risk-optimal weights using Hierarchical Tree Clustering and Recursive Bisection."""

    def __init__(
        self,
        max_weight: float = 0.20,
        min_weight: float = 0.03,
        linkage_method: str = "single",
    ):
        self.max_weight = max_weight
        self.min_weight = min_weight
        self.linkage_method = linkage_method

    def optimize(
        self,
        returns_df: pd.DataFrame,
        total_capital: float = 1_000_000.0,
    ) -> HRPOptimizationResult:
        """Calculate optimal HRP weights given historical return series."""
        clean_df = returns_df.dropna(how="all", axis=1).dropna()
        symbols = list(clean_df.columns)
        n = len(symbols)

        if n == 0:
            return HRPOptimizationResult(
                status="EMPTY",
                total_capital=total_capital,
                allocated_capital=0.0,
                num_assets=0,
                portfolio_volatility_annualized=0.0,
                diversification_ratio=1.0,
                allocations=[],
                weights={},
            )

        if n == 1:
            sym = symbols[0]
            annual_vol = float(clean_df[sym].std() * np.sqrt(252))
            alloc = AssetAllocation(
                symbol=sym,
                weight=1.0,
                weight_pct=100.0,
                rupee_allocation=total_capital,
                volatility_annualized=round(annual_vol, 4),
            )
            return HRPOptimizationResult(
                status="SINGLE_ASSET",
                total_capital=total_capital,
                allocated_capital=total_capital,
                num_assets=1,
                portfolio_volatility_annualized=round(annual_vol, 4),
                diversification_ratio=1.0,
                allocations=[alloc],
                weights={sym: 1.0},
            )

        cov = clean_df.cov() * 252.0  # Annualized covariance
        corr = clean_df.corr()

        try:
            # 1. Hierarchical Tree Clustering
            # Correlation distance: d_ij = sqrt(0.5 * (1 - rho_ij))
            dist = np.sqrt(0.5 * np.clip(1.0 - corr.values, 0.0, 2.0))
            # Extract upper triangle condensed distance matrix
            condensed_dist = dist[np.triu_indices(n, k=1)]
            link = linkage(condensed_dist, method=self.linkage_method)

            # 2. Quasi-Diagonalization (Sort tree leaves)
            sorted_indices = self._get_quasi_diag(link)
            sorted_symbols = [symbols[i] for i in sorted_indices]

            # 3. Recursive Bisection
            weights_series = self._get_rec_bisection(cov.loc[sorted_symbols, sorted_symbols], sorted_symbols)

            # 4. Enforce institutional position limits
            weights = self._apply_constraints(weights_series.to_dict())
            status = "OPTIMAL"
        except Exception as e:
            logger.warning(f"HRP clustering failed, falling back to inverse volatility: {e}")
            weights = self._fallback_inverse_volatility(clean_df)
            status = "FALLBACK_INVERSE_VOL"

        # Calculate final metrics
        w_vec = np.array([weights.get(s, 0.0) for s in symbols])
        cov_vals = cov.values
        port_variance = float(np.dot(w_vec.T, np.dot(cov_vals, w_vec)))
        port_vol = float(np.sqrt(max(0.0, port_variance)))

        # Diversification Ratio = Weighted avg vol / Portfolio vol
        indiv_vols = np.sqrt(np.diag(cov_vals))
        weighted_vol = float(np.dot(w_vec, indiv_vols))
        div_ratio = round(weighted_vol / port_vol, 2) if port_vol > 0 else 1.0

        allocations: List[AssetAllocation] = []
        for s in symbols:
            w = weights.get(s, 0.0)
            s_vol = float(clean_df[s].std() * np.sqrt(252))
            allocations.append(AssetAllocation(
                symbol=s,
                weight=round(w, 4),
                weight_pct=round(w * 100.0, 2),
                rupee_allocation=round(w * total_capital, 2),
                volatility_annualized=round(s_vol, 4),
            ))

        allocations.sort(key=lambda a: a.weight, reverse=True)

        return HRPOptimizationResult(
            status=status,
            total_capital=total_capital,
            allocated_capital=total_capital,
            num_assets=n,
            portfolio_volatility_annualized=port_vol,
            diversification_ratio=div_ratio,
            allocations=allocations,
            weights={a.symbol: a.weight for a in allocations},
        )

    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        """Seriation: reorder asset indices based on hierarchical tree linkage."""
        link = link.astype(int)
        num_items = link[-1, 3]
        tree = [link[-1, 0], link[-1, 1]]

        while any(i >= num_items for i in tree):
            next_tree = []
            for item in tree:
                if item >= num_items:
                    cluster_idx = item - num_items
                    next_tree.extend([link[cluster_idx, 0], link[cluster_idx, 1]])
                else:
                    next_tree.append(item)
            tree = next_tree
        return tree

    def _get_rec_bisection(self, cov: pd.DataFrame, sorted_symbols: List[str]) -> pd.Series:
        """Recursive bisection allocation based on cluster variances."""
        w = pd.Series(1.0, index=sorted_symbols)
        cluster_list = [sorted_symbols]

        while len(cluster_list) > 0:
            cluster_list = [
                c[i:j]
                for c in cluster_list
                for i, j in ((0, len(c) // 2), (len(c) // 2, len(c)))
                if len(c) > 1
            ]
            for i in range(0, len(cluster_list), 2):
                c1 = cluster_list[i]
                c2 = cluster_list[i + 1]

                v1 = self._get_cluster_variance(cov, c1)
                v2 = self._get_cluster_variance(cov, c2)

                alpha = 1.0 - (v1 / (v1 + v2)) if (v1 + v2) > 0 else 0.5
                w[c1] *= alpha
                w[c2] *= (1.0 - alpha)

        return w

    def _get_cluster_variance(self, cov: pd.DataFrame, cluster: List[str]) -> float:
        """Compute the variance of an inverse-variance weighted cluster."""
        sub_cov = cov.loc[cluster, cluster].values
        inv_diag = 1.0 / np.clip(np.diag(sub_cov), 1e-6, None)
        w = inv_diag / np.sum(inv_diag)
        return float(np.dot(w.T, np.dot(sub_cov, w)))

    def _apply_constraints(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply institutional ceiling (max_weight) and floor (min_weight)."""
        symbols = list(weights.keys())
        w_series = pd.Series(weights)

        # Clip within boundaries
        w_clipped = w_series.clip(lower=self.min_weight, upper=self.max_weight)
        # Normalize sum to 1.0
        w_final = w_clipped / w_clipped.sum()
        return {s: float(w_final[s]) for s in symbols}

    def _fallback_inverse_volatility(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Fallback: allocate inversely proportional to annualized volatility."""
        vols = returns_df.std() * np.sqrt(252)
        inv_vols = 1.0 / np.clip(vols, 1e-4, None)
        weights = inv_vols / inv_vols.sum()
        return self._apply_constraints(weights.to_dict())


hrp_optimizer = HierarchicalRiskParityOptimizer()
