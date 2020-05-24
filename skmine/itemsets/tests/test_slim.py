from ..slim import make_codetable
from ..slim import cover
from ..slim import generate_candidates
from ..slim import SLIM
from ...preprocessing.transaction_encoder import TransactionEncoder


import pytest
from roaringbitmap import RoaringBitmap
import pandas as pd
import numpy as np

def dense_D():
    D = ['ABC'] * 5 + ['AB', 'A', 'B']
    D = TransactionEncoder().fit_transform(D)
    return D

def sparse_D():
    D = ['ABC'] * 5 + ['AB', 'A', 'B']
    D = TransactionEncoder(sparse_output=True).fit_transform(D)
    return D

def test_make_cotetable():
    D = ['ABC'] * 5 + ['AB', 'A', 'B']
    standard_codetable = make_codetable(D)
    pd.testing.assert_series_equal(
        standard_codetable.map(len),
        pd.Series([7, 7, 5], index=['A', 'B', 'C'])
    )

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_cover_1(D):
    isets = list(map(frozenset, [
        'ABC', 'A', 'B', 'C',
    ]))

    covers = cover(isets, D)
    pd.testing.assert_series_equal(
        pd.Series([5, 2, 2, 0], index=isets),
        covers.map(len),
    )

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_cover_2(D):
    isets = list(map(frozenset, [
        'ABC', 'AB', 'A', 'B', 'C',
    ]))

    covers = cover(isets, D)
    pd.testing.assert_series_equal(
        pd.Series([5, 1, 1, 1, 0], index=isets),
        covers.map(len),
    )

def test_cover_3():
    D = ['ABC'] * 5 + ['AB', 'A', 'B', 'DE', 'CDE']
    D = TransactionEncoder().fit_transform(D)
    isets = list(map(frozenset, [
        'ABC', 'DE', 'A', 'B', 'C',
    ]))

    covers = cover(isets, D)
    pd.testing.assert_series_equal(
        pd.Series([5, 2, 2, 2, 1], index=isets),
        covers.map(len),
    )

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_cover_4(D):
    isets = list(map(frozenset, [
        'BC', 'AB', 'A', 'B', 'C',
    ]))

    covers = cover(isets, D)
    pd.testing.assert_series_equal(
        pd.Series([5, 1, 6, 1, 0], index=isets),
        covers.map(len),
    )

def test_generate_candidate_1():
    D = ['ABC'] * 5 + ['AB', 'A', 'B']
    codetable = make_codetable(D)
    codetable.index = codetable.index.map(lambda e: frozenset([e]))
    new_candidates = generate_candidates(codetable)
    assert new_candidates.to_dict() == {
        frozenset('AB'): 6,
        frozenset('BC'): 5,
    }

def test_generate_candidate_2():
    usage = list(map(RoaringBitmap, [
        range(6),
        [6],
        [7],
        range(5),
    ]))
    index = list(map(frozenset, ['AB', 'A', 'B', 'C']))
    codetable = pd.Series(usage, index=index)

    new_candidates = generate_candidates(codetable)
    assert new_candidates.to_dict() == {frozenset('ABC'): 5}

def test_generate_candidate_stack():
    usage = list(map(RoaringBitmap, [
        range(6),
        [6, 7],
        [6, 8],
        [],
    ]))
    index = list(map(frozenset, ['ABC', 'A', 'B', 'C']))
    codetable = pd.Series(usage, index=index)

    new_candidates = generate_candidates(codetable, stack={frozenset('AB')})
    assert new_candidates.to_dict() == {}


def test_cover_order_pos_1():
    slim = SLIM()._prefit(dense_D())
    codetable = ['A', 'B', 'C']
    codetable = list(map(frozenset, codetable))
    cand = frozenset('ABC')

    pos = slim._get_cover_order_pos(codetable, cand)

    assert pos == 0
    assert cand in slim._supports.keys()

def test_cover_order_pos_2():
    slim = SLIM()
    slim._prefit(dense_D())
    codetable = ['ABC', 'B', 'C']
    codetable = list(map(frozenset, codetable))
    cand = frozenset('AB')

    pos = slim._get_cover_order_pos(codetable, cand)

    assert pos == 1
    assert cand in slim._supports.keys()


def test_cover_order_pos_3():
    """ lower size but higher support"""
    slim = SLIM()
    slim._supports = {
        'ABC': 5, 
        'AB': 7,
        'BC': 8,
        'B': 10,
    }
    codetable = ['ABC', 'BC', 'B']
    cand = 'AB'

    pos = slim._get_cover_order_pos(codetable, cand)

    assert pos == 2
    assert cand in slim._supports.keys()


@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_cover_order_pos_support_needed(D):
    "support computation is needed to get the position in cover order"
    slim = SLIM()
    slim._prefit(D)
    codetable = ['ABC', 'B', 'C']
    codetable = list(map(frozenset, codetable))
    cand = frozenset('A')

    pos = slim._get_cover_order_pos(codetable, cand)

    assert pos == 1
    assert cand in slim._supports.keys()


def test_prefit():
    D = ['ABC'] * 5 + ['BC', 'B', 'C']
    D = TransactionEncoder().fit_transform(D)
    slim = SLIM()
    slim._prefit(D)
    np.testing.assert_almost_equal(slim._model_size, 9.614, 3)
    np.testing.assert_almost_equal(slim._data_size, 29.798, 3)
    assert len(slim.codetable) == 3
    assert slim.codetable.dtype == np.object
    assert slim.codetable.index.tolist() == list(map(frozenset, ['B', 'C', 'A']))

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_get_standard_size_1(D):
    slim = SLIM()
    slim._prefit(D)
    CT_index = ['ABC', 'AB', 'A', 'B']
    codes = slim.get_standard_codes(CT_index)
    pd.testing.assert_series_equal(
        codes,
        pd.Series([4.32, 4.32, 1.93], index=list('ABC')),
        check_less_precise=2
    )

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_get_standard_size_2(D):
    slim = SLIM()
    slim._prefit(D)
    CT_index = ['ABC', 'A', 'B']
    codes = slim.get_standard_codes(CT_index)
    pd.testing.assert_series_equal(
        codes,
        pd.Series([2.88, 2.88, 1.93], index=list('ABC')),
        check_less_precise=2
    )

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_compute_sizes_1(D):
    slim = SLIM()
    slim._prefit(D)
    CT = pd.Series({
        frozenset('ABC'): RoaringBitmap(range(0, 5)),
        frozenset('AB'): RoaringBitmap([5]),
        frozenset('A'): RoaringBitmap([6]),
        frozenset('B'): RoaringBitmap([7]),
    })

    data_size, model_size = slim.compute_sizes(CT)
    np.testing.assert_almost_equal(data_size, 12.4, 2)
    np.testing.assert_almost_equal(model_size, 20.25, 2)

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_compute_sizes_2(D):
    slim = SLIM()
    slim._prefit(D)
    CT = pd.Series({
        frozenset('ABC'): RoaringBitmap(range(0, 5)),
        frozenset('A'): RoaringBitmap([5, 6]),
        frozenset('B'): RoaringBitmap([5, 7]),
    })

    data_size, model_size = slim.compute_sizes(CT)
    np.testing.assert_almost_equal(data_size, 12.92, 2)
    np.testing.assert_almost_equal(model_size, 12.876, 2)

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_fit_no_pruning(D):
    slim = SLIM(pruning=False)
    self = slim.fit(D)
    assert self._codetable.index.tolist() == list(map(frozenset, ['ABC', 'AB', 'A', 'B', 'C']))

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_fit(D):
    slim = SLIM(pruning=True)
    self = slim.fit(D)
    assert self._codetable.index.tolist() == list(map(frozenset, ['ABC', 'A', 'B', 'C']))


@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_fit_ndarray(D):
    slim = SLIM(pruning=True)
    self = slim.fit(D.values)
    assert self._codetable.index.tolist() == list(map(frozenset, [[0, 1, 2], [0], [1], [2]]))

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_prune(D):
    slim = SLIM(pruning=False).fit(D)
    prune_set = slim.codetable.loc[[frozenset('AB')]]


    new_codetable, new_data_size, new_model_size = slim._prune(
        slim._codetable, D, prune_set, slim._model_size, slim._data_size
    )

    assert new_codetable.index.tolist() == list(map(frozenset, ['ABC', 'A', 'B', 'C']))
    np.testing.assert_almost_equal(new_data_size, 12.92, 2)

    total_enc_size = new_data_size + new_model_size
    np.testing.assert_almost_equal(total_enc_size, 26, 0)

@pytest.mark.parametrize("D", [dense_D(), sparse_D()])
def test_prune_empty(D):
    slim = SLIM(pruning=False).fit(D)
    prune_set = slim.codetable.loc[[frozenset('ABC')]]

    # nothing to prune so we should get the exact same codetable

    new_codetable, new_data_size, new_model_size = slim._prune(
        slim._codetable, D, prune_set, slim._model_size, slim._data_size
    )

    assert new_codetable.index.tolist() == list(map(frozenset, ['ABC', 'AB', 'A', 'B', 'C']))

@pytest.mark.parametrize('sparse', [False, True])
def test_predict_proba(sparse):
    te = TransactionEncoder(sparse_output=sparse)
    D = te.fit_transform(['ABC'] * 5 + ['AB', 'A', 'B'])
    slim = SLIM().fit(D)

    new_D = ['AB'] * 2 + ['ABD', 'AC', 'B']
    new_D = te.fit_transform(new_D)

    probas = slim.predict_proba(new_D)
    assert probas.dtype == np.float32
    assert len(probas) == len(new_D)
    np.testing.assert_array_almost_equal(
        probas.values,
        np.array([.44, .44, .44, .22, .22]),
        decimal=2
    )

