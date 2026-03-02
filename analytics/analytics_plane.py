from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime
import atexit
import signal
import sys
import os
import logging
import psycopg2  
from dotenv import load_dotenv 

load_dotenv()

app = Flask(__name__)
# Restrict CORS cho production: Chỉ cho phép origins từ Render URL hoặc local
CORS(app, origins=[
    "https://flappy-analytics.onrender.com",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5000",
    "https://laihoangson.github.io"
])

# Setup logging cho production
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup: Dùng PostgreSQL từ env var DATABASE_URL (Render cung cấp)
def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS game_sessions (
            id TEXT PRIMARY KEY,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            score INTEGER,
            coins_collected INTEGER,
            ufos_shot INTEGER,
            bullets_fired INTEGER,
            death_reason TEXT,
            game_duration INTEGER,
            pipes_passed INTEGER,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# THÊM: Hàm xử lý tắt server
def shutdown_handler(signum=None, frame=None):
    logger.info("\n🛑 Server is shutting down gracefully...")

# Đăng ký handlers cho tắt server
atexit.register(shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

@app.route('/api/game-analytics', methods=['POST', 'OPTIONS'])
def receive_analytics():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        logger.info("Received analytics data: %s", data)  # Debug log
        
        # Kiểm tra nếu là mảng (nhiều analytics)
        if isinstance(data, list):
            return process_batch_analytics(data)
        else:
            return process_single_analytics(data)
        
    except Exception as e:
        logger.error(f"Error storing analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Xử lý batch analytics
def process_batch_analytics(analytics_list):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        success_count = 0
        for data in analytics_list:
            try:
                c.execute('''
                    INSERT INTO game_sessions 
                    (id, start_time, end_time, score, coins_collected, ufos_shot, bullets_fired, death_reason, game_duration, pipes_passed)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                    start_time = EXCLUDED.start_time,
                    end_time = EXCLUDED.end_time,
                    score = EXCLUDED.score,
                    coins_collected = EXCLUDED.coins_collected,
                    ufos_shot = EXCLUDED.ufos_shot,
                    bullets_fired = EXCLUDED.bullets_fired,
                    death_reason = EXCLUDED.death_reason,
                    game_duration = EXCLUDED.game_duration,
                    pipes_passed = EXCLUDED.pipes_passed
                ''', (
                    data.get('gameId'),
                    data.get('startTime'),
                    data.get('endTime'),
                    data.get('score'),
                    data.get('coinsCollected'),
                    data.get('ufosShot'),
                    data.get('bulletsFired'),
                    data.get('deathReason'),
                    data.get('gameDuration'),
                    data.get('pipesPassed')
                ))
                success_count += 1
            except Exception as e:
                logger.error(f"Error processing game {data.get('gameId')}: {e}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Processed {success_count}/{len(analytics_list)} analytics'
        }), 200
        
    except Exception as e:
        logger.error(f"Error storing batch analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Xử lý single analytics
def process_single_analytics(data):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO game_sessions 
            (id, start_time, end_time, score, coins_collected, ufos_shot, bullets_fired, death_reason, game_duration, pipes_passed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            score = EXCLUDED.score,
            coins_collected = EXCLUDED.coins_collected,
            ufos_shot = EXCLUDED.ufos_shot,
            bullets_fired = EXCLUDED.bullets_fired,
            death_reason = EXCLUDED.death_reason,
            game_duration = EXCLUDED.game_duration,
            pipes_passed = EXCLUDED.pipes_passed
        ''', (
            data.get('gameId'),
            data.get('startTime'),
            data.get('endTime'),
            data.get('score'),
            data.get('coinsCollected'),
            data.get('ufosShot'),
            data.get('bulletsFired'),
            data.get('deathReason'),
            data.get('gameDuration'),
            data.get('pipesPassed')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error storing analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Endpoint để client đồng bộ dữ liệu local
@app.route('/api/sync-analytics', methods=['POST', 'OPTIONS'])
def sync_analytics():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        data = request.get_json()
        local_games = data.get('games', [])
        
        logger.info(f"Syncing {len(local_games)} local games to server")
        
        return process_batch_analytics(local_games)
        
    except Exception as e:
        logger.error(f"Error syncing analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Export data to JSON file
@app.route('/api/export-data')
def export_data():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Lấy tất cả data
        c.execute('''
            SELECT id, start_time, end_time, score, coins_collected, ufos_shot, 
                   bullets_fired, death_reason, game_duration, pipes_passed
            FROM game_sessions
        ''')
        
        games = []
        for row in c.fetchall():
            games.append({
                'id': row[0],
                'startTime': row[1],
                'endTime': row[2],
                'score': row[3],
                'coinsCollected': row[4],
                'ufosShot': row[5],
                'bulletsFired': row[6],
                'deathReason': row[7],
                'gameDuration': row[8],
                'pipesPassed': row[9]
            })
        
        conn.close()
        
        # Tạo thư mục data nếu chưa tồn tại
        os.makedirs('static/data', exist_ok=True)
        
        # Export to JSON file
        with open('static/data/analytics.json', 'w', encoding='utf-8') as f:
            json.dump({
                'games': games,
                'last_updated': datetime.now().isoformat(),
                'total_games': len(games)
            }, f, indent=2)
        
        return jsonify({'status': 'success', 'exported_games': len(games)})
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Generate complete stats data for static usage
def generate_complete_stats():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Basic stats
        c.execute('SELECT COUNT(*), AVG(score), MAX(score), AVG(game_duration), AVG(bullets_fired) FROM game_sessions')
        result = c.fetchone()
        total_games = result[0] if result[0] else 0
        avg_score = round(result[1] or 0, 1)
        max_score = result[2] or 0
        avg_duration = round(result[3] or 0, 1)
        avg_bullets = round(result[4] or 0, 1)
        
        # Death reasons
        c.execute('SELECT death_reason, COUNT(*) FROM game_sessions WHERE death_reason IS NOT NULL GROUP BY death_reason')
        death_reasons = dict(c.fetchall())
        
        # Recent games
        c.execute('''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration, death_reason, end_time 
            FROM game_sessions 
            ORDER BY end_time DESC 
            LIMIT 10
        ''')
        recent_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4],
                'death_reason': row[5]
            }
            for row in c.fetchall()
        ]
        
        # Score distribution
        c.execute('SELECT score FROM game_sessions')
        scores = [row[0] for row in c.fetchall()]

        score_distribution = {
            '0-4': 0,
            '5-9': 0,
            '10-14': 0,
            '15-19': 0,
            '20-24': 0,
            '25-29': 0,
            '30-34': 0,
            '35-39': 0,
            '40-44': 0,
            '45-49': 0,
            '50+': 0
        }

        for score in scores:
            if score >= 50:
                score_distribution['50+'] += 1
            elif score >= 45:
                score_distribution['45-49'] += 1
            elif score >= 40:
                score_distribution['40-44'] += 1
            elif score >= 35:
                score_distribution['35-39'] += 1
            elif score >= 30:
                score_distribution['30-34'] += 1
            elif score >= 25:
                score_distribution['25-29'] += 1
            elif score >= 20:
                score_distribution['20-24'] += 1
            elif score >= 15:
                score_distribution['15-19'] += 1
            elif score >= 10:
                score_distribution['10-14'] += 1
            elif score >= 5:
                score_distribution['5-9'] += 1
            else:
                score_distribution['0-4'] += 1
        
        # All games for scatter plots
        c.execute('''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration
            FROM game_sessions
        ''')
        all_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4]
            }
            for row in c.fetchall()
        ]
        
        # Bullets stats
        c.execute('SELECT MAX(bullets_fired), AVG(bullets_fired) FROM game_sessions')
        bullet_stats = c.fetchone()
        max_bullets = bullet_stats[0] or 0
        avg_bullets = round(bullet_stats[1] or 0, 1)
        
        conn.close()
        
        return {
            'total_games': total_games,
            'avg_score': avg_score,
            'max_score': max_score,
            'avg_duration': avg_duration,
            'avg_bullets': avg_bullets,
            'max_bullets': max_bullets,
            'death_reasons': death_reasons,
            'recent_games': recent_games,
            'score_distribution': score_distribution,
            'all_games': all_games
        }
        
    except Exception as e:
        logger.error(f"Error generating stats: {e}")
        return {}

# THÊM: Export complete stats to JSON
@app.route('/api/export-stats')
def export_stats():
    try:
        stats_data = generate_complete_stats()
        
        # Tạo thư mục data nếu chưa tồn tại
        os.makedirs('static/data', exist_ok=True)
        
        # Export stats to JSON file
        with open('static/data/stats.json', 'w', encoding='utf-8') as f:
            json.dump({
                **stats_data,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
        
        return jsonify({'status': 'success', 'message': 'Stats exported successfully'})
        
    except Exception as e:
        logger.error(f"Error exporting stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# THÊM: Generate static HTML dashboard
@app.route('/api/generate-dashboard')
def generate_dashboard():
    try:
        # Get current stats
        stats_data = generate_complete_stats()
        
        # Tạo thư mục static nếu chưa tồn tại
        os.makedirs('static', exist_ok=True)
        
        # HTML template với data nhúng sẵn
        html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flappy Plane Analytics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}

        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #eee;
        }}

        .header h1 {{
            color: #2c3e50;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            color: #7f8c8d;
            font-size: 1.1em;
        }}

        .stats-grid {{
            display: grid;
            grid-template-co...(truncated 5823 characters)...    </div>
        </div>

        <div class="recent-games">
            <h2>Recent Game Sessions</h2>
            <table class="game-table">
                <thead>
                    <tr>
                        <th>Score</th>
                        <th>Coins</th>
                        <th>UFOs Shot</th>
                        <th>Bullets Fired</th>
                        <th>Duration (s)</th>
                        <th>Death Reason</th>
                    </tr>
                </thead>
                <tbody id="recentGamesBody">
                    {"".join(f'''
                    <tr>
                        <td style="font-weight: bold; color: #2c3e50;">{game['score']}</td>
                        <td>{game['coins']}</td>
                        <td>{game['ufos']}</td>
                        <td>{game['bullets']}</td>
                        <td>{game['duration']}</td>
                        <td>{(game['death_reason'] or 'unknown').replace('_', ' ')}</td>
                    </tr>
                    ''' for game in stats_data.get('recent_games', []))}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // Embedded data from Flask server
        const statsData = {json.dumps(stats_data)};
        
        // Initialize charts with embedded data
        document.addEventListener('DOMContentLoaded', function() {{
            createDeathReasonsChart(statsData.death_reasons || {{}});
            createScoreHistogram(statsData.score_distribution || {{}});
            createScatterPlots(statsData.all_games || []);
        }});

        // Chart functions (same as your original JavaScript)
        function createDeathReasonsChart(deathReasons) {{
            const ctx = document.getElementById('deathChart').getContext('2d');
            const chartColors = {{
                pipe: '#e74c3c',
                ufo_collision: '#9b59b6',
                enemy_bullet: '#3498db',
                ground: '#f39c12',
                ceiling: '#1abc9c',
                unknown: '#95a5a6'
            }};

            const labels = Object.keys(deathReasons).map(reason => 
                reason.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase())
            );
            const data = Object.values(deathReasons);
            const backgroundColors = Object.keys(deathReasons).map(reason => chartColors[reason] || chartColors.unknown);

            new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: labels,
                    datasets: [{{
                        data: data,
                        backgroundColor: backgroundColors,
                        borderColor: 'white',
                        borderWidth: 2,
                        hoverOffset: 10
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right',
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const label = context.label || '';
                                    const value = context.raw || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${{label}}: ${{value}} (${{percentage}}%)`;
                                }}
                            }}
                        }}
                    }},
                    cutout: '60%'
                }}
            }});
        }}

        function createScoreHistogram(scoreBuckets) {{
            const ctx = document.getElementById('scoreChart').getContext('2d');
            
            const sortedEntries = Object.entries(scoreBuckets).sort((a, b) => {{
                const getBucketValue = (bucket) => {{
                    if (bucket === '50+') return 999;
                    if (bucket.includes('-')) {{
                        return parseInt(bucket.split('-')[0]);
                    }}
                    return parseInt(bucket);
                }};
                return getBucketValue(a[0]) - getBucketValue(b[0]);
            }});

            const sortedLabels = sortedEntries.map(entry => entry[0]);
            const sortedData = sortedEntries.map(entry => entry[1]);

            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: sortedLabels,
                    datasets: [{{
                        label: 'Number of Games',
                        data: sortedData,
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 1,
                        borderRadius: 5,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Number of Games' }} }},
                        x: {{ title: {{ display: true, text: 'Score Range' }} }}
                    }}
                }}
            }});
        }}

        function createScatterPlots(games) {{
            // Score vs Bullets
            const scoreBulletsCtx = document.getElementById('scoreBulletsChart').getContext('2d');
            const scoreBulletsData = games.map(game => ({{ x: game.bullets || 0, y: game.score || 0 }}));
            
            new Chart(scoreBulletsCtx, {{
                type: 'scatter',
                data: {{
                    datasets: [{{
                        label: 'Games',
                        data: scoreBulletsData,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)',
                        pointRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ title: {{ display: true, text: 'Bullets Fired' }} }},
                        y: {{ title: {{ display: true, text: 'Score' }} }}
                    }}
                }}
            }});

            // UFOs vs Coins
            const ufoCoinCtx = document.getElementById('ufoCoinChart').getContext('2d');
            const ufoCoinData = games.map(game => ({{ x: game.coins || 0, y: game.ufos || 0 }}));
            
            new Chart(ufoCoinCtx, {{
                type: 'scatter',
                data: {{
                    datasets: [{{
                        label: 'Games',
                        data: ufoCoinData,
                        backgroundColor: 'rgba(75, 192, 192, 0.6)',
                        pointRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ title: {{ display: true, text: 'Coins Collected' }} }},
                        y: {{ title: {{ display: true, text: 'UFOs Shot' }} }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
        '''
        
        # Save static HTML
        with open('static/dashboard.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return jsonify({
            'status': 'success', 
            'message': 'Static dashboard generated',
            'file': 'static/dashboard.html'
        })
        
    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/plane-stats')
def get_plane_stats():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Basic stats - thêm avg_bullets
        c.execute('SELECT COUNT(*), AVG(score), MAX(score), AVG(game_duration), AVG(bullets_fired) FROM game_sessions')
        result = c.fetchone()
        total_games = result[0] if result[0] else 0
        avg_score = round(result[1] or 0, 1)
        max_score = result[2] or 0
        avg_duration = round(result[3] or 0, 1)
        avg_bullets = round(result[4] or 0, 1)
        
        # Death reasons
        c.execute('SELECT death_reason, COUNT(*) FROM game_sessions WHERE death_reason IS NOT NULL GROUP BY death_reason')
        death_reasons = dict(c.fetchall())
        
        # Recent games - thêm bullets_fired
        c.execute('''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration, death_reason, end_time 
            FROM game_sessions 
            ORDER BY end_time DESC 
            LIMIT 100
        ''')
        recent_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4],
                'death_reason': row[5],
                'date': row[6]
            }
            for row in c.fetchall()
        ]
        
        # Score distribution với buckets mới
        c.execute('SELECT score FROM game_sessions')
        scores = [row[0] for row in c.fetchall()]

        score_distribution = {
            '0-4': 0,
            '5-9': 0,
            '10-14': 0,
            '15-19': 0,
            '20-24': 0,
            '25-29': 0,
            '30-34': 0,
            '35-39': 0,
            '40-44': 0,
            '45-49': 0,
            '50+': 0
        }

        # Count scores in each bucket
        for score in scores:
            if score >= 50:
                score_distribution['50+'] += 1
            elif score >= 45:
                score_distribution['45-49'] += 1
            elif score >= 40:
                score_distribution['40-44'] += 1
            elif score >= 35:
                score_distribution['35-39'] += 1
            elif score >= 30:
                score_distribution['30-34'] += 1
            elif score >= 25:
                score_distribution['25-29'] += 1
            elif score >= 20:
                score_distribution['20-24'] += 1
            elif score >= 15:
                score_distribution['15-19'] += 1
            elif score >= 10:
                score_distribution['10-14'] += 1
            elif score >= 5:
                score_distribution['5-9'] += 1
            else:
                score_distribution['0-4'] += 1
        
        # Lấy tất cả games cho scatter plots - thêm bullets_fired
        c.execute('''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration
            FROM game_sessions
        ''')
        all_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4]
            }
            for row in c.fetchall()
        ]
        
        # Thêm stats về bullets
        c.execute('SELECT MAX(bullets_fired), AVG(bullets_fired) FROM game_sessions')
        bullet_stats = c.fetchone()
        max_bullets = bullet_stats[0] or 0
        avg_bullets = round(bullet_stats[1] or 0, 1)
        
        conn.close()
        
        return jsonify({
            'total_games': total_games,
            'avg_score': avg_score,
            'max_score': max_score,
            'avg_duration': avg_duration,
            'avg_bullets': avg_bullets,
            'max_bullets': max_bullets,
            'death_reasons': death_reasons,
            'recent_games': recent_games,
            'score_distribution': score_distribution,
            'all_games': all_games  # Thêm dữ liệu cho scatter plots
        })
        
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'plane-analytics'})

# THÊM: Route để xem static dashboard
@app.route('/')
def serve_dashboard():
    return app.send_static_file('dashboard.html')

if __name__ == '__main__':
    init_db()
    logger.info("🚀 Plane Analytics Server starting on http://localhost:5000")
    logger.info("📊 New endpoints available:")
    logger.info("   - /api/export-data     - Export raw data to JSON")
    logger.info("   - /api/export-stats    - Export statistics to JSON") 
    logger.info("   - /api/generate-dashboard - Generate static HTML dashboard")
    logger.info("   - /                    - View static dashboard")
    logger.info("⚠️  Press Ctrl+C to stop server - data will be preserved")
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)), host='0.0.0.0') 
    
# Ensure DB initialized when app starts (Gunicorn compatible)
init_db()