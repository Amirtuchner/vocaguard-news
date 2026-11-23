# vocaguard-news

Recent phone-scam and fraud headlines (English, Hebrew, Russian, Arabic) for the news section on [vocaguard.com](https://vocaguard.com).

A GitHub Action (`.github/workflows/scam-news.yml`) runs every 3 hours, pulls Google News search RSS with `fetch_scam_news.py`, and commits `scam-news.json`. If a language fails to fetch, its previous headlines are kept.

The site reads: `https://raw.githubusercontent.com/Amirtuchner/vocaguard-news/main/scam-news.json`
