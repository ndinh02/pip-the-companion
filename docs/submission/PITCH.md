# Elevator pitch

(159 words)

Most people who watch football with a fan are not fans yet, and nothing invites them in between the big moments. **Pip** is a matchday companion for that mixed room. A shared TV plays a fully synthetic match, and everyone joins from their phone with a QR code: no app, no account, no names. At every dead ball, Pip, a small club-neutral bird, asks one question about how the next play will unfold. The match answers, and Pip explains why, with a plain line for newcomers and a data line for fans, in English, German or Vietnamese. Fans can also follow one player's live stats and runs.

Under the hood, Python generates the events and 5 Hz tracking. A bounded writer-and-checker workflow checks every explanation before kick-off, and code verifies every number. Its AI writer has been trialled with a local model on **Foundry Local**. The app runs on **Azure App Service**, and **GitHub Actions** tests and deploys it.
