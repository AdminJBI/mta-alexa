# mta-alexa — "Alexa, open station board"

A private Alexa skill that reads the MTA's live subway feed and says the next
trains at Franklin Avenue and Nostrand Avenue in Brooklyn. No API key, no server,
no cost: Amazon hosts the code for free.

- `lambda/mta.py` — reads the MTA feed and turns it into a sentence
- `lambda/config.py` — the settings you'd change (station pair, direction, count)
- `lambda/lambda_function.py` — the Alexa plumbing
- `skill-package/` — what Alexa listens for and the skill's name card
- `docs/SETUP.md` — the click-by-click guide for the Amazon side

Data: MTA GTFS-Realtime feeds (subway feeds are keyless; see https://www.mta.info/developers).
