# DECISIONS.md

1. **Indexes**
   I created indexes on `employees.emp_code` for preventing duplicate creation and compound unique index on `attendance_logs.(emp_code, date)` guaranteeing one record per employee per day and making punch-ins safe in concurrent environment.

2. **Punch-in race**
   Both requests compute the attendance date and attempt to insert. Because of the unique compound index on `(emp_code, date)`, MongoDB atomically accepts one insert and rejects the other.

3. **Ties**
   The leaderboard uses standard ranking via `$setWindowFields` with `$rank: {}` (1, 2, 2, 4). Filtering by `rank <= limit` occurs after ranking, so tied employees at the boundary are all included.

4. **Headcount**
   The pipeline starts from the `employees` collection filtered by `joined_on <= month_end`, grouping by department first and then performs a `$lookup` into `attendance_logs`. Employees without logs still contribute to the initial `$group` count.

5. **One thing to change for 100x data**
   Pre-aggregating department wise rollup using MongoDB, which eliminates on demand aggregation across millions of documents.
