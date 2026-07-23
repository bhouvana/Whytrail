#!/usr/bin/env python
"""Comprehensive demo of whytrail-numpy plugin.

Demonstrates how the numpy explainer plugin surfaces structured error
data that a bare traceback discards:
  - Broadcasting failures: operand shapes
  - dtype mismatches: type signatures
  - LinAlgError: decomposition operation and matrix properties
  - Index errors: array shape context
"""

import numpy as np
import whytrail

# Install whytrail's exception hook for automatic explanation on crashes
whytrail.install()

print("=" * 70)
print("DEMO 1: Broadcasting Error Explanation")
print("=" * 70)
print("\nAttempting: a (3, 4, 5) + b (4, 6) -- incompatible shapes")
try:
    a = np.zeros((3, 4, 5))
    b = np.zeros((4, 6))
    result = a + b
except ValueError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 2: dtype Mismatch Explanation")
print("=" * 70)
print("\nAttempting: structured array to float32 cast (type mismatch)")
try:
    structured = np.array(
        [(1, 2.0), (3, 4.0)],
        dtype=[("a", np.int32), ("b", np.float64)]
    )
    result = np.array(structured, dtype=np.float32)
except TypeError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 3: Singular Matrix (Non-Invertible)")
print("=" * 70)
print("\nAttempting: np.linalg.inv(singular_matrix)")
print("Matrix: [[1, 2], [2, 4]] (rank 1, not invertible)")
try:
    singular = np.array([[1.0, 2.0], [2.0, 4.0]])
    result = np.linalg.inv(singular)
except np.linalg.LinAlgError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 4: Cholesky Decomposition (Non-Positive-Definite Matrix)")
print("=" * 70)
print("\nAttempting: np.linalg.cholesky(non_pd_matrix)")
print("Matrix: [[1, 2], [2, 3]] (not positive-definite)")
try:
    non_pd = np.array([[1.0, 2.0], [2.0, 3.0]])
    result = np.linalg.cholesky(non_pd)
except np.linalg.LinAlgError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 5: Multi-Dimensional Index Error")
print("=" * 70)
print("\nAttempting: arr[5, 10] on shape (3, 4) array (out of bounds)")
try:
    arr = np.zeros((3, 4))
    result = arr[5, 10]
except IndexError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 6: Untracked Array (Honest Unknown)")
print("=" * 70)
print("\nQuerying: whytrail.why(untracked_array)")
arr = np.array([1, 2, 3])
exp = whytrail.why(arr)
print(f"\n{exp.text}")
print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("DEMO 7: Manual Override (User Registration Wins)")
print("=" * 70)
print("\nRegistering custom explainer for ValueError...")
whytrail.register(
    ValueError,
    lambda exc: whytrail.Explanation(
        subject="Custom Override",
        steps=[
            whytrail.ExplanationStep(
                description="User-provided custom explanation (manual registration wins)",
                confidence=whytrail.Confidence.EXPLICIT.value,
                kind="external",
            )
        ],
        tracked=True,
    ),
)
try:
    a = np.zeros((3, 4))
    b = np.zeros((5, 6))
    result = a + b
except ValueError as exc:
    exp = whytrail.why(exc)
    print(f"\n{exp.text}")
    print(f"Explanation known: {exp.known}")

print("\n" + "=" * 70)
print("All demos completed successfully!")
print("=" * 70)
