"""Conformal calibration and hierarchical beta-binomial pooling package (Section 7.5 & 11.3, FR-100, ADR-017, AG-01)."""

from backend.ai.calibration.conformal import (
    GRADES_ORDERED,
    ConformalCalibrationSession,
    ConformalEvaluationResult,
    MondrianCategoryQuantiles,
    MondrianConformalCalibrator,
    compute_conformal_quantile,
    derive_cum_probs,
    get_conformal_calibrator,
    reset_conformal_calibrator,
    set_conformal_calibrator,
)
from backend.ai.calibration.pooling import (
    GapCalibration,
    PooledCalibrationEstimate,
    clopper_pearson_lower_bound,
    estimate_pooled_calibration,
)

__all__ = [
    "GRADES_ORDERED",
    "ConformalCalibrationSession",
    "ConformalEvaluationResult",
    "MondrianCategoryQuantiles",
    "MondrianConformalCalibrator",
    "compute_conformal_quantile",
    "derive_cum_probs",
    "get_conformal_calibrator",
    "reset_conformal_calibrator",
    "set_conformal_calibrator",
    "GapCalibration",
    "PooledCalibrationEstimate",
    "clopper_pearson_lower_bound",
    "estimate_pooled_calibration",
]
