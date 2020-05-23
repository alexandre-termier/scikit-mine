"""SLIM pattern discovery"""

# Authors: Rémi Adon <remi.adon@gmail.com>
# License: BSD 3 clause

from collections import defaultdict
from functools import reduce
from itertools import chain
import warnings

import numpy as np
import pandas as pd
from roaringbitmap import RoaringBitmap

from ..base import BaseMiner
from ..utils import lazydict


def make_codetable(D: pd.Series):
    """
    Applied on an original dataset this makes up a standard codetable
    """
    codetable = defaultdict(RoaringBitmap)
    for idx, transaction in enumerate(D):
        for item in transaction:
            codetable[item].add(idx)
    return pd.Series(codetable)

def cover(itemsets: list, D: pd.DataFrame):
    """ assert itemset are sorted in Standard Cover Order
    D must be a pandas DataFrame containing boolean values
    """
    covers = list()
    mat = D.values

    _itemsets = list(map(D.columns.get_indexer, itemsets))

    for iset in _itemsets:
        parents = (v for k, v in zip(_itemsets, covers) if not set(iset).isdisjoint(k))
        rows_left = reduce(RoaringBitmap.union, parents, RoaringBitmap())
        rows_left.flip_range(0, len(D))
        _mat = mat[rows_left][:, iset]
        bools = _mat.all(axis=1)
        rows_where = np.where(bools)[0]
        rows_where += rows_left.min()  # pad indexes
        covers.append(RoaringBitmap(rows_where))

    return pd.Series(covers, index=itemsets)


def generate_candidates(codetable, stack=None):
    """
    assumes codetable is sorted in Standard Cover Order
    """
    res = list()
    for idx, (X, X_usage) in enumerate(codetable.iteritems()):
        Y = codetable.iloc[idx + 1:]
        XY_usage = Y.apply(lambda e: e.intersection_len(X_usage)).astype(np.uint32)
        XY_usage = XY_usage[XY_usage != 0]
        XY_usage.index = XY_usage.index.map(X.union)
        if stack is not None:
            XY_usage = XY_usage[~XY_usage.index.isin(stack)]
        if not XY_usage.empty:
            best_XY = XY_usage.idxmax()
            res.append(best_XY)
    return res

class SLIM(BaseMiner): # TODO : inherit MDLOptimizer
    """SLIM: Directly Mining Descriptive Patterns

    SLIM looks for a compressed representation of transactional data.
    This compressed representation if a set of descriptive patterns,
    and can be used to:
        - provide a natively interpretable modeling of this data
        - make predictions on new data, using this condensed representation as an encoding scheme

    Idea of early stopping is inspired from
    http://eda.mmci.uni-saarland.de/pres/ida14-slimmer-poster.pdf

    Parameters
    ----------
    n_iter_no_change: int, default=5
        Number of iteration to count before stopping optimization.
    tol: float, default=None
        Tolerance for the early stopping, in bits.
        When the compression size is not improving by at least tol for n_iter_no_change iterations,
        the training stops.
        Default to None, will be automatically computed considering the size of input data.
    pruning: bool, default=True
        Either to activate pruning or not. Pruned itemsets may be useful at
        prediction time, so it is usually recommended to set it to False
        to build a classifier. The model will be less concise, but will lead
        to more accurate predictions on average.

    Examples
    --------
    >>> import pandas as pd
    >>> from skmine.itemsets import SLIM
    >>> from skmine.preprocessing import TransactionEncoder
    >>> D = [['bananas', 'milk'], ['milk', 'bananas', 'cookies'], ['cookies', 'butter', 'tea']]
    >>> D = TransactionEncoder().fit_transform(D)
    >>> SLIM().fit(D)                       # doctest: +SKIP
    (butter, tea)         [2]
    (milk, bananas)    [0, 1]
    (cookies)          [1, 2]
    dtype: object

    References
    ----------
    .. [1]
        Smets, K & Vreeken, J
        "Slim: Directly Mining Descriptive Patterns", 2012

    .. [2] Gandhi, M & Vreeken, J
        "Slimmer, outsmarting Slim", 2014
    """
    def __init__(self, *, n_iter_no_change=5, tol=None, pruning=True, verbose=False):
        self.n_iter_no_change = n_iter_no_change
        self.tol = tol
        self._standard_codetable = None
        self._codetable = pd.Series([], dtype='object')
        self._supports = lazydict(self._get_support)
        self._model_size = None          # L(CT|D)
        self._data_size = None           # L(D|CT)
        self.pruning = pruning
        self.verbose = verbose

    def _get_support(self, itemset):
        U = reduce(RoaringBitmap.union, self._standard_codetable.loc[itemset])
        return len(U)

    def _get_cover_order_pos(self, codetable, cand):
        pos = 0
        while len(codetable[pos]) > len(cand):
            pos += 1
        while pos < len(codetable) and self._supports[codetable[pos]] > self._supports[cand]:
            if len(codetable[pos]) < len(cand):
                break
            pos += 1
        while pos < len(codetable) and codetable[pos] < cand:
            if len(codetable[pos]) < len(cand):
                break
            if self._supports[codetable[pos]] < self._supports[cand]:
                break
            pos += 1
        return pos

    def __repr__(self): return repr(self.codetable)  # TODO inherit from MDLOptimizer

    def _prefit(self, D):
        sct_d = {k: RoaringBitmap(np.where(D[k])[0]) for k in D.columns}
        self._standard_codetable = pd.Series(sct_d)
        usage = self._standard_codetable.map(len).astype(np.uint32)

        sorted_index = sorted(usage.index, key=lambda e: (-usage[e], e))
        self._codetable = self._standard_codetable.reindex(sorted_index, copy=True)
        self._codetable.index = self._codetable.index.map(lambda e: frozenset([e]))

        codes = -np.log2(usage / usage.sum())
        self._model_size = 2 * codes.sum()      # L(code_ST(X)) = L(code_CT(X)), because CT=ST
        self._data_size = (codes * usage).sum()

        return self

    def fit(self, D, y=None):
        """ fit SLIM on a transactional dataset

        This generate new candidate patterns and add those which improve compression,
        iteratibely refining the ``self.codetable``
        """
        if not isinstance(D, pd.DataFrame):
            D = pd.DataFrame(D)
        self._prefit(D)
        n_iter_no_change = 0
        is_better = False
        seen_cands = set()

        tol = self.tol or len(D) / 10

        while n_iter_no_change < self.n_iter_no_change:
            is_better = False
            candidates = generate_candidates(self._codetable, stack=seen_cands)
            for cand in candidates:
                n_iter_no_change_inner = 0
                CTc, data_size, model_size = self.evaluate(cand, D)
                diff = (self._model_size + self._data_size) - (data_size + model_size)

                seen_cands.add(cand)

                is_better = diff > tol
                if is_better:
                    if self.pruning:
                        prune_set = CTc.drop([cand])
                        prune_set = prune_set[prune_set.map(len) < self._codetable.map(len)]
                        prune_set = prune_set[prune_set.index.map(len) > 1]
                        CTc, data_size, model_size = self._prune(
                            CTc, D, prune_set, model_size, data_size
                        )

                    self._codetable = CTc
                    self._data_size = data_size
                    self._model_size = model_size
                    if self.verbose:
                        fmt = "data size : {:.2f} | model size : {:.2f}"
                        print(fmt.format(data_size, model_size))
                else:
                    n_iter_no_change_inner += 1
                    if n_iter_no_change_inner >= self.n_iter_no_change:
                        if self.verbose:
                            print('no improvement for {} iterations'.format(n_iter_no_change_inner))
                        break

            if not is_better:
                n_iter_no_change += 1

        return self

    def predict_proba(self, D):
        """Make predictions on a new transactional data

        This encodes transactions with the current codetable.

        Setting ``pruning`` to False when creating the model
        is recommended to make predictions.

        Example
        -------
        >>> from skmine.preprocessing import TransactionEncoder
        >>> D = [['bananas', 'milk'], ['milk', 'bananas', 'cookies'], ['cookies', 'butter', 'tea']]
        >>> te = TransactionEncoder()
        >>> D = te.fit_transform(D)
        >>> new_D = te.transform([['cookies', 'butter']])
        >>> slim = SLIM(pruning=False).fit(D)
        >>> slim.predict_proba(new_D)
        0    0.4
        dtype: float32
        """
        if not isinstance(D, pd.DataFrame): D = pd.DataFrame(D)
        codetable = self._codetable[self._codetable.map(len) > 0]
        covers = cover(codetable.index, D)
        mat = np.zeros(shape=(len(D), len(covers)))
        for idx, tids in enumerate(covers.values):
            mat[tids, idx] = 1
        mat = pd.DataFrame(mat, columns=covers.index)

        ct_codes = codetable.map(len) / codetable.map(len).sum()
        codes = (mat * ct_codes).sum(axis=1)
        return codes.astype(np.float32)

    def evaluate(self, candidate, D):
        """
        Evaluate ``candidate``, considering the current codetable and a dataset ``D``

        Parameters
        ----------
        candidate: frozenset
            a new candidate to be evaluated
        D: pd.Series
            a transactional dataset

        Returns
        -------
        (pd.Series, float, float, bool)
            updated (codetable, data size, model size
            and finally a boolean stating if compression improved
        """
        cand_pos = self._get_cover_order_pos(self._codetable.index, candidate)
        CTc_index = self._codetable.index.insert(cand_pos, candidate)

        CTc = cover(CTc_index, D)
        if self.verbose and not CTc.index.map(len).is_monotonic_decreasing:
            warnings.warn('codetable violates Standard Cover Order')
        data_size, model_size = self.compute_sizes(CTc)

        return CTc, data_size, model_size

    @property
    def codetable(self):
        """
        Returns
        -------
        pd.Series
            codetable containing patterns and ids of transactions in which they are used
        """
        return self._codetable[self._codetable.map(len) > 0]

    def get_standard_codes(self, index):
        """compute the size of a codetable index given the standard codetable"""
        flat_items = list(chain(*index))
        items, counts = np.unique(flat_items, return_counts=True)

        usages = self._standard_codetable.loc[items].map(len).astype(np.uint32)
        usages /= usages.sum()
        codes = -np.log2(usages)
        return codes * counts

    def compute_sizes(self, codetable):
        """
        Compute sizes for both the data and the model

        .. math:: L(D|CT)
        .. math:: L(CT|D)

        Parameters
        ----------
        codetable : pd.Series
            A series mapping itemsets to their usage tids

        Returns
        -------
        tuple(float, float)
            (data_size, model_size)
        """
        codetable = codetable[codetable.map(len) > 0]
        usages = codetable.map(len).astype(np.uint32)
        codes = -np.log2(usages / usages.sum())

        stand_codes = self.get_standard_codes(codetable.index)

        model_size = stand_codes.sum() + codes.sum() # L(CTc|D) = L(X|ST) + L(X|CTc)
        data_size = (codes * usages).sum()
        return data_size, model_size

    def _prune(self, codetable, D, prune_set, model_size, data_size): # pylint: disable= too-many-arguments
        """ post prune a codetable considering itemsets for which usage has decreased

        Parameters
        ----------
        codetable: pd.Series
        D: pd.Series
        prune_set: pd.Series
            subset of ``codetable`` for which usage has decreased
        models_size: float
            current model_size for ``codetable``
        data_size: float
            current data size when encoding ``D`` with ``codetable``

        Returns
        -------
        new_codetable, new_data_size, new_model_size: pd.Series, float, float
            a tuple containing the pruned codetable, and new model size and data size
            w.r.t this new codetable
        """
        while not prune_set.empty:
            cand = prune_set.map(len).idxmin()
            prune_set = prune_set.drop([cand])
            CTp_index = codetable.index.drop([cand])
            CTp = cover(CTp_index, D)
            d_size, m_size = self.compute_sizes(CTp)

            if d_size + m_size < model_size + data_size:
                decreased = CTp.map(len) < codetable[CTp.index].map(len)
                prune_set.update(CTp[decreased])
                codetable = CTp
                data_size, model_size = d_size, m_size

        return codetable, data_size, model_size
