from itertools import compress

import numpy as np
import pandas
import pandas as pd
import pytest
from sortedcontainers import SortedDict

from pyroaring import BitMap as Bitmap

from ..slim import SLIM, _to_vertical, generate_candidates, _log2


@pytest.fixture
def D():
    return pd.Series(["ABC"] * 5 + ["AB", "A", "B"])


@pytest.fixture
def codetable():
    return SortedDict({
        frozenset({'bananas'}): Bitmap([0, 1]),
        frozenset({'cookies'}): Bitmap([1, 2]),
        frozenset({'milk'}): Bitmap([0, 1]),
        frozenset({'butter'}): Bitmap([2]),
        frozenset({'tea'}): Bitmap([2])
    })


def to_tabular_df(D):
    return D.map(list).str.join("|").str.get_dummies(sep="|")


def _id(args):
    return args


def test_to_vertical(D):
    vert = _to_vertical(D)
    assert list(vert.keys()) == list("ABC")

    vert2 = _to_vertical(D, stop_items={"A"})
    assert list(vert2.keys()) == list("BC")


def test_complex_evaluate():
    """
    A   B   C
    A   B
    A       C
        B
        B   C   D   E
    A   B   C   D   E
    """
    slim = SLIM()
    D = ["ABC", "AB", "AC", "B", "BCDE", "ABCDE"]
    slim.prefit(D)

    u = {
        frozenset("ABC"): {0, 5},
        frozenset("AB"): {1},
        frozenset("BC"): {4},
        frozenset("DE"): {4, 5},
        frozenset("B"): {3},
        frozenset("A"): {2},
        frozenset("C"): {2},
        frozenset("D"): {},
        frozenset("E"): {},
    }

    u = {k: Bitmap(v) for k, v in u.items()}

    slim.codetable_.update(u)

    cand = frozenset("CDE")
    _, _, updated = slim.evaluate(cand)

    diff = {k: v for k, v in updated.items() if k in u and u[k] != v}

    assert len(diff) == 3
    assert len(updated[cand]) == 1  # {4}
    assert len(updated[frozenset("BC")]) == 0  # {4} -> {}
    assert len(updated[frozenset("B")]) == 2  # {3} -> {3, 4}
    assert len(updated[frozenset("DE")]) == 1  # {4, 5} -> {5}


def test_complex_evaluate_2():
    """
    A   B   C
    A   B
    A       C
        B
        B   C   D   E
    A   B   C   D   E
    """
    slim = SLIM(pruning=False)
    D = ["ABC", "AB", "AC", "B", "BCDE", "ABCDE"]
    slim.prefit(D)

    u = {
        frozenset("CDE"): {4, 5},
        frozenset("AB"): {0, 1, 5},
        frozenset("BC"): {},
        frozenset("DE"): {},
        frozenset("B"): {3, 4},
        frozenset("A"): {2},
        frozenset("C"): {0, 2},
        frozenset("D"): {},
        frozenset("E"): {},
    }

    u = {k: Bitmap(v) for k, v in u.items()}

    slim.codetable_.update(u)

    cand = frozenset("ABC")
    _, _, updated = slim.evaluate(cand)

    diff = {k: v for k, v in updated.items() if k in u and u[k] != v}

    assert len(diff) == 4
    assert len(updated[cand]) == 2
    assert len(updated[frozenset("CDE")]) == 1  # {4, 5} -> {4}
    assert len(updated[frozenset("DE")]) == 1  # {} -> {5}
    assert len(updated[frozenset("AB")]) == 1  # {0, 1, 5} -> {1}
    assert len(updated[frozenset("C")]) == 1  # {0, 2} -> {2}


def test_generate_candidate_1():
    codetable = SortedDict(
        {
            frozenset("A"): Bitmap(range(0, 7)),
            frozenset("B"): Bitmap([0, 1, 2, 3, 4, 5, 7]),
            frozenset("C"): Bitmap(range(0, 5)),
        }
    )
    print(codetable)

    new_candidates = generate_candidates(codetable)
    print(new_candidates)
    assert new_candidates == [
        (frozenset("AB"), 6),
        (frozenset("BC"), 5),
    ]


def test_generate_candidate_2():
    usage = [Bitmap(_) for _ in (range(6), [6], [7], range(5))]

    index = list(map(frozenset, ["AB", "A", "B", "C"]))
    codetable = SortedDict(zip(index, usage))

    new_candidates = generate_candidates(codetable)
    assert new_candidates == [(frozenset("ABC"), 5)]


def test_generate_candidate_stack():
    usage = [Bitmap(_) for _ in (range(6), [6, 7], [6, 8], [])]

    index = list(map(frozenset, ["ABC", "A", "B", "C"]))

    codetable = SortedDict(zip(index, usage))

    new_candidates = generate_candidates(codetable, stack={frozenset("AB")})
    assert new_candidates == []


@pytest.mark.parametrize("preproc", [to_tabular_df, _id])
def test_prefit(preproc):
    D = pd.Series(["ABC"] * 5 + ["BC", "B", "C"])
    D = preproc(D)
    slim = SLIM().prefit(D)
    np.testing.assert_almost_equal(slim.model_size_, 9.614, 3)
    np.testing.assert_almost_equal(slim.data_size_, 29.798, 3)
    assert len(slim.codetable_) == 3
    assert list(slim.codetable_) == list(map(frozenset, ["B", "C", "A"]))


def test_get_support(D):
    slim = SLIM().prefit(D)
    assert len(slim.get_support(*frozenset("ABC"))) == 5
    assert len(slim.get_support("C")) == 5
    assert slim.get_support.cache_info().currsize > 0


def test_compute_sizes_1(D):
    slim = SLIM()
    slim.prefit(D)
    CT = {
        frozenset("ABC"): Bitmap(range(0, 5)),
        frozenset("AB"): Bitmap([5]),
        frozenset("A"): Bitmap([6]),
        frozenset("B"): Bitmap([7]),
    }

    data_size, model_size = slim._compute_sizes(CT)
    np.testing.assert_almost_equal(data_size, 12.4, 2)
    np.testing.assert_almost_equal(model_size, 20.25, 2)


def test_compute_sizes_2(D):
    slim = SLIM()
    slim.prefit(D)
    CT = {
        frozenset("ABC"): Bitmap(range(0, 5)),
        frozenset("A"): Bitmap([5, 6]),
        frozenset("B"): Bitmap([5, 7]),
        frozenset("C"): Bitmap(),
    }

    data_size, model_size = slim._compute_sizes(CT)
    np.testing.assert_almost_equal(data_size, 12.92, 2)
    np.testing.assert_almost_equal(model_size, 12.876, 2)


@pytest.mark.parametrize("preproc,pass_y", ([to_tabular_df, False], [_id, True]))
def test_fit_pruning(D, preproc, pass_y):
    slim = SLIM(pruning=True)
    y = None if not pass_y else np.array([1] * len(D))
    D = preproc(D)
    self = slim.fit(D, y=y)
    assert list(self.codetable_) == list(map(frozenset, ["ABC", "A", "B", "C"]))


@pytest.mark.parametrize("preproc,pass_y", ([to_tabular_df, True], [_id, False]))
def test_fit_no_pruning(D, preproc, pass_y):
    slim = SLIM(pruning=False)
    y = None if not pass_y else np.array([1] * len(D))
    D = preproc(D)
    self = slim.fit(D, y=y)
    assert list(self.codetable_) == list(map(frozenset, ["ABC", "AB", "A", "B", "C"]))


def test_prune(D):
    slim = SLIM(pruning=False).fit(D)
    prune_set = [frozenset("AB")]

    new_codetable, new_data_size, new_model_size = slim._prune(
        slim.codetable_, prune_set, slim.model_size_, slim.data_size_
    )

    assert list(new_codetable) == list(map(frozenset, ["ABC", "A", "B", "C"]))
    np.testing.assert_almost_equal(new_data_size, 12.92, 2)

    total_enc_size = new_data_size + new_model_size
    np.testing.assert_almost_equal(total_enc_size, 26, 0)


def test_prune_empty(D):
    slim = SLIM(pruning=False).fit(D)
    prune_set = [frozenset("ABC")]

    # nothing to prune so we should get the exact same codetable

    new_codetable, new_data_size, new_model_size = slim._prune(
        slim.codetable_, prune_set, slim.model_size_, slim.data_size_
    )

    assert list(new_codetable) == list(map(frozenset, ["ABC", "AB", "A", "B", "C"]))


def test_decision_function(D):
    slim = SLIM(pruning=True).fit(D)

    new_D = pd.Series(["AB"] * 2 + ["ABD", "AC", "B"])
    new_D = new_D.str.join("|").str.get_dummies(sep="|")

    dists = slim.decision_function(new_D)
    assert dists.dtype == np.float32
    assert len(dists) == len(new_D)
    np.testing.assert_array_almost_equal(
        dists.values, np.array([-1.17, -1.17, -1.17, -2.17, -2.17]), decimal=2
    )


def test_cover_discover_compat(D):
    s = SLIM()
    s.fit(D)
    mat = s.discover(usage_tids=False, singletons=True) * s.cover(D)
    assert mat.notna().sum().all()


def test_reconstruct(D):
    slim = SLIM().fit(D)
    s = slim.reconstruct().map("".join)  # originally a string so we have to join
    true_s = pd.Series(["ABC"] * 5 + ["AB", "A", "B"])
    pd.testing.assert_series_equal(s, true_s)


@pytest.mark.parametrize("k", [1, 2])
def test_k(D, k):
    slim = SLIM(pruning=False, k=k).fit(D)
    assert len(slim.discover()) == k


def test_interactive(D):
    answers = [True, False]
    est_usages = [6, 5]
    slim = SLIM(pruning=False)
    slim.prefit(D)
    candidates = slim.generate_candidates()
    for true_est_usage, (cand, est_usage) in compress(
            zip(est_usages, candidates), answers
    ):
        assert est_usage == true_est_usage
        slim.update(cand)

    assert len(slim.discover(singletons=False)) == sum(answers)


def test_standard_candidate_order(codetable):
    slim = SLIM()
    slim.codetable_ = codetable
    sct = {
        'bananas': Bitmap([0, 1]), 'milk': Bitmap([0, 1]), 'cookies': Bitmap([1, 2]), 'butter': Bitmap([2]),
        'tea': Bitmap([2])
    }
    slim.standard_codetable_ = pd.Series(data=sct, index=['bananas', 'milk', 'cookies', 'butter', 'tea'])
    print(slim.codetable_)
    print(slim.standard_codetable_)
    sorted_codetable = SortedDict(slim._standard_candidate_order, slim.codetable_)
    print(sorted_codetable)
