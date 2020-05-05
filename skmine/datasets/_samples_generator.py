"""
Generate samples of synthetic datasets.
Mainly for benchmarks and experiments
"""

import numpy as np
import pandas as pd


def make_transactions(n_transactions=1000,
                      n_items=100,
                      avg_transaction_size=10,
                      random_state=None):
    """
    Generate a transactional dataset with predefined properties

    see: https://liris.cnrs.fr/Documents/Liris-3716.pdf

    Transaction sizes follow a normal distribution, centered around
    ``avg_transaction_size``.
    Individual items are integer values between 0 and ``n_items``.

    Parameters
    ---------
    n_transactions: int, default=1000
        The number of transactions to generate
    n_items: int, default=100
        The number of indidual items, i.e the size of the set of symbols
    avg_transaction_size: int, default=10
        The average size for a transactions
    random_state : int, RandomState instance, default=None
        Determines random number generation for dataset creation. Pass an int
        for reproducible output across multiple function calls.
        See :term:`Glossary <random_state>`.

    References
    ----------
    .. [1] F. Flouvat, F. De Marchi, JM. Petit
           "A new classification of datasets for frequent itemsets", 2009

    Example
    -------
    >>> from skmine.datasets import make_transactions
    >>> make_transactions(n_transactions=5, n_items=20, avg_transaction_size=5)
    0                  [7, 6, 11, 13, 12, 17, 1, 2, 16, 8]
    1                 [15, 10, 2, 0, 6, 18, 5, 17, 16, 13]
    2               [10, 5, 19, 17, 16, 11, 14, 3, 12, 13]
    3             [16, 10, 11, 0, 5, 7, 15, 13, 18, 3, 14]
    4    [10, 12, 13, 2, 1, 19, 9, 17, 0, 5, 7, 11, 18, 8]
    dtype: object

    Raises
    ------
    ValueError
        if ``n_items`` is lower than ``avg_transaction_size`` * 2,
        which is not suited to generate well balanced
        transactions containing distinct values.

    Returns
    -------
    pd.Series: a Series of shape (``n_transactions``,)
        Earch entry is a list of integer values
    """
    if avg_transaction_size * 2 > n_items:
        raise ValueError("""
            Average transaction size bigger than n_items // 2.
            Please set a lower ``avg_transaction_size``, or a higher ``n_items``
        """)
    generator = np.random.RandomState(random_state)  # pylint: disable= no-member

    choices = np.arange(n_items)
    t_sizes = generator.binomial(
        n=avg_transaction_size * 2,
        p=.5,  # centered around avg_transaction_size
        size=n_transactions
    )

    D = [generator.choice(choices, size, replace=False) for size in t_sizes]
    return pd.Series(D)