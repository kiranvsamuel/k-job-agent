import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from sqlalchemy import text, func, distinct

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from src.db.db import SessionLocal
    from src.db.models import Job, JobsApplied
except ImportError:
    # Fallback for direct execution
    from db.db import SessionLocal
    from db.models import Job, JobsApplied

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure Swagger
app.config['SWAGGER'] = {
    'title': 'Job Application Statistics API',
    'uiversion': 3,
    'version': '1.0.0',
    'description': 'API for retrieving job application statistics from the database',
    'termsOfService': '',
    'hide_top_bar': True
}

swagger = Swagger(app, template={
    "info": {
        "title": "Job Application Statistics API",
        "description": "API for retrieving job application statistics from the database",
        "version": "1.0.0"
    },
    "tags": [
        {
            "name": "Statistics",
            "description": "Endpoints for retrieving job application statistics"
        }
    ]
})

def get_db_session():
    """Create and return a database session"""
    return SessionLocal()

@app.route('/api/stats', methods=['GET'])
def get_job_stats():
    """
    Get overall job application statistics
    ---
    tags:
      - Statistics
    responses:
      200:
        description: Returns overall job application statistics
        content:
          application/json:
            schema:
              type: object
              properties:
                total_jobs_found:
                  type: integer
                  example: 150
                total_jobs_applied:
                  type: integer
                  example: 75
                total_unique_emails_sent:
                  type: integer
                  example: 60
      500:
        description: Internal server error
    """
    session = get_db_session()
    
    try:
        # Total Jobs Found
        total_jobs = session.query(Job).count()
        
        # Total Jobs Applied
        total_applied = session.query(JobsApplied).count()
        
        # Debug: First let's check if there are any jobs with applied_at not null
        test_query = text("SELECT COUNT(*) FROM jobs WHERE applied_at IS NOT NULL")
        test_result = session.execute(test_query).scalar()
        print(f"Jobs with applied_at not null: {test_result}", flush=True)
        
        # Try the email query with explicit connection
        try:
            email_query = text("""
                SELECT COUNT(DISTINCT TRIM(email))
                FROM jobs
                CROSS JOIN LATERAL unnest(string_to_array(contact_email, ',')) AS email
                WHERE applied_at IS NOT NULL
            """)
            
            email_result = session.execute(email_query)
            total_unique_emails = email_result.scalar()
            print(f"Email query result: {total_unique_emails}", flush=True)
            
            if total_unique_emails is None:
                total_unique_emails = 0
            else:
                total_unique_emails = int(total_unique_emails)
                
        except Exception as email_error:
            print(f"Email query error: {str(email_error)}", flush=True)
            total_unique_emails = 0
        
        stats = {
            "total_jobs_found": total_jobs,
            "total_jobs_applied": total_applied,
            "total_unique_emails_sent": total_unique_emails
        }
        
        print(f"Final stats: {stats}", flush=True)
        return jsonify(stats)
    
    except Exception as e:
        print(f"Error occurred: {str(e)}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    
    finally:
        session.close()

@app.route('/api/stats/applied-per-day', methods=['GET'])
def get_jobs_applied_per_day():
    """
    Get jobs applied count for a specific date
    ---
    tags:
      - Statistics
    parameters:
      - name: date
        in: query
        required: true
        description: Date in YYYY-MM-DD format
        schema:
          type: string
          example: "2024-01-15"
    responses:
      200:
        description: Returns jobs applied count for the specified date
        content:
          application/json:
            schema:
              type: object
              properties:
                date:
                  type: string
                  example: "2024-01-15"
                jobs_applied:
                  type: integer
                  example: 5
      400:
        description: Bad request - missing or invalid date parameter
      500:
        description: Internal server error
    """
    date_str = request.args.get('date')
    
    if not date_str:
        return jsonify({"error": "Date parameter is required"}), 400
    
    try:
        # Parse the date string (expecting format YYYY-MM-DD)
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    session = get_db_session()
    
    try:
        # Count jobs applied on the specific date
        jobs_applied_count = session.query(JobsApplied).filter(
            func.date(JobsApplied.applied_at) == target_date
        ).count()
        
        return jsonify({
            "date": date_str,
            "jobs_applied": jobs_applied_count
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    finally:
        session.close()

@app.route('/api/stats/daily-applications', methods=['GET'])
def get_daily_applications_summary():
    """
    Get daily application counts for a date range
    ---
    tags:
      - Statistics
    parameters:
      - name: start_date
        in: query
        required: false
        description: Start date in YYYY-MM-DD format
        schema:
          type: string
          example: "2024-01-01"
      - name: end_date
        in: query
        required: false
        description: End date in YYYY-MM-DD format
        schema:
          type: string
          example: "2024-01-31"
    responses:
      200:
        description: Returns daily application counts for the specified date range
        content:
          application/json:
            schema:
              type: object
              properties:
                daily_applications:
                  type: array
                  items:
                    type: object
                    properties:
                      date:
                        type: string
                        example: "2024-01-15"
                      applications:
                        type: integer
                        example: 5
      400:
        description: Bad request - invalid date format
      500:
        description: Internal server error
    """
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    session = get_db_session()
    
    try:
        # Base query to get daily counts
        query = session.query(
            func.date(JobsApplied.applied_at).label('application_date'),
            func.count(JobsApplied.id).label('applications_count')
        ).group_by('application_date').order_by('application_date')
        
        # Apply date filters if provided
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter(func.date(JobsApplied.applied_at) >= start_date)
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter(func.date(JobsApplied.applied_at) <= end_date)
        
        results = query.all()
        
        daily_stats = [{
            "date": str(result.application_date),
            "applications": result.applications_count
        } for result in results]
        
        return jsonify({"daily_applications": daily_stats})
    
    except ValueError:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()

@app.route('/')
def index():
    """Redirect to Swagger UI"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Job Application Statistics API</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background-color: white;
                padding: 20px;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            h1 {
                color: #333;
            }
            a {
                color: #007bff;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Job Application Statistics API</h1>
            <p>This API provides statistics about job applications from the database.</p>
            <p>Visit the <a href="/apidocs">Swagger UI documentation</a> to explore the API endpoints.</p>
            <h2>Available Endpoints:</h2>
            <ul>
                <li><strong>GET /api/stats</strong> - Get overall job application statistics</li>
                <li><strong>GET /api/stats/applied-per-day?date=YYYY-MM-DD</strong> - Get jobs applied count for a specific date</li>
                <li><strong>GET /api/stats/daily-applications?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD</strong> - Get daily application counts for a date range</li>
            </ul>
        </div>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)