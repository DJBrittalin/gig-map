# Gig Map

A web page with a map and a day picker. Choose a day and the map shows which venues have gigs and who is playing. The listings come from a gig guide page, which a small Python script reads once a day.

## What's in here

| File | What it does |
| --- | --- |
| `docs/index.html` | The map page people visit |
| `docs/gigs.json` | The gig data the page reads (example data until the scraper runs) |
| `scrape.py` | Reads the gig guide and writes `docs/gigs.json` |
| `venues.json` | Map coordinates for each venue, looked up once and saved |
| `.github/workflows/update-gigs.yml` | Runs the scraper every morning on GitHub, for free |
| `tests/sample_page.html` | A copy of the gig guide's layout, for testing the scraper offline |
| `tests/infinite_page.html` | A fake page that loads more gigs as you scroll, for testing the scrolling |

## Putting it online with GitHub (free)

1. Make a GitHub account if you don't have one, then create a new **public** repository (for example `gig-map`).
2. Upload everything in this folder to the repository. The `.github` folder is hidden on some computers, so check it went up. If it didn't, use **Add file > Create new file** and paste the workflow in at the path `.github/workflows/update-gigs.yml`.
3. Go to **Settings > Secrets and variables > Actions > Variables** and add two repository variables:
   - `GIG_GUIDE_URL`: the address of the gig guide page.
   - `SCRAPER_CONTACT`: an email address or website. The free map lookup service (OpenStreetMap's Nominatim) asks for this so it can contact you if something goes wrong.
   - `DAYS_AHEAD` (optional): how far ahead to load gigs, for example `120` for about four months. Leave it out to load everything the guide has.
4. Go to **Settings > Pages**. Under "Build and deployment", choose **Deploy from a branch**, branch `main`, folder `/docs`, then Save. After a minute your site appears at `https://YOUR-USERNAME.github.io/gig-map/`.
5. Go to the **Actions** tab, choose **Update gigs**, and press **Run workflow** to fetch real gigs straight away. After that it runs every morning by itself.

## If a venue doesn't show on the map

The page lists it with "not on map yet". Open `venues.json`, find the venue, and either type in its street address (the next run will look it up) or paste in the latitude and longitude yourself. You can get those by right-clicking the spot in Google Maps and clicking the numbers at the top of the menu.

## Running it on your own computer

The gig guide keeps loading more gigs as you scroll, so the scraper opens it in a hidden browser (Playwright) and scrolls to the bottom until nothing new appears. Loading the whole year can take a few minutes.

```
pip install requests beautifulsoup4 playwright
python -m playwright install chromium
python scrape.py https://the-gig-guide-address
cd docs
python -m http.server
```

Then open http://localhost:8000. (Opening `index.html` by double-clicking won't load the data, because browsers block that for local files.)

To test the scraper without the internet: `python scrape.py --file tests/sample_page.html --base https://example.com --offline`

## When it breaks

Scrapers stop working when a site changes its layout. If the Action fails with "No gigs found", look at the page with Inspect again and update the class names in `parse_page()` in `scrape.py`. The ones it relies on are `eventcardhost`, `data-gigstartdate`, `data-gigid`, `headliner`, `supports`, `time` and `venue`.

Before relying on this, check the gig guide's terms of use, and keep the scraper to once a day so it's polite to their server.
