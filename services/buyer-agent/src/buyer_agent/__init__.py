"""SurplusFlow buyer agent (Person 2).

Owns objective parsing, the procurement state machine, the deterministic
optimizer, purchase-intent construction, and provider orchestration.

This package never reads a wallet seed and never builds or signs a raw XRPL
transaction. It produces typed PurchaseIntent objects and hands them to the
payment boundary owned by Person 4.
"""

__version__ = "1.0.0"
