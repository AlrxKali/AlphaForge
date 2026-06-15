"""alphaforge_api: the service layer over the alphaforge analytics core.

A thin FastAPI app plus an arq worker. The API validates requests, persists
jobs to Supabase, and enqueues work. The worker runs the analytics core and
writes results back. The dependency arrow only ever points api -> core. The
core never imports anything here.
"""
