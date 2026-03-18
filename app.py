from flask import Flask, request, jsonify
from flask_cors import CORS
from jobspy import scrape_jobs
import traceback

app = Flask(__name__)
CORS(app, origins=[
    "https://c-my-pub.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
])


@app.route("/api/search", methods=["GET"])
def search_jobs():
    query = request.args.get("query", "").strip()
    site = request.args.get("site", "indeed")  # "linkedin", "indeed", "linkedin,indeed"
    location = request.args.get("location", "Morocco")
    limit = min(int(request.args.get("limit", "15")), 30)

    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    sites = [s.strip() for s in site.split(",") if s.strip() in ("linkedin", "indeed", "glassdoor")]
    if not sites:
        return jsonify({"error": "No valid site specified. Use: linkedin, indeed"}), 400

    try:
        jobs = scrape_jobs(
            site_name=sites,
            search_term=query,
            location=location,
            results_wanted=limit,
            hours_old=168,  # last 7 days
            country_indeed="Morocco",
        )

        results = []
        for _, row in jobs.iterrows():
            results.append({
                "id": f"job_{hash(str(row.get('job_url', '')))}_{len(results)}",
                "company": str(row.get("company_name", "")) or "Entreprise",
                "title": str(row.get("title", "")) or query,
                "city": str(row.get("location", "")) or location,
                "date": str(row.get("date_posted", ""))[:10] if row.get("date_posted") else "",
                "url": str(row.get("job_url", "")) or "",
                "source": str(row.get("site", sites[0])).capitalize(),
                "description": str(row.get("description", ""))[:200] if row.get("description") else "",
            })

        return jsonify({
            "results": results,
            "count": len(results),
            "query": query,
            "sites": sites,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": f"Scraping failed: {str(e)}",
            "results": [],
            "count": 0,
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
