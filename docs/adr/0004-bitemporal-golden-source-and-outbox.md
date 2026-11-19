# 4. A bitemporal golden source and an outbox

Status: accepted

Index providers publish corrections, not silent edits. Every golden price and index level is stored with the time
it was recorded; a restatement (late files the next morning) adds a version and closes the previous one. Queries
`as_of` a moment return exactly what was published then. Publications are written to an outbox table in the same
transaction as the level; a relay forwards them to Pub/Sub with the index as ordering key, so a correction never
overtakes the close it corrects and a crash between write and publish loses nothing.
