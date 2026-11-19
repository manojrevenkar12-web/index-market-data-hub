# 1. A simulated market with a hidden truth

Status: accepted

Index closes cannot be checked against reality without licensed vendor data and the exchanges' own closes. The
project therefore simulates the market (true closes, FX, splits, dividends, renames, reused tickers) and three
vendors that report it with realistic faults: missing quotes, repeated prices, bad ticks, pence labelled as pounds,
late files, lagging identifiers and wrong, late or missing corporate-action notices. Only the evaluation sees the
truth. Every design reads the same parsed files, drawn with keyed luck, so differences between designs come from
the designs. A second, independent index engine in the world computes the true levels; the product calculator must
agree with it to 1e-9 on the true market, so every index error in the reports comes from data, not arithmetic.
