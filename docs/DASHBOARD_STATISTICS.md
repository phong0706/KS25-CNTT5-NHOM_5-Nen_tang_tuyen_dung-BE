# Dashboard statistics API

Both endpoints require a bearer token. Employer statistics are scoped to the
authenticated employer; admin statistics require the `admin` role.

```text
GET /api/employer/dashboard/stats
GET /api/admin/dashboard/stats
```

Optional inclusive date filters use `YYYY-MM-DD`:

```text
?from_date=2026-11-01&to_date=2026-11-20
```

The API returns HTTP 400 for an invalid date or when `from_date` is later than
`to_date`.

Employer metrics include current job counts by status, cumulative views,
applications and their statuses for the selected period, unviewed applications,
the offer rate, upcoming interviews, and jobs created during the selected
period. The offer rate is `OFFERED applications / applications in period * 100`.
Views are cumulative because the database stores a counter, not per-view
timestamps. Upcoming interviews count scheduled interviews from now onward and
are independent of the selected date range.

Admin metrics include current user-role, active-user, company, job-status, and
total-job counts. New users, companies by their declared industry, jobs by
category, and applications by day are filtered by their creation/submission
date. `total_applications` is also scoped to the selected date range. When a
date is omitted, that side of the range is unbounded.
