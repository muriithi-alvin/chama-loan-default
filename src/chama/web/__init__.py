"""The web interface's server (Milestone 4, decisions D-026 and D-027).

A JSON API in FastAPI that the Next.js pages in frontend/ call, and a worker
that reads scanned pages and runs the pipeline. Layout:

- app.py, auth.py, errors.py: the FastAPI app, sign-in and sessions, errors
- routes/: the API routes, one module per area, with their role checks
- services/: the work behind the routes (scoring, reasons, scans, review, names)
- data/: database queries only, one module per area
- worker.py: python -m chama.web.worker
"""
