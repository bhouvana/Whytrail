"""whytrail plugin for the `numpy` library (ADR §03, §06).

Explains numpy structured errors that carry rich context beyond what
a bare traceback or Tier 1 exception chain shows:

- Broadcasting errors: operand shapes that are incompatible
- dtype mismatches: source/target type signatures and casting chains
- LinAlgError: decomposition operation type and matrix properties
- Index errors: axis index, array shape, size mismatches

This plugin clears the "structured error data" bar from ADR 0003.
Safe to import even if numpy is not installed (gracefully disabled).
"""

from __future__ import annotations

import typing as t

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_broadcasting_error(exc: ValueError, tb: t.Any) -> Explanation | None:
    """Extract operand shapes from frame locals for broadcasting failures.

    Broadcasting failures typically occur when array shapes don't align
    on non-1 axes. Extract all arrays from locals and identify which
    dimensions conflict.
    """
    if not _HAS_NUMPY or tb is None:
        return None

    frame = tb.tb_frame
    locals_ = frame.f_locals

    # Collect all numpy arrays and their shapes
    arrays = {}
    for name, val in locals_.items():
        if isinstance(val, np.ndarray):
            arrays[name] = val.shape

    if not arrays:
        return None

    description_lines = ["broadcasting failed -- operand shapes incompatible"]

    # Show all operands
    for name, shape in arrays.items():
        description_lines.append(f"  {name}: {shape}")

    # Try to identify the specific conflicting axis
    if len(arrays) >= 2:
        shapes_list = list(arrays.values())
        # Compare trailing dimensions (right-aligned)
        s1, s2 = shapes_list[0], shapes_list[1]

        # Pad with 1s on the left to same length
        max_len = max(len(s1), len(s2))
        s1_padded = (1,) * (max_len - len(s1)) + s1
        s2_padded = (1,) * (max_len - len(s2)) + s2

        for i, (a, b) in enumerate(zip(s1_padded, s2_padded)):
            # Conflict when both are > 1 and different
            if a != b and a != 1 and b != 1:
                axis_idx = i - max_len
                description_lines.append(f"  conflicting axis {axis_idx}: {a} vs {b}")
                break

    return Explanation(
        subject=f"ValueError: {exc}",
        steps=[
            ExplanationStep(
                description="\n".join(description_lines),
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        ],
        tracked=True,
    )


def _explain_dtype_error(exc: TypeError, tb: t.Any) -> Explanation | None:
    """Extract dtype information from frame locals for type mismatches.

    dtype errors occur when implicit casting fails or incompatible
    types are used. Extract source/target dtypes from locals.
    """
    if not _HAS_NUMPY or tb is None:
        return None

    frame = tb.tb_frame
    locals_ = frame.f_locals

    # Collect dtype info
    dtypes_info = []
    for name, val in locals_.items():
        if isinstance(val, np.ndarray):
            dtypes_info.append((name, f"ndarray[{val.dtype}]", val.shape))
        elif isinstance(val, (np.dtype, type)) and hasattr(val, "dtype"):
            dtypes_info.append((name, str(val.dtype), None))

    if not dtypes_info:
        return None

    description_lines = ["dtype mismatch -- incompatible types"]
    for name, dtype_str, shape in dtypes_info:
        if shape:
            description_lines.append(f"  {name}: {dtype_str} {shape}")
        else:
            description_lines.append(f"  {name}: {dtype_str}")

    return Explanation(
        subject=f"TypeError: {exc}",
        steps=[
            ExplanationStep(
                description="\n".join(description_lines),
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        ],
        tracked=True,
    )


def _explain_linalg_error(exc: Exception) -> Explanation | None:
    """Explain matrix decomposition and linear algebra failures.

    LinAlgError typically signals that a matrix decomposition failed
    or a matrix property check failed (singular, non-positive-definite,
    ill-conditioned, etc.).
    """
    if not _HAS_NUMPY:
        return None

    # Check if it's actually a LinAlgError
    if not isinstance(exc, np.linalg.LinAlgError):
        return None

    msg = str(exc).lower()

    # Map common error patterns to explanations
    explanations = {
        "singular": "Matrix is singular (non-invertible). No unique solution exists.",
        "converge": "Algorithm did not converge. Try increasing iterations or tolerance.",
        "svd": "SVD decomposition failed. Matrix may be ill-conditioned or has invalid dimensions.",
        "cholesky": "Cholesky decomposition failed. Matrix is not positive-definite or is ill-conditioned.",
        "positive.definite": "Matrix is not positive-definite. Check the matrix values or use a different decomposition.",
        "invalid": "Invalid matrix or operation. Check dimensions and values.",
        "dimension": "Dimension mismatch. Check matrix sizes for the operation.",
    }

    matched_explanation = None
    for pattern, explanation in explanations.items():
        if pattern in msg:
            matched_explanation = explanation
            break

    if matched_explanation is None:
        matched_explanation = f"Linear algebra operation failed: {exc}"

    return Explanation(
        subject=f"LinAlgError: {exc}",
        steps=[
            ExplanationStep(
                description=matched_explanation,
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        ],
        tracked=True,
    )


def _explain_index_error(exc: IndexError, tb: t.Any) -> Explanation | None:
    """Explain multi-dimensional indexing failures.

    Index errors in numpy often involve checking shapes against requested
    indices. Extract array shape and index info from the traceback.
    """
    if not _HAS_NUMPY or tb is None:
        return None

    frame = tb.tb_frame
    locals_ = frame.f_locals

    # Look for arrays and their attempted indices
    arrays_info = []
    for name, val in locals_.items():
        if isinstance(val, np.ndarray):
            arrays_info.append((name, val.shape, val.ndim))

    if not arrays_info:
        # Return generic IndexError explanation
        return Explanation(
            subject=f"IndexError: {exc}",
            steps=[
                ExplanationStep(
                    description="Array indexing out of bounds or invalid index.",
                    confidence=Confidence.EXPLICIT.value,
                    kind="external",
                )
            ],
            tracked=True,
        )

    description_lines = ["index error -- array index out of bounds"]
    for name, shape, ndim in arrays_info:
        description_lines.append(f"  {name}: shape {shape} ({ndim} dimensions)")

    return Explanation(
        subject=f"IndexError: {exc}",
        steps=[
            ExplanationStep(
                description="\n".join(description_lines),
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        ],
        tracked=True,
    )


def _explain_numpy_exception(exc: BaseException) -> Explanation | None:
    """Main entry point for numpy exception explanation.

    Called by whytrail when an exception is passed to why().
    Routes to appropriate explainer based on exception type.
    """
    if not _HAS_NUMPY:
        return None

    tb = exc.__traceback__

    if isinstance(exc, np.linalg.LinAlgError):
        return _explain_linalg_error(exc)

    elif isinstance(exc, ValueError):
        error_msg_lower = str(exc).lower()
        if "broadcast" in error_msg_lower or "could not be broadcast" in error_msg_lower:
            result = _explain_broadcasting_error(exc, tb)
            if result is not None:
                return result

    elif isinstance(exc, TypeError):
        error_msg_lower = str(exc).lower()
        if "dtype" in error_msg_lower or "type" in error_msg_lower:
            result = _explain_dtype_error(exc, tb)
            if result is not None:
                return result

    elif isinstance(exc, IndexError):
        result = _explain_index_error(exc, tb)
        if result is not None:
            return result

    # No numpy-specific explanation found
    return None


def register() -> None:
    """Register this explainer via whytrail's registry.

    Uses the entry-point lazy loading mechanism (ADR 0006) to avoid
    importing numpy until actually needed. Safe to call even if numpy
    is not installed.
    """
    if not _HAS_NUMPY:
        # numpy not available, skip registration silently
        return

    for _exc_type in (ValueError, TypeError, IndexError, np.linalg.LinAlgError):
        register_from_plugin(_exc_type, _explain_numpy_exception)
