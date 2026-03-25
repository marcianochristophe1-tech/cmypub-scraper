from flask import Flask, request, jsonify
from flask_cors import CORS
from jobspy import scrape_jobs
import traceback, time, re
from collections import defaultdict

app = Flask(__name__)
CORS(app, origins=[
    "https://c-my-pub.vercel.app",
])

# Simple rate limiting (in-memory)
_rate_limit = defaultdict(list)
def check_rate_limit(ip, max_requests=10, window=60):
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < window]
    if len(_rate_limit[ip]) >= max_requests:
        return False
    _rate_limit[ip].append(now)
    return True


@app.route("/api/search", methods=["GET"])
def search_jobs():
    if not check_rate_limit(request.remote_addr):
        return jsonify({"error": "Trop de requêtes. Réessayez dans une minute.", "results": [], "count": 0}), 429

    query = re.sub(r'[^\w\s\-\.\,\']', '', request.args.get("query", "").strip())[:100]
    site = request.args.get("site", "indeed")
    location = request.args.get("location", "Morocco")
    try:
        limit = min(int(request.args.get("limit", "15")), 30)
    except ValueError:
        limit = 15

    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    sites = [s.strip() for s in site.split(",") if s.strip() in ("linkedin", "indeed", "glassdoor")]
    if not sites:
        return jsonify({"error": "No valid site specified. Use: linkedin, indeed"}), 400

    # Parse countries for multi-country support
    countries = [c.strip() for c in location.split(",") if c.strip()]
    if not countries:
        countries = ["Morocco"]

    try:
        import pandas as pd
        all_jobs = pd.DataFrame()
        for country in countries:
            try:
                country_jobs = scrape_jobs(
                    site_name=sites,
                    search_term=query,
                    location=country,
                    results_wanted=limit,
                    hours_old=168,
                    country_indeed=country,
                )
                all_jobs = pd.concat([all_jobs, country_jobs], ignore_index=True)
            except Exception as e:
                print(f"Error scraping {country}: {e}")
                continue

        results = []
        for _, row in all_jobs.iterrows():
            # Fix LinkedIn URL format
            raw_url = str(row.get("job_url_direct", "") or row.get("job_url", "") or "")
            if "linkedin.com/job/" in raw_url:
                # Extract job ID and convert to proper format
                import re
                m = re.search(r'/job/(\d+)', raw_url)
                if m:
                    raw_url = f"https://www.linkedin.com/jobs/view/{m.group(1)}"
            results.append({
                "id": f"job_{hash(str(raw_url))}_{len(results)}",
                "company": str(row.get("company_name", "")).strip() if row.get("company_name") and str(row.get("company_name", "")).strip() not in ("", "nan", "None") else "",
                "title": str(row.get("title", "")) or query,
                "city": str(row.get("location", "")) or ", ".join(countries),
                "date": str(row.get("date_posted", ""))[:10] if row.get("date_posted") else "",
                "url": raw_url,
                "source": str(row.get("site", sites[0])).capitalize(),
                "description": str(row.get("description", ""))[:200] if row.get("description") else "",
            })

        return jsonify({
            "results": results,
            "count": len(results),
            "query": query,
            "sites": sites,
            "countries": countries,
        })

    except Exception as e:
        traceback.print_exc()  # Log server-side only
        return jsonify({
            "error": "La recherche a échoué. Réessayez dans quelques instants.",
            "results": [],
            "count": 0,
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
