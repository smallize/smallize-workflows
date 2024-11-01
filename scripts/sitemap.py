import requests
from requests.exceptions import RequestException
from xml.etree import ElementTree as ET
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Helper function to authenticate Google services
def authenticate_google_service(scopes, key_info):
    try:
        credentials = service_account.Credentials.from_service_account_info(
            key_info, scopes=scopes
        )
        return credentials
    except Exception as e:
        print(f"[ERROR] Authentication failed: {e}")
        return None

# Check sitemap status before submitting
def check_sitemap_status(service, site_url, sitemap_url):
    try:
        request = service.sitemaps().list(siteUrl=site_url)
        response = request.execute()
        for sitemap in response.get('sitemap', []):
            if sitemap.get('path') == sitemap_url:
                print(f"[INFO] Sitemap already submitted: {sitemap_url}")
                return True
        return False
    except Exception as e:
        print(f"[ERROR] Failed to check sitemap status for {sitemap_url}: {e}")
        return False

# Submit sitemap to Google
def submit_sitemap_to_google(service, site_url, sitemap_url):
    try:
        request = service.sitemaps().submit(siteUrl=site_url, feedpath=sitemap_url)
        request.execute()
        print(f"[INFO] Submitted sitemap to Google: {sitemap_url}")
    except Exception as e:
        print(f"[ERROR] Failed to submit sitemap: {sitemap_url}: {e}")

# Check sitemap availability for given domains, subdomains, and TLDs
def check_sitemap_availability(domains, subdomains, tlds):
    available_sitemaps = []
    for domain in domains:
        for tld in tlds:
            for subdomain in subdomains:
                url = f"https://{subdomain}.{domain}.{tld}/sitemap.xml"
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        print(f"[INFO] Sitemap found: {url}")
                        if is_sitemap_index(response.text):
                            individual_sitemaps = get_individual_sitemaps(response.text)
                            available_sitemaps.extend([(f"https://{subdomain}.{domain}.{tld}", sitemap) for sitemap in individual_sitemaps])
                        else:
                            available_sitemaps.append((f"https://{subdomain}.{domain}.{tld}", url))
                except RequestException as e:
                    print(f"[ERROR] Failed to fetch {url}: {e}")
    return available_sitemaps

# Determine if sitemap is an index
def is_sitemap_index(xml_content):
    try:
        root = ET.fromstring(xml_content)
        return any(loc.text.endswith('.xml') for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'))
    except ET.ParseError as e:
        print(f"[ERROR] Failed to parse sitemap index: {e}")
        return False

# Extract individual sitemaps from sitemap index
def get_individual_sitemaps(xml_content):
    sitemaps = []
    try:
        root = ET.fromstring(xml_content)
        sitemaps = [loc.text for loc in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc') if loc.text.endswith('.xml')]
    except ET.ParseError as e:
        print(f"[ERROR] Failed to parse individual sitemaps: {e}")
    return sitemaps

# Main integration
def main():
    # Load credentials from GitHub Actions secret
    try:
        credentials_info = json.loads(os.getenv('GOOGLE_CREDENTIALS_JSON'))
    except KeyError:
        print("[ERROR] GOOGLE_CREDENTIALS_JSON environment variable not set.")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to decode GOOGLE_CREDENTIALS_JSON: {e}")
        return

    webmaster_scopes = ['https://www.googleapis.com/auth/webmasters']

    # Authenticate Google service
    webmaster_credentials = authenticate_google_service(webmaster_scopes, credentials_info)
    if not webmaster_credentials:
        print("[ERROR] Unable to authenticate Google service. Exiting.")
        return

    try:
        webmaster_service = build('searchconsole', 'v1', credentials=webmaster_credentials)
    except Exception as e:
        print(f"[ERROR] Failed to initialize Google Search Console service: {e}")
        return

    # List of domain names, subdomains, and TLDs
    domains = ["documentize", "sheetize", "barcodize", "ocrize", "imagise", "slidize", "psdize", "smallize"]
    subdomains = ["brands", "products", "blog", "docs", "reference", "releases", "www"]
    tlds = ["com"]

    # Process each subdomain and submit sitemaps
    for subdomain in subdomains:
        try:
            available_sitemaps = check_sitemap_availability(domains, [subdomain], tlds)
            for site_url, sitemap in available_sitemaps:
                if not check_sitemap_status(webmaster_service, site_url, sitemap):
                    submit_sitemap_to_google(webmaster_service, site_url, sitemap)
        except Exception as e:
            print(f"[ERROR] Unexpected error processing subdomain {subdomain}: {e}")

if __name__ == "__main__":
    main()
