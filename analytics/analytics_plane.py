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

# Hàm xử lý tắt server
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
        
        # Gộp logic: Nếu là 1 object đơn, bọc nó vào mảng để dùng chung logic xử lý batch
        if not isinstance(data, list):
            data = [data]
            
        return process_batch_analytics(data)
        
    except Exception as e:
        logger.error(f"Error storing analytics: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Xử lý batch analytics (Đã dùng chung cho cả batch và single)
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

# Endpoint để client đồng bộ dữ liệu local
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

# Export data to JSON file
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

# GỘP LOGIC: Thêm tham số recent_limit (mặc định 10) để dùng chung cho cả static stats và api stats
def generate_complete_stats(recent_limit=10):
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
        
        # Recent games (Sử dụng tham số recent_limit)
        c.execute(f'''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration, death_reason, end_time 
            FROM game_sessions 
            ORDER BY end_time DESC 
            LIMIT {int(recent_limit)}
        ''')
        recent_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4],
                'death_reason': row[5],
                'date': row[6].isoformat() if hasattr(row[6], 'isoformat') else row[6] # Giữ lại hàm xử lý isoformat an toàn hơn
            }
            for row in c.fetchall()
        ]
        
        # Score distribution
        c.execute('SELECT score FROM game_sessions')
        scores = [row[0] for row in c.fetchall()]

        score_distribution = {
            '0-4': 0, '5-9': 0, '10-14': 0, '15-19': 0, '20-24': 0,
            '25-29': 0, '30-34': 0, '35-39': 0, '40-44': 0, '45-49': 0,
            '50-54': 0, '55-59': 0, '60-64': 0, '65-69': 0, '70+': 0
        }

        for score in scores:
            if score >= 70: score_distribution['70+'] += 1
            elif score >= 65: score_distribution['65-69'] += 1
            elif score >= 60: score_distribution['60-64'] += 1
            elif score >= 55: score_distribution['55-59'] += 1
            elif score >= 50: score_distribution['50-54'] += 1
            elif score >= 45: score_distribution['45-49'] += 1
            elif score >= 40: score_distribution['40-44'] += 1
            elif score >= 35: score_distribution['35-39'] += 1
            elif score >= 30: score_distribution['30-34'] += 1
            elif score >= 25: score_distribution['25-29'] += 1
            elif score >= 20: score_distribution['20-24'] += 1
            elif score >= 15: score_distribution['15-19'] += 1
            elif score >= 10: score_distribution['10-14'] += 1
            elif score >= 5: score_distribution['5-9'] += 1
            else: score_distribution['0-4'] += 1
        
        # All games for scatter plots
        c.execute('''
            SELECT score, coins_collected, ufos_shot, bullets_fired, game_duration, death_reason, end_time
            FROM game_sessions
        ''')
        all_games = [
            {
                'score': row[0],
                'coins': row[1],
                'ufos': row[2],
                'bullets': row[3],
                'duration': row[4],
                'death_reason': row[5],
                'date': row[6].isoformat() if hasattr(row[6], 'isoformat') else row[6]
            }
            for row in c.fetchall()
        ]
        
        # Bullets stats
        c.execute('SELECT MAX(bullets_fired), AVG(bullets_fired) FROM game_sessions')
        bullet_stats = c.fetchone()
        max_bullets = bullet_stats[0] or 0
        avg_bullets = round(bullet_stats[1] or 0, 1) # Override lại avg_bullets cho chuẩn xác với max
        
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

# Export complete stats to JSON
@app.route('/api/export-stats')
def export_stats():
    try:
        stats_data = generate_complete_stats() # Dùng mặc định limit = 10
        
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

# Generate static HTML dashboard
@app.route('/api/generate-dashboard')
def generate_dashboard():
    try:
        # Get current stats
        stats_data = generate_complete_stats() # Dùng mặc định limit = 10
        
        # Tạo thư mục static nếu chưa tồn tại
        os.makedirs('static', exist_ok=True)
        
        # Cập nhật khối HTML tĩnh theo file mới nhất từ client
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
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }}

        .stat-card:hover {{
            transform: translateY(-5px);
        }}

        .stat-card h3 {{
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            opacity: 0.9;
        }}

        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
        }}

        .charts-container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}

        .chart-box {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            height: 450px;
            position: relative;
            display: flex;
            flex-direction: column;
        }}

        .chart-box h2 {{
            color: #2c3e50;
            margin-bottom: 15px;
            text-align: center;
            font-size: 1.4em;
        }}

        .chart-container {{
            flex-grow: 1;
            position: relative;
            min-height: 0;
        }}

        .scatter-charts {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}

        .chart-controls {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }}

        .chart-controls select, .chart-controls input[type="number"] {{
            padding: 8px 12px;
            border: 1px solid #ccd1d9;
            border-radius: 6px;
            font-size: 0.9em;
            color: #2c3e50;
            background-color: #f8f9fa;
            outline: none;
            transition: all 0.3s ease;
        }}

        .chart-controls select:focus, .chart-controls input:focus {{
            border-color: #667eea;
            box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
        }}

        .chart-controls input[type="range"] {{
            accent-color: #667eea;
        }}

        .recent-games {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}

        .recent-games h2 {{
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
            font-size: 1.4em;
        }}

        .table-wrapper {{
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #eee;
            border-radius: 8px;
        }}

        .game-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 0;
        }}

        .game-table th {{
            background: #34495e;
            color: white;
            padding: 15px;
            text-align: center;
            font-weight: bold;
            border: none;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .game-table td {{
            padding: 12px 15px;
            text-align: center;
            border-bottom: 1px solid #eee;
        }}

        .game-table tr:nth-child(even) {{
            background: #f8f9fa;
        }}

        .game-table tr:hover {{
            background: #e9ecef;
        }}

        @media (max-width: 768px) {{
            .charts-container, .scatter-charts {{
                grid-template-columns: 1fr;
            }}
            
            .stat-card .value {{
                font-size: 2em;
            }}
            
            .chart-box {{
                height: 400px;
            }}
            
            .table-wrapper {{
                max-height: 300px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Flappy Plane Analytics</h1>
            <p>Detailed statistics and performance analysis (Static View)</p>
            <p style="font-size: 0.9em; margin-top: 10px;">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Games Played</h3>
                <div class="value">{stats_data.get('total_games', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Average Score</h3>
                <div class="value">{stats_data.get('avg_score', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Highest Score</h3>
                <div class="value">{stats_data.get('max_score', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Avg Duration (s)</h3>
                <div class="value">{stats_data.get('avg_duration', 0)}</div>
            </div>
            <div class="stat-card">
                <h3>Avg Bullets Fired</h3>
                <div class="value">{stats_data.get('avg_bullets', 0)}</div>
            </div>
        </div>

        <div class="charts-container">
            <div class="chart-box">
                <h2>Death Reasons Distribution</h2>
                <div class="chart-container">
                    <canvas id="deathChart"></canvas>
                </div>
            </div>
            
            <div class="chart-box">
                <h2>Score Distribution</h2>
                <div class="chart-controls">
                    <select id="scoreFilter">
                        <option value="All">All Death Reasons</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="scoreChart"></canvas>
                </div>
            </div>
        </div>

        <div class="scatter-charts">
            <div class="chart-box">
                <h2>Parameter Relationship</h2>
                <div class="chart-controls">
                    <select id="scatterX">
                        <option value="bullets" selected>Bullets Fired</option>
                        <option value="score">Score</option>
                        <option value="coins">Coins Collected</option>
                        <option value="ufos">UFOs Shot</option>
                        <option value="duration">Duration (s)</option>
                    </select>
                    <span style="font-weight: bold; color: #7f8c8d;">VS</span>
                    <select id="scatterY">
                        <option value="score" selected>Score</option>
                        <option value="bullets">Bullets Fired</option>
                        <option value="coins">Coins Collected</option>
                        <option value="ufos">UFOs Shot</option>
                        <option value="duration">Duration (s)</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="dynamicScatterChart"></canvas>
                </div>
            </div>
            
            <div class="chart-box">
                <h2 id="areaChartTitle">Daily Game Sessions</h2>
                <div class="chart-controls">
                    <select id="areaModeSelect">
                        <option value="daily" selected>Daily Sessions</option>
                        <option value="cumulative">Cumulative (Total)</option>
                    </select>
                    <label style="font-size: 0.9em; color: #7f8c8d; font-weight: bold; margin-left: 10px;">Last Days: <span id="daysSliderValue" style="color: #2c3e50;">All</span></label>
                    <input type="range" id="areaDaysFilter" min="1" max="100" value="100" style="width: 120px; cursor: pointer; vertical-align: middle;">
                </div>
                <div class="chart-container">
                    <canvas id="cumulativeAreaChart"></canvas>
                </div>
            </div>
        </div>

        <div class="recent-games">
            <h2>Recent Game Sessions</h2>
            <div class="table-wrapper">
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
    </div>

    <script>
        const statsData = {json.dumps(stats_data)};
        let globalGamesData = statsData.all_games || [];
        let deathChart, scoreChart, dynamicScatterChart, cumulativeAreaChart;

        document.addEventListener('DOMContentLoaded', function() {{
            createDeathReasonsChart(statsData.death_reasons || {{}});
            populateScoreFilterOptions(globalGamesData);
            updateScoreHistogram();
            updateScatterPlot();
            updateCumulativeAreaChart();

            document.getElementById('scoreFilter').addEventListener('change', updateScoreHistogram);

            const scatterX = document.getElementById('scatterX');
            const scatterY = document.getElementById('scatterY');
            const handleScatterChange = (e) => {{
                if (scatterX.value === scatterY.value) {{
                    const options = ['bullets', 'score', 'coins', 'ufos', 'duration'];
                    const changedId = e.target.id;
                    const otherSelect = changedId === 'scatterX' ? scatterY : scatterX;
                    otherSelect.value = options.find(opt => opt !== e.target.value);
                }}
                updateScatterPlot();
            }};
            scatterX.addEventListener('change', handleScatterChange);
            scatterY.addEventListener('change', handleScatterChange);

            document.getElementById('areaDaysFilter').addEventListener('input', updateCumulativeAreaChart);
            document.getElementById('areaModeSelect').addEventListener('change', updateCumulativeAreaChart);
        }});

        function createDeathReasonsChart(deathReasons) {{
            const ctx = document.getElementById('deathChart').getContext('2d');
            const chartColors = {{
                pipe: '#e74c3c', ufo_collision: '#9b59b6', enemy_bullet: '#3498db',
                ground: '#f39c12', ceiling: '#1abc9c', unknown: '#95a5a6'
            }};

            if (deathReasons['unknown']) delete deathReasons['unknown'];
            const sortedEntries = Object.entries(deathReasons).sort((a, b) => b[1] - a[1]);

            if (sortedEntries.length === 0) return;

            const labels = sortedEntries.map(([reason]) => reason.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase()));
            const data = sortedEntries.map(entry => entry[1]);
            const backgroundColors = sortedEntries.map(([reason]) => chartColors[reason] || chartColors.unknown);

            deathChart = new Chart(ctx, {{
                type: 'doughnut',
                data: {{
                    labels: labels,
                    datasets: [{{ data: data, backgroundColor: backgroundColors, borderColor: 'white', borderWidth: 2, hoverOffset: 10 }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false, rotation: -90 * (Math.PI / 180),
                    plugins: {{
                        legend: {{ position: 'right', labels: {{ padding: 20, usePointStyle: true, pointStyle: 'circle' }} }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const value = context.raw || 0;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((value / total) * 100);
                                    return `${{context.label}}: ${{value}} (${{percentage}}%)`;
                                }}
                            }}
                        }}
                    }},
                    cutout: '60%'
                }}
            }});
        }}

        function populateScoreFilterOptions(games) {{
            const select = document.getElementById('scoreFilter');
            select.innerHTML = '<option value="All">All Death Reasons</option>';
            const reasons = new Set();
            games.forEach(g => {{ if (g.death_reason && g.death_reason !== 'unknown') reasons.add(g.death_reason); }});
            Array.from(reasons).sort().forEach(reason => {{
                const opt = document.createElement('option');
                opt.value = reason;
                opt.textContent = reason.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase());
                select.appendChild(opt);
            }});
        }}

        function updateScoreHistogram() {{
            const filterValue = document.getElementById('scoreFilter').value;
            let filteredGames = globalGamesData;
            if (filterValue !== 'All') filteredGames = globalGamesData.filter(g => g.death_reason === filterValue);

            const scoreBuckets = {{
                '0-4': 0, '5-9': 0, '10-14': 0, '15-19': 0, '20-24': 0,
                '25-29': 0, '30-34': 0, '35-39': 0, '40-44': 0, '45-49': 0, 
                '50-54': 0, '55-59': 0, '60-64': 0, '65-69': 0, '70+': 0
            }};

            filteredGames.forEach(game => {{
                const score = game.score || 0;
                let bucket;
                if (score >= 70) bucket = '70+';
                else if (score >= 65) bucket = '65-69';
                else if (score >= 60) bucket = '60-64';
                else if (score >= 55) bucket = '55-59';
                else if (score >= 50) bucket = '50-54';
                else if (score >= 45) bucket = '45-49';
                else if (score >= 40) bucket = '40-44';
                else if (score >= 35) bucket = '35-39';
                else if (score >= 30) bucket = '30-34';
                else if (score >= 25) bucket = '25-29';
                else if (score >= 20) bucket = '20-24';
                else if (score >= 15) bucket = '15-19';
                else if (score >= 10) bucket = '10-14';
                else if (score >= 5)  bucket = '5-9';
                else bucket = '0-4';
                scoreBuckets[bucket]++;
            }});

            const ctx = document.getElementById('scoreChart').getContext('2d');
            if (scoreChart) scoreChart.destroy();

            const sortedEntries = Object.entries(scoreBuckets).sort((a, b) => {{
                const getBucketValue = (bucket) => {{
                    if (bucket === '70+') return 999;
                    if (bucket.includes('-')) return parseInt(bucket.split('-')[0]);
                    return parseInt(bucket);
                }};
                return getBucketValue(a[0]) - getBucketValue(b[0]);
            }});

            const sortedLabels = sortedEntries.map(entry => entry[0]);
            const sortedData = sortedEntries.map(entry => entry[1]);

            const maxDataValue = Math.max(...sortedData, 0);
            let calculatedStepSize = 1;
            if (maxDataValue > 100) calculatedStepSize = 20;
            else if (maxDataValue > 50) calculatedStepSize = 10;
            else if (maxDataValue > 20) calculatedStepSize = 5;
            else if (maxDataValue > 10) calculatedStepSize = 2;

            scoreChart = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: sortedLabels,
                    datasets: [{{
                        label: 'Number of Games',
                        data: sortedData,
                        backgroundColor: 'rgba(102, 126, 234, 0.7)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 1, borderRadius: 5,
                    }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        y: {{ beginAtZero: true, title: {{ display: true, text: 'Number of Games' }}, grid: {{ color: 'rgba(0, 0, 0, 0.1)' }}, ticks: {{ stepSize: calculatedStepSize, precision: 0 }} }},
                        x: {{ title: {{ display: true, text: 'Score Range' }}, grid: {{ display: false }} }}
                    }}
                }}
            }});
        }}

        function updateScatterPlot() {{
            const scatterX = document.getElementById('scatterX');
            const scatterY = document.getElementById('scatterY');
            const xParam = scatterX.value;
            const yParam = scatterY.value;
            const xLabel = scatterX.options[scatterX.selectedIndex].text;
            const yLabel = scatterY.options[scatterY.selectedIndex].text;
            
            const dataMap = globalGamesData.map(game => ({{ x: game[xParam] || 0, y: game[yParam] || 0 }}));
            const ctx = document.getElementById('dynamicScatterChart').getContext('2d');
            if (dynamicScatterChart) dynamicScatterChart.destroy();

            dynamicScatterChart = new Chart(ctx, {{
                type: 'scatter',
                data: {{
                    datasets: [{{
                        label: 'Games', data: dataMap,
                        backgroundColor: 'rgba(255, 99, 132, 0.6)', borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1, pointRadius: 6, pointHoverRadius: 8
                    }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    scales: {{
                        x: {{ title: {{ display: true, text: xLabel }}, grid: {{ color: 'rgba(0, 0, 0, 0.1)' }} }},
                        y: {{ title: {{ display: true, text: yLabel }}, grid: {{ color: 'rgba(0, 0, 0, 0.1)' }} }}
                    }}
                }}
            }});
        }}

        function updateCumulativeAreaChart() {{
            const mode = document.getElementById('areaModeSelect').value;
            document.getElementById('areaChartTitle').innerText = mode === 'daily' ? 'Daily Game Sessions' : 'Cumulative Game Sessions';

            const validGames = globalGamesData.filter(g => g.date && g.date !== 'N/A');
            if (validGames.length === 0) return;

            const dailyCounts = {{}};
            let minDate = new Date('9999-12-31');
            let maxDate = new Date('1970-01-01');

            validGames.forEach(g => {{
                const d = new Date(g.date);
                if (isNaN(d.getTime())) return;
                const dateStr = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
                dailyCounts[dateStr] = (dailyCounts[dateStr] || 0) + 1;
                const dayOnly = new Date(d.getFullYear(), d.getMonth(), d.getDate());
                if (dayOnly < minDate) minDate = dayOnly;
                if (dayOnly > maxDate) maxDate = dayOnly;
            }});

            const allDays = [];
            const counts = [];
            let currentDay = new Date(minDate);
            while (currentDay <= maxDate) {{
                const dateStr = currentDay.getFullYear() + '-' + String(currentDay.getMonth()+1).padStart(2, '0') + '-' + String(currentDay.getDate()).padStart(2, '0');
                allDays.push(dateStr);
                counts.push(dailyCounts[dateStr] || 0);
                currentDay.setDate(currentDay.getDate() + 1);
            }}

            let finalData;
            let chartLabel;
            let yAxisLabel;
            
            if (mode === 'daily') {{
                finalData = counts;
                chartLabel = 'Daily Sessions';
                yAxisLabel = 'Daily Sessions';
            }} else {{
                const cumulativeCounts = [];
                let sum = 0;
                for (let c of counts) {{ sum += c; cumulativeCounts.push(sum); }}
                finalData = cumulativeCounts;
                chartLabel = 'Total Sessions';
                yAxisLabel = 'Total Sessions';
            }}

            const slider = document.getElementById('areaDaysFilter');
            const sliderLabel = document.getElementById('daysSliderValue');
            const totalDays = allDays.length || 1;
            
            if (slider.getAttribute('data-total') !== totalDays.toString()) {{
                slider.max = totalDays;
                slider.value = totalDays;
                slider.setAttribute('data-total', totalDays);
            }}

            let daysLimit = parseInt(slider.value);
            if (daysLimit === totalDays) {{
                sliderLabel.innerText = "All";
                daysLimit = null;
            }} else {{
                sliderLabel.innerText = daysLimit;
            }}

            let finalLabels = allDays;
            if (daysLimit && daysLimit > 0 && allDays.length > daysLimit) {{
                finalLabels = allDays.slice(-daysLimit);
                finalData = finalData.slice(-daysLimit);
            }}

            const ctx = document.getElementById('cumulativeAreaChart').getContext('2d');
            if (cumulativeAreaChart) cumulativeAreaChart.destroy();

            cumulativeAreaChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: finalLabels,
                    datasets: [{{
                        label: chartLabel,
                        data: finalData,
                        fill: mode === 'cumulative',
                        backgroundColor: 'rgba(118, 75, 162, 0.1)',
                        borderColor: 'rgba(118, 75, 162, 1)',
                        borderWidth: 2,
                        stepped: true,
                        pointRadius: 0, 
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: 'rgba(118, 75, 162, 1)', 
                        pointHoverBorderColor: '#fff', 
                        pointHoverBorderWidth: 2, 
                        pointHitRadius: 10 
                    }}]
                }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{ mode: 'index', intersect: false }}
                    }},
                    scales: {{
                        x: {{
                            grid: {{ display: false }},
                            ticks: {{
                                autoSkip: true, maxTicksLimit: 12, maxRotation: 0,
                                callback: function(value, index, ticks) {{
                                    const dateStr = this.getLabelForValue(value);
                                    const d = new Date(dateStr);
                                    const label = d.toLocaleString('en-US', {{ month: 'short', year: 'numeric' }});
                                    if (label === 'Nov 2025') return null;
                                    if (index > 0) {{
                                        const prevDateStr = this.getLabelForValue(ticks[index - 1].value);
                                        const prevLabel = new Date(prevDateStr).toLocaleString('en-US', {{ month: 'short', year: 'numeric' }});
                                        if (label === prevLabel) return null; 
                                    }}
                                    return label;
                                }}
                            }}
                        }},
                        y: {{ beginAtZero: true, title: {{ display: true, text: yAxisLabel }}, grid: {{ color: 'rgba(0, 0, 0, 0.1)' }} }}
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

# GỘP LOGIC: Đã tận dụng lại toàn bộ hàm thống kê bên trên, chỉ đổi limit=500
@app.route('/api/plane-stats')
def get_plane_stats():
    try:
        # Gọi lại hàm lấy dữ liệu với limit 500
        stats_data = generate_complete_stats(recent_limit=500)
        return jsonify(stats_data)
        
    except Exception as e:
        logger.error(f"Error retrieving stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'plane-analytics'})

# Route để xem static dashboard
@app.route('/')
def serve_dashboard():
    return app.send_static_file('dashboard.html')

# KHỞI TẠO DATABASE AN TOÀN CHO RENDER (GUNICORN)
# Bọc trong app_context và try-except để không bị treo server nếu mạng chậm
with app.app_context():
    try:
        init_db()
        logger.info("✅ Database initialized successfully on boot!")
    except Exception as e:
        logger.error(f"⚠️ Warning: Could not initialize DB on boot: {e}")

if __name__ == '__main__':
    logger.info("🚀 Plane Analytics Server starting")
    logger.info("📊 New endpoints available:")
    logger.info("   - /api/export-data     - Export raw data to JSON")
    logger.info("   - /api/export-stats    - Export statistics to JSON") 
    logger.info("   - /api/generate-dashboard - Generate static HTML dashboard")
    logger.info("   - /                    - View static dashboard")
    logger.info("⚠️  Press Ctrl+C to stop server - data will be preserved")
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)), host='0.0.0.0')