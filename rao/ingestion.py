import os
import time
import json
import urllib.request
import urllib.error
from bs4 import BeautifulSoup

class SECIngestion:
    """
    Rate-limit-compliant client that connects to the SEC EDGAR API,
    downloads NVDA 10-K/10-Q filings, and splits them into logical sections.
    """
    CIK = "0001045810" # NVDA CIK
    
    def __init__(self, cache_dir="data/cache", user_agent=None):
        self.cache_dir = cache_dir
        self.user_agent = user_agent or os.environ.get("SEC_USER_AGENT", "Michael contact@yourdomain.com")
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_headers(self):
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov" if "data.sec.gov" in self.user_agent else "www.sec.gov"
        }
        
    def _request_url(self, url):
        """SEC EDGAR limits to 10 requests/sec. We sleep 0.15s to be extremely safe."""
        time.sleep(0.15)
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "identity", # standard identity decoding in python
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code} fetching {url}: {e.reason}")
            raise e
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            raise e

    def get_filing_list(self):
        """Fetches the list of all filings for NVDA from SEC EDGAR."""
        url = f"https://data.sec.gov/submissions/CIK{self.CIK}.json"
        cache_file = os.path.join(self.cache_dir, "submissions.json")
        
        # Cache submissions list for 24h to avoid spamming the SEC
        if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < 86400:
            with open(cache_file, "r") as f:
                return json.load(f)
                
        print("Fetching NVDA filings list from SEC EDGAR...")
        data_bytes = self._request_url(url)
        data = json.loads(data_bytes.decode("utf-8"))
        
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
            
        return data

    def download_nvda_filings(self, start_year=2021, end_year=2026):
        """Downloads all 10-K and 10-Q filings for NVDA between start_year and end_year."""
        data = self.get_filing_list()
        recent_filings = data["filings"]["recent"]
        
        filings_to_download = []
        n = len(recent_filings["accessionNumber"])
        
        for i in range(n):
            form = recent_filings["form"][i]
            filing_date = recent_filings["filingDate"][i]
            report_date = recent_filings["reportDate"][i]
            year = int(filing_date.split("-")[0])
            
            if form in ["10-K", "10-Q"] and start_year <= year <= end_year:
                acc_num = recent_filings["accessionNumber"][i]
                acc_num_no_dash = acc_num.replace("-", "")
                primary_doc = recent_filings["primaryDocument"][i]
                
                filings_to_download.append({
                    "form": form,
                    "filing_date": filing_date,
                    "report_date": report_date,
                    "acc_num": acc_num,
                    "acc_num_no_dash": acc_num_no_dash,
                    "primary_doc": primary_doc,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{int(self.CIK)}/{acc_num_no_dash}/{primary_doc}"
                })
                
        print(f"Found {len(filings_to_download)} NVDA filings (10-K/10-Q) from {start_year} to {end_year}.")
        
        downloaded = []
        for f in filings_to_download:
            local_name = f"{f['form']}_{f['report_date']}_{f['acc_num']}.html"
            local_path = os.path.join(self.cache_dir, local_name)
            f["local_path"] = os.path.abspath(local_path)
            
            if os.path.exists(local_path) and os.path.getsize(local_path) > 10000:
                # Document already cached
                downloaded.append(f)
                continue
                
            print(f"Downloading {f['form']} for report date {f['report_date']}...")
            try:
                doc_bytes = self._request_url(f["url"])
                # Save raw HTML
                with open(local_path, "wb") as out_f:
                    out_f.write(doc_bytes)
                downloaded.append(f)
            except Exception as e:
                print(f"Failed to download filing from {f['url']}: {str(e)}")
                
        # Save a manifest of downloaded filings
        manifest_path = os.path.join(self.cache_dir, "manifest.json")
        with open(manifest_path, "w") as m_f:
            json.dump(downloaded, m_f, indent=2)
            
        return downloaded

    @staticmethod
    def extract_mda_section(html_path):
        """
        Extracts the Management's Discussion and Analysis (MD&A) section from a 10-K/10-Q HTML document.
        To avoid stripping HTML tables and schema elements, we return the entire raw HTML.
        This allows pandas.read_html and BeautifulSoup to parse all tables inside the sandbox.
        """
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def extract_segment_note(html_path):
        """
        Extracts the Segment disclosures footnote (usually Note 17 or 18 'Segment Reporting')
        which contains Graphics vs. Compute & Networking revenues, operating income, and assets.
        To ensure HTML tags (<table>, <tr>, <td>) are preserved for sandboxed parsing, we return the entire raw HTML.
        """
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
