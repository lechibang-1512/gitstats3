"""
Table data generator for Gitstats3.
Converts .dat files (Gnuplot format) into HTML tables.
"""

import os

class TableDataGenerator:
    """Generates HTML tables from .dat files."""
    
    def _read_dat_file(self, filename):
        """Read .dat file and return rows as list of lists."""
        rows = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#'):
                        rows.append(line.split())
        return rows

    def format_hour_of_day_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Hour</th><th>Commits</th></tr>'
        for row in rows:
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_day_of_week_data(self, filename):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Day</th><th>Commits</th></tr>'
        for row in rows:
            day_idx = int(row[0])
            day_name = days[day_idx] if day_idx < len(days) else row[0]
            html += f'<tr><td>{day_name}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_domains_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Domain</th><th>Commits</th></tr>'
        for row in rows:
            html += f'<tr><td>{row[0]}</td><td>{row[2]}</td></tr>'
        html += '</table></div>'
        return html

    def format_month_of_year_data(self, filename):
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Month</th><th>Commits</th></tr>'
        for row in rows:
            month_idx = int(row[0]) - 1
            month_name = months[month_idx] if 0 <= month_idx < len(months) else row[0]
            html += f'<tr><td>{month_name}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_commits_by_year_month_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Month</th><th>Commits</th></tr>'
        for row in reversed(rows):
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_commits_by_year_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Year</th><th>Commits</th></tr>'
        for row in reversed(rows):
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_files_by_date_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Date</th><th>Files</th></tr>'
        for row in reversed(rows[-20:]):
            import datetime
            date_str = datetime.datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d')
            html += f'<tr><td>{date_str}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_files_by_year_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Year</th><th>Files</th></tr>'
        for row in reversed(rows):
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_lines_of_code_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Date</th><th>LOC</th></tr>'
        for row in reversed(rows[-25:]):
            import datetime
            date_str = datetime.datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d')
            html += f'<tr><td>{date_str}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html

    def format_lines_of_code_by_author_data(self, filename, authors):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Date</th>'
        for author in authors:
            html += f'<th>{author}</th>'
        html += '</tr>'
        for row in reversed(rows[-20:]):
            import datetime
            date_str = datetime.datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d')
            html += f'<tr><td>{date_str}</td>'
            for i in range(len(authors)):
                val = row[i+1] if i+1 < len(row) else '0'
                html += f'<td>{val}</td>'
            html += '</tr>'
        html += '</table></div>'
        return html

    def format_commits_by_author_data(self, filename, authors):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Date</th>'
        for author in authors:
            html += f'<th>{author}</th>'
        html += '</tr>'
        for row in reversed(rows[-20:]):
            import datetime
            date_str = datetime.datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d')
            html += f'<tr><td>{date_str}</td>'
            for i in range(len(authors)):
                val = row[i+1] if i+1 < len(row) else '0'
                html += f'<td>{val}</td>'
            html += '</tr>'
        html += '</table></div>'
        return html

    def format_pace_of_changes_data(self, filename):
        rows = self._read_dat_file(filename)
        html = '<div class="vtable"><table><tr><th>Date</th><th>Changes</th></tr>'
        for row in reversed(rows[-20:]):
            import datetime
            date_str = datetime.datetime.fromtimestamp(int(row[0])).strftime('%Y-%m-%d')
            html += f'<tr><td>{date_str}</td><td>{row[1]}</td></tr>'
        html += '</table></div>'
        return html
