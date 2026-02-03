"""
Interactive visualization module for Gitstats3.

Generates JavaScript-based interactive visualizations for HTML reports:
- File bubble plot (size/extension visualization)
- Commit activity heatmap calendar
- Module dependency diagrams
- Hotspot risk visualization
"""

from typing import Dict, List, Any, Optional
import json
import os

from .gitstats_config import conf


class VisualizationGenerator:
    """
    Generates interactive JavaScript visualizations for HTML reports.
    Uses Chart.js for charts and custom SVG for diagrams.
    """
    
    def __init__(self, data_collector, hotspot_data: Optional[Dict] = None):
        """
        Initialize the visualization generator.
        
        Args:
            data_collector: A DataCollector instance with collected repository data
            hotspot_data: Optional hotspot analysis results
        """
        self.data = data_collector
        self.hotspot_data = hotspot_data or {}
    
    def get_chart_js_cdn(self) -> str:
        """Return Chart.js CDN script tag."""
        return '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>'
    
    def generate_file_bubble_data(self) -> str:
        """
        Generate data for file bubble visualization.
        Files represented as bubbles with size proportional to LOC and color by extension.
        
        Returns:
            JSON string with bubble data
        """
        bubbles = []
        
        # Get file sizes
        file_sizes = getattr(self.data, 'file_sizes', {})
        file_revisions = getattr(self.data, 'file_revisions', {})
        
        if not file_revisions:
            file_revisions = self.data.code_analysis.get('file_revisions', {})
        
        # Extension color mapping
        ext_colors = {
            '.py': '#3572A5',
            '.js': '#F7DF1E',
            '.ts': '#3178C6',
            '.java': '#B07219',
            '.go': '#00ADD8',
            '.rs': '#DEA584',
            '.cpp': '#F34B7D',
            '.c': '#555555',
            '.rb': '#701516',
            '.php': '#4F5D95',
            '.swift': '#FA7343',
            '.kt': '#A97BFF',
            '.scala': '#DC322F',
            '.html': '#E34C26',
            '.css': '#563D7C',
            '.vue': '#4FC08D',
            '.jsx': '#61DAFB',
            '.tsx': '#3178C6',
        }
        default_color = '#6B7280'
        
        # Combine data
        all_files = set(file_sizes.keys()) | set(file_revisions.keys())
        
        for filepath in list(all_files)[:100]:  # Limit to 100 files for performance
            ext = os.path.splitext(filepath)[1].lower()
            size = file_sizes.get(filepath, 0)
            revisions = file_revisions.get(filepath, 0)
            
            # Normalize for bubble size (based on revisions)
            bubble_size = max(5, min(50, revisions * 3))
            
            bubbles.append({
                'label': os.path.basename(filepath),
                'path': filepath,
                'x': revisions,
                'y': size / 1000 if size > 0 else 1,  # Size in KB
                'r': bubble_size,
                'color': ext_colors.get(ext, default_color),
                'extension': ext or 'unknown'
            })
        
        return json.dumps(bubbles)
    
    def generate_file_bubble_chart_html(self) -> str:
        """Generate HTML/JS for file bubble chart."""
        bubble_data = self.generate_file_bubble_data()
        
        return f'''
<div class="visualization-section">
    <h3>📊 File Activity Bubble Chart</h3>
    <p class="viz-description">Each bubble represents a file. Size = revision count, position shows revisions vs file size.</p>
    <div style="height: 400px; position: relative;">
        <canvas id="fileBubbleChart"></canvas>
    </div>
</div>
<script>
(function() {{
    const bubbleData = {bubble_data};
    
    // Group by extension for datasets
    const grouped = {{}};
    bubbleData.forEach(b => {{
        const ext = b.extension || 'other';
        if (!grouped[ext]) grouped[ext] = [];
        grouped[ext].push(b);
    }});
    
    const datasets = Object.entries(grouped).map(([ext, files]) => ({{
        label: ext,
        data: files.map(f => ({{x: f.x, y: f.y, r: f.r, label: f.label, path: f.path}})),
        backgroundColor: files[0]?.color + '80' || '#6B728080',
        borderColor: files[0]?.color || '#6B7280',
        borderWidth: 1
    }}));
    
    new Chart(document.getElementById('fileBubbleChart'), {{
        type: 'bubble',
        data: {{ datasets }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{
                    display: true,
                    text: 'File Activity: Revisions vs Size'
                }},
                tooltip: {{
                    callbacks: {{
                        label: function(ctx) {{
                            const d = ctx.raw;
                            return d.label + ': ' + d.x + ' revisions, ' + d.y.toFixed(1) + ' KB';
                        }}
                    }}
                }}
            }},
            scales: {{
                x: {{
                    title: {{ display: true, text: 'Revisions' }},
                    beginAtZero: true
                }},
                y: {{
                    title: {{ display: true, text: 'File Size (KB)' }},
                    beginAtZero: true
                }}
            }}
        }}
    }});
}})();
</script>
'''
    
    def generate_commit_heatmap_data(self) -> str:
        """
        Generate data for commit activity heatmap calendar.
        
        Returns:
            JSON string with heatmap data (date -> commit count)
        """
        heatmap_data = {}
        
        # Get activity by date
        active_days = getattr(self.data, 'active_days', set())
        
        # Get commit counts by date if available
        commits_by_date = getattr(self.data, 'commits_by_date', {})
        
        if commits_by_date:
            heatmap_data = {str(k): v for k, v in commits_by_date.items()}
        elif active_days:
            # Fallback: just mark active days with count 1
            for day in active_days:
                heatmap_data[str(day)] = 1
        
        return json.dumps(heatmap_data)
    
    def generate_commit_heatmap_html(self) -> str:
        """Generate HTML/CSS/JS for commit activity heatmap."""
        heatmap_data = self.generate_commit_heatmap_data()
        
        return f'''
<div class="visualization-section">
    <h3>📅 Commit Activity Heatmap</h3>
    <p class="viz-description">Daily commit activity over the past year. Darker = more commits.</p>
    <div id="commitHeatmap" style="overflow-x: auto; padding: 10px 0;"></div>
</div>
<style>
.heatmap-container {{
    display: flex;
    flex-wrap: nowrap;
    gap: 2px;
}}
.heatmap-week {{
    display: flex;
    flex-direction: column;
    gap: 2px;
}}
.heatmap-day {{
    width: 12px;
    height: 12px;
    border-radius: 2px;
    cursor: pointer;
}}
.heatmap-day:hover {{
    outline: 2px solid #333;
}}
.heatmap-level-0 {{ background-color: #ebedf0; }}
.heatmap-level-1 {{ background-color: #9be9a8; }}
.heatmap-level-2 {{ background-color: #40c463; }}
.heatmap-level-3 {{ background-color: #30a14e; }}
.heatmap-level-4 {{ background-color: #216e39; }}
.heatmap-months {{
    display: flex;
    margin-bottom: 5px;
    font-size: 10px;
    color: #666;
}}
.heatmap-month-label {{
    flex: 1;
    text-align: center;
}}
</style>
<script>
(function() {{
    const heatmapData = {heatmap_data};
    const container = document.getElementById('commitHeatmap');
    
    // Generate last 52 weeks
    const today = new Date();
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - 364);
    
    // Align to Sunday
    startDate.setDate(startDate.getDate() - startDate.getDay());
    
    let html = '<div class="heatmap-container">';
    
    const maxCommits = Math.max(1, ...Object.values(heatmapData));
    
    for (let week = 0; week < 53; week++) {{
        html += '<div class="heatmap-week">';
        for (let day = 0; day < 7; day++) {{
            const date = new Date(startDate);
            date.setDate(date.getDate() + week * 7 + day);
            
            if (date > today) {{
                html += '<div class="heatmap-day heatmap-level-0"></div>';
                continue;
            }}
            
            const dateStr = date.toISOString().split('T')[0];
            const commits = heatmapData[dateStr] || 0;
            
            let level = 0;
            if (commits > 0) {{
                const ratio = commits / maxCommits;
                if (ratio > 0.75) level = 4;
                else if (ratio > 0.5) level = 3;
                else if (ratio > 0.25) level = 2;
                else level = 1;
            }}
            
            const title = dateStr + ': ' + commits + ' commit' + (commits !== 1 ? 's' : '');
            html += '<div class="heatmap-day heatmap-level-' + level + '" title="' + title + '"></div>';
        }}
        html += '</div>';
    }}
    
    html += '</div>';
    container.innerHTML = html;
}})();
</script>
'''
    
    def generate_hotspot_chart_html(self) -> str:
        """Generate HTML/JS for hotspot risk visualization."""
        hotspots = self.hotspot_data.get('hotspots', [])[:15]
        
        if not hotspots:
            return '<div class="visualization-section"><h3>🔥 Hotspot Analysis</h3><p>No hotspot data available.</p></div>'
        
        labels = [os.path.basename(h['filepath']) for h in hotspots]
        risk_scores = [h.get('risk_score', 0) for h in hotspots]
        churn_scores = [h.get('churn_score', 0) for h in hotspots]
        complexity_scores = [h.get('complexity_score', 0) for h in hotspots]
        
        return f'''
<div class="visualization-section">
    <h3>🔥 Code Hotspots - Risk Analysis</h3>
    <p class="viz-description">Files with highest combined risk from churn and complexity.</p>
    <div style="height: 400px; position: relative;">
        <canvas id="hotspotChart"></canvas>
    </div>
</div>
<script>
(function() {{
    new Chart(document.getElementById('hotspotChart'), {{
        type: 'bar',
        data: {{
            labels: {json.dumps(labels)},
            datasets: [
                {{
                    label: 'Risk Score',
                    data: {json.dumps(risk_scores)},
                    backgroundColor: 'rgba(255, 99, 132, 0.8)',
                    borderColor: 'rgb(255, 99, 132)',
                    borderWidth: 1,
                    order: 1
                }},
                {{
                    label: 'Churn Score',
                    data: {json.dumps(churn_scores)},
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    borderColor: 'rgb(54, 162, 235)',
                    borderWidth: 1,
                    order: 2
                }},
                {{
                    label: 'Complexity Score',
                    data: {json.dumps(complexity_scores)},
                    backgroundColor: 'rgba(255, 206, 86, 0.5)',
                    borderColor: 'rgb(255, 206, 86)',
                    borderWidth: 1,
                    order: 3
                }}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {{
                title: {{
                    display: true,
                    text: 'Top 15 Hotspots by Risk Score'
                }},
                tooltip: {{
                    mode: 'index',
                    intersect: false
                }}
            }},
            scales: {{
                x: {{
                    beginAtZero: true,
                    title: {{ display: true, text: 'Score' }}
                }}
            }}
        }}
    }});
}})();
</script>
'''
    
    def generate_hourly_activity_chart_html(self) -> str:
        """Generate HTML/JS for hourly activity polar chart."""
        hour_data = getattr(self.data, 'activity_by_hour_of_day', {})
        
        if not hour_data:
            return ''
        
        # Create 24-hour data array
        labels = [f'{h:02d}:00' for h in range(24)]
        values = [hour_data.get(h, 0) for h in range(24)]
        
        return f'''
<div class="visualization-section">
    <h3>⏰ Commit Activity by Hour</h3>
    <div style="height: 350px; max-width: 400px; margin: 0 auto; position: relative;">
        <canvas id="hourlyActivityChart"></canvas>
    </div>
</div>
<script>
(function() {{
    new Chart(document.getElementById('hourlyActivityChart'), {{
        type: 'polarArea',
        data: {{
            labels: {json.dumps(labels)},
            datasets: [{{
                data: {json.dumps(values)},
                backgroundColor: {json.dumps([f'hsla({h*15}, 70%, 50%, 0.7)' for h in range(24)])}
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                title: {{
                    display: true,
                    text: 'Commits by Hour of Day'
                }},
                legend: {{
                    display: false
                }}
            }}
        }}
    }});
}})();
</script>
'''
    def generate_detailed_hotspot_analysis_html(self) -> str:
        """Generate detailed hotspot analysis with churn, complexity, and coupling tables."""
        hotspots = self.hotspot_data.get('hotspots', [])
        
        if not hotspots:
            return '<div class="visualization-section"><h3>🔍 Detailed Hotspot Analysis</h3><p>No hotspot data available.</p></div>'
        
        # Separate by risk level
        critical = [h for h in hotspots if h.get('risk_level') == 'critical']
        high_risk = [h for h in hotspots if h.get('risk_level') == 'high']
        medium_risk = [h for h in hotspots if h.get('risk_level') == 'medium']
        
        # Get top churned files (sorted by revisions)
        top_churned = sorted(hotspots, key=lambda x: x.get('revisions', 0), reverse=True)[:15]
        
        # Get most complex files (sorted by complexity_score)
        most_complex = sorted(hotspots, key=lambda x: x.get('complexity_score', 0), reverse=True)[:15]
        
        # Get files with most coupling
        most_coupled = [h for h in hotspots if h.get('coupling_count', 0) > 0]
        most_coupled = sorted(most_coupled, key=lambda x: x.get('coupling_count', 0), reverse=True)[:10]
        
        html = f'''
<div class="visualization-section hotspot-analysis">
    <h3>🔍 Detailed Hotspot Analysis</h3>
    
    <div class="risk-summary">
        <h4>Risk Level Summary</h4>
        <div class="risk-badges">
            <span class="risk-badge critical">🚨 Critical: {len(critical)}</span>
            <span class="risk-badge high">⚠️ High: {len(high_risk)}</span>
            <span class="risk-badge medium">📊 Medium: {len(medium_risk)}</span>
        </div>
    </div>
    
    <div class="analysis-subsection">
        <h4>📈 Churn Analysis (Most Changed Files)</h4>
        <p class="analysis-desc">Files with the most revisions require more attention.</p>
        <table class="sortable analysis-table">
            <tr><th>File</th><th>Revisions</th><th>Churn Score</th><th>Risk</th></tr>
'''
        for h in top_churned[:10]:
            risk = h.get('risk_level', 'low')
            fname = os.path.basename(h.get('filepath', 'unknown'))
            html += f'            <tr class="risk-{risk}"><td>{fname}</td><td>{h.get("revisions", 0)}</td><td>{h.get("churn_score", 0):.1f}</td><td class="level-{risk}">{risk.upper()}</td></tr>\n'
        
        html += '''        </table>
    </div>
    
    <div class="analysis-subsection">
        <h4>🧩 Complexity Analysis (Most Complex Files)</h4>
        <p class="analysis-desc">High complexity combined with frequent changes = high bug risk.</p>
        <table class="sortable analysis-table">
            <tr><th>File</th><th>MI Score</th><th>Cyclomatic</th><th>Complexity</th><th>Risk</th></tr>
'''
        for h in most_complex[:10]:
            risk = h.get('risk_level', 'low')
            fname = os.path.basename(h.get('filepath', 'unknown'))
            mi = h.get('maintainability_index')
            mi_str = f'{mi:.1f}' if mi is not None else 'N/A'
            html += f'            <tr class="risk-{risk}"><td>{fname}</td><td>{mi_str}</td><td>{h.get("cyclomatic_complexity", 0)}</td><td>{h.get("complexity_score", 0):.1f}</td><td class="level-{risk}">{risk.upper()}</td></tr>\n'
        
        html += '''        </table>
    </div>
'''
        
        if most_coupled:
            html += '''
    <div class="analysis-subsection">
        <h4>🔗 Change Coupling (Files That Change Together)</h4>
        <p class="analysis-desc">Files that always change together may have hidden dependencies.</p>
        <table class="sortable analysis-table">
            <tr><th>File</th><th>Coupled Files</th><th>Top Coupled With</th><th>Strength</th></tr>
'''
            for h in most_coupled:
                fname = os.path.basename(h.get('filepath', 'unknown'))
                coupled = h.get('coupled_files', [])
                top_file = os.path.basename(coupled[0][0]) if coupled else 'N/A'
                strength = coupled[0][1] if coupled else 0
                html += f'            <tr><td>{fname}</td><td>{h.get("coupling_count", 0)}</td><td>{top_file}</td><td>{strength:.0%}</td></tr>\n'
            html += '''        </table>
    </div>
'''
        
        html += '''
</div>
<style>
.risk-badges { display: flex; gap: 15px; flex-wrap: wrap; margin: 10px 0 20px; }
.risk-badge { padding: 8px 16px; border-radius: 20px; font-weight: bold; }
.risk-badge.critical { background: #fee2e2; color: #991b1b; }
.risk-badge.high { background: #fef3c7; color: #92400e; }
.risk-badge.medium { background: #dbeafe; color: #1e40af; }
.analysis-subsection { margin: 20px 0; }
.analysis-desc { color: #666; font-size: 0.9em; margin-bottom: 10px; }
.analysis-table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
.analysis-table th { background: #f3f4f6; padding: 8px; text-align: left; }
.analysis-table td { padding: 6px 8px; border-bottom: 1px solid #e5e7eb; }
.analysis-table tr:hover { background: #f9fafb; }
.analysis-table tr.risk-critical { background: #fef2f2; }
.analysis-table tr.risk-high { background: #fffbeb; }
.level-critical { color: #dc2626; font-weight: bold; }
.level-high { color: #f59e0b; font-weight: bold; }
.level-medium { color: #3b82f6; }
.level-low { color: #10b981; }
</style>
'''
        return html
    
    def generate_all_visualizations_html(self) -> str:
        """
        Generate all visualizations as a complete HTML section with tabs.
        
        Returns:
            HTML string with tabbed visualizations
        """
        charts_content = '\n'.join([
            self.generate_file_bubble_chart_html(),
            self.generate_hotspot_chart_html(),
        ])
        
        analysis_content = self.generate_detailed_hotspot_analysis_html()
        
        activity_content = '\n'.join([
            self.generate_commit_heatmap_html(),
            self.generate_hourly_activity_chart_html(),
        ])
        
        html = f'''
<div id="interactive-visualizations" class="visualization-container">
    <h2>📈 Interactive Visualizations & Analysis</h2>
    
    <div class="viz-tabs">
        <input type="radio" name="viz-tab" id="tab-charts" checked>
        <label for="tab-charts">📊 Charts</label>
        
        <input type="radio" name="viz-tab" id="tab-analysis">
        <label for="tab-analysis">🔍 Analysis</label>
        
        <input type="radio" name="viz-tab" id="tab-activity">
        <label for="tab-activity">📅 Activity</label>
        
        <div class="tab-content" id="content-charts">
            {charts_content}
        </div>
        
        <div class="tab-content" id="content-analysis">
            {analysis_content}
        </div>
        
        <div class="tab-content" id="content-activity">
            {activity_content}
        </div>
    </div>
</div>
'''
        return html
    
    def get_visualization_styles(self) -> str:
        """Get CSS styles for visualizations including tabs."""
        return '''
<style>
.visualization-container {
    padding: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    margin: 20px 0;
}
.visualization-section {
    background: white;
    padding: 20px;
    border-radius: 8px;
    margin: 15px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.visualization-section h3 {
    margin-top: 0;
    color: #333;
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
}
.viz-description {
    color: #666;
    font-size: 0.9em;
    margin-bottom: 15px;
}

/* Tab Styles */
.viz-tabs {
    position: relative;
}
.viz-tabs input[type="radio"] {
    display: none;
}
.viz-tabs label {
    display: inline-block;
    padding: 12px 24px;
    background: #e5e7eb;
    color: #374151;
    cursor: pointer;
    border-radius: 8px 8px 0 0;
    margin-right: 4px;
    font-weight: 500;
    transition: all 0.2s ease;
}
.viz-tabs label:hover {
    background: #d1d5db;
}
.viz-tabs input[type="radio"]:checked + label {
    background: white;
    color: #2563eb;
    box-shadow: 0 -2px 4px rgba(0,0,0,0.05);
}
.tab-content {
    display: none;
    background: white;
    padding: 20px;
    border-radius: 0 8px 8px 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
#tab-charts:checked ~ #content-charts,
#tab-analysis:checked ~ #content-analysis,
#tab-activity:checked ~ #content-activity {
    display: block;
}
</style>
'''


def generate_visualizations(data_collector, hotspot_data: Optional[Dict] = None) -> Dict[str, str]:
    """
    Convenience function to generate all visualization HTML.
    
    Args:
        data_collector: A DataCollector instance
        hotspot_data: Optional hotspot analysis results
        
    Returns:
        Dictionary with 'styles', 'scripts', and 'content' keys
    """
    viz = VisualizationGenerator(data_collector, hotspot_data)
    
    return {
        'cdn_scripts': viz.get_chart_js_cdn(),
        'styles': viz.get_visualization_styles(),
        'content': viz.generate_all_visualizations_html()
    }
