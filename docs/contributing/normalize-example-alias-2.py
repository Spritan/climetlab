from climetlab.decorators import normalize

DATES = dict(
    april=["20210401", "20210402", "20210403"],
    june=["20210610", "20210611"],
)
@normalize("x", "date-list(YYYYMMDD)", aliases=DATES)
def f(x):
    return x

assert f("2021-06-10") == ["20210610"]
assert f("june") == ["20210610", "20210611"]