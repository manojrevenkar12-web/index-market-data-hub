# 3. Identifiers valid on a date, and linked renames

Status: accepted

Each vendor keys quotes differently (ISIN, RIC, ticker plus MIC). After a rename the old ticker can be given to a
newcomer within days, and a vendor that keeps the old identifier then quotes the wrong company under it. The security
master keeps every identifier with the dates it was valid; a quote maps only through an identifier valid on its trade
date. Because a RIC's root is the exchange ticker, one vendor's RIC rename also moves the ticker and the other way
round, so a vendor that missed its own rename notice is not trusted under the old ticker. On development the same hub
with an undated map was off on 74 closes instead of 0.
