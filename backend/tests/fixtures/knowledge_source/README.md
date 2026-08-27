# SYNTHETIC TEST FIXTURES - NOT REAL LENNY CONTENT

Everything under this directory (`index.json`, `podcasts/*.md`,
`newsletters/*.md`) is fabricated data written for the automated test
suite only. The guests, episode titles, dates, and transcript excerpts
are all invented and do not correspond to any real Lenny's Podcast
episode or Lenny's Newsletter post.

The real knowledge source used for actual ingestion is the official
`LennysNewsletter/lennys-newsletterpodcastdata` GitHub repository - see
the root `README.md` "Knowledge base setup" for how to fetch it. It is
intentionally not vendored into this repository (its license permits
personal use and projects built with it, but not redistributing the raw
dataset files).

This fixture only needs to match the *shape* of that real data closely
enough to exercise `app.knowledge.parsing`/`chunking`/`ingest` and
`app.services.knowledge_retriever` faithfully.
