"""Exception types for the dataset layer.

Kept flat and small, mirroring ``gitscore.github.exceptions``: one base
class plus two concrete cases callers actually branch on.
"""


class DatasetError(Exception):
    """Base class for all dataset-construction errors."""


class DatasetSchemaError(DatasetError):
    """The dataframe's *shape* is wrong.

    Wrong column set, wrong column order, or a forbidden identifier /
    timestamp column present. Raised before any value-level checks.
    """


class DatasetValidationError(DatasetError):
    """The dataframe's shape is right but its *values* are malformed.

    Nulls in required columns, non-numeric data in a numeric column,
    non-boolean data in a boolean column, or a non-string categorical
    value. Fails loudly rather than silently coercing.
    """
