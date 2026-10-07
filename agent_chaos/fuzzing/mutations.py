"""Mutation strategies and payload generators for Tool Schema Fuzzing."""

from __future__ import annotations

import copy
import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class MutationType(str, Enum):
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    TYPE_INVERSION = "type_inversion"
    BOUNDARY_VALUES = "boundary_values"
    EMPTY_PAYLOAD = "empty_payload"
    TOKEN_BOMB = "token_bomb"
    ADVERSARIAL_INJECTION = "adversarial_injection"
    NULL_INJECTION = "null_injection"


class FuzzedPayload(BaseModel):
    """Result of mutating a tool output payload."""
    mutation_type: MutationType
    description: str
    target_field: Optional[str] = None
    original_value: Optional[Any] = None
    mutated_payload: Any


class BaseMutationStrategy(ABC):
    """Abstract strategy for mutating tool payloads."""

    @abstractmethod
    def generate(
        self,
        schema: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> List[FuzzedPayload]:
        pass


class MissingFieldsStrategy(BaseMutationStrategy):
    """Strips required or optional fields from the baseline payload."""

    def generate(
        self,
        schema: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> List[FuzzedPayload]:
        results: List[FuzzedPayload] = []
        if not isinstance(baseline, dict) or not baseline:
            return results

        # Identify required fields from schema if available
        required = schema.get("required", []) if isinstance(schema, dict) else []

        # 1. Drop required fields individually
        for field in required:
            if field in baseline:
                mutated = copy.deepcopy(baseline)
                orig_val = mutated.pop(field)
                results.append(
                    FuzzedPayload(
                        mutation_type=MutationType.MISSING_REQUIRED_FIELDS,
                        description=f"Stripped required field '{field}'",
                        target_field=field,
                        original_value=orig_val,
                        mutated_payload=mutated,
                    )
                )

        # 2. Drop all keys individually if no required list
        if not required:
            for key, val in list(baseline.items())[:5]:
                mutated = copy.deepcopy(baseline)
                mutated.pop(key)
                results.append(
                    FuzzedPayload(
                        mutation_type=MutationType.MISSING_REQUIRED_FIELDS,
                        description=f"Stripped field '{key}'",
                        target_field=key,
                        original_value=val,
                        mutated_payload=mutated,
                    )
                )

        # 3. Completely empty payload
        results.append(
            FuzzedPayload(
                mutation_type=MutationType.EMPTY_PAYLOAD,
                description="Completely stripped all fields (empty dict)",
                mutated_payload={},
            )
        )

        return results


class TypeInversionStrategy(BaseMutationStrategy):
    """Inverts data types (e.g. number to string, string to integer, array to object)."""

    def generate(
        self,
        schema: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> List[FuzzedPayload]:
        results: List[FuzzedPayload] = []
        if not isinstance(baseline, dict):
            return results

        for key, val in baseline.items():
            mutated = copy.deepcopy(baseline)
            inverted_val: Any = None
            desc = ""

            if isinstance(val, bool):
                inverted_val = "not_a_boolean"
                desc = f"Inverted boolean '{key}' to string"
            elif isinstance(val, (int, float)):
                inverted_val = "NaN_corrupt_number"
                desc = f"Inverted number '{key}' to string"
            elif isinstance(val, str):
                inverted_val = 999999
                desc = f"Inverted string '{key}' to integer"
            elif isinstance(val, list):
                inverted_val = {"unexpected_dict": True}
                desc = f"Inverted array '{key}' to dict"
            elif isinstance(val, dict):
                inverted_val = ["unexpected_array_item"]
                desc = f"Inverted dict '{key}' to list"
            else:
                continue

            mutated[key] = inverted_val
            results.append(
                FuzzedPayload(
                    mutation_type=MutationType.TYPE_INVERSION,
                    description=desc,
                    target_field=key,
                    original_value=val,
                    mutated_payload=mutated,
                )
            )

        return results


class BoundaryValuesStrategy(BaseMutationStrategy):
    """Injects boundary numbers, extreme lengths, and null values."""

    def generate(
        self,
        schema: Dict[str, Any],
        baseline: Dict[str, Any],
    ) -> List[FuzzedPayload]:
        results: List[FuzzedPayload] = []
        if not isinstance(baseline, dict):
            return results

        for key, val in baseline.items():
            # Null injection
            mut_null = copy.deepcopy(baseline)
            mut_null[key] = None
            results.append(
                FuzzedPayload(
                    mutation_type=MutationType.NULL_INJECTION,
                    description=f"Injected null into field '{key}'",
                    target_field=key,
                    original_value=val,
                    mutated_payload=mut_null,
                )
            )

            # Numbers: negative, zero, max int
            if isinstance(val, (int, float)):
                for extreme in [-1, -999999, 0, 999999999999]:
                    mut_ext = copy.deepcopy(baseline)
                    mut_ext[key] = extreme
                    results.append(
                        FuzzedPayload(
                            mutation_type=MutationType.BOUNDARY_VALUES,
                            description=f"Injected boundary number {extreme} into field '{key}'",
                            target_field=key,
                            original_value=val,
                            mutated_payload=mut_ext,
                        )
                    )

            # Strings: empty string, giant token bomb
            if isinstance(val, str):
                # Empty string
                mut_empty = copy.deepcopy(baseline)
                mut_empty[key] = ""
                results.append(
                    FuzzedPayload(
                        mutation_type=MutationType.BOUNDARY_VALUES,
                        description=f"Injected empty string into field '{key}'",
                        target_field=key,
                        original_value=val,
                        mutated_payload=mut_empty,
                    )
                )

                # Giant string / token bomb (5,000 characters)
                mut_bomb = copy.deepcopy(baseline)
                mut_bomb[key] = "TOKEN_BOMB_A" * 500
                results.append(
                    FuzzedPayload(
                        mutation_type=MutationType.TOKEN_BOMB,
                        description=f"Injected 6,000-char token bomb into field '{key}'",
                        target_field=key,
                        original_value=val,
                        mutated_payload=mut_bomb,
                    )
                )

        return results
