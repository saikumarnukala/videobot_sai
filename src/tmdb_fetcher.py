import os
import re
import urllib.parse
import shutil
import requests


class TMDBFetcher:
    """
    Dedicated image extractor for The Movie Database (TMDB - https://www.themoviedb.org).
    Fetches official high-definition movie backdrops and posters for any film.
    """

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def clean_title(self, topic: str) -> tuple[str, str]:
        """Strip review prefixes and region tags; extract year if present."""
        t = topic.strip()
        t = re.sub(r'^(?:review\s+(?:of\s+)?(?:the\s+)?(?:movie\s+)?)', '', t, flags=re.IGNORECASE).strip()

        year_match = re.search(r'\((\d{4})\)', t)
        year = year_match.group(1) if year_match else ''
        t = re.sub(r'\(\d{4}\)', '', t)
        t = re.sub(
            r'\s*\((?:bollywood|hollywood|tollywood|kollywood|mollywood|sandalwood|film|movie)\)',
            '',
            t,
            flags=re.IGNORECASE,
        ).strip()
        return t, year

    def _fetch_tmdb_page(self, path: str) -> str:
        """
        Fetch HTML from TMDB. Uses web reader gateway to ensure uninterrupted access
        across all networks and regions without ISP DNS blocks.
        """
        tmdb_url = f"https://www.themoviedb.org/{path.lstrip('/')}"
        gateway_url = f"https://r.jina.ai/{tmdb_url}"
        try:
            r = requests.get(gateway_url, timeout=12)
            if r.status_code == 200 and len(r.text) > 200:
                return r.text
        except Exception as e:
            print(f"[TMDB] Gateway fetch error for {tmdb_url}: {e}")

        # Direct attempt fallback
        try:
            r = self.session.get(tmdb_url, timeout=4)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass

        return ""

    def search_movie_slug(self, topic: str) -> str | None:
        """Search TMDB for the movie and return its URL slug/id."""
        title, year = self.clean_title(topic)
        queries = []
        if year:
            queries.append(f"{title} {year}")
        queries.append(title)

        for q in queries:
            html = self._fetch_tmdb_page(f"search/movie?query={urllib.parse.quote(q)}")
            if not html:
                continue

            match = re.search(r'/(?:movie)/(\d+[-a-zA-Z0-9_]*)', html)
            if match:
                slug = match.group(1)
                print(f"[TMDB] Found movie on TMDB: '{title}' -> {slug}")
                return slug

        print(f"[TMDB] No movie found on TMDB for: '{topic}'")
        return None

    def fetch_image_urls(self, topic: str, count: int = 8) -> list[str]:
        """Retrieve up to `count` high-definition backdrop and poster URLs from TMDB."""
        slug = self.search_movie_slug(topic)
        if not slug:
            return []

        all_imgs: list[str] = []

        # 1. Fetch Backdrops (16:9 movie stills)
        b_html = self._fetch_tmdb_page(f"movie/{slug}/images/backdrops")
        if b_html:
            raw_backdrops = re.findall(
                r'https://(?:image|media)\.themoviedb\.org/t/p/[^\s\)\"\']+\.(?:jpg|png|webp)',
                b_html,
            )
            for img in raw_backdrops:
                # Normalize domain to image.tmdb.org CDN and upgrade to 1280px high-res
                high_res = img.replace("media.themoviedb.org", "image.tmdb.org")
                high_res = high_res.replace("www.themoviedb.org", "image.tmdb.org")
                high_res = re.sub(r'/w\d+[^/]*/', '/w1280/', high_res)
                high_res = high_res.replace('/original/', '/w1280/')
                if high_res not in all_imgs:
                    all_imgs.append(high_res)

        # 2. Fetch Posters if backdrops are fewer than needed
        if len(all_imgs) < count:
            p_html = self._fetch_tmdb_page(f"movie/{slug}/images/posters")
            if p_html:
                raw_posters = re.findall(
                    r'https://(?:image|media)\.themoviedb\.org/t/p/[^\s\)\"\']+\.(?:jpg|png|webp)',
                    p_html,
                )
                for img in raw_posters:
                    high_res = img.replace("media.themoviedb.org", "image.tmdb.org")
                    high_res = high_res.replace("www.themoviedb.org", "image.tmdb.org")
                    high_res = re.sub(r'/w\d+[^/]*/', '/w1280/', high_res)
                    if high_res not in all_imgs:
                        all_imgs.append(high_res)

        print(f"[TMDB] Retrieved {len(all_imgs)} official stills from TMDB for '{topic}'")
        return all_imgs

    def download_movie_images(self, topic: str, count: int = 8, output_dir: str = "temp") -> list[str]:
        """
        Download exact `count` high-definition images from TMDB to output_dir.
        Returns list of file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        image_urls = self.fetch_image_urls(topic, count=count)

        downloaded_paths = []
        dl_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }

        for i in range(count):
            out_file = os.path.join(output_dir, f"temp_bg_{i}.jpg")
            url = image_urls[i] if i < len(image_urls) else None

            success = False
            if url:
                # Ensure using image.tmdb.org CDN
                url = url.replace("media.themoviedb.org", "image.tmdb.org")
                url = url.replace("www.themoviedb.org", "image.tmdb.org")
                print(f"[{i + 1}/{count}] Downloading TMDB image: {url}...")
                for _ in range(2):
                    try:
                        resp = requests.get(url, headers=dl_headers, stream=True, timeout=8)
                        if resp.status_code == 200:
                            with open(out_file, "wb") as f:
                                for chunk in resp.iter_content(65536):
                                    if chunk:
                                        f.write(chunk)
                            if os.path.exists(out_file) and os.path.getsize(out_file) >= 10240:
                                print(f"  [OK] Saved TMDB image to {out_file}")
                                success = True
                                break
                    except Exception as e:
                        print(f"  [!] Download attempt failed: {e}")

            # If this slot failed or there weren't enough unique URLs, reuse an earlier image
            if not success and downloaded_paths:
                print(f"  [Fallback] Reusing TMDB image from slot 1 for slot {i + 1}")
                shutil.copyfile(downloaded_paths[0], out_file)
                success = True

            if success and os.path.exists(out_file):
                downloaded_paths.append(out_file)

        return downloaded_paths


if __name__ == "__main__":
    fetcher = TMDBFetcher()
    test_topic = "Review of the movie Inception (2010)"
    files = fetcher.download_movie_images(test_topic, count=8)
    print(f"\nDownloaded {len(files)} TMDB images:")
    for f in files:
        print(f"  {f} ({os.path.getsize(f)} bytes)")
