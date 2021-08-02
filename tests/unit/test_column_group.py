import numpy as np

from nvtabular import ColumnGroup, Dataset, Workflow, dispatch
from nvtabular.column_selector import ColumnSelector
from nvtabular.ops import Categorify, Rename
from tests.conftest import assert_eq


def test_column_group_select():
    df = dispatch._make_df({"a": [1, 4, 9, 16, 25], "b": [0, 1, 2, 3, 4], "c": [25, 16, 9, 4, 1]})

    input_features = ColumnGroup(ColumnSelector(["a", "b", "c"]))
    # pylint: disable=unnecessary-lambda
    sqrt_features = input_features[["a", "c"]] >> (lambda col: np.sqrt(col))
    plus_one_features = input_features["b"] >> (lambda col: col + 1)
    features = sqrt_features + plus_one_features

    workflow = Workflow(features)
    df_out = workflow.fit_transform(Dataset(df)).to_ddf().compute(scheduler="synchronous")

    expected = dispatch._make_df()
    expected["a"] = np.sqrt(df["a"])
    expected["c"] = np.sqrt(df["c"])
    expected["b"] = df["b"] + 1

    assert_eq(expected, df_out)


def test_nested_column_group():
    # TODO: Sort out how to do nesting/sub-groups in the DSL for building up graphs
    # This test appears to be the only place in the test suite that relies on that
    # behavior. The key challenges here are that `>>`'ing a list on to an operator
    # is no longer allowed, and that a `ColumnSelector` should never contain a
    # `ColumnGroup`.
    df = dispatch._make_df(
        {
            "geo": ["US>CA", "US>NY", "CA>BC", "CA>ON"],
            "user": ["User_A", "User_A", "User_A", "User_B"],
        }
    )

    geo_selector = ColumnSelector(["geo"])
    country = geo_selector >> (lambda col: col.str.slice(0, 2)) >> Rename(postfix="_country")

    # make sure we can do a 'combo' categorify (cross based) of country+user
    # as well as categorifying the country and user columns on their own
    cats = country + "user" + [country + "user"] >> Categorify(encode_type="combo")

    workflow = Workflow(cats)
    df_out = workflow.fit_transform(Dataset(df)).to_ddf().compute(scheduler="synchronous")

    geo_country = df_out["geo_country"]
    assert geo_country[0] == geo_country[1]  # rows 0,1 are both 'US'
    assert geo_country[2] == geo_country[3]  # rows 2,3 are both 'CA'

    user = df_out["user"]
    assert user[0] == user[1] == user[2]
    assert user[3] != user[2]

    geo_country_user = df_out["geo_country_user"]
    assert geo_country_user[0] == geo_country_user[1]  # US / userA
    assert geo_country_user[2] != geo_country_user[0]  # same user but in canada

    # TODO: Sort out how to check this since >>'ing a list in to an op no longer works

    # make sure we get an exception if we nest too deeply (can't handle arbitrarily deep
    # nested column groups - and the exceptions we would get in operators like Categorify
    # are super confusing for users)
    # with pytest.raises(ValueError):
    #   cats = [[country + "user"] + country + "user"] >> Categorify(encode_type="combo")
