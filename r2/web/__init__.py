"""
The report viewer: a local web service that renders the reports coding
agents write into `.reportlab/reports/`, and links every path they cite to
the lines of code it is about.

Needs the `web` extra. One daemon serves every attached project on the
machine, on 127.0.0.1 only. Three things here keep a browser from reading
the user's filesystem: path confinement (`r2.core.reports.scan.confine`),
the bearer token, and the `Origin` and `Host` checks (`r2.web.security`).
"""
