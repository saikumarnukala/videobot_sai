import re
import urllib.parse
import requests


class WikipediaFetcher:
    """
    Fetches verified movie metadata (plot summary, director, cast, year)
    from Wikipedia to ground the video script in accurate facts.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": "FacelessVideoBot/1.0 (https://github.com/saikumarnukala/videobot_sai; bot@faceless.local)"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def clean_movie_title(self, topic: str) -> tuple[str, str]:
        """Extract clean movie name and release year from topic string."""
        t = topic.strip()
        t = re.sub(r'^(?:review\s+(?:of\s+)?(?:the\s+)?(?:movie\s+)?)', '', t, flags=re.IGNORECASE).strip()

        year_match = re.search(r'\((\d{4})\)', t)
        year = year_match.group(1) if year_match else ''
        t = re.sub(r'\(\d{4}\)', '', t)
        t = re.sub(
            r'\s*\((?:bollywood|hollywood|tollywood|kollywood|mollywood|sandalwood|film|movie)\)',
            '',
            t,
            flags=re.IGNORECASE
        )
        return t.strip(), year

    def _clean_wikitext(self, text: str) -> str:
        """Strip wikitext templates, links, refs, and markup into clean comma-separated text."""
        if not text:
            return ""
        # Remove comments and refs
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ref[^>]*/>', '', text)
        text = re.sub(r'<[^>]+>', '', text)

        # Handle list templates like {{ubl|A|B}}, {{plainlist|* A\n* B}}, {{flatlist|...}}
        text = re.sub(r'\{\{(?:ubl|flatlist|plainlist|hlist)\s*\|\s*', '', text, flags=re.IGNORECASE)
        # Handle internal wiki links [[Link|Display]] or [[Link]]
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
        # Strip remaining curly templates
        text = re.sub(r'\{\{[^}]*\}\}', '', text)
        text = text.replace('}}', '').replace('{{', '')

        items = [x.strip() for x in re.split(r'[*|\n,]+', text) if x.strip()]
        # Filter out common noise tokens
        filtered = [x for x in items if x.lower() not in ("uncredited", "bullet", "none", "see below")]
        return ", ".join(filtered)

    def fetch_movie_details(self, topic: str) -> dict:
        """
        Search Wikipedia for the movie and retrieve its summary, director, cast, and plot.
        Returns a dict with found=True and details, or found=False on failure.
        """
        title, year = self.clean_movie_title(topic)
        queries = []
        if year:
            queries.append(f"{title} {year} film")
        queries.extend([f"{title} film", f"{title} movie", title])

        page_title = None
        for q in queries:
            try:
                r = self.session.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": q,
                        "format": "json",
                        "utf8": 1,
                    },
                    timeout=10,
                )
                if r.status_code != 200:
                    continue
                results = r.json().get("query", {}).get("search", [])
                if results:
                    page_title = results[0]["title"]
                    break
            except Exception as e:
                print(f"[WikipediaFetcher] Search error for query '{q}': {e}")
                continue

        if not page_title:
            print(f"[WikipediaFetcher] No Wikipedia page found for: '{topic}'")
            return {
                "found": False,
                "movie_name": title,
                "year": year,
                "topic": topic,
            }

        print(f"[WikipediaFetcher] Found Wikipedia article: '{page_title}'")

        # 1. Fetch Summary
        summary_text = ""
        try:
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title)}"
            sr = self.session.get(summary_url, timeout=10)
            if sr.status_code == 200:
                summary_text = sr.json().get("extract", "")
        except Exception as e:
            print(f"[WikipediaFetcher] Summary fetch error: {e}")

        # 2. Fetch Infobox (section 0) for director and cast
        director = ""
        cast_list_str = ""
        try:
            pr = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "parse",
                    "page": page_title,
                    "prop": "wikitext",
                    "section": 0,
                    "format": "json",
                },
                timeout=10,
            ).json()
            wt = pr.get("parse", {}).get("wikitext", {}).get("*", "")

            dir_m = re.search(r'\|\s*director\s*=\s*(.*?)(?=\n\||\n\}\})', wt, re.DOTALL | re.IGNORECASE)
            if dir_m:
                director = self._clean_wikitext(dir_m.group(1))

            star_m = re.search(r'\|\s*starring\s*=\s*(.*?)(?=\n\||\n\}\})', wt, re.DOTALL | re.IGNORECASE)
            if star_m:
                cast_list_str = self._clean_wikitext(star_m.group(1))
        except Exception as e:
            print(f"[WikipediaFetcher] Infobox parse error: {e}")

        # 3. Fetch Plot Section
        plot_text = ""
        try:
            cr = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "prop": "extracts",
                    "explaintext": True,
                    "titles": page_title,
                    "format": "json",
                },
                timeout=10,
            ).json()
            pages = cr.get("query", {}).get("pages", {})
            full_text = ""
            for _, pinfo in pages.items():
                full_text = pinfo.get("extract", "")
                break

            plot_match = re.search(
                r'==\s*(?:Plot|Synopsis|Premise)\s*==\s*\n(.*?)(?=\n==|\Z)',
                full_text,
                re.DOTALL | re.IGNORECASE,
            )
            if plot_match:
                raw_plot = plot_match.group(1).strip()
                paragraphs = [p.strip() for p in raw_plot.split("\n") if p.strip()]
                # Use the opening 2-3 paragraphs of the plot for a strong hook & context
                plot_text = " ".join(paragraphs[:3])
                if len(plot_text) > 1000:
                    plot_text = plot_text[:1000].rsplit(".", 1)[0] + "."
        except Exception as e:
            print(f"[WikipediaFetcher] Plot parse error: {e}")

        # If plot is empty, fallback to lead summary
        if not plot_text:
            plot_text = summary_text

        # Extract hero / heroine hints from cast list if available
        cast_members = [c.strip() for c in cast_list_str.split(",") if c.strip()]
        hero_candidate = cast_members[0] if cast_members else ""
        heroine_candidate = cast_members[1] if len(cast_members) > 1 else ""

        return {
            "found": True,
            "topic": topic,
            "movie_name": title,
            "year": year,
            "page_title": page_title,
            "director": director,
            "cast": cast_list_str,
            "hero_hint": hero_candidate,
            "heroine_hint": heroine_candidate,
            "summary": summary_text,
            "plot": plot_text,
        }


if __name__ == "__main__":
    fetcher = WikipediaFetcher()
    for test_topic in [
        "Review of the movie Inception (2010)",
        "Review of the movie Dangal (Bollywood)",
        "Review of the movie Baahubali: The Beginning (Tollywood)",
        "Review of the movie The Dark Knight (Hollywood)",
    ]:
        print(f"\nFetching: {test_topic}")
        data = fetcher.fetch_movie_details(test_topic)
        print(f"Title: {data.get('movie_name')}")
        print(f"Director: {data.get('director')}")
        print(f"Cast: {data.get('cast')[:60]}...")
        print(f"Plot ({len(data.get('plot', ''))} chars): {data.get('plot', '')[:120]}...")
