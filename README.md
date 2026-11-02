# Gig Map

A web page with a map and a day picker. Choose a day and the map shows which venues have gigs and who is playing.

The gig guide blocks automated visitors, so you grab the listings yourself in your normal browser with a short snippet, then upload the file to GitHub. GitHub does the rest: it reads the gigs, finds new venues on the map, and updates the website.

## What's in here

| File | What it does |
| --- | --- |
| `docs/index.html` | The map page people visit |
| `docs/gigs.json` | The gig data the page reads |
| `grab-gigs.js` | The snippet you paste into your browser to save the gig guide |
| `scrape.py` | Reads the saved page and writes `docs/gigs.json` |
| `venues.json` | Map coordinates for each venue, looked up once and saved |
| `.github/workflows/update-gigs.yml` | Runs `scrape.py` on GitHub whenever you upload a new page |
| `tests/` | Fake gig guide pages for testing |

## Updating the gigs (every week or so)

1. Open the gig guide in Chrome, Edge or Firefox, the same way you normally would.
2. Open the browser console: press F12 and click the **Console** tab (on a Mac, Cmd+Option+J).
3. Open `grab-gigs.js`, copy all of it, paste it into the console and press Enter.
   - The first time, Chrome may refuse the paste and ask you to type `allow pasting` first. Type that, press Enter, then paste again.
4. Leave the tab open while it scrolls. When the console says **Saved**, a file called `gig-page.html` is in your Downloads folder.
5. On GitHub, go to the main page of your repository and click **Add file > Upload files**. Drag in `gig-page.html` and click **Commit changes**.
6. That's it. The **Actions** tab shows the update running. When it gets a green tick (a minute or two, longer the first time while it finds every venue), refresh your map.

The snippet grabs 60 days ahead. To change that, edit the `DAYS = 60` line before you paste it.

If the downloaded file is called something like `gig-page (1).html`, that's fine. Anything starting with `gig-page` and ending in `.html` works. The upload is deleted automatically once it's been read.

## First-time setup

1. Create a **public** repository on GitHub and upload everything in this folder (the files inside it, not the folder itself). If the `.github` folder doesn't upload, use **Add file > Create new file**, type `.github/workflows/update-gigs.yml` as the name, and paste in that file's contents.
2. **Settings > Secrets and variables > Actions > Variables**: add `SCRAPER_CONTACT` with your email address or your map's web address. OpenStreetMap's free venue lookup asks apps to identify themselves.
3. **Settings > Pages**: choose **Deploy from a branch**, branch `main`, folder `/docs`, and Save. Your site appears at `https://YOUR-USERNAME.github.io/gig-map/`.
4. **Settings > Actions > General > Workflow permissions**: choose **Read and write permissions** and Save.
5. Do your first update using the steps above.

## If a venue doesn't show on the map

The page lists it with "not on map yet". Open `venues.json` on GitHub, click the pencil icon, and type the venue's street address between the quote marks after `"address"`. Or paste in the latitude and longitude yourself: right-click the spot in Google Maps and click the numbers at the top of the menu. The next update fills in the rest.

## When it breaks

If the snippet says it found no gigs, or the update says "No gigs found", the gig guide has probably changed its layout. Look at a gig with Inspect again and compare the class names with the ones the snippet and `parse_page()` in `scrape.py` rely on: `eventcardhost`, `data-gigstartdate`, `data-gigid`, `headliner`, `supports`, `time` and `venue`.

## Testing on your own computer

```
pip install requests beautifulsoup4
python scrape.py --file tests/sample_page.html --base https://example.com --offline
cd docs
python -m http.server
```

Then open http://localhost:8000.
