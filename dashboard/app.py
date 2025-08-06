import os
from flask import Flask, render_template, jsonify, request
import pandas as pd

from dashboard.config import Config
from dashboard.data_access import get_latest_metrics, get_equity_curve, get_todays_signals, get_sharpe_heatmap_data

app = Flask(__name__)
app.config.from_object(Config)

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signals')
def signals():
    return render_template('signals.html')

@app.route('/ticker/<string:ticker>')
def ticker_profile(ticker):
    return render_template('ticker.html', ticker=ticker)

@app.route('/backtest')
def backtest():
    return render_template('backtest.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

# --- API Endpoints ---

@app.route('/api/metrics')
def api_metrics():
    latest_metrics = get_latest_metrics()
    metrics_display = [
        {'label': 'Sharpe_60d', 'value': f"{latest_metrics.get('sharpe_ratio_60d', 0):.2f}"},
        {'label': 'Coverage', 'value': f"{latest_metrics.get('coverage_pct', 0):.1f}%"},
        {'label': 'PSI Confidence', 'value': f"{latest_metrics.get('psi_confidence', 0):.3f}"},
        {'label': 'Last Updated', 'value': latest_metrics.get('date', 'N/A')},
    ]
    return render_template('partials/metrics_cards.html', metrics=metrics_display)

@app.route('/api/equity')
def api_equity():
    equity_data = get_equity_curve()
    return jsonify({
        "dates": equity_data['date'].dt.strftime('%Y-%m-%d').tolist(),
        "equity": equity_data['equity'].tolist(),
        "spy_equity": equity_data['spy_equity'].tolist()
    })

@app.route('/api/signals')
def api_signals():
    signals_df = get_todays_signals()
    ticker_filter = request.args.get('ticker', '').upper()
    dir_filter = request.args.get('dir', '')
    h_filter = request.args.get('h', type=int)

    if ticker_filter:
        signals_df = signals_df[signals_df['ticker'].str.upper().str.contains(ticker_filter)]
    if dir_filter:
        signals_df = signals_df[signals_df['direction'] == dir_filter]
    if h_filter:
        signals_df = signals_df[signals_df['horizon_days'] <= h_filter]

    return render_template('partials/signals_table_rows.html', signals=signals_df.to_dict(orient='records'))

@app.route('/api/system_status')
def api_system_status():
    retrain_flag_path = os.path.join(Config.DATA_DIR, "RETRAIN_REQUIRED")
    status = {
        'retrain_required': os.path.exists(retrain_flag_path),
        'cache_size': 'N/A',
        'last_retrain_date': 'N/A'
    }
    return render_template('partials/system_status.html', status=status)

@app.route('/api/force_retrain', methods=['POST'])
def api_force_retrain():
    retrain_flag_path = os.path.join(Config.DATA_DIR, "RETRAIN_REQUIRED")
    with open(retrain_flag_path, 'w') as f:
        f.write(f"Forced by admin at {pd.Timestamp.now()}")
    return '<div class="alert alert-success" role="alert">RETRAIN_REQUIRED flag created.</div>'

@app.route('/api/clean_cache', methods=['POST'])
def api_clean_cache():
    # Placeholder logic
    return '<div class="alert alert-info" role="alert">Cache cleaning not implemented yet.</div>'

@app.route('/api/sharpe_heatmap')
def api_sharpe_heatmap():
    heatmap_data = get_sharpe_heatmap_data()
    return jsonify(heatmap_data)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
