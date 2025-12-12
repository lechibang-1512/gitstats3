"""
Table data generator for Gitstats3 HTML reports.

Formats collected data into table-friendly structures for HTML output.
"""

import datetime
from typing import List, Any


class TableDataGenerator:
    """
    Generates table data instead of charts for better accessibility and data readability.
    """
    
    def __init__(self):
        """Initialize the table data generator."""
        pass
    
    def read_data_file(self, data_file: str) -> List[List[str]]:
        """
        Read data from a file and return as lines.
        
        Args:
            data_file: Path to the data file
            
        Returns:
            List of lines, each line split into fields
        """
        try:
            with open(data_file, 'r') as f:
                return [line.strip().split() for line in f if line.strip()]
        except Exception as e:
            print(f"Warning: Failed to read data file {data_file}: {e}")
            return []
    
    def generate_table_data(self, data_file: str, chart_type: str) -> List[List[Any]]:
        """
        Generate table data for the given chart type.
        
        Args:
            data_file: Path to the data file
            chart_type: Type of data ('hour_of_day', 'day_of_week', etc.)
            
        Returns:
            Formatted table data as list of rows
        """
        data = self.read_data_file(data_file)
        if not data:
            return []
        
        formatters = {
            'hour_of_day': self._format_hour_of_day_data,
            'day_of_week': self._format_day_of_week_data,
            'domains': self._format_domains_data,
            'month_of_year': self._format_month_of_year_data,
            'commits_by_year_month': self._format_commits_by_year_month_data,
            'commits_by_year': self._format_commits_by_year_data,
            'files_by_date': self._format_files_by_date_data,
            'files_by_year': self._format_files_by_year_data,
            'lines_of_code': self._format_lines_of_code_data,
            'pace_of_changes': self._format_pace_of_changes_data,
        }
        
        formatter = formatters.get(chart_type)
        if formatter:
            return formatter(data)
        return data
    
    def _format_hour_of_day_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format hour of day data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                hour = int(row[0])
                commits = int(row[1])
                formatted.append([f"{hour:02d}:00", commits])
        return formatted
    
    def _format_day_of_week_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format day of week data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 3:
                day_name = row[1]
                commits = int(row[2])
                formatted.append([day_name, commits])
        return formatted
    
    def _format_domains_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format domains data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 3:
                domain = row[0]
                commits = int(row[2])
                formatted.append([domain, commits])
        return sorted(formatted, key=lambda x: x[1], reverse=True)
    
    def _format_month_of_year_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format month of year data for table display."""
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        formatted = []
        for row in data:
            if len(row) >= 2:
                month = int(row[0])
                commits = int(row[1])
                month_name = month_names[month - 1] if 1 <= month <= 12 else str(month)
                formatted.append([month_name, commits])
        return formatted
    
    def _format_commits_by_year_month_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format commits by year-month data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                year_month = row[0]
                commits = int(row[1])
                formatted.append([year_month, commits])
        return formatted
    
    def _format_commits_by_year_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format commits by year data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                year = int(row[0])
                commits = int(row[1])
                formatted.append([year, commits])
        return sorted(formatted, key=lambda x: x[0])
    
    def _format_files_by_date_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format files by date data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                try:
                    date_str = row[0]
                    files = int(row[1])
                    # Convert timestamp to readable date if needed
                    if date_str.isdigit():
                        date_obj = datetime.datetime.fromtimestamp(int(date_str))
                        date_str = date_obj.strftime('%Y-%m-%d')
                    formatted.append([date_str, files])
                except (ValueError, OSError):
                    formatted.append([row[0], int(row[1])])
        return formatted[-50:]  # Show last 50 entries
    
    def _format_files_by_year_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format files by year data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                year = int(row[0])
                files = int(row[1])
                formatted.append([year, files])
        return sorted(formatted, key=lambda x: x[0])
    
    def _format_lines_of_code_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format lines of code data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                try:
                    timestamp = int(row[0])
                    lines = int(row[1])
                    date_obj = datetime.datetime.fromtimestamp(timestamp)
                    date_str = date_obj.strftime('%Y-%m-%d')
                    formatted.append([date_str, lines])
                except (ValueError, OSError):
                    formatted.append([row[0], int(row[1])])
        return formatted[-50:]  # Show last 50 entries
    
    def _format_pace_of_changes_data(self, data: List[List[str]]) -> List[List[Any]]:
        """Format pace of changes data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                try:
                    timestamp = int(row[0])
                    changes = int(row[1])
                    date_obj = datetime.datetime.fromtimestamp(timestamp)
                    date_str = date_obj.strftime('%Y-%m-%d')
                    formatted.append([date_str, changes])
                except (ValueError, OSError):
                    formatted.append([row[0], int(row[1])])
        return formatted[-50:]  # Show last 50 entries

    def _format_lines_of_code_by_author_data(
        self, data: List[List[str]], authors_to_plot: List[str]
    ) -> List[List[Any]]:
        """Format lines of code by author data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                author = row[0]
                if author in authors_to_plot:
                    lines = int(row[1])
                    formatted.append([author, lines])
        return formatted
    
    def _format_commits_by_author_data(
        self, data: List[List[str]], authors_to_plot: List[str]
    ) -> List[List[Any]]:
        """Format commits by author data for table display."""
        formatted = []
        for row in data:
            if len(row) >= 2:
                author = row[0]
                if author in authors_to_plot:
                    commits = int(row[1])
                    formatted.append([author, commits])
        return formatted

    # Public methods that wrap the private formatting methods
    def format_hour_of_day_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format hour of day data."""
        data = self.read_data_file(data_file)
        return self._format_hour_of_day_data(data)
    
    def format_day_of_week_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format day of week data."""
        data = self.read_data_file(data_file)
        return self._format_day_of_week_data(data)
    
    def format_domains_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format domains data."""
        data = self.read_data_file(data_file)
        return self._format_domains_data(data)
    
    def format_month_of_year_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format month of year data."""
        data = self.read_data_file(data_file)
        return self._format_month_of_year_data(data)
    
    def format_commits_by_year_month_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format commits by year month data."""
        data = self.read_data_file(data_file)
        return self._format_commits_by_year_month_data(data)
    
    def format_commits_by_year_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format commits by year data."""
        data = self.read_data_file(data_file)
        return self._format_commits_by_year_data(data)
    
    def format_files_by_date_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format files by date data."""
        data = self.read_data_file(data_file)
        return self._format_files_by_date_data(data)
    
    def format_files_by_year_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format files by year data."""
        data = self.read_data_file(data_file)
        return self._format_files_by_year_data(data)
    
    def format_lines_of_code_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format lines of code data."""
        data = self.read_data_file(data_file)
        return self._format_lines_of_code_data(data)
    
    def format_pace_of_changes_data(self, data_file: str) -> List[List[Any]]:
        """Public method to format pace of changes data."""
        data = self.read_data_file(data_file)
        return self._format_pace_of_changes_data(data)
    
    def format_lines_of_code_by_author_data(
        self, data_file: str, authors_to_plot: List[str]
    ) -> List[List[Any]]:
        """Public method to format lines of code by author data."""
        data = self.read_data_file(data_file)
        return self._format_lines_of_code_by_author_data(data, authors_to_plot)
    
    def format_commits_by_author_data(
        self, data_file: str, authors_to_plot: List[str]
    ) -> List[List[Any]]:
        """Public method to format commits by author data."""
        data = self.read_data_file(data_file)
        return self._format_commits_by_author_data(data, authors_to_plot)
