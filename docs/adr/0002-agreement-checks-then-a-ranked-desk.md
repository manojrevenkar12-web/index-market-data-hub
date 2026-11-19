# 2. Agreement first, then checks, then a ranked desk

Status: accepted

A golden price is the median of the largest group of vendors that agree within 5 bp. Before grouping, the hub
repairs a quote 80 to 125 times its peers (pence labelled as pounds) and drops a quote that repeats the vendor's
previous close while the others moved. With one vendor left, a move further than 6% from the peer-expected price
is not accepted: the last valid price is held and the question goes to the desk. Splits are applied when two
vendors agree or when the price confirms the announced ratio; a price move that looks like an unannounced split goes
to the desk.

The unit check compares each quote with yesterday's golden price moved by the peers, and with the other vendors
only when there is no yesterday: with two vendors left, one mislabelled quote would otherwise make the good one look
mislabelled too (found in the dashboard after the held-out run, see docs/heldout.md).

Questions are ranked by index weight times the size of the doubt, and the desk answers at most 12 a day before
the close. Ranking matters: the same desk working in instrument order used 145 lookups on development and 214 on
held-out instead of 13 and 12, and on held-out still let two closes through.
