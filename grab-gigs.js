// Gig Map: grab the gig guide page
// 1. Open the gig guide in your normal browser.
// 2. Press F12 (Cmd+Option+J on a Mac) and click the Console tab.
// 3. Paste all of this in and press Enter.
// It scrolls down until it has DAYS days of gigs, then downloads gig-page.html.
// Upload that file to the top level of your GitHub repository and the map updates itself.

(async () => {
  const DAYS = 60; // how far ahead to grab; change this number if you like

  const stopAt = Date.now() + DAYS * 864e5;
  const lastDate = () => {
    const els = document.querySelectorAll("[data-gigstartdate]");
    if (!els.length) return null;
    const d = new Date(els[els.length - 1].dataset.gigstartdate.replace(/\s*\(.*\)$/, ""));
    return isNaN(d) ? null : d;
  };

  let count = 0, stalls = 0;
  console.log("Scrolling... leave this tab open until it says Saved.");
  while (stalls < 8) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise((r) => setTimeout(r, 1500));
    const n = document.querySelectorAll(".eventcardhost").length;
    if (n === count) { stalls++; continue; }
    stalls = 0;
    count = n;
    const d = lastDate();
    console.log(`${n} gigs loaded${d ? ", up to " + d.toDateString() : ""}`);
    if (d && d.getTime() > stopAt) break;
  }

  if (!count) {
    console.log("No gigs found on this page. Make sure you're on the gig guide list itself.");
    return;
  }

  // Keep only the day headings and gig cards, so the file stays small.
  const parts = [...document.querySelectorAll("h3, .eventcardhost")].map((el) => el.outerHTML);
  const html = `<html><head><meta name="source-url" content="${location.href}"></head><body>\n${parts.join("\n")}\n</body></html>`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  a.download = "gig-page.html";
  document.body.append(a);
  a.click();
  a.remove();
  console.log(`Saved ${count} gigs to gig-page.html in your Downloads folder.`);
})();
